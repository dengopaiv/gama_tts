"""Two checks on the long-token hazard.

1. With tokens broken every 100 characters, does the GamaTTS parser stay clean under ASan?
2. At what length does the shipped Gnuspeech DLL (no ASan) first fail?

Usage: python -I guard_check.py ASAN_PROBE DATA ASAN_BIN_DIR GS_DLL GS_DATA
Public domain. Written 2026-11-02 for gama_tts docs/09.
"""
import os
import random
import string
import subprocess
import sys
import tempfile

ALPHABETS = {
    "lower": string.ascii_lowercase,
    "vowelless": "bcdfghjklmnpqrstvwxz",
    "vowels": "aeiou",
    "upper": string.ascii_uppercase,
    "base64": string.ascii_letters + string.digits + "+/",
    "hex": "0123456789abcdef",
    "digits": string.digits,
    "mixed": string.ascii_letters + string.digits + "-_.~%&=?#:@!$'()*+,;[]{}|^`<>\\\"",
}
GS_CHILD = r"""
import ctypes, sys
lib = ctypes.CDLL(sys.argv[1]); p = ctypes.c_void_p
lib.gs_create.restype = p; lib.gs_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
lib.gs_set_deterministic.argtypes = [p, ctypes.c_int]
lib.gs_speak.argtypes = [p, ctypes.c_char_p]
err = ctypes.create_string_buffer(512)
e = lib.gs_create(sys.argv[2].encode("mbcs"), err, 512)
lib.gs_set_deterministic(e, 1)
try:
    rc = lib.gs_speak(e, open(sys.argv[3], "rb").read() + b" ")
    sys.exit(0 if rc == 0 else 2)
except OSError:
    sys.exit(3)
"""


def guard(tok, n=100):
    return " ".join(tok[i : i + n] for i in range(0, len(tok), n))


def main():
    probe, data, bindir, dll, gs_data = sys.argv[1:6]
    env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"], PROBE_STDERR="1",
               ASAN_OPTIONS="symbolize=1:halt_on_error=1")
    rng = random.Random(7)

    print("== 1. GamaTTS parser under ASan, tokens broken every 100 characters")
    print(f"{'alphabet':10} {'cases':>6} {'clean':>6} {'exc':>5} {'ASAN':>5}")
    for name, alpha in ALPHABETS.items():
        clean = exc = asan = 0
        for n in (500, 2000, 8000):
            for _ in range(2):
                tok = "".join(rng.choice(alpha) for _ in range(n))
                r = subprocess.run([probe, "ph", data, "5_male", guard(tok)], capture_output=True, text=True,
                                   env=env, errors="replace", timeout=180)
                if "AddressSanitizer" in r.stderr:
                    asan += 1
                elif r.returncode:
                    exc += 1
                else:
                    clean += 1
        print(f"{name:10} {clean + exc + asan:6d} {clean:6d} {exc:5d} {asan:5d}", flush=True)

    print("== 2. The shipped Gnuspeech DLL, no ASan: three tokens at each length")
    print("   . all spoke; e = error return; AV = access violation (ctypes turns it into OSError); DEAD = process killed")
    lengths = (64, 128, 200, 256, 300, 400, 500, 600, 800, 1000, 1500)
    print(f"{'alphabet':10}" + "".join(f"{n:>6}" for n in lengths))
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    for name, alpha in ALPHABETS.items():
        row = []
        for n in lengths:
            worst = "."
            for _ in range(3):
                with open(path, "w", encoding="ascii", newline="\n") as f:
                    f.write("".join(rng.choice(alpha) for _ in range(n)))
                r = subprocess.run([sys.executable, "-I", "-c", GS_CHILD, dll, gs_data, path], capture_output=True, timeout=180)
                if r.returncode == 3:
                    worst = "AV"
                elif r.returncode == 2:
                    worst = "e" if worst == "." else worst
                elif r.returncode != 0:
                    worst = "DEAD"
                    break
            row.append(worst)
        print(f"{name:10}" + "".join(f"{x:>6}" for x in row), flush=True)
    os.remove(path)


if __name__ == "__main__":
    main()
