"""Level measures shared by the tests and the measuring scripts.

The method is GnuspeechSA-NVDA's tools/measure/loudness.py and stress_level.py: IEC 61672
A-weighting through the analogue prototype and the bilinear transform, then the mean
power of the 20 ms frames within 30 dB of the loudest. So numbers here can be set beside
that project's docs/08, docs/12 and docs/13.

Needs numpy and scipy. Copyright 2026 dengopaiv. GPL-3.0-or-later.
"""

import math

import numpy as np
from scipy.signal import bilinear, lfilter

#: Control lines per second: control_period = 4 ms, as the shipped data has it.
CONTROL_RATE = 250.0


def a_weight(x, fs):
	f1, f2, f3, f4 = 20.598997, 107.65265, 737.86223, 12194.217
	num = [(2 * np.pi * f4) ** 2 * 10 ** (1.9997 / 20), 0, 0, 0, 0]
	den = np.polymul([1, 4 * np.pi * f4, (2 * np.pi * f4) ** 2], [1, 4 * np.pi * f1, (2 * np.pi * f1) ** 2])
	den = np.polymul(np.polymul(den, [1, 2 * np.pi * f3]), [1, 2 * np.pi * f2])
	b, a = bilinear(num, den, fs)
	return lfilter(b, a, x)


def active_db(y, fs):
	"""Mean power of the 20 ms frames within 30 dB of the loudest, in dB."""
	w = int(0.02 * fs)
	n = len(y) // w
	p = np.mean(y[: n * w].reshape(n, w) ** 2, axis=1)
	return 10 * np.log10(np.mean(p[p > p.max() * 1e-3]))


def a_weighted_db(samples, fs):
	"""The A-weighted level of active speech, of 16-bit samples, in dB of full scale."""
	return active_db(a_weight(np.asarray(samples, dtype=np.float64) / 32768, fs), fs)


def parse_track(text):
	"""The control lines of a parameter track as gama_track or gama_tts -p write it:
	one row of 16 values per line, with no header."""
	return np.array([[float(v) for v in ln.split()] for ln in text.splitlines() if ln.strip()])


def voiced_frame_sd(x, fs, track, rate=CONTROL_RATE):
	"""How much the loudness moves inside an utterance: the sd, in dB, of the A-weighted
	level over the 40 ms around each voiced control line (glottal volume 57 dB or more)
	whose 40 ms lie wholly inside its voiced stretch. x is untrimmed, in any scale. None
	if fewer than two lines qualify."""
	y = a_weight(np.asarray(x, dtype=np.float64), fs)
	energy = np.concatenate([[0.0], np.cumsum(y * y)])
	half = int(0.02 * fs)
	voiced = track[:, 1] >= 57
	inner = voiced.copy()
	for d in range(1, 6):  # 5 lines, 20 ms, on either side
		inner[d:] &= voiced[:-d]
		inner[:-d] &= voiced[d:]
	levels = []
	for k in np.nonzero(inner)[0]:
		c = int(round(k * fs / rate))
		lo, hi = max(0, c - half), min(len(y), c + half)
		if hi > lo:
			levels.append(10 * math.log10(max((energy[hi] - energy[lo]) / (hi - lo), 1e-30)))
	return float(np.std(levels)) if len(levels) > 1 else None


def parts(x, fs, track, rate=CONTROL_RATE):
	"""The A-weighted level (dB) of the voiced lines (glottal volume 57 dB or more) and
	of the noise lines (frication or aspiration, with glottal volume below 30 dB)."""
	y = a_weight(np.asarray(x, dtype=np.float64), fs)
	energy = np.concatenate([[0.0], np.cumsum(y * y)])
	half = int(0.01 * fs)

	def power(k):
		c = int(round(k * fs / rate))
		lo, hi = max(0, c - half), min(len(y), c + half)
		return (energy[hi] - energy[lo]) / max(hi - lo, 1)

	glot, noise = track[:, 1], (track[:, 2] > 0) | (track[:, 3] > 0)
	v = [power(k) for k in range(len(track)) if glot[k] >= 57]
	n = [power(k) for k in range(len(track)) if glot[k] < 30 and noise[k]]
	db = lambda ps: 10 * np.log10(np.mean(ps)) if ps else float("nan")  # noqa: E731
	return db(v), db(n)
