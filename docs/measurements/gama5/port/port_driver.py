"""One-time port of the Gnuspeech driver and its test. Every replacement must apply."""
import os
import re
import sys

GS = r"C:\GIT\speech synthesis\GnuspeechSA-NVDA"
OUT = r"C:\GIT\speech synthesis\gama_tts"


def apply(s, R):
	for a, b in R:
		if a not in s:
			sys.exit("MISSING:\n" + a)
		s = s.replace(a, b)
	return s


def read(path):
	return open(path, encoding="utf-8", newline="").read().replace("\r\n", "\n")


def write(path, s):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	open(path, "w", encoding="utf-8", newline="\n").write(s)


# ---- the driver
s = read(os.path.join(GS, "nvda-addon", "addon", "synthDrivers", "gnuspeech.py"))
s = re.sub(r"\bgs_", "gama_", s)
s = apply(s, [
("""# NVDA synthesizer driver for Gnuspeech, over gnuspeech_api.dll.
#
# Part of IveHeardOfWildebeest. Copyright 2026 dengopaiv.
# GPL-3.0-or-later, like the engine: Gnuspeech is by David R. Hill, Leonard
# Manzara and Craig Schock (1991-2002); GnuspeechSA, the C++ port inside the
# DLL, is by Marcelo Y. Matuda (2014-2015). See NOTICE.md in the add-on.
#
# The structure follows rsynth-nvda's driver (rsynth.py), which follows
# NVDA's own eSpeak and OneCore drivers.
\"\"\"NVDA driver for Gnuspeech, an articulatory text-to-speech system.

Everything that makes speech is inside gnuspeech_api.dll and its data folder:
the English text parser and dictionary, the Monet rules and the tube model.
""",
"""# NVDA synthesizer driver for GamaTTS, model 5, over gama_api.dll.
#
# Copyright 2026 dengopaiv. GPL-3.0-or-later, like the engine: Gnuspeech is by
# David R. Hill, Leonard Manzara and Craig Schock (1991-2002); GamaTTS, the engine
# inside the DLL with its model 5 tube, is by Marcelo Y. Matuda (2014-2025). See
# NOTICE.md in the add-on.
#
# Adapted from gnuspeech.py in GnuspeechSA-NVDA, whose structure follows rsynth-nvda's
# driver (rsynth.py), which follows NVDA's own eSpeak and OneCore drivers.
\"\"\"NVDA driver for GamaTTS, an articulatory text-to-speech system.

Everything that makes speech is inside gama_api.dll and its data folder: the English
text parser and dictionary, the rules and the 30-section tube, model 5.
"""),
("""  gnuspeech_api.dll (ctypes) -- gama_* in src/api/gnuspeech_api.h""", """  gama_api.dll (ctypes)      -- gama_* in api/gama_api.h"""),
('''_DLL = os.path.join(_DIR, "gnuspeech_api.dll")
_DATA = os.path.join(_DIR, "gnuspeech_data", "en")

#: The oldest GS_API_VERSION (gnuspeech_api.h) with everything this driver
#: uses: version 3 brought gama_set_leveling (docs/12) and GS_LEVEL_CONSTANT
#: (docs/13).
_API_VERSION = 3
_GS_OK = 0

#: Samples handed to the player at a time: 50 ms at 44.1 kHz. Cancel is
#: noticed between blocks.
_BLOCK = 2205
''',
'''_DLL = os.path.join(_DIR, "gama_api.dll")
_DATA = os.path.join(_DIR, "gamatts_data")

#: The oldest GAMA_API_VERSION (gama_api.h) with everything this driver uses.
_API_VERSION = 1
_GS_OK = 0

#: Handed to the player at a time: 50 ms. Cancel is noticed between blocks.
_BLOCKS_PER_SECOND = 20
'''),
("""	# Translators: a Gnuspeech voice.
	"male": _("Male"),
	# Translators: a Gnuspeech voice.
	"female": _("Female"),
	# Translators: a Gnuspeech voice.
	"large_child": _("Large child"),
	# Translators: a Gnuspeech voice.
	"small_child": _("Small child"),
	# Translators: a Gnuspeech voice.
	"baby": _("Baby"),""",
"""	# Translators: a GamaTTS voice.
	"male": _("Male"),
	# Translators: a GamaTTS voice.
	"female": _("Female"),
	# Translators: a GamaTTS voice.
	"large_child": _("Large child"),
	# Translators: a GamaTTS voice.
	"small_child": _("Small child"),
	# Translators: a GamaTTS voice.
	"baby": _("Baby"),"""),
("""#: The gain at NVDA volume 100, so that switching synthesizers keeps the level.
#: It matches the A-weighted level of eSpeak NG en+klatt5 at volume 100 (the
#: user's everyday voice): -20.8 dB against Gnuspeech's -19.9 at gain 1.0, over
#: the golden corpus (tools/measure/loudness.py, docs/08 "Loudness"). A first
#: calibration by BS.1770 loudness (0.54) sounded too quiet: Gnuspeech carries
#: far more energy below 500 Hz and less at 1-4 kHz than eSpeak, which LUFS
#: rewards and the ear does not.
_FULL_VOLUME_GAIN = 0.90
""",
"""#: The gain at NVDA volume 100 in the engine's own peak levelling, so that switching
#: synthesizers keeps the level. It matches the A-weighted level of eSpeak NG en+klatt5
#: at volume 100 (the author's everyday voice): -20.8 dB, against model 5 male's -20.3 at
#: gain 1.0 over the corpus (docs/10).
_FULL_VOLUME_GAIN = 0.94
"""),
("""#: With Loudness "steady throughout" or "even per message", every utterance
#: is levelled to this A-weighted level (dB, GS_LEVEL_CONSTANT or
#: GS_LEVEL_LOUDNESS), and volume 100 is gain 1.0: the calibration is in
#: the target. -22 dB is 1.1 dB below eSpeak NG en+klatt5 at volume 100 over
#: the golden corpus, and the peak limiter then touches 1.6 % of lines, by at
#: most 0.65 dB; at -21 the level would match klatt5 but 4.9 % would be
#: limited (tools/measure/level_target.py, docs/12). Steady throughout keeps
#: the same overall level (docs/13).
""",
"""#: With Loudness "steady throughout" or "even per message", every utterance is
#: levelled to this A-weighted level (dB), and volume 100 is gain 1.0: the calibration
#: is in the target. -22 dB is 1.2 dB below eSpeak NG en+klatt5 at volume 100, the value
#: the Gnuspeech add-on chose by ear. How often the peak limiter acts for model 5: docs/10.
"""),
("""	# Translators: a choice of the Gnuspeech Loudness setting: every syllable
""", """	# Translators: a choice of the GamaTTS Loudness setting: every syllable
"""),
("""	# Translators: a choice of the Gnuspeech Loudness setting: every message at
	# the same loudness, while inside a message stressed and open vowels are
	# louder, as Gnuspeech makes them.
""", """	# Translators: a choice of the GamaTTS Loudness setting: every message at
	# the same loudness, while inside a message stressed and open vowels are
	# louder, as the engine makes them.
"""),
("""	# Translators: a choice of the Gnuspeech Loudness setting: each message
	# scaled to its own peak, as Gnuspeech was made, so the loudness varies
	# from message to message and inside each.
	"peak": (_("Gnuspeech's own peaks"), _GS_LEVEL_PEAK),""",
"""	# Translators: a choice of the GamaTTS Loudness setting: each message
	# scaled to its own peak, as the engine was made, so the loudness varies
	# from message to message and inside each.
	"peak": (_("The engine's own peaks"), _GS_LEVEL_PEAK),"""),
("""	raise RuntimeError(f"Gnuspeech cannot open its data through a narrow path: {path}")""",
 """	raise RuntimeError(f"GamaTTS cannot open its data through a narrow path: {path}")"""),
('''	"""gnuspeech_api.dll with every signature declared.''', '''	"""gama_api.dll with every signature declared.'''),
('''f"gnuspeech_api.dll speaks API {lib.gama_api_version()}, driver wants {_API_VERSION} or later",''',
 '''f"gama_api.dll speaks API {lib.gama_api_version()}, driver wants {_API_VERSION} or later",'''),
("""	name = "gnuspeech"
	# Translators: the name of the Gnuspeech synthesizer in NVDA's list.
	description = _("Gnuspeech (articulatory)")""",
"""	name = "gamatts"
	# Translators: the name of the GamaTTS synthesizer in NVDA's list.
	description = _("GamaTTS (articulatory)")"""),
("""			# Translators: a Gnuspeech setting: random variation in the intonation
			# of each sentence, as Gnuspeech ships. Off, the same text always
			# sounds the same.""",
"""			# Translators: a GamaTTS setting: random variation in the intonation
			# of each sentence, as GamaTTS ships. Off, the same text always
			# sounds the same."""),
("""			# Translators: a Gnuspeech setting: how the loudness is kept, from
			# steady throughout to as Gnuspeech makes it.""",
"""			# Translators: a GamaTTS setting: how the loudness is kept, from
			# steady throughout to as the engine makes it."""),
("""			# Translators: a Gnuspeech setting: shorten the silence Gnuspeech leaves
			# before and after everything it says (about 0.4 s), so short
			# messages come quicker. Off, the pauses are as Gnuspeech makes them.""",
"""			# Translators: a GamaTTS setting: shorten the silence the engine leaves
			# before and after everything it says (about 0.3 s), so short
			# messages come quicker. Off, the pauses are as the engine makes them."""),
("""			and os.path.isfile(os.path.join(_DATA, "monet.xml"))""",
 """			and os.path.isfile(os.path.join(_DATA, "voice", "english", "5_male", "_index.txt"))"""),
('''raise RuntimeError("Gnuspeech: " + err.value.decode("utf-8", "replace"))''',
 '''raise RuntimeError("GamaTTS: " + err.value.decode("utf-8", "replace"))'''),
("""			f"Gnuspeech: API {self._lib.gama_api_version()}, voices""", """			f"GamaTTS: API {self._lib.gama_api_version()}, voices"""),
("""threading.Thread(target=self._speak_thread, name="gnuspeech", daemon=True)""", """threading.Thread(target=self._speak_thread, name="gamatts", daemon=True)"""),
("""				log.error("Gnuspeech speak thread", exc_info=True)""", """				log.error("GamaTTS speak thread", exc_info=True)"""),
("""			log.debug(f"Gnuspeech: nothing spoken for""", """			log.debug(f"GamaTTS: nothing spoken for"""),
("""		buf = (ctypes.c_int16 * _BLOCK)()
		while epoch == self._epoch:
			n = lib.gama_read(e, buf, _BLOCK)""",
"""		block = max(1, self._player.samplesPerSec // _BLOCKS_PER_SECOND)
		buf = (ctypes.c_int16 * block)()
		while epoch == self._epoch:
			n = lib.gama_read(e, buf, block)"""),
])
write(os.path.join(OUT, "nvda-addon", "addon", "synthDrivers", "gamatts.py"), s)
for word in ("nuspeech", "docs/1", "docs/0", "monet", "Monet", "44"):
	for m in re.finditer(word, s):
		line = s.count("\n", 0, m.start()) + 1
		print(f"driver left: {word} line {line}: {s.splitlines()[line - 1].strip()[:90]}")

# ---- its test
s = read(os.path.join(GS, "tests", "nvda", "test_driver.py"))
s = apply(s, [
('''"""Drive nvda-addon/addon/synthDrivers/gnuspeech.py without NVDA.

    python -I tests/nvda/test_driver.py <gnuspeech_api.dll> <data_dir> <golden.tsv>
    python -I tests/nvda/test_driver.py --addon <gnuspeech-x.y.z.nvda-addon> <golden.tsv>
''', '''"""Drive nvda-addon/addon/synthDrivers/gamatts.py without NVDA.

    python -I tests/nvda/test_driver.py <gama_api.dll> <data_dir> <golden.tsv>
    python -I tests/nvda/test_driver.py --addon <gamatts-x.y.z.nvda-addon> <golden.tsv>
'''),
('''Adapted from rsynth-nvda's tests/test_driver.py.
Part of IveHeardOfWildebeest. Copyright 2026 dengopaiv. GPL-3.0-or-later.''',
'''Adapted from GnuspeechSA-NVDA's tests/nvda/test_driver.py, itself from rsynth-nvda's
tests/test_driver.py. Copyright 2026 dengopaiv. GPL-3.0-or-later.'''),
('''DRIVER = os.path.join(ROOT, "nvda-addon", "addon", "synthDrivers", "gnuspeech.py")
BLOCK_BYTES = 2205 * 2''', '''DRIVER = os.path.join(ROOT, "nvda-addon", "addon", "synthDrivers", "gamatts.py")
RATE = 48000
PER_MS = RATE / 1000
BLOCK_BYTES = RATE // 20 * 2'''),
('''	"""The add-on's synthDrivers folder: driver, DLL, gnuspeech_data/en."""
	os.makedirs(dest)
	shutil.copy2(driver, os.path.join(dest, "gnuspeech.py"))
	shutil.copy2(dll, os.path.join(dest, "gnuspeech_api.dll"))
	shutil.copytree(data, os.path.join(dest, "gnuspeech_data", "en"))''',
'''	"""The add-on's synthDrivers folder: driver, DLL, gamatts_data."""
	os.makedirs(dest)
	shutil.copy2(driver, os.path.join(dest, "gamatts.py"))
	shutil.copy2(dll, os.path.join(dest, "gama_api.dll"))
	shutil.copytree(data, os.path.join(dest, "gamatts_data"))'''),
('''os.path.join(folder, "gnuspeech.py"))
	mod = ''' if False else '''spec_from_file_location(name, os.path.join(folder, "gnuspeech.py"))''', '''spec_from_file_location(name, os.path.join(folder, "gamatts.py"))'''),
('''			parts = line.rstrip("\\r\\n").split("\\t")
			if len(parts) == 7 and parts[6] == "Hello world.":
				return parts[1], int(parts[4])''',
'''			parts = line.rstrip("\\r\\n").split("\\t")
			if len(parts) == 9 and parts[0] == "5_male" and parts[1] == "1.0" and parts[8] == "Hello world.":
				return parts[3], int(parts[6])'''),
('''tempfile.mkdtemp(prefix="gs-driver-")''', '''tempfile.mkdtemp(prefix="gama-driver-")'''),
('''			dll = os.path.join(folder, "gnuspeech_api.dll")
			data = os.path.join(folder, "gnuspeech_data", "en")''',
'''			dll = os.path.join(folder, "gama_api.dll")
			data = os.path.join(folder, "gamatts_data")'''),
('''drv = load_driver(folder, "gnuspeech_driver")''', '''drv = load_driver(folder, "gamatts_driver")'''),
('''check(lead is not None and lead <= 441 + 2,''', '''check(lead is not None and lead <= 10 * PER_MS + 2,'''),
('''trail_ms * 44.1 - 3 <= trail <= trail_ms * 44.1 + 441,''', '''trail_ms * PER_MS - 3 <= trail <= trail_ms * PER_MS + 10 * PER_MS,'''),
('''f"trim {text!r}: {trail} samples after the sound, want {trail_ms * 44.1:.0f} (+10 ms)")''',
 '''f"trim {text!r}: {trail} samples after the sound, want {trail_ms * PER_MS:.0f} (+10 ms)")'''),
('''f"({(len(untrimmed[text]) - len(got)) / 2 / 44.1:.0f} ms saved)")''', '''f"({(len(untrimmed[text]) - len(got)) / 2 / PER_MS:.0f} ms saved)")'''),
('''first[: len(first) - int(150 * 44.1) * 2]''', '''first[: len(first) - int(150 * PER_MS) * 2]'''),
('''check(len(audio(evs)) < 44100 * 2 * 60, "cancel did not stop the feeding")''', '''check(len(audio(evs)) < RATE * 2 * 60, "cancel did not stop the feeding")'''),
('''check(ok and len(audio(evs)) > 44100 * 2 * 0.5, "break shorter than 500 ms")''', '''check(ok and len(audio(evs)) > RATE * 2 * 0.5, "break shorter than 500 ms")'''),
('''		for text in ("日本語 \\U0001f600 café [x] 12345678901234567890 \\x00\\x07",
				"*", "...", "", "   ", "\\u201cQuoted\\u201d \\u2014 and\\u2026 C:\\\\Users\\\\Inbox"):''',
'''		# The long ones killed the process before the API's guard (docs/09, docs/10).
		for text in ("日本語 \\U0001f600 café [x] 12345678901234567890 \\x00\\x07",
				"*", "...", "", "   ", "\\u201cQuoted\\u201d \\u2014 and\\u2026 C:\\\\Users\\\\Inbox",
				"w" * 3000, "<" * 3000, "1" * 3000, "deadbeef" * 400, "aGVsbG8gd29ybGQ" * 300):'''),
('''os.path.join(folder, "gnuspeech.py"))
		try:
			os.path.abspath(odd)''', '''os.path.join(folder, "gamatts.py"))
		try:
			os.path.abspath(odd)'''),
('''drv2 = load_driver(odd, "gnuspeech_driver_odd")''', '''drv2 = load_driver(odd, "gamatts_driver_odd")'''),
])
s = s.replace('''lay_out(odd, dll, data, os.path.join(folder, "gamatts.py"))''', '''lay_out(odd, dll, data, os.path.join(folder, "gamatts.py"))''')
write(os.path.join(OUT, "tests", "nvda", "test_driver.py"), s)
for word in ("nuspeech", "44100", "44\\.1", "441", "docs/0"):
	for m in re.finditer(word, s):
		line = s.count("\n", 0, m.start()) + 1
		print(f"test left: {word} line {line}: {s.splitlines()[line - 1].strip()[:90]}")
print("done")
