"""Listening files for judging GamaTTS as an everyday voice. Nothing here is committed.

Usage: python -I make_kit.py PROBE DATA GS_DLL GS_DATA OUT
Public domain. Written 2026-11-02 for gama_tts docs/09.
"""
import ctypes
import os
import subprocess
import sys
import wave

import numpy as np

SENTENCES = ("This is a test of the screen reader. The quick brown fox jumps over the lazy dog. "
             "Would you like to save your changes before closing? It cost 25 dollars in 1984, "
             "which was more than she expected.")
MENU = ["File", "Edit", "View", "Insert", "Format", "Tools", "Help", "Save", "Save as", "Open", "Close", "Exit",
        "Cut", "Copy", "Paste", "Delete", "Select all", "Undo", "Redo", "Find", "Replace", "Print", "Options",
        "button", "check box, checked", "not checked", "link", "heading level 2", "list, 5 items", "blank"]


def read(path):
    with wave.open(path, "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16), w.getframerate()


def write(path, x, fs):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(np.asarray(x, dtype=np.int16).tobytes())
    print(f"{os.path.basename(path):44} {len(x) / fs:6.1f} s")


class Gnuspeech:
    def __init__(self, dll, data):
        lib = self.lib = ctypes.CDLL(dll)
        p = ctypes.c_void_p
        lib.gs_create.restype = p
        lib.gs_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
        lib.gs_set_rate.argtypes = [p, ctypes.c_double]
        lib.gs_speak.argtypes = [p, ctypes.c_char_p]
        lib.gs_pending.argtypes = [p]
        lib.gs_pending.restype = ctypes.c_size_t
        lib.gs_read.argtypes = [p, ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t]
        lib.gs_read.restype = ctypes.c_size_t
        lib.gs_sample_rate.argtypes = [p]
        err = ctypes.create_string_buffer(512)
        self.e = lib.gs_create(data.encode("mbcs"), err, 512)

    def say(self, text, tempo=1.0):
        self.lib.gs_set_rate(self.e, tempo)
        if self.lib.gs_speak(self.e, (text + " ").encode("ascii")) != 0:
            raise RuntimeError(text)
        n = self.lib.gs_pending(self.e)
        b = (ctypes.c_int16 * n)()
        got = self.lib.gs_read(self.e, b, n)
        return np.frombuffer(b, dtype=np.int16, count=got).copy(), self.lib.gs_sample_rate(self.e)


def trim(x, fs):
    """As the Gnuspeech add-on: 10 ms before the first sound, 30 ms after the last, at -60 dBFS."""
    idx = np.flatnonzero(np.abs(x) > 32768 * 10 ** (-60 / 20))
    if not len(idx):
        return x
    return x[max(0, idx[0] - fs // 100) : idx[-1] + fs * 30 // 1000]


def main():
    probe, data, gs_dll, gs_data, out = sys.argv[1:6]
    os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, "_t.wav")

    def gama(voice, text, tempo=1.0):
        subprocess.run([probe, "wav", data, voice, tmp, str(tempo), "0", "0", text], check=True, capture_output=True)
        x, fs = read(tmp)
        os.remove(tmp)
        return x, fs

    gs = Gnuspeech(gs_dll, gs_data)

    # A. The same sentences through each voice, at normal speed, with the varied intonation each ships with.
    x, fs = gs.say(SENTENCES)
    write(os.path.join(out, "A1-gnuspeech-addon-engine-male.wav"), x, fs)
    for name, voice in (("A2-gama-model0-male", "0_male"), ("A3-gama-model5-male", "5_male"),
                        ("A4-gama-model5-female", "5_female"), ("A5-gama-model5-large-child", "5_large_child"),
                        ("A6-gama-model5-small-child", "5_small_child"), ("A7-gama-model5-baby", "5_baby"),
                        ("A8-gama-model0-female", "0_female")):
        x, fs = gama(voice, SENTENCES)
        write(os.path.join(out, name + ".wav"), x, fs)

    # B. Model 5 male as the speed rises. Tempo 4 needs the scratch patch for short words; these are the same text.
    for t in (1.5, 2.0, 2.5, 3.0, 3.5, 4.0):
        x, fs = gama("5_male", SENTENCES, t)
        write(os.path.join(out, f"B-gama-model5-male-tempo-{t:.1f}.wav"), x, fs)
    x, fs = gs.say(SENTENCES, 3.0)
    write(os.path.join(out, "B-gnuspeech-male-tempo-3.0-for-comparison.wav"), x, fs)

    # C. What a screen reader mostly says: short items, with the add-on's trimming and 300 ms between them.
    def menu(utter, fs_hint=None):
        parts = []
        fs = None
        for item in MENU:
            x, fs = utter(item)
            parts += [trim(x, fs), np.zeros(fs * 300 // 1000, dtype=np.int16)]
        return np.concatenate(parts), fs

    for name, fn in (("C1-menu-gnuspeech-male", lambda i: gs.say(i)),
                     ("C2-menu-gama-model5-male", lambda i: gama("5_male", i)),
                     ("C3-menu-gama-model5-female", lambda i: gama("5_female", i)),
                     ("C4-menu-gama-model5-male-tempo-2.0", lambda i: gama("5_male", i, 2.0)),
                     ("C5-menu-gama-model5-male-tempo-3.0", lambda i: gama("5_male", i, 3.0))):
        x, fs = menu(fn)
        write(os.path.join(out, name + ".wav"), x, fs)


if __name__ == "__main__":
    main()
