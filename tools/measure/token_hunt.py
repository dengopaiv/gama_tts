"""Each case of check_robustness's token stage, in a child process: which one kills it?"""
import os
import random
import string
import subprocess
import sys
import tempfile

CHILD = r"""
import ctypes, sys
p = ctypes.c_void_p
lib = ctypes.CDLL(sys.argv[1])
lib.gama_create.restype = p; lib.gama_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
lib.gama_set_deterministic.argtypes = [p, ctypes.c_int]
lib.gama_set_rate.argtypes = [p, ctypes.c_double]
lib.gama_text_to_phonetic.restype = ctypes.c_size_t
lib.gama_text_to_phonetic.argtypes = [p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
lib.gama_speak.argtypes = [p, ctypes.c_char_p]
lib.gama_last_error.restype = ctypes.c_char_p; lib.gama_last_error.argtypes = [p]
e = lib.gama_create(sys.argv[2].encode(), None, 0)
lib.gama_set_deterministic(e, 1); lib.gama_set_rate(e, 4.0)
data = open(sys.argv[3], "rb").read()
n = lib.gama_text_to_phonetic(e, data, None, 0)
print("parsed", n, flush=True)
rc = lib.gama_speak(e, data)
print("rc", rc, lib.gama_last_error(e), flush=True)
"""
ALPHABETS = {
	"lower": string.ascii_lowercase,
	"consonants": "bcdfghjklmnpqrstvwxz",
	"vowels": "aeiou",
	"upper": string.ascii_uppercase,
	"base64": string.ascii_letters + string.digits + "+/",
	"hex": "0123456789abcdef",
	"digits": string.digits,
	"mixed": string.ascii_letters + string.digits + "-_.~%&=?#:@!$'()*+,;[]{}|^`<>\\\"",
}


def main():
	dll, data = sys.argv[1:3]
	rng = random.Random(1)
	cases = []
	for name, alpha in ALPHABETS.items():
		for n in (64, 100, 101, 128, 200, 256, 400, 1000, 1024, 2000, 8000):
			cases.append((f"{name}-{n}", "".join(rng.choice(alpha) for _ in range(n))))
		for ch in alpha[:6]:
			cases.append((f"repeat {ch!r} 3000", ch * 3000))
	for ch in "wWmMeE1":
		for n in (100, 101, 500):
			cases.append((f"repeat {ch!r} {n}", ch * n))
	cases += [("url", "https://example.com/" + "path-segment_" * 400), ("sentences", "The quick brown fox. " * 300),
		("no stop", "the quick brown fox " * 300), ("numbers", " ".join(["1,234,567.89"] * 200))]
	fd, path = tempfile.mkstemp()
	os.close(fd)
	bad = 0
	for name, text in cases:
		open(path, "wb").write(text.encode())
		r = subprocess.run([sys.executable, "-I", "-c", CHILD, dll, data, path], capture_output=True, text=True, timeout=300)
		out = " | ".join(x for x in r.stdout.splitlines() if x.startswith(("parsed", "rc")))
		if r.returncode:
			bad += 1
			print(f"DEAD {name}: exit {r.returncode & 0xFFFFFFFF:#x}; {out}; head {text[:40]!r}", flush=True)
	print(f"{len(cases)} cases, {bad} dead")
	os.remove(path)


if __name__ == "__main__":
	main()
