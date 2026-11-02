"""The last 100 ms of an utterance, against the rules' track: where does the end sound come from?

    python -I tools/measure/tail.py <gama_api library> <data_dir> text [text...]

Copyright 2026 dengopaiv. GPL-3.0-or-later.
"""

import ctypes
import sys

import numpy as np

p = ctypes.c_void_p
NAMES = ["pitch", "glotVol", "aspVol", "fricVol", "fricPos", "fricCF", "fricBW", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "velum"]


def main():
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
	lib.gama_track.restype = ctypes.c_size_t
	lib.gama_track.argtypes = [p, ctypes.c_char_p, ctypes.c_size_t]
	e = lib.gama_create(sys.argv[2].encode(), None, 0)
	lib.gama_set_deterministic(e, 1)
	for t in sys.argv[3:]:
		lib.gama_speak(e, (t + " ").encode("ascii"))
		n = lib.gama_pending(e)
		b = (ctypes.c_int16 * max(n, 1))()
		lib.gama_read(e, b, n)
		x = np.frombuffer(b, dtype=np.int16).astype(np.int32)
		fs = lib.gama_sample_rate(e)
		m = lib.gama_track(e, None, 0)
		c = ctypes.create_string_buffer(m + 1)
		lib.gama_track(e, c, m + 1)
		track = np.array([[float(v) for v in ln.split()] for ln in c.value.decode().splitlines() if ln.strip()])
		print(f"\n{t!r}: {n} samples = {n * 1000 / fs:.1f} ms; track {len(track)} lines = {len(track) * 4} ms; peak {np.abs(x).max()}")
		w = fs // 200
		print("ms from end: peak in each 5 ms, newest last")
		print("  " + " ".join(f"{np.abs(x[max(0, n - (k + 1) * w):n - k * w]).max():4d}" for k in range(39, -1, -1)))
		print("track's last lines:", " ".join(NAMES))
		for row in track[-24::4]:
			print("  " + " ".join(f"{v:7.2f}" for v in row))


if __name__ == "__main__":
	main()
