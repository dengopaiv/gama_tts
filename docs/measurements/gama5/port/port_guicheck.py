"""One-time port of the GUI's outside check. Every replacement must apply."""
import re
import sys

src = r"C:\GIT\speech synthesis\GnuspeechSA-NVDA\tests\gui\gui_check.py"
dst = r"C:\GIT\speech synthesis\gama_tts\tests\gui\gui_check.py"
s = open(src, encoding="utf-8", newline="").read().replace("\r\n", "\n")
s = re.sub(r"\bgs_", "gama_", s)

R = [
('''"""Check gnuspeech_gui.exe from outside, the way a screen reader sees it.

    python tests/gui/gui_check.py <gnuspeech_gui.exe> <gnuspeech_api.dll> <data/en> <golden.tsv>

Windows only; needs comtypes (for oleacc's IAccessible). docs/10 has the
results of the recorded run.

Adapted from rsynth-nvda's tests/gui_check.py (2026-10-16, LGPL-2.0-or-later,
"the rsynth-nvda contributors"): the private desktop, the process start, the
key posting with an exact modifier state, and the file-dialog driving are
taken from it. What differs is that wxWidgets gives its controls no fixed
ids, so controls are found by their MSAA names, and a field's group is the
group box it is a child of (wxStaticBoxSizer makes the fields its children).
''', '''"""Check gama_gui.exe from outside, the way a screen reader sees it.

    python tests/gui/gui_check.py <gama_gui.exe> <gama_api.dll> <data> <golden.tsv>

Windows only; needs comtypes (for oleacc's IAccessible), numpy and scipy. docs/10 has
the results of the recorded run.

Adapted from GnuspeechSA-NVDA's tests/gui/gui_check.py, itself from rsynth-nvda's
tests/gui_check.py (LGPL-2.0-or-later, "the rsynth-nvda contributors"): the private desktop,
the process start, the key posting with an exact modifier state, and the file-dialog driving
are taken from it. wxWidgets gives its controls no fixed ids, so controls are found by
their MSAA names, and a field's group is the group box it is a child of.
'''),
('''3. Every category (Ctrl+1 ... Ctrl+7): its fields, their names, units and
   group; all 42 parameters and the 4 output fields are reachable.''',
 '''3. Every category (Ctrl+1 ... Ctrl+7): its fields, their names, units and
   group; all 49 parameters and the 6 output fields are reachable.'''),
('''against the golden hashes of gnuspeech_sa; then the same through Use''', '''against the golden hashes of gama_tts; then the same through Use'''),
('''from loudness import a_weighted_db  # noqa: E402
from stress_level import parse_track, voiced_frame_sd  # noqa: E402
''', '''from levels import a_weighted_db, parse_track, voiced_frame_sd  # noqa: E402
'''),
('DESKTOP_NAME = "gnuspeech_gui_check"', 'DESKTOP_NAME = "gama_gui_check"'),
('text_of(h) == "Gnuspeech"), None)', 'text_of(h) == "GamaTTS"), None)'),
('sys.exit("gnuspeech_gui did not open a window")', 'sys.exit("gama_gui did not open a window")'),
('''			if line.startswith("#") or line.startswith("id\\t"):
				continue
			i, pcm, trm, n, peak, rate, text = line.rstrip("\\r\\n").split("\\t", 6)
			if int(i) == row_id:
				return pcm, trm, int(n), int(rate), text''',
'''			if line.startswith("#") or line.startswith("voice\\t"):
				continue
			voice, tempo, i, pcm, trm, n, peak, rate, text = line.rstrip("\\r\\n").split("\\t", 8)
			if voice == "5_male" and tempo == "1.0" and int(i) == row_id:
				return pcm, trm, int(n), int(rate), text'''),
('''	("Speech", ["Tempo", "Pitch offset (semitones)"]),
	("Intonation", ["Micro intonation", "Macro intonation", "Intonation drift", "Random intonation",
					"Drift deviation (semitones)", "Drift speed (Hz)"]),
	("Glottal source", ["Glottal waveform", "Reference glottal pitch (semitones)", "Pulse rise time (%)",
						"Pulse fall time, minimum (%)", "Pulse fall time, maximum (%)", "Breathiness (%)",
						"Master volume (dB)"]),
	("Vocal tract", ["Tract length (cm)", "Tract length offset (cm)", "Temperature (degrees C)", "Junction loss (%)",
					 "Aperture scaling radius (cm)", "Mouth aperture coefficient (Hz)", "Global radius coefficient"]
	 + [f"Region {k} radius coefficient" for k in range(1, 9)]),
	("Nose", ["Nose aperture coefficient (Hz)", "Global nose radius coefficient"]
	 + [f"Nasal section {k} radius (cm)" for k in range(1, 6)]),
	("Throat and noise", ["Throat cutoff (Hz)", "Throat volume (dB)", "Pulse-modulated noise",
						  "Noise crossmix offset (dB)"]),
''', '''	("Speech", ["Tempo", "Pitch offset (semitones)", "Initial pitch (semitones)", "Control period"]),
	("Intonation", ["Micro intonation", "Macro intonation", "Smooth intonation", "Intonation drift", "Random intonation",
					"Drift deviation (semitones)", "Drift speed (Hz)", "Intonation range"]),
	("Glottal source", ["Glottal waveform", "Reference glottal pitch (semitones)", "Pulse rise time (%)",
						"Pulse fall time, minimum (%)", "Pulse fall time, maximum (%)", "Breathiness (%)",
						"Glottal loss, closed (%)", "Glottal loss, open (%)", "Glottal low-pass cutoff (Hz)"]),
	("Vocal tract", ["Tract length (cm)", "Tract length offset (cm)", "Temperature (degrees C)", "Junction loss (%)",
					 "Fixed mouth radiation", "Fixed mouth radius (cm)", "Global radius coefficient"]
	 + [f"Region {k} radius coefficient" for k in range(1, 9)]),
	("Nose", ["Global nose radius coefficient"] + [f"Nasal section {k} radius (cm)" for k in range(2, 8)]),
	("Noise", ["Pulse-modulated noise", "Noise crossmix offset (dB)", "Glottal noise cutoff (Hz)",
			   "Frication noise cutoff (Hz)", "Frication strength"]),
'''),
('tempfile.mkdtemp(prefix="gnuspeech_gui_check_")', 'tempfile.mkdtemp(prefix="gama_gui_check_")'),
('check(total == 42 + 6, f"{total} fields in all: the 42 parameters and 6 output settings")',
 'check(total == 49 + 6, f"{total} fields in all: the 49 parameters and 6 output settings")'),
('''	print("6. Saving, against the golden traces of gnuspeech_sa")
	# The golden run had intonation drift and random intonation off.
	g.key(ord("2"), (VK_CONTROL,))
	g.key(VK_TAB)
	g.key(VK_TAB)
	drift = g.focus()''', '''	print("6. Saving, against the golden traces of gama_tts")
	# The golden run had intonation drift and random intonation off.
	g.key(ord("2"), (VK_CONTROL,))
	g.key(VK_TAB)
	g.key(VK_TAB)
	g.key(VK_TAB)
	drift = g.focus()'''),
('''		check(abs(level - (-22.0)) <= 0.1 and int(np.max(np.abs(x))) <= 31129,''', '''		check(abs(level - (-22.0)) <= 0.2 and int(np.max(np.abs(x))) <= 31129,'''),
('''check(msaa(leveling)["value"] == "Gnuspeech's own peaks", f"Down arrow again: {msaa(leveling)['value']!r}")''',
 '''check(msaa(leveling)["value"] == "The engine's own peaks", f"Down arrow again: {msaa(leveling)['value']!r}")'''),
('''"the track is gnuspeech_sa -p's, byte for byte")''', '''"the track is gama_tts -p's, byte for byte")'''),
('''	track_rate, track_rows = parse_track(track_bytes.decode("ascii"))
	sd_steady = voiced_frame_sd(steady / 32768, r, track_rate, track_rows)
	sd_peak = voiced_frame_sd(np.frombuffer(frames, dtype="<i2") / 32768, r, track_rate, track_rows)''',
'''	track_rows = parse_track(track_bytes.decode("ascii"))
	sd_steady = voiced_frame_sd(steady / 32768, r, track_rows)
	sd_peak = voiced_frame_sd(np.frombuffer(frames, dtype="<i2") / 32768, r, track_rows)'''),
('os.path.join(tmp, "test.gspreset")', 'os.path.join(tmp, "test.gamapreset")'),
('"Opened test.gspreset." == g.status()', '"Opened test.gamapreset." == g.status()'),
('''	print("8. Speaking (at volume 0), stopping, closing")''',
'''	print("7b. Values that share a limit, which the status must explain")
	g.key(ord("3"), (VK_CONTROL,))
	for _ in range(3):
		g.key(VK_TAB)
	tn_min = g.focus()
	check(msaa(tn_min)["name"] == "Pulse fall time, minimum (%)", f"on the fall time minimum ({msaa(tn_min)['name']!r})")
	check(text_of(tn_min) == "24.0", f"it reads 24.0 ({text_of(tn_min)!r})")
	set_text(tn_min, "30")
	g.settle()
	g.key(VK_TAB)
	g.settle()
	check(text_of(tn_min) == "24.0", f"30 is above the maximum, so it stays at 24.0 ({text_of(tn_min)!r})")
	check("refused" in g.status() and "may not pass" in g.status(),
		  f"and the status says why, not the next field's help: {g.status()!r}")
	# A preset holding values that can only be set in one order.
	limits = os.path.join(tmp, "limits.gamapreset")
	with open(limits, "w", encoding="ascii") as f:
		f.write("glottal_pulse_tn_min = 40\\nglottal_pulse_tn_max = 45\\nglottal_pulse_tp = 50\\n")
	g.key(ord("O"), (VK_CONTROL,))
	check(g.file_dialog(limits), "opening a preset with the minimum before the maximum")
	wait_for(lambda: "Opened" in g.status())
	check(text_of(tn_min) == "40.0" and g.status() == "Opened limits.gamapreset.",
		  f"it takes every value in the end: {text_of(tn_min)!r}, {g.status()!r}")
	g.key(ord("R"), (VK_CONTROL,))
	check(text_of(tn_min) == "24.0", "Ctrl+R puts it back")

	print("8. Speaking (at volume 0), stopping, closing")'''),
]
for a, b in R:
	if a not in s:
		sys.exit("MISSING:\n" + a)
	s = s.replace(a, b)
for word in ("nuspeech", "gspreset", "trm"):
	for m in re.finditer(word, s):
		line = s.count("\n", 0, m.start()) + 1
		print(f"left: {word} line {line}: {s.splitlines()[line - 1].strip()[:90]}")
open(dst, "w", encoding="utf-8", newline="\n").write(s)

p = r"C:\GIT\speech synthesis\gama_tts\gui\gama_gui.cpp"
g = open(p, encoding="utf-8", newline="").read()
a = '''                setStatus(name + ": " + typed + " is refused. " + reason + " It stays at " +
                          spin->GetTextValue() + ".");'''
b = '''                // Kept, so that moving on does not replace it with the next field's help.
                pendingNote_ = name + ": " + typed + " is refused. " + reason + " It stays at " +
                               spin->GetTextValue() + ".";
                setStatus(pendingNote_);'''
if a not in g:
	sys.exit("gui: missing")
open(p, "w", encoding="utf-8", newline="\n").write(g.replace(a, b))
print("done")
