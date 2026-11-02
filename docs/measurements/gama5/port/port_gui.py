"""One-time port of gnuspeech_gui.cpp to gama_gui.cpp. Every replacement must apply."""
import re
import sys

src = r"C:\GIT\speech synthesis\GnuspeechSA-NVDA\gui\gnuspeech_gui.cpp"
dst = r"C:\GIT\speech synthesis\gama_tts\gui\gama_gui.cpp"
s = open(src, encoding="utf-8", newline="").read().replace("\r\n", "\n")

s = re.sub(r"\bgs_", "gama_", s)
s = re.sub(r"\bGS_", "GAMA_", s)

R = [
("""// gnuspeech_gui.cpp -- the desktop GUI for Gnuspeech (docs/10).
//
//   gnuspeech_gui [--data <folder with monet.xml>] [--smoke]
//
// Part of IveHeardOfWildebeest. Copyright 2026 dengopaiv. GPL-3.0-or-later,
// like the engine (Gnuspeech: Copyright 1991-2002 David R. Hill, Leonard
// Manzara, Craig Schock; GnuspeechSA: Copyright 2014-2015 Marcelo Y. Matuda).
// See NOTICE.md.
//
// C++17 and wxWidgets over the C API (gnuspeech_api.h) and nothing else of the
// engine.""",
"""// gama_gui.cpp -- the desktop GUI for GamaTTS, model 5 (docs/10).
//
//   gama_gui [--data <folder holding voice/english>] [--smoke]
//
// Copyright 2026 dengopaiv. GPL-3.0-or-later, like the engine (Gnuspeech:
// Copyright 1991-2002 David R. Hill, Leonard Manzara, Craig Schock; GamaTTS:
// Copyright 2014-2025 Marcelo Y. Matuda). See NOTICE.md. Adapted from
// gnuspeech_gui.cpp in GnuspeechSA-NVDA.
//
// C++17 and wxWidgets over the C API (gama_api.h) and nothing else of the
// engine."""),
('#include "gnuspeech_api.h"', '#include "gama_api.h"'),
('const char* const kProgramName = "Gnuspeech";', 'const char* const kProgramName = "GamaTTS";'),
('{ "Gnuspeech\'s own peaks", "peak", GAMA_LEVEL_PEAK },', '{ "The engine\'s own peaks", "peak", GAMA_LEVEL_PEAK },'),
("""// The data folder: --data, else data/en beside the program, else data/en in
// a folder above it (a build tree inside the repository).""",
"""// The data folder: --data, else data beside the program, else data in a folder
// above it (a build tree inside the repository)."""),
("""        wxString candidate = dir + wxFILE_SEP_PATH + "data" + wxFILE_SEP_PATH + "en";
        if (wxFileName::FileExists(candidate + wxFILE_SEP_PATH + "monet.xml"))""",
"""        wxString candidate = dir + wxFILE_SEP_PATH + "data";
        if (wxFileName::FileExists(candidate + "/voice/english/5_male/_index.txt"))"""),
("""        for (size_t i = 0; i < s.values.size(); ++i)
            gama_set_param(e, static_cast<int>(i), s.values[i]);
""",
"""        // Some values share a limit (the API's rule 10), so one may be refused
        // until another has been set. The settings are valid together, so a
        // second round always finishes it.
        for (int round = 0; round < 3; ++round) {
            bool refused = false;
            for (size_t i = 0; i < s.values.size(); ++i)
                refused = gama_set_param(e, static_cast<int>(i), s.values[i]) != GAMA_OK || refused;
            if (!refused)
                break;
        }
"""),
('"Hello. This is Gnuspeech, an articulatory speech synthesizer."', '"Hello. This is GamaTTS, an articulatory speech synthesizer."'),
('"Text goes through the text parser. Phonetic string is spoken as written, in Monet\'s notation."',
 '"Text goes through the text parser. Phonetic string is spoken as written, in Gnuspeech\'s notation."'),
('''"Loads the voice file's values into the glottal source, vocal tract and nose parameters. "
                "Every other parameter keeps its value."''',
 '''"Loads the voice file's values into the parameters kept there. "
                "Every other parameter keeps its value."'''),
('"What the text parser made of the text (Ctrl+P), in Monet\'s notation."', '"What the text parser made of the text (Ctrl+P), in Gnuspeech\'s notation."'),
('"Ctrl+T\\tSave the TRM parameter track\\n"', '"Ctrl+T\\tSave the parameter track\\n"'),
("""            wxString::Format("Gnuspeech, a desktop GUI. C API version %d.\\n\\n", gama_api_version()) +
            "Gnuspeech: David R. Hill, Leonard Manzara and Craig Schock, 1991-2002.\\n"
            "GnuspeechSA, the C++ port used here: Marcelo Y. Matuda, 2014-2015.\\n"
            "This GUI and the C API: dengopaiv, 2026.\\n\\n"
            "GPL-3.0-or-later. See NOTICE.md and COPYING.",""",
"""            wxString::Format("GamaTTS, a desktop GUI for its model 5. C API version %d.\\n\\n", gama_api_version()) +
            "Gnuspeech: David R. Hill, Leonard Manzara and Craig Schock, 1991-2002.\\n"
            "GamaTTS, the engine and model 5: Marcelo Y. Matuda, 2014-2025.\\n"
            "This GUI and the C API: dengopaiv, 2026.\\n\\n"
            "GPL-3.0-or-later. See NOTICE.md and LICENSE.txt.","""),
("""                wxBell();
                setStatus(name + ": " + spin->GetTextValue() + " is refused.");""",
"""                wxBell();
                // Said before the value is put back, so that it is the value typed.
                const wxString typed = wxString::FromCDouble(ev.GetValue());
                setStatus(name + ": " + typed + " is refused. " + u8(gama_last_error(engine_)) + " It stays at " +
                          spin->GetTextValue() + ".");"""),
("""                gama_get_param(engine_, i, &v);
                spin->SetValue(v);
                wxBell();""",
"""                gama_get_param(engine_, i, &v);
                const wxString reason = u8(gama_last_error(engine_));
                spin->SetValue(v);
                wxBell();"""),
('u8(gama_last_error(engine_)) + " It stays at "', 'reason + " It stays at "'),
("""                "vowel. Even per message: each utterance at the target, louder and softer syllables inside it as "
                "Gnuspeech makes them. Gnuspeech's own peaks: each utterance scaled to its own peak, so the "
                "loudness varies with the text. Default steady throughout.");""",
"""                "vowel. Even per message: each utterance at the target, louder and softer syllables inside it as "
                "the engine makes them. The engine's own peaks: each utterance scaled to its own peak, so the "
                "loudness varies with the text. Default steady throughout.");"""),
("""                "The A-weighted level of each utterance, in dB relative to full scale, unless Loudness is "
                "Gnuspeech's own peaks. -22 is about 1 dB below eSpeak's klatt5 at full volume. From -40 to -10. "
                "Default -22.");""",
"""                "The A-weighted level of each utterance, in dB relative to full scale, unless Loudness is "
                "the engine's own peaks. -22 is about 1 dB below eSpeak's klatt5 at full volume. From -40 to -10. "
                "Default -22.");"""),
('''"Gnuspeech leaves about 0.1 to 0.2 seconds of silence before and after every utterance. "''',
 '''"The engine leaves about 0.1 to 0.2 seconds of silence before and after every utterance. "'''),
("""    // gnuspeech_sa feeds the engine each line plus one space; so does this,
    // so that its output is the golden traces' (tests/golden/README.md).""",
"""    // gama_tts feeds the engine each line plus one space; so does this, so that
    // its output is the golden traces' (tests/golden/README.md)."""),
('"gnuspeech.wav"', '"gamatts.wav"'),
('wxFileDialog dlg(this, "Save the TRM parameter track", wxEmptyString, "gnuspeech_track.txt",',
 'wxFileDialog dlg(this, "Save the parameter track", wxEmptyString, "gamatts_track.txt",'),
("""// trim_trail_ms, loudness (constant, message or peak) and
// loudness_target_db, then one line per parameter. even_loudness (1 or 0),
// from the first version of the levelling, is read as message or peak. A
// key left out keeps its
// current value; an unknown key is skipped and a bad value is clamped, and
// both are counted.""",
"""// trim_trail_ms, loudness (constant, message or peak) and
// loudness_target_db, then one line per parameter. A key left out keeps its
// current value; an unknown key is skipped and a bad value is clamped, and
// both are counted."""),
('"voice.gspreset"', '"voice.gamapreset"'),
('"Gnuspeech presets (*.gspreset)|*.gspreset|All files (*.*)|*.*",\n                     wxFD_SAVE',
 '"GamaTTS presets (*.gamapreset)|*.gamapreset|All files (*.*)|*.*",\n                     wxFD_SAVE'),
('"# Gnuspeech voice preset, from the desktop GUI (docs/10).\\n"', '"# GamaTTS voice preset, from the desktop GUI (docs/10).\\n"'),
('"Gnuspeech presets (*.gspreset)|*.gspreset|All files (*.*)|*.*", wxFD_OPEN',
 '"GamaTTS presets (*.gamapreset)|*.gamapreset|All files (*.*)|*.*", wxFD_OPEN'),
("""    // The voice first: it loads the voice file's values, which the preset's
    // own values then replace.
    for (const auto& [key, value] : entries) {""",
"""    // Values that share a limit (the API's rule 10) may be refused until their
    // partner has been set: they wait here, and are tried again after the rest.
    std::vector<std::pair<int, double>> refused;

    // The voice first: it loads the voice file's values, which the preset's
    // own values then replace.
    for (const auto& [key, value] : entries) {"""),
("""        } else if (key == "even_loudness") {
            leveling_->SetSelection(v != 0.0 ? 1 : 2);
        } else if (key == "loudness_target_db") {""",
"""        } else if (key == "loudness_target_db") {"""),
("""            if (gama_set_param(engine_, i, p->kind == GAMA_PARAM_NUMBER ? clampTo(p->min, p->max) : v) != GAMA_OK)
                ++corrected;
        }
    }
""",
"""            const double wanted = p->kind == GAMA_PARAM_NUMBER ? clampTo(p->min, p->max) : v;
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
"""),
('{ wxCMD_LINE_OPTION, nullptr, "data", "the folder holding monet.xml (default: data/en)" },',
 '{ wxCMD_LINE_OPTION, nullptr, "data", "the folder holding voice/english (default: data)" },'),
('wxString("No data folder was found (data/en with monet.xml); use --data.")',
 'wxString("No data folder was found (data, with voice/english); use --data.")'),
('setStatus("Every parameter is back to the data files\' value for the " + voice_->GetStringSelection() + " voice.");',
 'setStatus("Every parameter is back to the data files\' value for the " + voice_->GetStringSelection() + " voice.");'),
('setStatus("Voice " + voice_->GetStringSelection() + ": its glottal source, tract and nose values are loaded.");',
 'setStatus("Voice " + voice_->GetStringSelection() + ": the values kept in its file are loaded.");'),
]
for a, b in R:
    if a not in s:
        sys.exit("MISSING:\n" + a)
    s = s.replace(a, b)

for word in ("nuspeech", "monet", "TRM", "gspreset", "data/en"):
    for m in re.finditer(word, s):
        line = s.count("\n", 0, m.start()) + 1
        print(f"left: {word} at line {line}: {s.splitlines()[line - 1].strip()[:90]}")
open(dst, "w", encoding="utf-8", newline="\n").write(s)
print("wrote", len(s.splitlines()), "lines")
