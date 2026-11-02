"""Does the long-token crash hold for the DLL inside Gnuspeech add-on 1.2.0 itself?

    python -I docs/measurements/gama5/check_shipped_gnuspeech.py <gnuspeech-1.2.0.nvda-addon> <workdir> [other dlls...]

Chapter 9 measured build/Release/gnuspeech_api.dll, which turned out to be older than 1.2.0. This
unpacks the package and runs each input in a child process, so that a crash names its input. It
also runs the same tempo sweep as gs_tempo.py on the short corpus lines that matter there.
Public domain. Written 2026-11-02.
"""

import hashlib
import os
import random
import subprocess
import sys
import tempfile
import zipfile

CHILD = r"""
import ctypes, sys
lib = ctypes.CDLL(sys.argv[1]); p = ctypes.c_void_p
lib.gs_create.restype = p; lib.gs_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
lib.gs_set_deterministic.argtypes = [p, ctypes.c_int]
lib.gs_set_rate.argtypes = [p, ctypes.c_double]
lib.gs_speak.argtypes = [p, ctypes.c_char_p]
lib.gs_pending.argtypes = [p]; lib.gs_pending.restype = ctypes.c_size_t
e = lib.gs_create(sys.argv[2].encode("mbcs"), None, 0)
lib.gs_set_deterministic(e, 1)
lib.gs_set_rate(e, float(sys.argv[4]))
try:
    rc = lib.gs_speak(e, open(sys.argv[3], "rb").read() + b" ")
    print("rc", rc, "samples", lib.gs_pending(e))
    sys.exit(0 if rc == 0 else 2)
except OSError:
    print("access violation")
    sys.exit(3)
"""


def status(rc):
	return {0: "spoke", 2: "refused", 3: "ACCESS VIOLATION"}.get(rc, f"PROCESS DIED {rc & 0xFFFFFFFF:#x}")


def main():
	addon, work = sys.argv[1:3]
	os.makedirs(work, exist_ok=True)
	with zipfile.ZipFile(addon) as z:
		z.extractall(work)
	dll = os.path.join(work, "synthDrivers", "gnuspeech_api.dll")
	data = os.path.join(work, "synthDrivers", "gnuspeech_data", "en")
	digest = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]  # noqa: E731
	print(f"package DLL {digest(dll)}, {os.path.getsize(dll)} bytes, dated {zipfile.ZipFile(addon).getinfo('synthDrivers/gnuspeech_api.dll').date_time}")
	for other in sys.argv[3:]:
		print(f"  against {other}: {digest(other)}, {os.path.getsize(other)} bytes, {'SAME' if digest(other) == digest(dll) else 'DIFFERENT'}")
	rng = random.Random(7)
	cases = [(f"{ch!r} x {n}", ch * n, 1.0) for ch, n in (("w", 100), ("w", 60), ("<", 24), ("<", 23), ("a", 1000), ("1", 256))]
	cases += [(f"{n} random consonants", "".join(rng.choice("bcdfghjklmnpqrstvwxz") for _ in range(n)), 1.0) for n in (128, 200, 400)]
	cases += [(f"{n} random hex", "".join(rng.choice("0123456789abcdef") for _ in range(n)), 1.0) for n in (400, 1000)]
	cases += [(f"{t!r} at tempo {tempo}", t, tempo) for t in ("OK", "a") for tempo in (3.9, 4.0, 6.0, 10.0)]
	fd, path = tempfile.mkstemp(suffix=".txt")
	os.close(fd)
	for name, text, tempo in cases:
		with open(path, "w", encoding="ascii", newline="\n") as f:
			f.write(text)
		r = subprocess.run([sys.executable, "-I", "-c", CHILD, dll, data, path, str(tempo)], capture_output=True, text=True, timeout=300)
		print(f"{name:32} {status(r.returncode):28} {r.stdout.strip()[:30]}", flush=True)
	os.remove(path)


if __name__ == "__main__":
	main()
