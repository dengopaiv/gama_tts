"""How common is the tick at the very end of an utterance, and how far back does it reach?

    python -I tools/measure/end_tick.py <gama_api library> <data_dir> <corpus.txt>

The sample-rate converter pads with zeros at the end of synthesis (flushBuffer). Where the
tube's output has not settled to zero, that step goes through the output differentiator and
makes a click. For each voice, over the corpus, in peak mode, this prints the largest sample in
each of the last 5 ms bins, and how many utterances have, in their last 5 ms, a sample above
-60 dBFS, which is what trimming would take for the last sound.

Copyright 2026 dengopaiv. GPL-3.0-or-later.
"""

import ctypes
import sys

import numpy as np

p = ctypes.c_void_p


def main():
	lib = ctypes.CDLL(sys.argv[1])
	lib.gama_create.restype = p
	lib.gama_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
	lib.gama_set_deterministic.argtypes = [p, ctypes.c_int]
	lib.gama_set_voice.argtypes = [p, ctypes.c_int]
	lib.gama_voice_name.restype = ctypes.c_char_p
	lib.gama_voice_name.argtypes = [p, ctypes.c_int]
	lib.gama_voice_count.argtypes = [p]
	lib.gama_speak.argtypes = [p, ctypes.c_char_p]
	lib.gama_pending.restype = ctypes.c_size_t
	lib.gama_pending.argtypes = [p]
	lib.gama_read.restype = ctypes.c_size_t
	lib.gama_read.argtypes = [p, ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t]
	lib.gama_sample_rate.argtypes = [p]
	e = lib.gama_create(sys.argv[2].encode(), None, 0)
	lib.gama_set_deterministic(e, 1)
	lines = [x.strip() for x in open(sys.argv[3], encoding="ascii") if x.strip() and not x.startswith("#")]
	for v in range(lib.gama_voice_count(e)):
		lib.gama_set_voice(e, v)
		fs = lib.gama_sample_rate(e)
		w = fs // 200
		bins = []
		hit = []
		for t in lines:
			if lib.gama_speak(e, (t + " ").encode("ascii")) != 0:
				continue
			n = lib.gama_pending(e)
			b = (ctypes.c_int16 * max(n, 1))()
			lib.gama_read(e, b, n)
			x = np.abs(np.frombuffer(b, dtype=np.int16).astype(np.int32))
			row = [x[n - (k + 1) * w : n - k * w].max() for k in range(6)]
			bins.append(row)
			if row[0] >= 33:
				hit.append((int(row[0]), t))
		bins = np.array(bins)
		hit.sort(reverse=True)
		print(f"{lib.gama_voice_name(e, v).decode():12} {len(bins)} lines; {len(hit)} end with a sample above -60 dBFS; "
			f"largest in the last 5 ms bins, newest first: {list(int(m) for m in bins.max(axis=0))}")
		print(f"             medians: {list(int(m) for m in np.median(bins, axis=0))}; worst: {[(a, t[:24]) for a, t in hit[:4]]}", flush=True)


if __name__ == "__main__":
	main()
