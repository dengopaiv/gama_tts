#!/usr/bin/env python3
# Compare WAV files against a reference: alignment, gain, correlation, SNR,
# identical samples, and (with --bands) per-band level and coherence plus a
# list of 50 ms stretches where the waveforms stop matching.
#
# Usage: compare_wav.py [--bands] reference.wav candidate.wav [more.wav ...]
#
# Files must have the same sample rate; only the first channel is used.
# The best lag is searched in +/-400 samples; 1000 samples at each end are
# skipped so that start-up and flush differences do not dominate.
#
# Needs numpy. Public domain. Written 2026-10-16 for docs/07-measurements.md.

import argparse
import wave

import numpy as np

BANDS = [(50, 300), (300, 1000), (1000, 2000), (2000, 4000), (4000, 6000),
         (6000, 8000), (8000, 10000), (10000, 15000)]


def read(path):
    with wave.open(path) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float)
        if w.getnchannels() == 2:
            a = a[0::2]
        return w.getframerate(), a


def align(ref, x):
    n = min(len(ref), len(x))
    lag = max(range(-400, 401),
              key=lambda L: np.dot(ref[1000:n - 1000], x[1000 + L:n - 1000 + L]))
    return lag, ref[1000:n - 1000], x[1000 + lag:n - 1000 + lag]


def bands(rate, r, y):
    N = 2048
    win = np.hanning(N)
    sxy = sxx = syy = 0
    for i in range(0, len(r) - N, N // 2):
        a = np.fft.rfft(r[i:i + N] * win)
        b = np.fft.rfft(y[i:i + N] * win)
        sxy = sxy + a * np.conj(b)
        sxx = sxx + abs(a) ** 2
        syy = syy + abs(b) ** 2
    f = np.fft.rfftfreq(N, 1 / rate)
    coh = abs(sxy) ** 2 / (sxx * syy)
    for lo, hi in BANDS:
        m = (f >= lo) & (f < hi)
        level = 10 * np.log10(np.sum(sxx[m]) / np.sum(syy[m]))
        share = np.sum(sxx[m]) / np.sum(sxx) * 100
        print(f"    {lo:5d}-{hi:5d} Hz  coherence {np.mean(coh[m]):.3f}  "
              f"level ref/cand {level:+.1f} dB  energy share {share:5.1f} %")
    seg = int(rate * 0.05)
    rows = []
    for i in range(0, len(r) - seg, seg):
        a = r[i:i + seg]
        b = y[i:i + seg]
        if np.dot(a, a) > 1e3 * seg and np.dot(b, b) > 0:
            c = np.dot(a, b) / np.sqrt(np.dot(a, a) * np.dot(b, b))
            rows.append(((i + 1000) / rate, c, np.sqrt(np.mean(a ** 2))))
    print(f"    50 ms stretches with signal: {len(rows)}, "
          f"median correlation {np.median([c for _, c, _ in rows]):.3f}")
    for t, c, e in rows:
        if c < 0.9:
            print(f"      t = {t:.2f} s  correlation {c:+.3f}  rms {e:.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bands", action="store_true")
    ap.add_argument("reference")
    ap.add_argument("candidates", nargs="+")
    args = ap.parse_args()

    rate, ref = read(args.reference)
    print(f"reference {args.reference}: {rate} Hz, {len(ref)} samples, "
          f"rms {np.sqrt(np.mean(ref ** 2)):.0f}")
    for p in args.candidates:
        r2, x = read(p)
        if r2 != rate:
            print(f"{p}: sample rate {r2} differs, skipped")
            continue
        lag, r, y = align(ref, x)
        g = np.dot(r, y) / np.dot(y, y)
        err = r - g * y
        corr = np.dot(r, y) / np.sqrt(np.dot(r, r) * np.dot(y, y))
        e2 = np.dot(err, err)
        snr = 10 * np.log10(np.dot(r, r) / e2) if e2 > 0 else float("inf")
        same = np.mean(r == y) * 100
        print(f"{p}: {len(x)} samples, lag {lag:+d}, gain {g:.3f}, "
              f"correlation {corr:.5f}, SNR {snr:.1f} dB, identical {same:.1f} %")
        if args.bands:
            bands(rate, r, y)


if __name__ == "__main__":
    main()
