"""Long unbroken tokens, each in a child process, through GamaTTS (probe) and Gnuspeech (DLL).

A screen reader meets these on real pages: base64 images, minified URLs, hashes.
Usage: python -I longtokens.py PROBE DATA GS_DLL GS_DATA OUTDIR
Public domain. Written 2026-11-02 for gama_tts docs/09.
"""
import base64
import ctypes
import hashlib
import os
import subprocess
import sys

GS_CHILD = r"""
import ctypes, sys
lib = ctypes.CDLL(sys.argv[1]); p = ctypes.c_void_p
lib.gs_create.restype = p; lib.gs_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
lib.gs_set_deterministic.argtypes = [p, ctypes.c_int]
lib.gs_speak.argtypes = [p, ctypes.c_char_p]
lib.gs_pending.argtypes = [p]; lib.gs_pending.restype = ctypes.c_size_t
err = ctypes.create_string_buffer(512)
e = lib.gs_create(sys.argv[2].encode("mbcs"), err, 512)
lib.gs_set_deterministic(e, 1)
text = open(sys.argv[3], "rb").read() + b" "
rc = lib.gs_speak(e, text)
print("rc", rc, "samples", lib.gs_pending(e))
"""


def cases():
    seed = hashlib.sha256(b"gama").digest()
    blob = base64.b64encode(seed * 400).decode()
    hexs = (seed.hex() * 300)
    out = []
    for n in (100, 500, 1000, 1023, 1024, 1100, 2000, 5000, 20000):
        out.append((f"letters-{n}", ("abcdefghij" * (n // 10 + 1))[:n]))
    for n in (1000, 1100, 2000, 5000):
        out.append((f"base64-{n}", blob[:n]))
        out.append((f"hex-{n}", hexs[:n]))
        out.append((f"digits-{n}", ("1234567890" * (n // 10 + 1))[:n]))
        out.append((f"caps-{n}", ("ABCDEFGHIJ" * (n // 10 + 1))[:n]))
    out.append(("url-2000", "https://example.com/" + "path-segment_" * 150))
    out.append(("words-20000", "The quick brown fox jumps over the lazy dog. " * 450))
    out.append(("words-nostop-20000", "the quick brown fox jumps over the lazy dog " * 450))
    return out


def status(rc):
    if rc == 0:
        return "ok"
    u = rc & 0xFFFFFFFF
    names = {0xC0000005: "ACCESS VIOLATION", 0xC0000409: "STACK BUFFER OVERRUN", 0xC00000FD: "STACK OVERFLOW",
             0xC0000374: "HEAP CORRUPTION", 3: "abort"}
    return f"CRASH {names.get(u, hex(u))}" if u not in (1,) else "error return"


def main():
    probe, data, gs_dll, gs_data, out = sys.argv[1:6]
    os.makedirs(out, exist_ok=True)
    print(f"{'case':24} {'GamaTTS (5_male)':34} Gnuspeech (DLL)")
    for name, text in cases():
        path = os.path.join(out, name + ".txt")
        with open(path, "w", encoding="ascii", newline="\n") as f:
            f.write(text + "\n")
        try:
            r = subprocess.run([probe, "lines", data, "5_male", path, "1", "0"], capture_output=True, text=True, timeout=120)
            tail = [x for x in r.stdout.splitlines() if x.strip()]
            note = ""
            if r.returncode == 0 and tail:
                note = "FAIL " + tail[-1].strip()[:18] if any(" FAIL " in x for x in tail) else "spoke"
            g = f"{status(r.returncode)} {note}"
        except subprocess.TimeoutExpired:
            g = "TIMEOUT 120 s"
        try:
            r = subprocess.run([sys.executable, "-I", "-c", GS_CHILD, gs_dll, gs_data, path], capture_output=True, text=True, timeout=120)
            s = f"{status(r.returncode)} {r.stdout.strip()[:30]}"
        except subprocess.TimeoutExpired:
            s = "TIMEOUT 120 s"
        print(f"{name:24} {g:34} {s}", flush=True)


if __name__ == "__main__":
    main()
