"""Level, spectral balance and edge silence of GamaTTS voices against Gnuspeech and eSpeak.

The A-weighting and active-speech gate are the method of GnuspeechSA-NVDA's
tools/measure/loudness.py, so the numbers can be set beside that project's docs/08.
Usage: python -I audio_metrics.py PROBE DATA GS_DLL GS_DATA CORPUS ESPEAK_WAV WORK
Public domain. Written 2026-11-02 for gama_tts docs/09.
"""
import ctypes
import glob
import math
import os
import shutil
import subprocess
import sys
import wave

import numpy as np
from scipy.signal import bilinear, butter, lfilter, sosfilt

MENU = ["File", "Edit", "View", "Insert", "Format", "Tools", "Help", "Save", "Save as", "Open", "Close", "Exit",
	"Cut", "Copy", "Paste", "Delete", "Select all", "Undo", "Redo", "Find", "Replace", "Print", "Options",
	"button", "check box, checked", "not checked", "link", "heading level 2", "list, 5 items", "blank"]


def a_weight(fs):
    f1, f2, f3, f4 = 20.598997, 107.65265, 737.86223, 12194.217
    a1000 = 1.9997
    nums = [(2 * math.pi * f4) ** 2 * 10 ** (a1000 / 20), 0, 0, 0, 0]
    dens = np.polymul([1, 4 * math.pi * f4, (2 * math.pi * f4) ** 2], [1, 4 * math.pi * f1, (2 * math.pi * f1) ** 2])
    dens = np.polymul(np.polymul(dens, [1, 2 * math.pi * f3]), [1, 2 * math.pi * f2])
    return bilinear(nums, dens, fs)


def active_db(y, fs):
    n = int(0.02 * fs)
    if len(y) < n:
        return float("nan")
    p = np.array([np.mean(y[i : i + n] ** 2) for i in range(0, len(y) - n + 1, n)])
    p = p[p > 0]
    if not len(p):
        return float("nan")
    return 10 * math.log10(np.mean(p[p > p.max() * 1e-3]))


def band_db(x, fs, lo, hi):
    if lo is None:
        sos = butter(4, hi, "low", fs=fs, output="sos")
    else:
        sos = butter(4, [lo, min(hi, fs / 2 - 1)], "band", fs=fs, output="sos")
    return active_db(sosfilt(sos, x), fs)


def edges(x, fs):
    thr = 10 ** (-60 / 20)
    idx = np.flatnonzero(np.abs(x) > thr)
    if not len(idx):
        return float("nan"), float("nan")
    return idx[0] * 1000 / fs, (len(x) - 1 - idx[-1]) * 1000 / fs


def read_wav(path):
    with wave.open(path, "rb") as w:
        fs = w.getframerate()
        d = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
    return d, fs


def gnuspeech_lines(dll, data, lines):
    lib = ctypes.CDLL(dll)
    p = ctypes.c_void_p
    lib.gs_create.restype = p
    lib.gs_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
    lib.gs_set_deterministic.argtypes = [p, ctypes.c_int]
    lib.gs_speak.argtypes = [p, ctypes.c_char_p]
    lib.gs_pending.argtypes = [p]
    lib.gs_pending.restype = ctypes.c_size_t
    lib.gs_read.argtypes = [p, ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t]
    lib.gs_read.restype = ctypes.c_size_t
    lib.gs_sample_rate.argtypes = [p]
    err = ctypes.create_string_buffer(512)
    e = lib.gs_create(data.encode("mbcs"), err, 512)
    lib.gs_set_deterministic(e, 1)
    out = []
    for t in lines:
        if lib.gs_speak(e, (t + " ").encode("ascii")) != 0:
            continue
        n = lib.gs_pending(e)
        b = (ctypes.c_int16 * n)()
        got = lib.gs_read(e, b, n)
        out.append(np.frombuffer(b, dtype=np.int16, count=got).astype(np.float64) / 32768.0)
    return out, lib.gs_sample_rate(e)


def gama_lines(probe, data, voice, lines, work):
    d = os.path.join(work, voice)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    src = os.path.join(work, "lines.txt")
    with open(src, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    subprocess.run([probe, "wavs", data, voice, d, "1", "0", "1", src], check=True, capture_output=True)
    out, fs = [], 48000
    for path in sorted(glob.glob(os.path.join(d, "*.wav"))):
        x, fs = read_wav(path)
        out.append(x)
    return out, fs


def report(name, utt, fs):
    b, a = a_weight(fs)
    levels = []
    leads, trails = [], []
    for x in utt:
        levels.append(active_db(lfilter(b, a, x), fs))
        l, t = edges(x, fs)
        leads.append(l)
        trails.append(t)
    joined = np.concatenate(utt)
    overall = active_db(lfilter(b, a, joined), fs)
    pres = band_db(joined, fs, 1000, 4000) - overall
    low = band_db(joined, fs, None, 500) - overall
    high = band_db(joined, fs, 4000, 10000) - overall
    print(f"{name:18} {overall:7.1f} {np.nanstd(levels):6.2f} {low:7.1f} {pres:7.1f} {high:7.1f} "
          f"{np.nanmedian(leads):7.0f} {np.nanmedian(trails):7.0f} {max(np.abs(x).max() for x in utt):6.3f} {fs:6d}")


def main():
    probe, data, gs_dll, gs_data, corpus, espeak, work = sys.argv[1:8]
    os.makedirs(work, exist_ok=True)
    lines = [x.strip() for x in open(corpus, encoding="ascii") if x.strip() and not x.startswith("#")]
    lines = [x for x in lines if any(c.isalnum() for c in x)]
    print(f"{len(lines)} corpus lines; randomness off; every synthesizer peak-normalised per utterance as shipped")
    head = f"{'':18} {'A dB':>7} {'sd':>6} {'<500':>7} {'1-4k':>7} {'4-10k':>7} {'lead':>7} {'trail':>7} {'peak':>6} {'Hz':>6}"
    print("== corpus; bands in dB against the A-weighted level; edges in ms (median, -60 dBFS)")
    print(head)
    u, fs = gnuspeech_lines(gs_dll, gs_data, lines)
    report("Gnuspeech male", u, fs)
    for v in ("0_male", "4_male", "5_male", "0_female", "5_female", "5_large_child", "5_small_child", "5_baby"):
        u, fs = gama_lines(probe, data, v, lines, work)
        report(v, u, fs)
    print("== the menu words, against eSpeak klatt5 (the file made for GnuspeechSA-NVDA docs/12)")
    print(head)
    x, fs = read_wav(espeak)
    report("eSpeak klatt5", [x], fs)
    u, fs = gnuspeech_lines(gs_dll, gs_data, MENU)
    report("Gnuspeech male", u, fs)
    for v in ("0_male", "5_male", "5_female"):
        u, fs = gama_lines(probe, data, v, MENU, work)
        report(v, u, fs)


if __name__ == "__main__":
    main()
