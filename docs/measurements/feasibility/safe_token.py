"""Find the longest token the text parser handles without a memory error, under AddressSanitizer.

Runs the parser only (no tube), one process per token, so each crash names its token.
Usage: python -I safe_token.py ASAN_PROBE DATA ASAN_BIN_DIR
Public domain. Written 2026-11-02 for gama_tts docs/09.
"""
import os
import random
import string
import subprocess
import sys

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
LENGTHS = (32, 64, 100, 128, 200, 256, 300, 400, 500, 600, 800, 1000)


def main():
    probe, data, bindir = sys.argv[1:4]
    env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"], PROBE_STDERR="1",
               ASAN_OPTIONS="symbolize=1:halt_on_error=1")
    rng = random.Random(20261102)
    print(f"{'alphabet':10}" + "".join(f"{n:>7}" for n in LENGTHS))
    sites = {}
    for name, alpha in ALPHABETS.items():
        row = []
        for n in LENGTHS:
            worst = "ok"
            for _ in range(3):
                tok = "".join(rng.choice(alpha) for _ in range(n))
                r = subprocess.run([probe, "ph", data, "5_male", tok], capture_output=True, text=True, env=env,
                                   errors="replace", timeout=120)
                if "AddressSanitizer" in r.stderr:
                    worst = "ASAN"
                    lines = [x.strip() for x in r.stderr.splitlines()]
                    kind = next((x for x in lines if "ERROR: AddressSanitizer" in x), "?").split("AddressSanitizer: ")[-1].split(" on ")[0]
                    frame = next((x for x in lines if x.startswith("#0")), "?")
                    fn = frame.split(" in ")[-1].split("(")[0].strip() if " in " in frame else "?"
                    if "::" not in fn or "__asan" in fn or fn.startswith("str") or "sprintf" in fn or "strcpy" in fn:
                        frame = next((x for x in lines if x.startswith("#1")), frame)
                        fn = frame.split(" in ")[-1].split("(")[0].strip() if " in " in frame else fn
                    sites.setdefault((kind, fn), []).append((name, n))
                    break
                if r.returncode != 0 and worst == "ok":
                    worst = "exc"
            row.append(worst)
        print(f"{name:10}" + "".join(f"{x:>7}" for x in row), flush=True)
    print("ok = parsed; exc = a C++ exception (would be an error return in an API); ASAN = a memory error")
    for (kind, fn), where in sorted(sites.items(), key=lambda kv: min(w[1] for w in kv[1])):
        low = min(where, key=lambda w: w[1])
        print(f"{kind:28} {fn:60} first at {low[1]} chars ({low[0]}); {len(where)} cases")


if __name__ == "__main__":
    main()
