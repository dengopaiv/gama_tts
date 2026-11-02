"""Drive nvda-addon/addon/synthDrivers/gamatts.py without NVDA.

    python -I tests/nvda/test_driver.py <gama_api.dll> <data_dir> <golden.tsv>
    python -I tests/nvda/test_driver.py --addon <gamatts-x.y.z.nvda-addon> <golden.tsv>

The second form runs the same tests on the driver, DLL and data exactly as
packaged, unzipped into a temporary folder: it proves the package is whole.

The NVDA modules the driver imports are replaced by small stand-ins that
record what the driver does: the audio it feeds, the index marks it reports,
when it says it is done. The driver and the DLL are the real ones, copied with
the engine's data into a temporary folder laid out as in the add-on.

This proves the driver's own logic (queueing, index marks, cancel, settings,
spelling, text folding) and that its ctypes declarations match the DLL. It
does not prove the driver inside NVDA: NVDA's real player, speech manager and
settings dialogs are only reachable from NVDA itself.

Adapted from GnuspeechSA-NVDA's tests/nvda/test_driver.py, itself from rsynth-nvda's
tests/test_driver.py. Copyright 2026 dengopaiv. GPL-3.0-or-later.
"""

import array
import builtins
import ctypes
import hashlib
import importlib.util
import os
import shutil
import sys
import tempfile
import threading
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DRIVER = os.path.join(ROOT, "nvda-addon", "addon", "synthDrivers", "gamatts.py")
RATE = 48000
PER_MS = RATE / 1000
BLOCK_BYTES = RATE // 20 * 2

# --- stand-ins for NVDA ---------------------------------------------------

builtins._ = lambda s: s
events = []          # (kind, value, time) in the order they happened
events_lock = threading.Lock()


def record(kind, value=None):
	with events_lock:
		events.append((kind, value, time.perf_counter()))


def module(name, **attrs):
	m = types.ModuleType(name)
	m.__dict__.update(attrs)
	sys.modules[name] = m
	return m


class WavePlayer:
	instances = []

	def __init__(self, channels, samplesPerSec, bitsPerSample, outputDevice=""):
		assert channels == 1 and bitsPerSample == 16
		self.samplesPerSec = samplesPerSec
		self.pending = []        # onDone callbacks not yet "played"
		self.closed = False
		WavePlayer.instances.append(self)

	def feed(self, data, size=None, onDone=None):
		data = bytes(data)
		record("audio", data)
		time.sleep(0.0005)       # playback a little behind, as the real player is
		if onDone:
			record("mark")
			self.pending.append(onDone)

	def idle(self):
		for cb in self.pending:
			cb()
		self.pending.clear()
		record("idle")

	def stop(self):
		self.pending.clear()
		record("stop")

	def pause(self, switch):
		record("pause", switch)

	def close(self):
		self.closed = True


class Notifier:
	def __init__(self, kind):
		self.kind = kind

	def notify(self, synth=None, index=None):
		record(self.kind, index)


class _Prosody:
	def __init__(self, offset=0, multiplier=1):
		self.offset, self.multiplier = offset, multiplier

	@property
	def newValue(self):
		return int(50 * self.multiplier) + self.offset


class SynthDriverBase:
	# NVDA's AutoPropertyObject turns synth.rate = x into _set_rate(x); the
	# stand-in does not, so the tests call the accessors directly.
	@classmethod
	def VoiceSetting(cls):
		return "voice"

	RateSetting = PitchSetting = VolumeSetting = VoiceSetting

	def __init__(self):
		pass

	def terminate(self):
		record("saved")


class VoiceInfo:
	def __init__(self, id, displayName, language=None):
		self.id, self.displayName, self.language = id, displayName, language


class StringParameterInfo:
	def __init__(self, id, displayName):
		self.id, self.displayName = id, displayName


class Log:
	def info(self, msg, *a, **k):
		print("log:", msg)

	def error(self, msg, *a, **k):
		record("error", msg)
		import traceback

		traceback.print_exc()

	def debug(self, msg, *a, **k):
		pass

	debugWarning = info


def install_stand_ins():
	module("addonHandler", initTranslation=lambda: None)
	module("config", conf={"audio": {"outputDevice": "default"}})
	module("nvwave", WavePlayer=WavePlayer)
	module("logHandler", log=Log())
	module("autoSettingsUtils")
	module(
		"autoSettingsUtils.driverSetting",
		BooleanDriverSetting=lambda id, name, defaultVal=False: ("bool", id),
		DriverSetting=lambda id, name, defaultVal=None: ("string", id, defaultVal),
	)
	module("autoSettingsUtils.utils", StringParameterInfo=StringParameterInfo)
	module("speech")
	module(
		"speech.commands",
		IndexCommand=type("IndexCommand", (), {"__init__": lambda s, i: setattr(s, "index", i)}),
		CharacterModeCommand=type(
			"CharacterModeCommand", (), {"__init__": lambda s, st: setattr(s, "state", st)},
		),
		BreakCommand=type("BreakCommand", (), {"__init__": lambda s, t: setattr(s, "time", t)}),
		PitchCommand=type("PitchCommand", (_Prosody,), {}),
	)
	module(
		"synthDriverHandler",
		SynthDriver=SynthDriverBase,
		VoiceInfo=VoiceInfo,
		synthIndexReached=Notifier("index"),
		synthDoneSpeaking=Notifier("done"),
	)


def lay_out(dest, dll, data, driver=DRIVER):
	"""The add-on's synthDrivers folder: driver, DLL, gamatts_data."""
	os.makedirs(dest)
	shutil.copy2(driver, os.path.join(dest, "gamatts.py"))
	shutil.copy2(dll, os.path.join(dest, "gama_api.dll"))
	shutil.copytree(data, os.path.join(dest, "gamatts_data"))


def load_driver(folder, name):
	spec = importlib.util.spec_from_file_location(name, os.path.join(folder, "gamatts.py"))
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod


# --- helpers ---------------------------------------------------------------

failures = 0


def check(cond, msg):
	global failures
	if not cond:
		failures += 1
		print("FAIL:", msg)
	return cond


def wait_for(kind, timeout=30.0):
	end = time.time() + timeout
	while time.time() < end:
		with events_lock:
			if any(k == kind for k, _, _ in events):
				return True
		time.sleep(0.01)
	return False


def take():
	with events_lock:
		out = list(events)
		events.clear()
	return out


def audio(evs):
	return b"".join(v for k, v, _ in evs if k == "audio")


def peak(data):
	samples = array.array("h")
	samples.frombytes(data)
	return max((abs(s) for s in samples), default=0)


def say(synth, seq):
	synth.speak(seq)
	ok = wait_for("done")
	return ok, take()


def golden_hello(path):
	with open(path, encoding="ascii") as f:
		for line in f:
			parts = line.rstrip("\r\n").split("\t")
			if len(parts) == 9 and parts[0] == "5_male" and parts[1] == "1.0" and parts[8] == "Hello world.":
				return parts[3], int(parts[6])
	sys.exit("no 'Hello world.' line in the golden file")


# --- tests ---------------------------------------------------------------

def main():
	addon = None
	if len(sys.argv) == 4 and sys.argv[1] == "--addon":
		addon, golden = os.path.abspath(sys.argv[2]), os.path.abspath(sys.argv[3])
		dll = data = None
	elif len(sys.argv) == 4:
		dll, data, golden = (os.path.abspath(a) for a in sys.argv[1:4])
	else:
		sys.exit(__doc__)
	hello_sha, hello_peak = golden_hello(golden)
	install_stand_ins()
	from speech.commands import BreakCommand, CharacterModeCommand, IndexCommand, PitchCommand

	tmp = tempfile.mkdtemp(prefix="gama-driver-")
	try:
		folder = os.path.join(tmp, "synthDrivers")
		if addon:
			import zipfile

			with zipfile.ZipFile(addon) as z:
				z.extractall(tmp)
			print(f"info: testing the package {os.path.basename(addon)}")
			# For test 10 below, which lays the add-on out again elsewhere.
			dll = os.path.join(folder, "gama_api.dll")
			data = os.path.join(folder, "gamatts_data")
		else:
			lay_out(folder, dll, data)
		drv = load_driver(folder, "gamatts_driver")
		check(drv.SynthDriver.check(), "check() is false with the DLL and data in place")
		synth = drv.SynthDriver()

		# 0. Voices, in upstream's order, with names.
		voices = synth._getAvailableVoices()
		check(list(voices) == ["male", "female", "large_child", "small_child", "baby"], f"voices {list(voices)}")
		check(voices["large_child"].displayName == "Large child", "voice display name")
		check(synth._get_voice() == "male", "starting voice")

		# 1. The golden trace, end to end through the driver: intonation not
		#    varied, silence not trimmed, everything else at its default.
		# The level calibration (a gain below 1 at volume 100) is set aside
		# for this check and the trimming checks; it is the only thing between
		# the driver and the engine's own output.
		check(synth._get_trimSilence() is True, "trimming should be on by default")
		check(synth._get_leveling() == "constant", f"loudness should be steady throughout by default, is {synth._get_leveling()}")
		levelings = synth._get_availableLevelings()
		check(list(levelings) == ["constant", "message", "peak"], f"loudness choices {list(levelings)}")
		check(all(v.id == k and v.displayName for k, v in levelings.items()), "loudness choices without names")
		check(("string", "leveling", "constant") in drv.SynthDriver.supportedSettings, "no Loudness setting")
		# The golden trace and the level checks below are in peak mode, the
		# engine's own; section 5b checks the other two.
		synth._set_leveling("peak")
		calibration = drv._FULL_VOLUME_GAIN
		check(0 < calibration <= 1, f"full-volume gain {calibration} out of range")
		drv._FULL_VOLUME_GAIN = 1.0
		synth._set_varyIntonation(False)
		synth._set_trimSilence(False)
		synth._set_volume(100)
		ok, evs = say(synth, ["Hello world."])
		check(ok, "golden: never reported done")
		pcm = audio(evs)
		check(hashlib.sha256(pcm).hexdigest() == hello_sha,
			f"driver output differs from the golden trace ({len(pcm) // 2} samples, peak {peak(pcm)})")

		# 1b. Trimming: only the outer edges of a message, by its last character.
		def edges(data):
			a = array.array("h")
			a.frombytes(data)
			loud = [i for i, v in enumerate(a) if abs(v) >= 33]
			return (loud[0], len(a) - 1 - loud[-1]) if loud else (None, None)

		untrimmed = {}
		for text in ("8", "Button,", "Hello world.", "Hello world. Goodbye world."):
			untrimmed[text] = audio(say(synth, [text])[1])
		synth._set_trimSilence(True)
		for text, trail_ms in (("8", 30), ("Button,", 100), ("Hello world.", 150), ("Hello world. Goodbye world.", 150)):
			got = audio(say(synth, [text])[1])
			lead, trail = edges(got)
			check(lead is not None and lead <= 10 * PER_MS + 2, f"trim {text!r}: {lead} samples of silence before the sound")
			# The API decides on the engine's float output at -60 dBFS (32.8 in 16
			# bits); this counts whole 16-bit samples above 33, so a faint tail
			# right at the threshold can read a few ms longer here.
			check(trail is not None and trail_ms * PER_MS - 3 <= trail <= trail_ms * PER_MS + 10 * PER_MS,
				f"trim {text!r}: {trail} samples after the sound, want {trail_ms * PER_MS:.0f} (+10 ms)")
			check(got in untrimmed[text], f"trim {text!r}: the kept audio is not a slice of the untrimmed audio")
			print(f"info: trimmed {text!r}: {len(untrimmed[text]) // 2} -> {len(got) // 2} samples "
				f"({(len(untrimmed[text]) - len(got)) / 2 / PER_MS:.0f} ms saved)")
		# Two sentences in one message: the pause between them is the engine's own.
		whole = audio(say(synth, ["Hello world. Goodbye world."])[1])
		first = audio(say(synth, ["Hello world."])[1])
		check(whole.startswith(first[: len(first) - int(150 * PER_MS) * 2]),
			"the first sentence of a two-sentence message was trimmed at its end")
		synth._set_trimSilence(False)
		check(audio(say(synth, ["8"])[1]) == untrimmed["8"], "trimming off does not give the untrimmed audio back")
		synth._set_trimSilence(True)

		# 1c. The level calibration back on (the checks above ran at gain 1.0,
		#     the engine's own level, which is what trimming decides on).
		drv._FULL_VOLUME_GAIN = calibration
		synth._set_volume(100)
		ok, evs = say(synth, ["Hello world."])
		calibrated = peak(audio(evs))
		check(ok and abs(calibrated - round(calibration * hello_peak)) <= 1,
			f"volume 100: peak {calibrated}, want {round(calibration * hello_peak)} (calibration {calibration})")

		# 2. Text, index marks, done -- in that order, marks between the audio.
		ok, evs = say(synth, ["Hello,", IndexCommand(1), "world.", IndexCommand(2)])
		check(ok, "index: never reported done")
		kinds = [k for k, _, _ in evs if k in ("index", "done")]
		check(kinds == ["index", "index", "done"], f"index/done order: {kinds}")
		check([v for k, v, _ in evs if k == "index"] == [1, 2], "index values")
		marks = [i for i, (k, _, _) in enumerate(evs) if k == "mark"]
		if check(len(marks) == 2, f"{len(marks)} index callbacks attached, want 2"):
			check(len(audio(evs[: marks[0]])) > 0, "no audio before the first index")
			check(len(audio(evs[marks[0] : marks[1]])) > 0, "no audio between the index marks")
			check(len(audio(evs[marks[1] :])) == 0, "audio after the last index")

		# 3. A long paragraph: sentences are split, so the first sound comes
		#    quickly; then cancel: audio stops, no done for it.
		paragraph = " ".join(f"This is sentence number {n}, and it goes on for a while." for n in range(1, 31))
		t0 = time.perf_counter()
		synth.speak([paragraph])
		end = time.time() + 20
		while time.time() < end and len(audio(list(events))) < 20 * BLOCK_BYTES:
			time.sleep(0.005)
		synth.cancel()
		time.sleep(0.5)
		evs = take()
		first = next((t for k, _, t in evs if k == "audio"), None)
		latency = (first - t0) if first else None
		check(latency is not None and latency < 0.5, f"first sound after {latency} s")
		stops = [i for i, (k, _, _) in enumerate(evs) if k == "stop"]
		if check(stops, "cancel did not stop the player"):
			after = len(audio(evs[stops[-1] + 1 :]))
			check(after <= BLOCK_BYTES, f"{after} bytes fed after the last stop")
		check(not any(k == "done" for k, _, _ in evs), "done reported for a cancelled utterance")
		check(len(audio(evs)) < RATE * 2 * 60, "cancel did not stop the feeding")
		print(f"info: first sound of a 30-sentence paragraph after {latency * 1000:.0f} ms")

		# 4. A setting changed then a cancel: the setting survives.
		hello_len = len(audio(say(synth, ["Hello world."])[1]))
		synth._set_rate(100)
		synth.cancel()
		ok, evs = say(synth, ["Hello world."])
		fast = len(audio(evs))
		check(ok and fast < hello_len * 0.6, f"rate 100 not faster: {fast} vs {hello_len} bytes")
		synth._set_rate(0)
		ok, evs = say(synth, ["Hello world."])
		slow = len(audio(evs))
		check(ok and slow > hello_len * 1.5, f"rate 0 not slower: {slow} vs {hello_len} bytes")
		synth._set_rate(50)

		# 5. Volume, and the earlier add-on's bug: a voice change must not
		#    reset it (docs/03, E1).
		synth._set_volume(30)
		ok, evs = say(synth, ["Hello world."])
		want = round(0.3 * calibration * hello_peak)
		check(ok and abs(peak(audio(evs)) - want) <= 1, f"volume 30: peak {peak(audio(evs))}, want {want}")
		synth._set_voice("female")
		ok, evs = say(synth, ["Hello world."])
		check(ok and abs(peak(audio(evs)) - want) <= 1,
			f"volume 30 after a voice change: peak {peak(audio(evs))}, want {want}")
		check(synth._get_volume() == 30, "volume setting did not stick")
		synth._set_volume(0)
		ok, evs = say(synth, ["Silence."])
		check(ok and len(audio(evs)) > 0 and peak(audio(evs)) == 0, "volume 0 is not silence")
		synth._set_volume(100)
		synth._set_voice("male")

		# 5b. Loudness (docs/12, 13): the levelling switches with the setting,
		#     never goes past 0.95 of full scale, and volume is a gain on it.
		#     How even it is, is checked in tests/api/check_leveling.py. An
		#     unknown choice changes nothing.
		synth._set_varyIntonation(False)
		peak_mode = audio(say(synth, ["Stop! Look at the bright red bicycle."])[1])
		levelled = {}
		for choice in ("message", "constant"):
			synth._set_leveling(choice)
			even = levelled[choice] = audio(say(synth, ["Stop! Look at the bright red bicycle."])[1])
			check(len(even) == len(peak_mode) and even != peak_mode, f"loudness {choice} changed nothing")
			check(peak(even) <= 31129, f"loudness {choice}: peak {peak(even)} above 31129")
			synth._set_volume(30)
			even30 = audio(say(synth, ["Stop! Look at the bright red bicycle."])[1])
			check(abs(peak(even30) - round(0.3 * peak(even))) <= 1, f"loudness {choice} at volume 30: peak {peak(even30)}")
			synth._set_volume(100)
		check(levelled["message"] != levelled["constant"], "steady throughout is the same as even per message")
		synth._set_leveling("no such thing")
		check(synth._get_leveling() == "constant", "an unknown loudness choice was taken")
		synth._set_leveling("peak")
		check(audio(say(synth, ["Stop! Look at the bright red bicycle."])[1]) == peak_mode, "peak loudness does not give peak mode back")
		synth._set_varyIntonation(True)

		# 6. Every voice speaks.
		for voice in voices:
			synth._set_voice(voice)
			ok, evs = say(synth, ["Schedule a tomato."])
			check(ok and len(audio(evs)) > 0, f"voice {voice}: no audio")
		synth._set_voice("male")

		# 7. Pitch command around spelling, a break.
		ok, evs = say(synth, [PitchCommand(offset=30), CharacterModeCommand(True), "a", CharacterModeCommand(False), PitchCommand()])
		check(ok and len(audio(evs)) > 0, "spelling 'a': no audio")
		ok, evs = say(synth, ["Before", BreakCommand(500), "after"])
		check(ok and len(audio(evs)) > RATE * 2 * 0.5, "break shorter than 500 ms")

		# 8. Vary intonation: off repeats exactly; on varies.
		synth._set_varyIntonation(False)
		a1 = audio(say(synth, ["The quick brown fox jumps over the lazy dog."])[1])
		a2 = audio(say(synth, ["The quick brown fox jumps over the lazy dog."])[1])
		check(a1 == a2 and a1, "intonation not varied, yet two runs differ")
		synth._set_varyIntonation(True)
		varied = {audio(say(synth, ["The quick brown fox jumps over the lazy dog."])[1]) for _ in range(3)}
		check(len(varied) > 1, "vary intonation on, yet three runs were identical")

		# 9. Hostile and awkward text: nothing breaks, done always comes.
		# The long ones killed the process before the API's guard (docs/09, docs/10).
		for text in ("日本語 \U0001f600 café [x] 12345678901234567890 \x00\x07",
				"*", "...", "", "   ", "\u201cQuoted\u201d \u2014 and\u2026 C:\\Users\\Inbox",
				"w" * 400, "<" * 400, "1" * 400, "deadbeef" * 50, "aGVsbG8gd29ybGQ" * 30):
			ok, evs = say(synth, [text])
			check(ok, f"no done for {text!r}")
			check(not any(k == "error" for k, _, _ in evs), f"error logged for {text!r}")

		# 9b. A huge unbroken token: split into pieces, so that cancel comes in time.
		# It spells to about 25 minutes of speech, which in one piece would be about 25 s
		# of synthesis that nothing could interrupt.
		synth.speak(["w" * 3000])
		end = time.time() + 20
		while time.time() < end and not audio(list(events)):
			time.sleep(0.005)
		check(audio(list(events)), "a huge token: no sound came")
		t0 = time.perf_counter()
		synth.cancel()
		take()
		ok, evs = say(synth, ["Hello."])
		spent = time.perf_counter() - t0
		check(ok and audio(evs), "after cancelling a huge token, the next speech did not come")
		check(spent < 5.0, f"cancelling a huge token took {spent:.1f} s to give way")
		print(f"info: {spent:.2f} s from cancelling a huge token to the end of the next word")
		check([len(x) for x in drv._pieces("w" * 450)] == [200, 200, 50], "_pieces on an unbroken run")
		check(list(drv._pieces("short one")) == ["short one"], "_pieces on a short text")
		check(max(len(x) for x in drv._pieces("word " * 100)) <= 200, "_pieces at spaces")
		check("".join(drv._pieces("word " * 100)).replace(" ", "") == "word" * 100, "_pieces lost a word")

		synth.terminate()
		check(not synth._thread.is_alive(), "speak thread still alive after terminate")
		check(any(k == "saved" for k, _, _ in take()), "base terminate (settings save) not called")

		# 10. A data folder whose name does not fit the ANSI code page: the
		#     driver falls back to the 8.3 short path.
		odd = os.path.join(tmp, "\u0442\u0435\u0441\u0442-\u03b1", "synthDrivers")
		lay_out(odd, dll, data, os.path.join(folder, "gamatts.py"))
		try:
			os.path.abspath(odd).encode("mbcs")
			print("info: the Cyrillic/Greek folder name fits this ANSI code page; fallback not exercised")
		except UnicodeEncodeError:
			buf = ctypes.create_unicode_buffer(32768)
			ctypes.windll.kernel32.GetShortPathNameW(odd, buf, len(buf))
			short_ok = buf.value != odd
			drv2 = load_driver(odd, "gamatts_driver_odd")
			try:
				s2 = drv2.SynthDriver()
				ok, evs = say(s2, ["Hello world."])
				check(ok and len(audio(evs)) > 0, "no audio from a non-ANSI data path")
				s2.terminate()
				print("info: non-ANSI data path opened through its short path")
			except RuntimeError as e:
				check(not short_ok, f"non-ANSI path failed although a short path exists: {e}")
				print(f"info: no 8.3 short names on this volume, so a non-ANSI path cannot work: {e}")
	finally:
		shutil.rmtree(tmp, ignore_errors=True)

	print("all passed" if not failures else f"{failures} failure(s)")
	sys.exit(1 if failures else 0)


if __name__ == "__main__":
	main()
