"""Which spelled runs really overflow the unguarded parser? Chapter 10 had calculated this from a table.

    python -I docs/measurements/gama5/check_spelling_limit.py <probe.exe over the unchanged engine> <data>

Runs the parser alone (`probe ph`) in a child process per input. Public domain. Written 2026-11-02.
"""

import subprocess
import sys

CASES = [("w", n) for n in (50, 55, 58, 60, 61, 62, 65, 70, 80, 100)]
CASES += [("<", n) for n in (24, 100, 1000)]
CASES += [("b" + "<", n) for n in (10, 12, 13, 20, 50)]  # a letter in it, so that it is a word
CASES += [("b" + "(", n) for n in (10, 14, 20, 50)]
CASES += [("B", n) for n in (100, 150, 200)]


def main():
	probe, data = sys.argv[1:3]
	print(f"{'token':24} {'chars':>6}  result")
	for unit, n in CASES:
		tok = unit * n
		r = subprocess.run([probe, "ph", data, "5_male", tok], capture_output=True, text=True, errors="replace", timeout=60)
		code = r.returncode & 0xFFFFFFFF
		what = {0: "parsed", 0xC0000409: "PROCESS DIED: stack buffer overrun or an uncaught exception", 0xC0000005: "PROCESS DIED: access violation"}.get(code, f"exit {code:#x}")
		print(f"{unit!r} x {n:<16} {len(tok):6d}  {what}", flush=True)


if __name__ == "__main__":
	main()
