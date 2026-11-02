"""What is at the two ends of an utterance? Model 5's ends are not quite silent.

    python -I tools/measure/edges.py <gama_api library> <data_dir> [text...]

For each text, in peak mode, deterministic, untrimmed: where the first and last sample above
-60 dBFS fall, the largest sample in the last 20 ms and the 200 ms before that, the last 8
samples, and whether the output's end is a step (a click at the end of playback).

Copyright 2026 dengopaiv. GPL-3.0-or-later.
"""

import ctypes
import sys

import numpy as np

p = ctypes.c_void_p


def main():
	if len(sys.argv) < 3:
		sys.exit(__doc__)
	lib = ctypes.CDLL(sys.argv[1])
	lib.gama_create.restype = p
	lib.gama_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
	lib.gama_set_deterministic.argtypes = [p, ctypes.c_int]
	lib.gama_speak.argtypes = [p, ctypes.c_char_p]
	lib.gama_pending.restype = ctypes.c_size_t
	lib.gama_pending.argtypes = [p]
	lib.gama_read.restype = ctypes.c_size_t
	lib.gama_read.argtypes = [p, ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t]
	lib.gama_sample_rate.argtypes = [p]
	e = lib.gama_create(sys.argv[2].encode(), None, 0)
	lib.gama_set_deterministic(e, 1)
	texts = sys.argv[3:] or ["8", "Button,", "Hello world.", "Hello world. Goodbye world.", "File", "Edit", "OK", "yes", "no",
		"check box, checked", "The quick brown fox jumps over the lazy dog."]
	print(f"{'text':32} {'n':>7} {'first':>6} {'last':>7} {'tail ms':>7} {'pk last 20ms':>12} {'pk 200ms before':>15}  last 8 samples")
	for t in texts:
		if lib.gama_speak(e, (t + " ").encode("ascii")) != 0:
			print(f"{t:32} nothing to say")
			continue
		n = lib.gama_pending(e)
		b = (ctypes.c_int16 * max(n, 1))()
		lib.gama_read(e, b, n)
		x = np.frombuffer(b, dtype=np.int16).astype(np.int32)
		fs = lib.gama_sample_rate(e)
		loud = np.flatnonzero(np.abs(x) >= 33)
		w = fs // 50
		print(f"{t[:32]:32} {n:7d} {loud[0]:6d} {loud[-1]:7d} {(n - 1 - loud[-1]) * 1000 / fs:7.1f} "
			f"{np.abs(x[-w:]).max():12d} {np.abs(x[-w - fs // 5:-w]).max():15d}  {list(x[-8:])}")


if __name__ == "__main__":
	main()
