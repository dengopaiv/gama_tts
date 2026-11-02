import sys
p = r"C:\GIT\speech synthesis\gama_tts\gui\gama_gui.cpp"
s = open(p, encoding="utf-8", newline="").read()
R = [
("""    spin->SetDigits(static_cast<unsigned>(decimals));
    grid->Add(spin, 0);
    return spin;""",
"""    spin->SetDigits(static_cast<unsigned>(decimals));
    // wxSpinCtrlDouble's validator swallows a key that would put the value out of range, with
    // no message: "99" in a field that stops at 24 becomes 9, while a screen reader has echoed
    // both nines. Without it the text says what was typed, and the handler below says what
    // happens to it. It must go after SetDigits, which sets it again.
    for (wxWindow* child : spin->GetChildren())
        if (wxDynamicCast(child, wxTextCtrl))
            child->SetValidator(wxDefaultValidator);
    grid->Add(spin, 0);
    return spin;"""),
("""                    setStatus(pendingNote_);
                }
            }
            ev.Skip();""",
"""                    setStatus(pendingNote_);
                }
            } else if (!ev.GetString().empty() && ev.GetString() != "-") {
                double v = 0.0;
                gama_get_param(engine_, i, &v);
                pendingNote_ = name + ": " + ev.GetString() + " is not a number. It stays at " +
                               formatNumber(v, p->decimals) + ".";
                setStatus(pendingNote_);
            }
            ev.Skip();"""),
("""        spin->Bind(wxEVT_TEXT, [this, p, name = f.name](wxCommandEvent& ev) {""",
 """        spin->Bind(wxEVT_TEXT, [this, i, p, name = f.name](wxCommandEvent& ev) {"""),
]
for a, b in R:
    if a not in s: sys.exit("MISSING " + a)
    s = s.replace(a, b)
open(p, "w", encoding="utf-8", newline="\n").write(s)
p = r"C:\GIT\speech synthesis\gama_tts\tests\gui\gui_check.py"
s = open(p, encoding="utf-8", newline="").read()
a = """	g.key(ord("R"), (VK_CONTROL,))
	check(text_of(pitch) == "-4.0", f"Ctrl+R resets it to -4.0 ({text_of(pitch)!r})")
"""
b = """	g.key(VK_TAB, (VK_SHIFT,))
	check(g.focus() == pitch, "Shift+Tab goes back to it")
	g.type_into(pitch, "abc")
	check(text_of(pitch) == "abc", f"letters reach the field, so that what was typed is what it says ({text_of(pitch)!r})")
	g.key(VK_TAB)
	check(text_of(pitch) == "24.0", f"and leaving it puts the value back ({text_of(pitch)!r})")
	check("is not a number" in g.status() and "24.0" in g.status(), f"and the status says so: {g.status()!r}")
	g.key(ord("R"), (VK_CONTROL,))
	check(text_of(pitch) == "-4.0", f"Ctrl+R resets it to -4.0 ({text_of(pitch)!r})")
"""
if a not in s: sys.exit("MISSING test")
open(p, "w", encoding="utf-8", newline="\n").write(s.replace(a, b))
p = r"C:\GIT\speech synthesis\GnuspeechSA-NVDA\docs\09-open-items.md"
s = open(p, encoding="utf-8", newline="").read()
a = "GamaTTS's copy of the check types instead, and saves a WAV to prove silence before playing anything."
b = a + "\n\nTyping shows a real defect in the GUI as well: wxWidgets 3.3's `wxSpinCtrlDouble` holds a validator that swallows a key which would put the value out of range, with no message. Typing 99 into a field that stops at 24 leaves 9, and a screen reader has echoed both nines. GamaTTS's GUI removes the validator from the inner edit, after `SetDigits`, so the text says what was typed and the status says what became of it (`gui/gama_gui.cpp`, `addSpin`). The same applies to `gnuspeech_gui.cpp`."
if a not in s: sys.exit("MISSING gs")
open(p, "w", encoding="utf-8", newline="\n").write(s.replace(a, b))
print("ok")
