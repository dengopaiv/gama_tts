"""Loudness levelling (gama_set_leveling) against an independent measure.

Usage: python -I check_leveling.py <gama_api library> <data_dir> <corpus.txt>

The API's own A-weighting is C++. The measure here goes through scipy
(tools/measure/levels.py). Every corpus line is spoken in GAMA_LEVEL_LOUDNESS and in
GAMA_LEVEL_CONSTANT at the default target, deterministic, and must:
  - fail exactly where peak mode fails;
  - have the same length as in peak mode, with trimming off and on;
  - peak at no more than 0.95 of full scale (31129);
  - measure the target within 0.06 dB, or, where the limiter acted, below it by at
    most 1 dB;
  - in GAMA_LEVEL_CONSTANT, hold one level inside: over the voiced frames, the sd within
    an utterance is at most MAX_FRAME_SD, and on average at most MEAN_FRAME_SD.
Also: the range checks, volume as a gain on top, and the pitch: an octave down and up,
the noise consonants against the voice (levels.parts) stay within MAX_BALANCE_SHIFT dB of
their balance at the voice's own pitch in both levelled modes, where in peak mode they
move by more than 6 dB.

Adapted from GnuspeechSA-NVDA's tests/api/check_leveling.py. Needs numpy and scipy.
Copyright 2026 dengopaiv. GPL-3.0-or-later.
"""

import ctypes
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools", "measure"))
from levels import a_weighted_db, parse_track, parts, voiced_frame_sd  # noqa: E402

OK, ERR_RANGE = 0, -2
PEAK, LOUDNESS, CONSTANT = 0, 1, 2
NAMES = {PEAK: "peak", LOUDNESS: "loudness", CONSTANT: "constant"}
BALANCE_LINES, MAX_BALANCE_SHIFT = 20, 1.5
p = ctypes.c_void_p
failures = 0

#: From the first full run: at most 0.47 in any line, 0.33 on average, male voice (docs/10).
MAX_FRAME_SD, MEAN_FRAME_SD = 0.9, 0.5


def check(cond, msg):
	global failures
	if not cond:
		failures += 1
		print("FAIL", msg)
	return cond


def load(path):
	lib = ctypes.CDLL(path)
	lib.gama_create.restype = p
	lib.gama_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
	lib.gama_destroy.argtypes = [p]
	lib.gama_set_deterministic.argtypes = [p, ctypes.c_int]
	lib.gama_speak.argtypes = [p, ctypes.c_char_p]
	lib.gama_pending.restype = ctypes.c_size_t
	lib.gama_pending.argtypes = [p]
	lib.gama_read.restype = ctypes.c_size_t
	lib.gama_read.argtypes = [p, ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t]
	lib.gama_sample_rate.argtypes = [p]
	lib.gama_set_volume.argtypes = [p, ctypes.c_double]
	lib.gama_set_pitch.argtypes = [p, ctypes.c_double]
	lib.gama_set_trim.argtypes = [p, ctypes.c_int, ctypes.c_int]
	lib.gama_set_voice.argtypes = [p, ctypes.c_int]
	lib.gama_voice_count.argtypes = [p]
	lib.gama_set_leveling.argtypes = [p, ctypes.c_int, ctypes.c_double]
	lib.gama_leveling.argtypes = [p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_double)]
	lib.gama_track.restype = ctypes.c_size_t
	lib.gama_track.argtypes = [p, ctypes.c_char_p, ctypes.c_size_t]
	return lib


def track_of(lib, e):
	n = lib.gama_track(e, None, 0)
	b = ctypes.create_string_buffer(n + 1)
	lib.gama_track(e, b, n + 1)
	return parse_track(b.value.decode("ascii"))


def speak(lib, e, text):
	rc = lib.gama_speak(e, text.encode("ascii"))
	if rc != OK:
		return rc, None
	n = lib.gama_pending(e)
	buf = (ctypes.c_int16 * max(n, 1))()
	got = lib.gama_read(e, buf, n)
	return rc, np.frombuffer(buf, dtype=np.int16)[:got].copy()


def main():
	if len(sys.argv) != 4:
		sys.exit(__doc__)
	lib = load(sys.argv[1])
	e = lib.gama_create(sys.argv[2].encode(), None, 0)
	if not e:
		sys.exit("cannot create the engine")
	lib.gama_set_deterministic(e, 1)
	lines = [x.rstrip("\r\n") for x in open(sys.argv[3], encoding="ascii")]
	lines = [x for x in lines if x.strip() and not x.startswith("#")]

	mode, target = ctypes.c_int(-1), ctypes.c_double(0)
	lib.gama_leveling(e, ctypes.byref(mode), ctypes.byref(target))
	check(mode.value == PEAK, f"default mode {mode.value}, want peak")
	default_target = target.value
	for bad in ((3, -22.0), (-1, -22.0), (LOUDNESS, -41.0), (LOUDNESS, -9.0), (LOUDNESS, math.nan), (CONSTANT, -9.0)):
		check(lib.gama_set_leveling(e, *bad) == ERR_RANGE, f"gama_set_leveling{bad} accepted")
	lib.gama_leveling(e, ctypes.byref(mode), ctypes.byref(target))
	check(mode.value == PEAK and target.value == default_target, "a refused value changed the levelling")

	for voice in range(lib.gama_voice_count(e)):
		lib.gama_set_voice(e, voice)
		stats = {m: {"limited": 0, "worst": 0.0, "levels": [], "frame_sds": []} for m in NAMES}
		for i, text in enumerate(lines):
			line = text + " "
			lib.gama_set_leveling(e, PEAK, default_target)
			rc_peak, peak_samples = speak(lib, e, line)
			fs = lib.gama_sample_rate(e)
			if rc_peak == OK and np.any(peak_samples):
				sd = voiced_frame_sd(peak_samples / 32768, fs, track_of(lib, e))
				if sd is not None:
					stats[PEAK]["frame_sds"].append(sd)
			for m in (LOUDNESS, CONSTANT):
				st = stats[m]
				lib.gama_set_leveling(e, m, default_target)
				rc, s = speak(lib, e, line)
				if rc_peak != OK:
					check(rc != OK, f"voice {voice} {i}: peak mode failed, {NAMES[m]} mode returned {rc}")
					continue
				if not check(rc == OK, f"voice {voice} {i}: {NAMES[m]} mode failed on {text!r}"):
					continue
				check(len(s) == len(peak_samples), f"voice {voice} {i}: length {len(s)} in {NAMES[m]} mode, {len(peak_samples)} in peak mode")
				check(int(np.max(np.abs(s))) <= 31129, f"voice {voice} {i}: {NAMES[m]} mode, peak {np.max(np.abs(s))} above 31129")
				if not np.any(s):
					continue
				level = a_weighted_db(s, fs)
				st["levels"].append(level)
				short = default_target - level
				if short > 0.05:
					st["limited"] += 1
					st["worst"] = max(st["worst"], short)
					check(short <= 1.0, f"voice {voice} {i}: {NAMES[m]} mode, {text!r} ends {short:.2f} dB below the target")
				else:
					check(abs(short) <= 0.06, f"voice {voice} {i}: {NAMES[m]} mode, {text!r} measures {level:.3f} dB, target {default_target}")
				sd = voiced_frame_sd(s / 32768, fs, track_of(lib, e))
				if sd is not None:
					st["frame_sds"].append(sd)
					if m == CONSTANT:
						check(sd <= MAX_FRAME_SD, f"voice {voice} {i}: constant mode, {text!r} moves {sd:.2f} dB (sd) inside")
		mean_sd = float(np.mean(stats[CONSTANT]["frame_sds"]))
		check(mean_sd <= MEAN_FRAME_SD, f"voice {voice}: constant mode moves {mean_sd:.2f} dB (sd) inside an utterance on average")
		sds = np.array(stats[PEAK]["frame_sds"])
		print(f"voice {voice}, peak mode: voiced frames inside an utterance move {sds.mean():.2f} dB (sd) on average, at most {sds.max():.2f}")
		for m in (LOUDNESS, CONSTANT):
			st = stats[m]
			levels, sds = np.array(st["levels"]), np.array(st["frame_sds"])
			print(f"voice {voice}, {NAMES[m]} mode, {len(levels)} lines at {default_target} dB: measured {levels.min():.2f} to "
				f"{levels.max():.2f} dB (sd {levels.std():.3f}); {st['limited']} limited, at most {st['worst']:.2f} dB below; "
				f"voiced frames inside move {sds.mean():.2f} dB (sd) on average, at most {sds.max():.2f}", flush=True)
	lib.gama_set_voice(e, 0)

	# Volume is a gain on top; trimming gives the same length in every mode.
	text = "Hello world. "
	lib.gama_set_trim(e, 10, 30)
	lib.gama_set_leveling(e, PEAK, default_target)
	_, trimmed_peak = speak(lib, e, text)
	lib.gama_set_trim(e, -1, -1)
	for m in (LOUDNESS, CONSTANT):
		lib.gama_set_leveling(e, m, default_target)
		_, full = speak(lib, e, text)
		lib.gama_set_volume(e, 0.5)
		_, half = speak(lib, e, text)
		check(len(half) == len(full) and np.max(np.abs(half - np.round(full * 0.5))) <= 1, f"{NAMES[m]} mode, volume 0.5 is not half")
		lib.gama_set_volume(e, 1.0)
		lib.gama_set_trim(e, 10, 30)
		_, trimmed = speak(lib, e, text)
		check(len(trimmed) == len(trimmed_peak), f"trimming gives different lengths in {NAMES[m]} and peak modes")
		lib.gama_set_trim(e, -1, -1)

	# The noise against the voice across the pitch setting.
	balance_lines = [t for t in lines if len(t.split()) >= 4][:BALANCE_LINES]
	fs = lib.gama_sample_rate(e)

	def balance(m, semitones):
		lib.gama_set_leveling(e, m, default_target)
		lib.gama_set_pitch(e, semitones)
		diffs = []
		for t in balance_lines:
			_, s = speak(lib, e, t + " ")
			voiced, noise = parts(s / 32768, fs, track_of(lib, e))
			if not (math.isnan(voiced) or math.isnan(noise)):
				diffs.append(noise - voiced)
		lib.gama_set_pitch(e, 0.0)
		return float(np.mean(diffs))

	for m in (PEAK, LOUDNESS, CONSTANT):
		own = balance(m, 0.0)
		shifts = [balance(m, st) - own for st in (-12.0, 12.0)]
		print(f"{NAMES[m]} mode: noise against voice moves {shifts[0]:+.2f} dB an octave down, {shifts[1]:+.2f} dB an octave up")
		if m == PEAK:
			check(min(abs(v) for v in shifts) > 6.0, f"peak mode: the balance moves only {shifts} dB")
		else:
			check(max(abs(v) for v in shifts) <= MAX_BALANCE_SHIFT, f"{NAMES[m]} mode: noise against voice moves {shifts} dB")
	lib.gama_set_leveling(e, PEAK, default_target)
	lib.gama_destroy(e)
	print(f"{failures} failures")
	sys.exit(1 if failures else 0)


if __name__ == "__main__":
	main()
