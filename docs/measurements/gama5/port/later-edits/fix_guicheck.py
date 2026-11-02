"""Type into number fields with real keys, and prove volume 0. Every replacement must apply."""
import sys

p = r"C:\GIT\speech synthesis\gama_tts\tests\gui\gui_check.py"
s = open(p, encoding="utf-8", newline="").read()
R = [
('''	def by_name(self, name):''',
'''	def type_into(self, h, text):
		"""Replace a field's text with real keystrokes. WM_SETTEXT will not do for a number:
		it clears the edit's modified flag, so wxSpinCtrlDouble then shows the text, but
		never commits it, and the value never reaches the engine."""
		user32.SendMessageW(h, EM_SETSEL, 0, -1)
		for ch in text:
			user32.PostMessageW(h, WM_CHAR, ord(ch), 1)
		self.settle()

	def by_name(self, name):'''),
('''def read_wav(path):''', '''EM_SETSEL, WM_CHAR = 0x00B1, 0x0102


def read_wav(path):'''),
('''	set_text(pitch, "99")
	g.settle()
	g.key(VK_TAB)''', '''	g.type_into(pitch, "99")
	g.key(VK_TAB)'''),
('''	set_text(tn_min, "30")
	g.settle()
	g.key(VK_TAB)
	g.settle()''', '''	g.type_into(tn_min, "30")
	g.key(VK_TAB)
	g.settle()'''),
('''	check("refused" in g.status() and "may not pass" in g.status(),
		  f"and the status says why, not the next field's help: {g.status()!r}")
''', '''	check("refused" in g.status() and "may not pass" in g.status(),
		  f"and the status says why, not the next field's help: {g.status()!r}")
	g.key(VK_TAB, (VK_SHIFT,))
	g.type_into(tn_min, "20")
	g.key(VK_TAB)
	check(text_of(tn_min) == "20.0", f"20 is allowed ({text_of(tn_min)!r})")
	typed_preset = os.path.join(tmp, "typed.gamapreset")
	g.key(ord("S"), (VK_CONTROL, VK_SHIFT))
	check(g.file_dialog(typed_preset) and wait_for(lambda: os.path.exists(typed_preset)), "saving a preset after typing a value")
	with open(typed_preset, encoding="utf-8") as f:
		check("glottal_pulse_tn_min = 20\\n" in f.read(), "and the typed value reached the engine, as 20")
	g.key(ord("R"), (VK_CONTROL,))
'''),
('''	set_text(volume, "0")
	g.key(VK_TAB)
	check(text_of(volume) == "0", f"volume 0 ({text_of(volume)!r})")
	g.key(ord("A"), (VK_MENU,))
	g.key(VK_UP)
	set_text(text_box, "Test.")
''', '''	g.type_into(volume, "0")
	g.key(VK_TAB)
	check(text_of(volume) == "0", f"volume 0 ({text_of(volume)!r})")
	g.key(ord("A"), (VK_MENU,))
	g.key(VK_UP)
	set_text(text_box, "Test.")
	# Before anything plays through the speakers, prove that it is silent.
	silent = os.path.join(tmp, "silent.wav")
	g.key(ord("S"), (VK_CONTROL,))
	check(g.file_dialog(silent) and wait_for(lambda: os.path.exists(silent), timeout=20), "saving at volume 0")
	silent_frames = read_wav(silent)[3]
	if not check(len(silent_frames) > 0 and not any(silent_frames), "and that WAV is silent, so the speakers will be"):
		sys.exit("volume 0 did not take effect, so nothing more is played")
'''),
('''	# Before anything plays''', '''	# The speech below goes to the real output device: wxSound does not know about the
	# private desktop.
	# Before anything plays'''),
]
for a, b in R:
	if a not in s:
		sys.exit("MISSING:\n" + a)
	s = s.replace(a, b)
open(p, "w", encoding="utf-8", newline="\n").write(s)

p = r"C:\GIT\speech synthesis\gama_tts\gui\gama_gui.cpp"
s = open(p, encoding="utf-8", newline="").read()
a = """    for (int precision = 1; precision <= 17; ++precision) {"""
b = """    // From 6: at 1, "%.*g" writes 20 as 2e+01, which reads back but is no way to write it.
    for (int precision = 6; precision <= 17; ++precision) {"""
if a not in s:
    sys.exit("gui missing")
s = s.replace(a, b)
for a, b in (
    ("// Trimming: the values the NVDA driver keeps after a sentence (docs/08).", "// Trimming: the values the NVDA driver keeps after a sentence."),
    ("// The Loudness choices (docs/12, 13), in the order shown", "// The Loudness choices (docs/10), in the order shown"),
    ("// form, as the NVDA driver does (docs/08).", "// form, as the NVDA driver does."),
    ("// Levelling (docs/12, 13): steady throughout by default", "// Levelling (docs/10): steady throughout by default"),
):
    if a not in s:
        sys.exit("gui missing " + a)
    s = s.replace(a, b)
open(p, "w", encoding="utf-8", newline="\n").write(s)

p = r"C:\GIT\speech synthesis\gama_tts\nvda-addon\addon\synthDrivers\gamatts.py"
s = open(p, encoding="utf-8", newline="").read()
for a, b in (
    ("#: levelling mode for each (docs/12, 13).", "#: levelling mode for each (docs/10)."),
    ('#: 100-230 ms there, which is only delay (docs/08, "Trimming").', "#: about 120 ms there, which is only delay."),
):
    if a not in s:
        sys.exit("driver missing " + a)
    s = s.replace(a, b)
open(p, "w", encoding="utf-8", newline="\n").write(s)
p = r"C:\GIT\speech synthesis\GnuspeechSA-NVDA\docs\09-open-items.md"
s = open(p, encoding="utf-8", newline="").read()
a = "- **Where it is written down:** GamaTTS's `docs/09`, section 3, and `docs/measurements/feasibility/`. Scripts: `longtokens.py`, `guard_check.py`."
if a not in s:
    sys.exit("gs item missing")
b = """- **Corrected the same day.** The fix above is not enough: on GamaTTS's parser, a run of 100 `w` still kills the process, since a word the parser cannot pronounce is spelled into a buffer of 1,027 bytes, and `w` spells to 17 bytes and `<` to 43. GamaTTS's API therefore breaks a run after 45 letters or digits, or 20 other characters, and that came through clean (GamaTTS's `docs/10`). A guard here should do the same. So should a split of long text, since a long spelled token also holds the speak thread for many seconds where cancel cannot reach it.
- **Where it is written down:** GamaTTS's `docs/09`, section 3, and `docs/10`, and `docs/measurements/feasibility/`. Scripts: `longtokens.py`, `guard_check.py`.

### 15. `tests/gui/gui_check.py` sets number fields in a way that does not reach the engine

Found 2026-11-02 while porting it to GamaTTS. `set_text` uses `WM_SETTEXT`, which clears the edit's modified flag, so `wxSpinCtrlDouble` reformats the text when the focus leaves, but sends no event, and the engine keeps its old value. So the check's "volume 0" does not set volume 0, and its "Speaking" step plays through the speakers at full volume, and "99 becomes 24.0" tests only the text. The GUI itself is right: with real keystrokes (`WM_CHAR`), values reach the engine and out-of-range values are corrected. GamaTTS's copy of the check types instead, and saves a WAV to prove silence before playing anything."""
open(p, "w", encoding="utf-8", newline="\n").write(s.replace(a, b))
print("done")
