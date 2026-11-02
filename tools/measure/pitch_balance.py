"""Model 5: noise consonants against the voice, and level, as the pitch moves.

    python -I tools/measure/pitch_balance.py <gama_api library> <data_dir> <corpus.txt> [lines]

Why. The levelled modes bring every utterance to one A-weighted level. If the tube's
voiced sound moves with the pitch and its noise does not, levelling moves the s and f with
the pitch: GnuspeechSA-NVDA's docs/13 section 6 found that by ear, on its own tube. The
constant kNoiseDbPerSemitone in the API corrects for it, and it was fitted to that tube.
Model 5's source, losses and radiation differ, so it is measured here.

For each pitch from an octave down to an octave up, and each levelling mode, this prints
N-V, the level of the noise lines against the voiced lines (tools/measure/levels.py), with
its change from the voice's own pitch, and the A-weighted level.

Needs numpy and scipy. Copyright 2026 dengopaiv. GPL-3.0-or-later.
"""

import ctypes
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from levels import a_weighted_db, parse_track, parts  # noqa: E402

p = ctypes.c_void_p
SEMITONES = (-12, -6, 0, 6, 12)


def load(path):
	lib = ctypes.CDLL(path)
	lib.gama_create.restype = p
	lib.gama_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
	lib.gama_set_deterministic.argtypes = [p, ctypes.c_int]
	lib.gama_set_voice.argtypes = [p, ctypes.c_int]
	lib.gama_set_pitch.argtypes = [p, ctypes.c_double]
	lib.gama_set_leveling.argtypes = [p, ctypes.c_int, ctypes.c_double]
	lib.gama_speak.argtypes = [p, ctypes.c_char_p]
	lib.gama_pending.restype = ctypes.c_size_t
	lib.gama_pending.argtypes = [p]
	lib.gama_read.restype = ctypes.c_size_t
	lib.gama_read.argtypes = [p, ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t]
	lib.gama_sample_rate.argtypes = [p]
	lib.gama_track.restype = ctypes.c_size_t
	lib.gama_track.argtypes = [p, ctypes.c_char_p, ctypes.c_size_t]
	return lib


def speak(lib, e, text):
	if lib.gama_speak(e, (text + " ").encode("ascii")) != 0:
		return None
	n = lib.gama_pending(e)
	b = (ctypes.c_int16 * max(n, 1))()
	got = lib.gama_read(e, b, n)
	return np.frombuffer(b, dtype=np.int16)[:got].copy()


def track_of(lib, e):
	n = lib.gama_track(e, None, 0)
	b = ctypes.create_string_buffer(n + 1)
	lib.gama_track(e, b, n + 1)
	return parse_track(b.value.decode("ascii"))


def main():
	if len(sys.argv) not in (4, 5):
		sys.exit(__doc__)
	lib = load(sys.argv[1])
	e = lib.gama_create(sys.argv[2].encode(), None, 0)
	lib.gama_set_deterministic(e, 1)
	count = int(sys.argv[4]) if len(sys.argv) == 5 else 40
	lines = [x.strip() for x in open(sys.argv[3], encoding="ascii") if x.strip() and not x.startswith("#")]
	lines = [x for x in lines if len(x.split()) >= 4][:count]
	fs = lib.gama_sample_rate(e)
	for voice, vname in ((0, "male"), (1, "female")):
		lib.gama_set_voice(e, voice)
		for mode, name in ((0, "peak"), (1, "even per message"), (2, "steady throughout")):
			lib.gama_set_leveling(e, mode, -22.0)
			rows = {}
			for st in SEMITONES:
				lib.gama_set_pitch(e, st)
				diffs, levels = [], []
				for t in lines:
					s = speak(lib, e, t)
					if s is None or not np.any(s):
						continue
					v, n = parts(s / 32768, fs, track_of(lib, e))
					if not (math.isnan(v) or math.isnan(n)):
						diffs.append(n - v)
					levels.append(a_weighted_db(s, fs))
				rows[st] = (float(np.mean(diffs)), float(np.median(levels)))
			lib.gama_set_pitch(e, 0.0)
			own = rows[0][0]
			print(f"\n{vname}, {name}: {len(lines)} lines")
			print(f"{'semitones':>9} {'N-V dB':>8} {'change':>8} {'dB/semi':>8} {'A dB':>7}")
			for st in SEMITONES:
				d, lv = rows[st]
				slope = (d - own) / st if st else 0.0
				print(f"{st:9d} {d:8.2f} {d - own:+8.2f} {slope:+8.2f} {lv:7.2f}", flush=True)


if __name__ == "__main__":
	main()
