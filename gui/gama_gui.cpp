// gama_gui.cpp -- the desktop GUI for GamaTTS, model 5 (docs/10).
//
//   gama_gui [--data <folder holding voice/english>] [--smoke]
//
// Copyright 2026 dengopaiv. GPL-3.0-or-later, like the engine (Gnuspeech:
// Copyright 1991-2002 David R. Hill, Leonard Manzara, Craig Schock; GamaTTS:
// Copyright 2014-2025 Marcelo Y. Matuda). See NOTICE.md. Adapted from
// gnuspeech_gui.cpp in GnuspeechSA-NVDA.
//
// C++17 and wxWidgets over the C API (gama_api.h) and nothing else of the
// engine. Two engine handles, each used by one thread only (the API's rule 1):
// the window's, which holds the settings and makes phonetic strings, and the
// worker's, which renders each job from a copy of those settings.
//
// Accessibility (docs/10, from rsynth's GUI and Tawkative's phase 0):
//  - standard controls only; numbers are wxSpinCtrlDouble, never sliders;
//  - every label is created just before its control, and every control, and
//    the edit inside every wxSpinCtrlDouble, is also given its name and
//    description explicitly (NamedAccessible);
//  - the parameter groups are all built at start-up and shown one at a time,
//    so nothing is destroyed under the focus and hidden fields are out of the
//    Tab order and out of the accessibility tree.
//
// --smoke builds the window, renders one utterance through the worker and
// exits 0 if both worked: ctest runs it.
#include "gama_api.h"

#include <wx/app.h>
#include <wx/button.h>
#include <wx/checkbox.h>
#include <wx/choice.h>
#include <wx/cmdline.h>
#include <wx/filedlg.h>
#include <wx/filename.h>
#include <wx/frame.h>
#include <wx/menu.h>
#include <wx/msgdlg.h>
#include <wx/panel.h>
#include <wx/sizer.h>
#include <wx/sound.h>
#include <wx/spinctrl.h>
#include <wx/statbox.h>
#include <wx/stattext.h>
#include <wx/statusbr.h>
#include <wx/stdpaths.h>
#include <wx/textctrl.h>
#include <wx/timer.h>
#include <wx/utils.h>

#if wxUSE_ACCESSIBILITY
#  include <wx/access.h>
#endif

#ifdef _WIN32
#  include <windows.h>
#endif

#include <algorithm>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <functional>
#include <iterator>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace {

const char* const kProgramName = "GamaTTS";

// The exit code of a --smoke run: 1 until the utterance has come back.
int g_smokeExitCode = 1;

// Trimming: the values the NVDA driver keeps after a sentence.
const int kDefaultLeadMs = 10;
// The Loudness choices (docs/10), in the order shown, with the preset
// word and the levelling mode of each; the first is the default, as in the
// NVDA add-on.
struct Leveling {
    const char* name;
    const char* word;
    int mode;
};
const Leveling kLevelings[] = {
    { "Steady throughout", "constant", GAMA_LEVEL_CONSTANT },
    { "Even per message", "message", GAMA_LEVEL_LOUDNESS },
    { "The engine's own peaks", "peak", GAMA_LEVEL_PEAK },
};
const int kDefaultTrailMs = 150;

wxString u8(const char* s)
{
    return wxString::FromUTF8(s ? s : "");
}

// ---------------------------------------------------------------------------
// Accessibility

#if wxUSE_ACCESSIBILITY
// The name and description given explicitly, not left to the platform's
// guess from the label before the control. wxSpinCtrlDouble is a composite on
// Windows: an edit and a spin button inside a pane, and the edit, which takes
// the focus, would otherwise have no name (Tawkative, 2026-10-13). The
// description is read after the name and value, so it carries the range,
// the default and what the parameter does.
class NamedAccessible : public wxWindowAccessible {
public:
    NamedAccessible(wxWindow* w, wxString name, wxString description)
        : wxWindowAccessible(w), name_(std::move(name)), description_(std::move(description))
    {
    }
    wxAccStatus GetName(int child, wxString* name) override
    {
        if (child != wxACC_SELF)
            return wxACC_NOT_IMPLEMENTED;
        *name = name_;
        return wxACC_OK;
    }
    wxAccStatus GetDescription(int child, wxString* description) override
    {
        if (child != wxACC_SELF || description_.empty())
            return wxACC_NOT_IMPLEMENTED;
        *description = description_;
        return wxACC_OK;
    }
    void SetDescription(const wxString& d) { description_ = d; }

private:
    wxString name_, description_;
};
#endif

// Names `control`, and every edit inside it, for a screen reader.
void nameControl(wxWindow* control, const wxString& name, const wxString& description)
{
#if wxUSE_ACCESSIBILITY
    control->SetAccessible(new NamedAccessible(control, name, description));
    for (wxWindow* child : control->GetChildren())
        if (wxDynamicCast(child, wxTextCtrl))
            child->SetAccessible(new NamedAccessible(child, name, description));
#else
    (void)control;
    (void)name;
#endif
    control->SetToolTip(description);
}

// Changes the description nameControl gave (a default changes with the voice).
void describeControl(wxWindow* control, const wxString& description)
{
#if wxUSE_ACCESSIBILITY
    if (auto* a = dynamic_cast<NamedAccessible*>(control->GetAccessible()))
        a->SetDescription(description);
    for (wxWindow* child : control->GetChildren())
        if (auto* a = dynamic_cast<NamedAccessible*>(child->GetAccessible()))
            a->SetDescription(description);
#endif
    control->SetToolTip(description);
}

// ---------------------------------------------------------------------------
// Values and files

wxString formatNumber(double v, int decimals)
{
    return wxString::FromCDouble(v, decimals);
}

// A value for a preset file: as short as reads back the same.
std::string formatExact(double v)
{
    char buf[64];
    // From 6: at 1, "%.*g" writes 20 as 2e+01, which reads back but is no way to write it.
    for (int precision = 6; precision <= 17; ++precision) {
        std::snprintf(buf, sizeof buf, "%.*g", precision, v);
        if (std::strtod(buf, nullptr) == v)
            break;
    }
    return buf;
}

wxString voiceDisplayName(const char* name)
{
    wxString s = u8(name);
    s.Replace("_", " ");
    if (!s.empty())
        s[0] = wxToupper(s[0]);
    return s;
}

// The engine opens its data with narrow paths. On Windows that is the ANSI
// code page; a folder that cannot be written in it goes by its 8.3 short
// form, as the NVDA driver does.
std::optional<std::string> narrowPath(const wxString& path)
{
#ifdef _WIN32
    auto toAnsi = [](const std::wstring& w) -> std::optional<std::string> {
        BOOL lossy = FALSE;
        int n = WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, w.c_str(), -1, nullptr, 0, nullptr, &lossy);
        if (n <= 0 || lossy)
            return std::nullopt;
        std::string s(static_cast<size_t>(n), '\0');
        WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, w.c_str(), -1, s.data(), n, nullptr, &lossy);
        s.resize(static_cast<size_t>(n - 1));
        return s;
    };
    std::wstring w = path.ToStdWstring();
    if (auto s = toAnsi(w))
        return s;
    std::wstring shortPath(32768, L'\0');
    DWORD n = GetShortPathNameW(w.c_str(), shortPath.data(), static_cast<DWORD>(shortPath.size()));
    if (n == 0 || n >= shortPath.size())
        return std::nullopt;
    shortPath.resize(n);
    return toAnsi(shortPath);
#else
    return path.utf8_string();
#endif
}

// The data folder: --data, else data beside the program, else data in a folder
// above it (a build tree inside the repository).
wxString findDataDir(const wxString& given)
{
    if (!given.empty())
        return given;
    wxFileName exe(wxStandardPaths::Get().GetExecutablePath());
    wxString dir = exe.GetPath();
    for (int up = 0; up < 6; ++up) {
        wxString candidate = dir + wxFILE_SEP_PATH + "data";
        if (wxFileName::FileExists(candidate + "/voice/english/5_male/_index.txt"))
            return candidate;
        wxFileName parent = wxFileName::DirName(dir);
        if (parent.GetDirCount() == 0)
            break;
        parent.RemoveLastDir();
        dir = parent.GetPath();
    }
    return wxString();
}

// A 16-bit mono WAV in memory.
std::vector<char> makeWav(const std::vector<int16_t>& samples, int rate)
{
    const uint32_t dataBytes = static_cast<uint32_t>(samples.size() * 2);
    std::vector<char> out(44 + dataBytes);
    char* p = out.data();
    auto put32 = [&](uint32_t v) { for (int i = 0; i < 4; ++i) *p++ = static_cast<char>((v >> (8 * i)) & 0xff); };
    auto put16 = [&](uint16_t v) { *p++ = static_cast<char>(v & 0xff); *p++ = static_cast<char>(v >> 8); };
    auto tag = [&](const char* t) { std::memcpy(p, t, 4); p += 4; };
    tag("RIFF"); put32(36 + dataBytes); tag("WAVE");
    tag("fmt "); put32(16); put16(1); put16(1); put32(static_cast<uint32_t>(rate));
    put32(static_cast<uint32_t>(rate) * 2); put16(2); put16(16);
    tag("data"); put32(dataBytes);
    for (int16_t s : samples) put16(static_cast<uint16_t>(s));
    return out;
}

// Writes to <path>.part and renames it into place, so a failure leaves no
// half-written file (Tawkative's review, 2026-10-13).
bool writeFileAtomically(const wxString& path, const char* data, size_t size, wxString* error)
{
    const wxString part = path + ".part";
    {
        std::ofstream f(part.fn_str(), std::ios::binary | std::ios::trunc);
        if (!f) {
            *error = "cannot write " + part;
            return false;
        }
        f.write(data, static_cast<std::streamsize>(size));
        if (!f) {
            *error = "writing " + part + " failed";
            f.close();
            wxRemoveFile(part);
            return false;
        }
    }
    if (!wxRenameFile(part, path, true)) {
        wxRemoveFile(part);
        *error = "cannot replace " + path;
        return false;
    }
    return true;
}

// ---------------------------------------------------------------------------
// The worker: one thread, one engine, the latest job only.

struct Settings {
    int voice = 0;
    std::vector<double> values;   // gama_param order
    double gain = 1.0;
    int leadMs = -1, trailMs = -1;
    int levelMode = GAMA_LEVEL_PEAK;
    double levelTarget = GAMA_LEVEL_DEFAULT_TARGET;
};

enum class JobKind { Play, SaveWav, SaveTrack, Smoke };

struct Job {
    unsigned id = 0;
    JobKind kind = JobKind::Play;
    std::string input;            // UTF-8 text, or a phonetic string
    bool phonetic = false;
    Settings settings;
    wxString path;
};

struct Result {
    unsigned id = 0;
    JobKind kind = JobKind::Play;
    bool ok = false;
    std::string error;
    std::vector<int16_t> samples;
    int rate = 0;
    std::string track;
    wxString path;
    double renderSeconds = 0.0;
};

class Worker {
public:
    Worker(std::string dataDir, std::function<void(Result)> done)
        : dataDir_(std::move(dataDir)), done_(std::move(done)), thread_([this] { run(); })
    {
    }
    ~Worker()
    {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            quit_ = true;
        }
        wake_.notify_all();
        thread_.join();
    }
    // Replaces a job that has not started yet.
    void submit(Job job)
    {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            pending_ = std::move(job);
        }
        wake_.notify_all();
    }

private:
    void run()
    {
        char err[512] = "";
        gama_engine* e = gama_create(dataDir_.c_str(), err, sizeof err);
        for (;;) {
            Job job;
            {
                std::unique_lock<std::mutex> lock(mutex_);
                wake_.wait(lock, [this] { return quit_ || pending_.has_value(); });
                if (quit_)
                    break;
                job = std::move(*pending_);
                pending_.reset();
            }
            Result r;
            r.id = job.id;
            r.kind = job.kind;
            r.path = job.path;
            if (!e) {
                r.error = std::string("the engine did not load: ") + err;
            } else {
                render(e, job, r);
            }
            done_(std::move(r));
        }
        gama_destroy(e);
    }

    static void render(gama_engine* e, const Job& job, Result& r)
    {
        const Settings& s = job.settings;
        // The voice first: it loads the voice file's values, which the
        // copied values then replace.
        if (gama_set_voice(e, s.voice) != GAMA_OK) {
            r.error = std::string("voice: ") + gama_last_error(e);
            return;
        }
        // Some values share a limit (the API's rule 10), so one may be refused
        // until another has been set. The settings are valid together, so a
        // second round always finishes it.
        for (int round = 0; round < 3; ++round) {
            bool refused = false;
            for (size_t i = 0; i < s.values.size(); ++i)
                refused = gama_set_param(e, static_cast<int>(i), s.values[i]) != GAMA_OK || refused;
            if (!refused)
                break;
        }
        gama_set_volume(e, s.gain);
        gama_set_trim(e, s.leadMs, s.trailMs);
        gama_set_leveling(e, s.levelMode, s.levelTarget);

        const auto start = std::chrono::steady_clock::now();
        const int rc = job.phonetic ? gama_speak_phonetic(e, job.input.c_str()) : gama_speak(e, job.input.c_str());
        if (rc != GAMA_OK) {
            const char* why = gama_last_error(e);
            r.error = why && *why ? why : "there is nothing to say in that text";
            return;
        }
        r.samples.resize(gama_pending(e));
        r.samples.resize(gama_read(e, r.samples.data(), r.samples.size()));
        r.rate = gama_sample_rate(e);
        if (job.kind == JobKind::SaveTrack) {
            r.track.resize(gama_track(e, nullptr, 0) + 1);
            r.track.resize(gama_track(e, r.track.data(), r.track.size()));
        }
        r.renderSeconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
        r.ok = true;
    }

    std::string dataDir_;
    std::function<void(Result)> done_;
    std::mutex mutex_;
    std::condition_variable wake_;
    std::optional<Job> pending_;
    bool quit_ = false;
    std::thread thread_;  // last: it starts running in the constructor
};

// ---------------------------------------------------------------------------
// The window

enum {
    ID_SPEAK = wxID_HIGHEST + 1,
    ID_STOP,
    ID_SAVE_WAV,
    ID_SAVE_TRACK,
    ID_SHOW_PHONETIC,
    ID_USE_PHONETIC,
    ID_RESET,
    ID_OPEN_PRESET,
    ID_SAVE_PRESET,
    ID_KEYS,
    ID_GO_TEXT,         // Alt+letter: move to a control
    ID_GO_READ_AS,
    ID_GO_VOICE,
    ID_GO_CATEGORY,
    ID_GO_PHONETIC,
    ID_CATEGORY_FIRST,  // + category index, Ctrl+1 ... Ctrl+9
};

// One parameter's control.
struct Field {
    int param = -1;          // gama_param index; -1 for the GUI's own Output fields
    wxWindow* control = nullptr;
    wxString name;           // "Tract length (cm)"
};

class MainFrame : public wxFrame {
public:
    MainFrame(gama_engine* engine, const std::string& dataDir, bool smoke);
    ~MainFrame() override;

private:
    void buildMenus();
    void buildCategory(wxWindow* parent, wxSizer* sizer, const wxString& category);
    void addParamField(wxWindow* box, wxSizer* grid, int i);
    void addOutputFields(wxWindow* box, wxSizer* grid);
    wxSpinCtrlDouble* addSpin(wxWindow* box, wxSizer* grid, const wxString& name, double min, double max,
                              double value, double step, int decimals);
    wxString describe(int i) const;

    void showCategory(int c, bool focusFirst);
    void refreshFields();
    void setStatus(const wxString& s) { SetStatusText(s); }

    Settings snapshot() const;
    std::optional<std::string> currentInput(bool selectionOnly) const;
    void submit(JobKind kind, const wxString& path = wxString());
    void onResult(Result r);

    void onSpeak();
    void onStop();
    void onSaveWav();
    void onSaveTrack();
    void onShowPhonetic();
    void onUsePhonetic();
    void onReset();
    void onOpenPreset();
    void onSavePreset();
    void onVoice();
    void onChildFocus(wxChildFocusEvent& ev);

    gama_engine* engine_;  // the window's own handle: the settings
    std::unique_ptr<Worker> worker_;
    bool smoke_;
    unsigned jobId_ = 0;

    wxPanel* panel_ = nullptr;
    wxTextCtrl* text_ = nullptr;
    wxChoice* readAs_ = nullptr;
    wxChoice* voice_ = nullptr;
    wxChoice* category_ = nullptr;
    wxTextCtrl* phonetic_ = nullptr;
    std::vector<wxString> categories_;
    std::vector<wxStaticBoxSizer*> groups_;
    std::vector<wxWindow*> firstInGroup_;
    std::vector<Field> fields_;

    // The Output fields that are not engine parameters.
    wxSpinCtrlDouble* volume_ = nullptr;
    wxCheckBox* trim_ = nullptr;
    wxSpinCtrlDouble* lead_ = nullptr;
    wxSpinCtrlDouble* trail_ = nullptr;
    wxChoice* leveling_ = nullptr;
    wxSpinCtrlDouble* target_ = nullptr;
    void applyLeveling();

    wxString pendingNote_;  // a typed value that leaving the field will correct
    wxSound sound_;
    wxTimer playTimer_;
};

MainFrame::MainFrame(gama_engine* engine, const std::string& dataDir, bool smoke)
    : wxFrame(nullptr, wxID_ANY, kProgramName), engine_(engine), smoke_(smoke)
{
    worker_ = std::make_unique<Worker>(dataDir, [this](Result r) {
        // From the worker thread: CallAfter queues it for the window's thread.
        CallAfter([this, r = std::move(r)]() mutable { onResult(std::move(r)); });
    });

    buildMenus();
    CreateStatusBar();

    panel_ = new wxPanel(this);
    auto* top = new wxBoxSizer(wxVERTICAL);
    const int gap = FromDIP(6);

    // Text, read as, voice.
    top->Add(new wxStaticText(panel_, wxID_ANY, "&Text to speak"), 0, wxLEFT | wxRIGHT | wxTOP, gap);
    text_ = new wxTextCtrl(panel_, wxID_ANY, "Hello. This is GamaTTS, an articulatory speech synthesizer.",
                           wxDefaultPosition, FromDIP(wxSize(560, 110)), wxTE_MULTILINE);
    nameControl(text_, "Text to speak",
                "Ctrl+Enter speaks the selection, or all of it. In phonetic mode this is a phonetic string.");
    top->Add(text_, 1, wxEXPAND | wxALL, gap);

    auto* row = new wxBoxSizer(wxHORIZONTAL);
    row->Add(new wxStaticText(panel_, wxID_ANY, "Read &as"), 0, wxALIGN_CENTER_VERTICAL | wxRIGHT, gap);
    wxArrayString readAs;
    readAs.Add("Text");
    readAs.Add("Phonetic string");
    readAs_ = new wxChoice(panel_, wxID_ANY, wxDefaultPosition, wxDefaultSize, readAs);
    readAs_->SetSelection(0);
    nameControl(readAs_, "Read as",
                "Text goes through the text parser. Phonetic string is spoken as written, in Gnuspeech's notation.");
    row->Add(readAs_, 0, wxRIGHT, 3 * gap);
    row->Add(new wxStaticText(panel_, wxID_ANY, "&Voice"), 0, wxALIGN_CENTER_VERTICAL | wxRIGHT, gap);
    wxArrayString voices;
    for (int v = 0; v < gama_voice_count(engine_); ++v)
        voices.Add(voiceDisplayName(gama_voice_name(engine_, v)));
    voice_ = new wxChoice(panel_, wxID_ANY, wxDefaultPosition, wxDefaultSize, voices);
    voice_->SetSelection(gama_voice(engine_));
    nameControl(voice_, "Voice",
                "Loads the voice file's values into the parameters kept there. "
                "Every other parameter keeps its value.");
    voice_->Bind(wxEVT_CHOICE, [this](wxCommandEvent&) { onVoice(); });
    row->Add(voice_, 0);
    top->Add(row, 0, wxALL, gap);

    // Commands.
    auto* buttons = new wxBoxSizer(wxHORIZONTAL);
    auto button = [&](int id, const wxString& label, const wxString& help) {
        auto* b = new wxButton(panel_, id, label);
        nameControl(b, wxStripMenuCodes(label), help);
        buttons->Add(b, 0, wxRIGHT, gap);
    };
    button(ID_SPEAK, "Spea&k", "Ctrl+Enter. Speaks the selection, or all the text.");
    button(ID_STOP, "St&op", "Esc. Stops speaking.");
    button(ID_SAVE_WAV, "Save as &WAV...", "Ctrl+S. Renders the text with the current settings to a WAV file.");
    button(ID_SHOW_PHONETIC, "Show phonetic str&ing",
           "Ctrl+P. Shows what the text parser makes of the text, and moves there.");
    button(ID_USE_PHONETIC, "&Use phonetic string as text",
           "Ctrl+U. Replaces the text with its phonetic string, to edit, and reads it as a phonetic string.");
    top->Add(buttons, 0, wxALL, gap);

    // Parameters: the category combo, then one group per category.
    auto* catRow = new wxBoxSizer(wxHORIZONTAL);
    catRow->Add(new wxStaticText(panel_, wxID_ANY, "Para&meters for"), 0, wxALIGN_CENTER_VERTICAL | wxRIGHT, gap);
    for (int i = 0; i < gama_param_count(); ++i) {
        wxString c = u8(gama_param_describe(i)->category);
        if (std::find(categories_.begin(), categories_.end(), c) == categories_.end())
            categories_.push_back(c);
    }
    if (std::find(categories_.begin(), categories_.end(), "Output") == categories_.end())
        categories_.push_back("Output");
    wxArrayString catNames;
    for (size_t c = 0; c < categories_.size(); ++c)
        catNames.Add(categories_[c]);
    category_ = new wxChoice(panel_, wxID_ANY, wxDefaultPosition, wxDefaultSize, catNames);
    category_->SetSelection(0);
    nameControl(category_, "Parameters for",
                "Chooses which parameters are shown below. Ctrl+1 to Ctrl+" + wxString::Format("%zu", categories_.size()) +
                " choose a category and move to its first field.");
    category_->Bind(wxEVT_CHOICE, [this](wxCommandEvent& ev) { showCategory(ev.GetSelection(), false); });
    catRow->Add(category_, 0, wxRIGHT, 3 * gap);
    auto* reset = new wxButton(panel_, ID_RESET, "&Reset all parameters");
    nameControl(reset, "Reset all parameters",
                "Ctrl+R. Every parameter back to the data files' value for the current voice.");
    catRow->Add(reset, 0);
    top->Add(catRow, 0, wxALL, gap);

    for (const wxString& c : categories_) {
        // The group box is created before its fields (NVDA finds a field's
        // group by walking back to it), and the fields are its children.
        auto* group = new wxStaticBoxSizer(wxVERTICAL, panel_, c);
        auto* grid = new wxFlexGridSizer(2, gap / 2, 2 * gap);
        grid->AddGrowableCol(1);
        const size_t before = fields_.size();
        buildCategory(group->GetStaticBox(), grid, c);
        firstInGroup_.push_back(fields_.size() > before ? fields_[before].control : nullptr);
        group->Add(grid, 1, wxEXPAND | wxALL, gap);
        top->Add(group, 0, wxEXPAND | wxALL, gap);
        groups_.push_back(group);
    }

    top->Add(new wxStaticText(panel_, wxID_ANY, "Phonetic stri&ng"), 0, wxLEFT | wxRIGHT | wxTOP, gap);
    phonetic_ = new wxTextCtrl(panel_, wxID_ANY, wxEmptyString, wxDefaultPosition, FromDIP(wxSize(560, 60)),
                               wxTE_MULTILINE | wxTE_READONLY);
    nameControl(phonetic_, "Phonetic string", "What the text parser made of the text (Ctrl+P), in Gnuspeech's notation.");
    top->Add(phonetic_, 0, wxEXPAND | wxALL, gap);

    panel_->SetSizer(top);

    // The window is as large as the largest group needs, so it does not
    // jump when the category changes.
    wxSize best(0, 0);
    for (size_t c = 0; c < groups_.size(); ++c) {
        for (size_t k = 0; k < groups_.size(); ++k)
            top->Show(groups_[k], k == c, true);
        top->Layout();
        best.IncTo(top->GetMinSize());
    }
    showCategory(0, false);
    panel_->SetMinSize(best);
    auto* frameSizer = new wxBoxSizer(wxVERTICAL);
    frameSizer->Add(panel_, 1, wxEXPAND);
    SetSizerAndFit(frameSizer);

    Bind(wxEVT_BUTTON, [this](wxCommandEvent&) { onSpeak(); }, ID_SPEAK);
    Bind(wxEVT_BUTTON, [this](wxCommandEvent&) { onStop(); }, ID_STOP);
    Bind(wxEVT_BUTTON, [this](wxCommandEvent&) { onSaveWav(); }, ID_SAVE_WAV);
    Bind(wxEVT_BUTTON, [this](wxCommandEvent&) { onShowPhonetic(); }, ID_SHOW_PHONETIC);
    Bind(wxEVT_BUTTON, [this](wxCommandEvent&) { onUsePhonetic(); }, ID_USE_PHONETIC);
    Bind(wxEVT_BUTTON, [this](wxCommandEvent&) { onReset(); }, ID_RESET);
    panel_->Bind(wxEVT_CHILD_FOCUS, &MainFrame::onChildFocus, this);

    // Alt+letter, from anywhere in the window. The labels' own mnemonics
    // reach only the controls at the panel's level: from a field inside a
    // group box, Alt+V did nothing (tests/gui/gui_check.py, 2026-10-16). The
    // menus keep F, S, P and H.
    const std::pair<int, int> go[] = {
        { 'T', ID_GO_TEXT }, { 'A', ID_GO_READ_AS }, { 'V', ID_GO_VOICE }, { 'M', ID_GO_CATEGORY },
        { 'N', ID_GO_PHONETIC }, { 'K', ID_SPEAK }, { 'O', ID_STOP }, { 'W', ID_SAVE_WAV },
        { 'I', ID_SHOW_PHONETIC }, { 'U', ID_USE_PHONETIC }, { 'R', ID_RESET },
    };
    std::vector<wxAcceleratorEntry> keys;
    for (const auto& [letter, id] : go)
        keys.emplace_back(wxACCEL_ALT, letter, id);
    SetAcceleratorTable(wxAcceleratorTable(static_cast<int>(keys.size()), keys.data()));
    Bind(wxEVT_MENU, [this](wxCommandEvent&) { text_->SetFocus(); }, ID_GO_TEXT);
    Bind(wxEVT_MENU, [this](wxCommandEvent&) { readAs_->SetFocus(); }, ID_GO_READ_AS);
    Bind(wxEVT_MENU, [this](wxCommandEvent&) { voice_->SetFocus(); }, ID_GO_VOICE);
    Bind(wxEVT_MENU, [this](wxCommandEvent&) { category_->SetFocus(); }, ID_GO_CATEGORY);
    Bind(wxEVT_MENU, [this](wxCommandEvent&) { phonetic_->SetFocus(); }, ID_GO_PHONETIC);
    playTimer_.Bind(wxEVT_TIMER, [this](wxTimerEvent&) { setStatus("Done."); });
    Bind(wxEVT_CLOSE_WINDOW, [this](wxCloseEvent& ev) {
        wxSound::Stop();
        ev.Skip();
    });

    text_->SetFocus();
    setStatus("Ready. F1 lists the keys.");
    if (smoke_)
        submit(JobKind::Smoke);
}

MainFrame::~MainFrame()
{
    // The worker's callback refers to this window: stop it first.
    worker_.reset();
}

void MainFrame::buildMenus()
{
    auto* file = new wxMenu;
    file->Append(ID_OPEN_PRESET, "&Open voice preset...\tCtrl+O");
    file->Append(ID_SAVE_PRESET, "Save voice &preset...\tCtrl+Shift+S");
    file->AppendSeparator();
    file->Append(ID_SAVE_WAV, "Save as &WAV...\tCtrl+S");
    file->Append(ID_SAVE_TRACK, "Save parameter &track...\tCtrl+T");
    file->AppendSeparator();
    file->Append(wxID_EXIT, "E&xit");

    auto* speech = new wxMenu;
    speech->Append(ID_SPEAK, "&Speak\tCtrl+Enter");
    speech->Append(ID_STOP, "S&top\tEsc");
    speech->AppendSeparator();
    speech->Append(ID_SHOW_PHONETIC, "Show &phonetic string\tCtrl+P");
    speech->Append(ID_USE_PHONETIC, "&Use phonetic string as text\tCtrl+U");
    speech->AppendSeparator();
    speech->Append(ID_RESET, "&Reset all parameters\tCtrl+R");

    auto* params = new wxMenu;
    // The categories in table order, as the combo lists them.
    int n = 0;
    std::vector<wxString> cats;
    for (int i = 0; i < gama_param_count(); ++i) {
        wxString c = u8(gama_param_describe(i)->category);
        if (std::find(cats.begin(), cats.end(), c) == cats.end())
            cats.push_back(c);
    }
    if (std::find(cats.begin(), cats.end(), "Output") == cats.end())
        cats.push_back("Output");
    for (const wxString& c : cats) {
        wxString label = "&" + wxString::Format("%d", n + 1) + " " + c;
        if (n < 9)
            label += wxString::Format("\tCtrl+%d", n + 1);
        params->Append(ID_CATEGORY_FIRST + n, label);
        ++n;
    }

    auto* help = new wxMenu;
    help->Append(ID_KEYS, "&Keys\tF1");
    help->Append(wxID_ABOUT, "&About");

    auto* bar = new wxMenuBar;
    bar->Append(file, "&File");
    bar->Append(speech, "&Speech");
    bar->Append(params, "&Parameters");
    bar->Append(help, "&Help");
    SetMenuBar(bar);

    Bind(wxEVT_MENU, [this](wxCommandEvent&) { onOpenPreset(); }, ID_OPEN_PRESET);
    Bind(wxEVT_MENU, [this](wxCommandEvent&) { onSavePreset(); }, ID_SAVE_PRESET);
    Bind(wxEVT_MENU, [this](wxCommandEvent&) { onSaveWav(); }, ID_SAVE_WAV);
    Bind(wxEVT_MENU, [this](wxCommandEvent&) { onSaveTrack(); }, ID_SAVE_TRACK);
    Bind(wxEVT_MENU, [this](wxCommandEvent&) { Close(); }, wxID_EXIT);
    Bind(wxEVT_MENU, [this](wxCommandEvent&) { onSpeak(); }, ID_SPEAK);
    Bind(wxEVT_MENU, [this](wxCommandEvent&) { onStop(); }, ID_STOP);
    Bind(wxEVT_MENU, [this](wxCommandEvent&) { onShowPhonetic(); }, ID_SHOW_PHONETIC);
    Bind(wxEVT_MENU, [this](wxCommandEvent&) { onUsePhonetic(); }, ID_USE_PHONETIC);
    Bind(wxEVT_MENU, [this](wxCommandEvent&) { onReset(); }, ID_RESET);
    Bind(wxEVT_MENU, [this](wxCommandEvent& ev) { showCategory(ev.GetId() - ID_CATEGORY_FIRST, true); },
         ID_CATEGORY_FIRST, ID_CATEGORY_FIRST + 31);
    Bind(wxEVT_MENU, [this](wxCommandEvent&) {
        wxMessageBox(
            "Ctrl+Enter\tSpeak the selection, or all the text\n"
            "Esc\tStop\n"
            "Ctrl+S\tSave the speech as a WAV file\n"
            "Ctrl+T\tSave the parameter track\n"
            "Ctrl+P\tShow the phonetic string (the focus moves to it)\n"
            "Ctrl+U\tUse the phonetic string as the text\n"
            "Ctrl+R\tReset every parameter to the data files' values\n"
            "Ctrl+O\tOpen a voice preset\n"
            "Ctrl+Shift+S\tSave a voice preset\n"
            "Ctrl+1 to Ctrl+7\tShow a parameter category, and move to its first field\n"
            "Up, Down\tOne step in a number; Page Up, Page Down: ten steps\n"
            "Alt+T, A, V, M, N\tText, Read as, Voice, Parameters for, Phonetic string\n"
            "Alt+K, O, W, I, U, R\tThe buttons: Speak, Stop, Save as WAV, Show phonetic string,\n"
            "\tUse phonetic string as text, Reset all parameters\n"
            "F1\tThis list",
            "Keys", wxOK | wxICON_INFORMATION, this);
    }, ID_KEYS);
    Bind(wxEVT_MENU, [this](wxCommandEvent&) {
        wxMessageBox(
            wxString::Format("GamaTTS, a desktop GUI for its model 5. C API version %d.\n\n", gama_api_version()) +
            "Gnuspeech: David R. Hill, Leonard Manzara and Craig Schock, 1991-2002.\n"
            "GamaTTS, the engine and model 5: Marcelo Y. Matuda, 2014-2025.\n"
            "This GUI and the C API: dengopaiv, 2026.\n\n"
            "GPL-3.0-or-later. See NOTICE.md and LICENSE.txt.",
            "About", wxOK | wxICON_INFORMATION, this);
    }, wxID_ABOUT);
}

wxString MainFrame::describe(int i) const
{
    const gama_param_info* p = gama_param_describe(i);
    double def = 0.0;
    gama_param_default(engine_, i, &def);
    wxString unit = *p->unit ? " " + u8(p->unit) : wxString();
    wxString d = u8(p->help) + " ";
    if (p->kind == GAMA_PARAM_NUMBER) {
        d += "From " + formatNumber(p->min, p->decimals) + " to " + formatNumber(p->max, p->decimals) + unit +
             ". Default " + formatNumber(def, p->decimals) + ".";
    } else if (p->kind == GAMA_PARAM_SWITCH) {
        d += wxString("Default ") + (def != 0.0 ? "on." : "off.");
    } else {
        for (int k = 0; k < p->choice_count; ++k)
            if (p->choice_values[k] == def)
                d += "Default " + u8(p->choice_names[k]) + ".";
    }
    if (std::strcmp(p->file, "voice") == 0)
        d += " Kept in the voice file.";
    return d;
}

void MainFrame::buildCategory(wxWindow* box, wxSizer* grid, const wxString& category)
{
    for (int i = 0; i < gama_param_count(); ++i)
        if (u8(gama_param_describe(i)->category) == category)
            addParamField(box, grid, i);
    if (category == "Output")
        addOutputFields(box, grid);
}

wxSpinCtrlDouble* MainFrame::addSpin(wxWindow* box, wxSizer* grid, const wxString& name, double min, double max,
                                     double value, double step, int decimals)
{
    // The label is created immediately before its control. No colon: the
    // name is given explicitly, and a colon would become part of it on GTK.
    grid->Add(new wxStaticText(box, wxID_ANY, name), 0, wxALIGN_CENTER_VERTICAL);
    auto* spin = new wxSpinCtrlDouble(box, wxID_ANY, wxEmptyString, wxDefaultPosition, FromDIP(wxSize(130, -1)),
                                      wxSP_ARROW_KEYS, min, max, value, step);
    spin->SetDigits(static_cast<unsigned>(decimals));
    // wxSpinCtrlDouble's validator swallows a key that would put the value out of range, with
    // no message: "99" in a field that stops at 24 becomes 9, while a screen reader has echoed
    // both nines. Without it the text says what was typed, and the handler below says what
    // happens to it. It must go after SetDigits, which sets it again.
    for (wxWindow* child : spin->GetChildren())
        if (wxDynamicCast(child, wxTextCtrl))
            child->SetValidator(wxDefaultValidator);
    grid->Add(spin, 0);
    return spin;
}

void MainFrame::addParamField(wxWindow* box, wxSizer* grid, int i)
{
    const gama_param_info* p = gama_param_describe(i);
    double value = 0.0;
    gama_get_param(engine_, i, &value);
    Field f;
    f.param = i;
    f.name = u8(p->label);
    if (*p->unit)
        f.name += " (" + u8(p->unit) + ")";

    if (p->kind == GAMA_PARAM_NUMBER) {
        auto* spin = addSpin(box, grid, f.name, p->min, p->max, value, p->step, p->decimals);
        spin->Bind(wxEVT_SPINCTRLDOUBLE, [this, i, spin, name = f.name](wxSpinDoubleEvent& ev) {
            if (gama_set_param(engine_, i, ev.GetValue()) == GAMA_OK) {
                setStatus(name + ": " + spin->GetTextValue());
            } else {
                double v = 0.0;
                gama_get_param(engine_, i, &v);
                const wxString reason = u8(gama_last_error(engine_));
                spin->SetValue(v);
                wxBell();
                // Said before the value is put back, so that it is the value typed.
                const wxString typed = wxString::FromCDouble(ev.GetValue());
                // Kept, so that moving on does not replace it with the next field's help.
                pendingNote_ = name + ": " + typed + " is refused. " + reason + " It stays at " +
                               spin->GetTextValue() + ".";
                setStatus(pendingNote_);
            }
        });
        // wxSpinCtrlDouble corrects a typed value outside the range when the
        // field loses the focus, silently. The note is kept until then, and
        // shown instead of the next control's help (onChildFocus): otherwise
        // a screen-reader user tabbing on would never learn of it, as
        // rsynth's GUI found (rsynth docs/07).
        spin->Bind(wxEVT_TEXT, [this, i, p, spin, name = f.name](wxCommandEvent& ev) {
            // Not typed: wxWidgets writing the corrected value as the focus leaves. That must
            // not clear the note saying what was corrected.
            const wxWindow* focus = wxWindow::FindFocus();
            if (!focus || (focus != spin && focus->GetParent() != spin)) {
                ev.Skip();
                return;
            }
            double typed = 0.0;
            pendingNote_.clear();
            if (ev.GetString().ToCDouble(&typed) || ev.GetString().ToDouble(&typed)) {
                if (typed < p->min || typed > p->max) {
                    const double limit = typed < p->min ? p->min : p->max;
                    pendingNote_ = name + ": " + ev.GetString() + " is outside " + formatNumber(p->min, p->decimals) +
                                   " to " + formatNumber(p->max, p->decimals) + "; set to " +
                                   formatNumber(limit, p->decimals) + ".";
                    setStatus(pendingNote_);
                }
            } else if (!ev.GetString().empty() && ev.GetString() != "-") {
                double v = 0.0;
                gama_get_param(engine_, i, &v);
                pendingNote_ = name + ": " + ev.GetString() + " is not a number. It stays at " +
                               formatNumber(v, p->decimals) + ".";
                setStatus(pendingNote_);
            }
            ev.Skip();
        });
        f.control = spin;
    } else if (p->kind == GAMA_PARAM_SWITCH) {
        // A check box carries its own label.
        grid->AddSpacer(0);
        auto* check = new wxCheckBox(box, wxID_ANY, f.name);
        check->SetValue(value != 0.0);
        check->Bind(wxEVT_CHECKBOX, [this, i](wxCommandEvent& ev) {
            gama_set_param(engine_, i, ev.IsChecked() ? 1.0 : 0.0);
        });
        grid->Add(check, 0);
        f.control = check;
    } else {
        grid->Add(new wxStaticText(box, wxID_ANY, f.name), 0, wxALIGN_CENTER_VERTICAL);
        wxArrayString names;
        int selection = 0;
        for (int k = 0; k < p->choice_count; ++k) {
            names.Add(u8(p->choice_names[k]));
            if (p->choice_values[k] == value)
                selection = k;
        }
        auto* choice = new wxChoice(box, wxID_ANY, wxDefaultPosition, wxDefaultSize, names);
        choice->SetSelection(selection);
        choice->Bind(wxEVT_CHOICE, [this, i, p](wxCommandEvent& ev) {
            gama_set_param(engine_, i, p->choice_values[ev.GetSelection()]);
        });
        grid->Add(choice, 0);
        f.control = choice;
    }
    nameControl(f.control, f.name, describe(i));
    fields_.push_back(f);
}

void MainFrame::addOutputFields(wxWindow* box, wxSizer* grid)
{
    volume_ = addSpin(box, grid, "Volume (%)", 0, 100, 100, 1, 0);
    nameControl(volume_, "Volume (%)",
                "A gain on the finished speech, after the levelling below. 100 leaves it as levelled. "
                "Default 100.");
    volume_->Bind(wxEVT_SPINCTRLDOUBLE, [this](wxSpinDoubleEvent& ev) {
        gama_set_volume(engine_, ev.GetValue() / 100.0);
        setStatus("Volume: " + volume_->GetTextValue() + "%");
    });
    fields_.push_back({ -1, volume_, "Volume (%)" });

    // Levelling (docs/10): steady throughout by default, as in the NVDA add-on.
    grid->Add(new wxStaticText(box, wxID_ANY, "Loudness"), 0, wxALIGN_CENTER_VERTICAL);
    wxArrayString levelings;
    for (const Leveling& l : kLevelings)
        levelings.Add(l.name);
    leveling_ = new wxChoice(box, wxID_ANY, wxDefaultPosition, wxDefaultSize, levelings);
    leveling_->SetSelection(0);
    nameControl(leveling_, "Loudness",
                "Steady throughout: every syllable at the loudness target below, whatever its stress, pitch or "
                "vowel. Even per message: each utterance at the target, louder and softer syllables inside it as "
                "the engine makes them. The engine's own peaks: each utterance scaled to its own peak, so the "
                "loudness varies with the text. Default steady throughout.");
    grid->Add(leveling_, 0);
    fields_.push_back({ -1, leveling_, "Loudness" });
    target_ = addSpin(box, grid, "Loudness target (dB)", -40, -10, GAMA_LEVEL_DEFAULT_TARGET, 0.5, 1);
    nameControl(target_, "Loudness target (dB)",
                "The A-weighted level of each utterance, in dB relative to full scale, unless Loudness is "
                "the engine's own peaks. -22 is about 1 dB below eSpeak's klatt5 at full volume. From -40 to -10. "
                "Default -22.");
    fields_.push_back({ -1, target_, "Loudness target (dB)" });
    leveling_->Bind(wxEVT_CHOICE, [this](wxCommandEvent&) { applyLeveling(); });
    target_->Bind(wxEVT_SPINCTRLDOUBLE, [this](wxSpinDoubleEvent&) { applyLeveling(); });
    applyLeveling();

    grid->AddSpacer(0);
    trim_ = new wxCheckBox(box, wxID_ANY, "Trim the silence at both ends");
    nameControl(trim_, "Trim the silence at both ends",
                "The engine leaves about 0.1 to 0.2 seconds of silence before and after every utterance. "
                "On, it keeps only the amounts below. Default off.");
    grid->Add(trim_, 0);
    fields_.push_back({ -1, trim_, "Trim the silence at both ends" });

    lead_ = addSpin(box, grid, "Silence kept before (ms)", 0, 1000, kDefaultLeadMs, 5, 0);
    nameControl(lead_, "Silence kept before (ms)", "Used when trimming is on. From 0 to 1000. Default 10.");
    fields_.push_back({ -1, lead_, "Silence kept before (ms)" });
    trail_ = addSpin(box, grid, "Silence kept after (ms)", 0, 1000, kDefaultTrailMs, 10, 0);
    nameControl(trail_, "Silence kept after (ms)", "Used when trimming is on. From 0 to 1000. Default 150.");
    fields_.push_back({ -1, trail_, "Silence kept after (ms)" });

    auto applyTrim = [this](wxEvent&) {
        if (trim_->GetValue())
            gama_set_trim(engine_, static_cast<int>(lead_->GetValue()), static_cast<int>(trail_->GetValue()));
        else
            gama_set_trim(engine_, -1, -1);
    };
    trim_->Bind(wxEVT_CHECKBOX, applyTrim);
    lead_->Bind(wxEVT_SPINCTRLDOUBLE, applyTrim);
    trail_->Bind(wxEVT_SPINCTRLDOUBLE, applyTrim);
}

void MainFrame::applyLeveling()
{
    gama_set_leveling(engine_, kLevelings[leveling_->GetSelection()].mode, target_->GetValue());
}

void MainFrame::showCategory(int c, bool focusFirst)
{
    if (c < 0 || c >= static_cast<int>(groups_.size()))
        return;
    wxSizer* top = panel_->GetSizer();
    for (size_t k = 0; k < groups_.size(); ++k)
        top->Show(groups_[k], static_cast<int>(k) == c, true);
    category_->SetSelection(c);
    panel_->Layout();
    if (focusFirst && firstInGroup_[c])
        firstInGroup_[c]->SetFocus();
    setStatus("Parameters for " + categories_[c] + ".");
}

void MainFrame::refreshFields()
{
    for (const Field& f : fields_) {
        if (f.param < 0)
            continue;
        const gama_param_info* p = gama_param_describe(f.param);
        double v = 0.0;
        gama_get_param(engine_, f.param, &v);
        if (auto* spin = wxDynamicCast(f.control, wxSpinCtrlDouble))
            spin->SetValue(v);
        else if (auto* check = wxDynamicCast(f.control, wxCheckBox))
            check->SetValue(v != 0.0);
        else if (auto* choice = wxDynamicCast(f.control, wxChoice))
            for (int k = 0; k < p->choice_count; ++k)
                if (p->choice_values[k] == v)
                    choice->SetSelection(k);
        describeControl(f.control, describe(f.param));
    }
}

void MainFrame::onChildFocus(wxChildFocusEvent& ev)
{
    // The status bar shows the focused control's description, unless a value
    // was just corrected on leaving its field: then that is shown, with a beep.
    if (!pendingNote_.empty()) {
        setStatus(pendingNote_);
        pendingNote_.clear();
        wxBell();
        ev.Skip();
        return;
    }
    wxWindow* w = ev.GetWindow();
    for (wxWindow* p = w; p && p != panel_; p = p->GetParent()) {
        wxString tip = p->GetToolTipText();
        if (!tip.empty()) {
            setStatus(tip);
            break;
        }
    }
    ev.Skip();
}

Settings MainFrame::snapshot() const
{
    Settings s;
    s.voice = gama_voice(engine_);
    s.values.resize(static_cast<size_t>(gama_param_count()));
    for (int i = 0; i < gama_param_count(); ++i)
        gama_get_param(engine_, i, &s.values[static_cast<size_t>(i)]);
    s.gain = gama_volume(engine_);
    gama_trim(engine_, &s.leadMs, &s.trailMs);
    gama_leveling(engine_, &s.levelMode, &s.levelTarget);
    return s;
}

std::optional<std::string> MainFrame::currentInput(bool selectionOnly) const
{
    wxString t = selectionOnly ? text_->GetStringSelection() : wxString();
    if (t.empty())
        t = text_->GetValue();
    t.Trim(true).Trim(false);
    if (t.empty())
        return std::nullopt;
    // gama_tts feeds the engine each line plus one space; so does this, so that
    // its output is the golden traces' (tests/golden/README.md).
    t.Replace("\r\n", "\n");
    t.Replace("\n", " ");
    std::string s = t.utf8_string();
    s += ' ';
    return s;
}

void MainFrame::submit(JobKind kind, const wxString& path)
{
    Job job;
    job.kind = kind;
    job.path = path;
    job.phonetic = readAs_->GetSelection() == 1;
    if (kind == JobKind::Smoke) {
        job.input = "Hello world. ";
        job.phonetic = false;
    } else {
        auto input = currentInput(kind == JobKind::Play);
        if (!input) {
            wxBell();
            setStatus("There is no text to speak.");
            return;
        }
        job.input = *input;
    }
    job.settings = snapshot();
    job.id = ++jobId_;
    setStatus(kind == JobKind::Play ? "Speaking..." : "Rendering...");
    worker_->submit(std::move(job));
}

void MainFrame::onResult(Result r)
{
    if (r.id != jobId_)
        return;  // stopped, or overtaken by a newer job
    if (r.kind == JobKind::Smoke) {
        std::fprintf(stdout, "smoke: %s, %zu samples at %d Hz\n", r.ok ? "ok" : r.error.c_str(), r.samples.size(),
                     r.rate);
        std::fflush(stdout);
        g_smokeExitCode = r.ok && !r.samples.empty() ? 0 : 1;
        Close(true);
        return;
    }
    if (!r.ok) {
        wxBell();
        setStatus("Could not speak: " + u8(r.error.c_str()));
        return;
    }
    const double seconds = r.rate > 0 ? static_cast<double>(r.samples.size()) / r.rate : 0.0;
    const wxString length = wxString::Format("%.1f s at %d Hz", seconds, r.rate);
    wxString error;
    switch (r.kind) {
    case JobKind::Play: {
        std::vector<char> wav = makeWav(r.samples, r.rate);
        wxSound::Stop();
        if (sound_.Create(wav.size(), wav.data()) && sound_.Play(wxSOUND_ASYNC)) {
            setStatus("Speaking, " + length + ".");
            playTimer_.StartOnce(static_cast<int>(seconds * 1000) + 100);
        } else {
            wxBell();
            setStatus("Could not play the sound.");
        }
        break;
    }
    case JobKind::SaveWav: {
        std::vector<char> wav = makeWav(r.samples, r.rate);
        if (writeFileAtomically(r.path, wav.data(), wav.size(), &error))
            setStatus("Saved " + length + " to " + r.path + ".");
        else
            setStatus("Not saved: " + error + ".");
        break;
    }
    case JobKind::SaveTrack:
        if (writeFileAtomically(r.path, r.track.data(), r.track.size(), &error))
            setStatus(wxString::Format("Saved the parameter track of %s, %zu bytes, to ", length, r.track.size()) +
                      r.path + ".");
        else
            setStatus("Not saved: " + error + ".");
        break;
    case JobKind::Smoke:
        break;
    }
    if (!error.empty())
        wxBell();
}

void MainFrame::onSpeak()
{
    submit(JobKind::Play);
}

void MainFrame::onStop()
{
    ++jobId_;  // a render still running is dropped when it arrives
    playTimer_.Stop();
    wxSound::Stop();
    setStatus("Stopped.");
}

void MainFrame::onSaveWav()
{
    wxFileDialog dlg(this, "Save as WAV", wxEmptyString, "gamatts.wav", "WAV files (*.wav)|*.wav",
                     wxFD_SAVE | wxFD_OVERWRITE_PROMPT);
    if (dlg.ShowModal() == wxID_OK)
        submit(JobKind::SaveWav, dlg.GetPath());
}

void MainFrame::onSaveTrack()
{
    wxFileDialog dlg(this, "Save the parameter track", wxEmptyString, "gamatts_track.txt",
                     "Text files (*.txt)|*.txt|All files (*.*)|*.*", wxFD_SAVE | wxFD_OVERWRITE_PROMPT);
    if (dlg.ShowModal() == wxID_OK)
        submit(JobKind::SaveTrack, dlg.GetPath());
}

void MainFrame::onShowPhonetic()
{
    if (readAs_->GetSelection() == 1) {
        phonetic_->ChangeValue(text_->GetValue());
    } else {
        auto input = currentInput(false);
        if (!input) {
            wxBell();
            setStatus("There is no text.");
            return;
        }
        size_t n = gama_text_to_phonetic(engine_, input->c_str(), nullptr, 0);
        if (n == 0) {
            wxBell();
            setStatus("The text parser failed: " + u8(gama_last_error(engine_)));
            return;
        }
        std::string s(n + 1, '\0');
        gama_text_to_phonetic(engine_, input->c_str(), s.data(), s.size());
        s.resize(n);
        phonetic_->ChangeValue(u8(s.c_str()));
    }
    phonetic_->SetFocus();
    phonetic_->SetInsertionPoint(0);
}

void MainFrame::onUsePhonetic()
{
    if (readAs_->GetSelection() == 1) {
        setStatus("The text is already a phonetic string.");
        return;
    }
    onShowPhonetic();
    wxString p = phonetic_->GetValue();
    if (p.empty())
        return;
    text_->ChangeValue(p.Trim());
    readAs_->SetSelection(1);
    text_->SetFocus();
    setStatus("The text is now its phonetic string, read as a phonetic string.");
}

void MainFrame::onReset()
{
    gama_reset_params(engine_);
    refreshFields();
    setStatus("Every parameter is back to the data files' value for the " + voice_->GetStringSelection() + " voice.");
}

void MainFrame::onVoice()
{
    const int v = voice_->GetSelection();
    if (gama_set_voice(engine_, v) != GAMA_OK) {
        wxBell();
        setStatus("Could not load the voice: " + u8(gama_last_error(engine_)));
        voice_->SetSelection(gama_voice(engine_));
        return;
    }
    refreshFields();
    setStatus("Voice " + voice_->GetStringSelection() + ": the values kept in its file are loaded.");
}

// Voice presets: plain text, "key = value" as the engine's own data files
// are written, "#" for comments. voice, volume_percent, trim, trim_lead_ms,
// trim_trail_ms, loudness (constant, message or peak) and
// loudness_target_db, then one line per parameter. A key left out keeps its
// current value; an unknown key is skipped and a bad value is clamped, and
// both are counted.
void MainFrame::onSavePreset()
{
    wxFileDialog dlg(this, "Save voice preset", wxEmptyString, "voice.gamapreset",
                     "GamaTTS presets (*.gamapreset)|*.gamapreset|All files (*.*)|*.*",
                     wxFD_SAVE | wxFD_OVERWRITE_PROMPT);
    if (dlg.ShowModal() != wxID_OK)
        return;
    std::ostringstream out;
    out << "# GamaTTS voice preset, from the desktop GUI (docs/10).\n";
    out << "voice = " << gama_voice_name(engine_, gama_voice(engine_)) << "\n";
    out << "volume_percent = " << formatExact(volume_->GetValue()) << "\n";
    out << "trim = " << (trim_->GetValue() ? 1 : 0) << "\n";
    out << "trim_lead_ms = " << formatExact(lead_->GetValue()) << "\n";
    out << "trim_trail_ms = " << formatExact(trail_->GetValue()) << "\n";
    out << "loudness = " << kLevelings[leveling_->GetSelection()].word << "\n";
    out << "loudness_target_db = " << formatExact(target_->GetValue()) << "\n";
    wxString lastCategory;
    for (int i = 0; i < gama_param_count(); ++i) {
        const gama_param_info* p = gama_param_describe(i);
        if (u8(p->category) != lastCategory) {
            lastCategory = u8(p->category);
            out << "\n# " << p->category << "\n";
        }
        double v = 0.0;
        gama_get_param(engine_, i, &v);
        out << p->key << " = " << formatExact(v) << "\n";
    }
    const std::string s = out.str();
    wxString error;
    if (writeFileAtomically(dlg.GetPath(), s.data(), s.size(), &error))
        setStatus("Saved the preset to " + dlg.GetPath() + ".");
    else {
        wxBell();
        setStatus("Not saved: " + error + ".");
    }
}

void MainFrame::onOpenPreset()
{
    wxFileDialog dlg(this, "Open voice preset", wxEmptyString, wxEmptyString,
                     "GamaTTS presets (*.gamapreset)|*.gamapreset|All files (*.*)|*.*", wxFD_OPEN | wxFD_FILE_MUST_EXIST);
    if (dlg.ShowModal() != wxID_OK)
        return;
    std::ifstream in(dlg.GetPath().fn_str());
    if (!in) {
        wxBell();
        setStatus("Cannot read " + dlg.GetPath() + ".");
        return;
    }
    std::vector<std::pair<std::string, std::string>> entries;
    std::string line;
    int unknown = 0, corrected = 0;
    while (std::getline(in, line)) {
        if (!line.empty() && line.back() == '\r')
            line.pop_back();
        const size_t hash = line.find('#');
        if (hash != std::string::npos)
            line.erase(hash);
        const size_t eq = line.find('=');
        auto trim = [](std::string s) {
            const char* ws = " \t";
            s.erase(0, s.find_first_not_of(ws));
            s.erase(s.find_last_not_of(ws) + 1);
            return s;
        };
        if (eq == std::string::npos) {
            if (!trim(line).empty())
                ++unknown;
            continue;
        }
        entries.emplace_back(trim(line.substr(0, eq)), trim(line.substr(eq + 1)));
    }
    // Values that share a limit (the API's rule 10) may be refused until their
    // partner has been set: they wait here, and are tried again after the rest.
    std::vector<std::pair<int, double>> refused;

    // The voice first: it loads the voice file's values, which the preset's
    // own values then replace.
    for (const auto& [key, value] : entries) {
        if (key != "voice")
            continue;
        int found = -1;
        for (int v = 0; v < gama_voice_count(engine_); ++v)
            if (value == gama_voice_name(engine_, v))
                found = v;
        if (found >= 0) {
            gama_set_voice(engine_, found);
            voice_->SetSelection(found);
        } else {
            ++corrected;
        }
    }
    for (const auto& [key, value] : entries) {
        if (key == "voice")
            continue;
        if (key == "loudness") {
            int found = -1;
            for (int k = 0; k < static_cast<int>(std::size(kLevelings)); ++k)
                if (value == kLevelings[k].word)
                    found = k;
            if (found >= 0)
                leveling_->SetSelection(found);
            else
                ++corrected;
            continue;
        }
        char* end = nullptr;
        double v = std::strtod(value.c_str(), &end);
        if (end == value.c_str() || *end != '\0' || !std::isfinite(v)) {
            ++corrected;
            continue;
        }
        auto clampTo = [&](double lo, double hi) {
            if (v < lo || v > hi) {
                v = std::clamp(v, lo, hi);
                ++corrected;
            }
            return v;
        };
        if (key == "volume_percent") {
            volume_->SetValue(clampTo(0, 100));
            gama_set_volume(engine_, volume_->GetValue() / 100.0);
        } else if (key == "trim") {
            trim_->SetValue(v != 0.0);
        } else if (key == "trim_lead_ms") {
            lead_->SetValue(clampTo(0, 1000));
        } else if (key == "trim_trail_ms") {
            trail_->SetValue(clampTo(0, 1000));
        } else if (key == "loudness_target_db") {
            target_->SetValue(clampTo(-40, -10));
        } else {
            const int i = gama_param_index(key.c_str());
            if (i < 0) {
                ++unknown;
                continue;
            }
            const gama_param_info* p = gama_param_describe(i);
            if (p->kind == GAMA_PARAM_SWITCH)
                v = v != 0.0 ? 1.0 : 0.0;
            const double wanted = p->kind == GAMA_PARAM_NUMBER ? clampTo(p->min, p->max) : v;
            if (gama_set_param(engine_, i, wanted) != GAMA_OK)
                refused.emplace_back(i, wanted);
        }
    }
    for (int round = 0; round < 3 && !refused.empty(); ++round) {
        std::vector<std::pair<int, double>> still;
        for (const auto& [i, wanted] : refused)
            if (gama_set_param(engine_, i, wanted) != GAMA_OK)
                still.emplace_back(i, wanted);
        refused = std::move(still);
    }
    corrected += static_cast<int>(refused.size());
    if (trim_->GetValue())
        gama_set_trim(engine_, static_cast<int>(lead_->GetValue()), static_cast<int>(trail_->GetValue()));
    else
        gama_set_trim(engine_, -1, -1);
    applyLeveling();
    refreshFields();
    wxString note = "Opened " + wxFileName(dlg.GetPath()).GetFullName() + ".";
    if (unknown)
        note += wxString::Format(" %d unknown line%s skipped.", unknown, unknown == 1 ? "" : "s");
    if (corrected)
        note += wxString::Format(" %d value%s out of range or unreadable, corrected or skipped.", corrected,
                                 corrected == 1 ? "" : "s");
    if (unknown || corrected)
        wxBell();
    setStatus(note);
}

// ---------------------------------------------------------------------------

class App : public wxApp {
public:
    bool OnInit() override;
    int OnExit() override;
    int OnRun() override
    {
        const int rc = wxApp::OnRun();
        return smoke_ && rc == 0 ? g_smokeExitCode : rc;
    }
    void OnInitCmdLine(wxCmdLineParser& parser) override
    {
        static const wxCmdLineEntryDesc desc[] = {
            { wxCMD_LINE_OPTION, nullptr, "data", "the folder holding voice/english (default: data)" },
            { wxCMD_LINE_SWITCH, nullptr, "smoke", "build the window, render one utterance, and exit" },
            wxCMD_LINE_DESC_END,
        };
        parser.SetDesc(desc);
    }
    bool OnCmdLineParsed(wxCmdLineParser& parser) override
    {
        parser.Found("data", &dataArg_);
        smoke_ = parser.Found("smoke");
        return true;
    }

private:
    wxString dataArg_;
    bool smoke_ = false;
    gama_engine* engine_ = nullptr;
};

bool App::OnInit()
{
    if (!wxApp::OnInit())
        return false;
    SetAppName(kProgramName);
    const wxString dir = findDataDir(dataArg_);
    std::optional<std::string> narrow = dir.empty() ? std::nullopt : narrowPath(dir);
    char err[512] = "";
    if (narrow)
        engine_ = gama_create(narrow->c_str(), err, sizeof err);
    if (!engine_) {
        wxString why = dir.empty() ? wxString("No data folder was found (data, with voice/english); use --data.")
                       : !narrow  ? "The data folder's path cannot be passed to the engine: " + dir
                                  : "The engine did not load from " + dir + ": " + u8(err);
        if (smoke_)
            std::fprintf(stderr, "smoke: %s\n", static_cast<const char*>(why.utf8_str()));
        else
            wxMessageBox(why, kProgramName, wxOK | wxICON_ERROR);
        return false;
    }
    auto* frame = new MainFrame(engine_, *narrow, smoke_);
    if (!smoke_)
        frame->Show();
    return true;
}

int App::OnExit()
{
    gama_destroy(engine_);
    engine_ = nullptr;
    return wxApp::OnExit();
}

} // namespace

wxIMPLEMENT_APP(App);
