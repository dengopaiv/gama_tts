import sys
p = r"C:\GIT\speech synthesis\gama_tts\gui\gama_gui.cpp"
s = open(p, encoding="utf-8", newline="").read()
a = """        spin->Bind(wxEVT_TEXT, [this, i, p, name = f.name](wxCommandEvent& ev) {
            double typed = 0.0;
            pendingNote_.clear();"""
b = """        spin->Bind(wxEVT_TEXT, [this, i, p, name = f.name](wxCommandEvent& ev) {
            // Not typed: wxWidgets writing the corrected value as the focus leaves. That must
            // not clear the note saying what was corrected.
            if (wxWindow::FindFocus() != ev.GetEventObject()) {
                ev.Skip();
                return;
            }
            double typed = 0.0;
            pendingNote_.clear();"""
if a not in s: sys.exit("MISSING")
open(p, "w", encoding="utf-8", newline="\n").write(s.replace(a, b))
