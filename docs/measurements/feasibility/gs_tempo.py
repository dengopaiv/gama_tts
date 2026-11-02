"""Does the shipped Gnuspeech engine (gnuspeech_api.dll) survive the same inputs?

Reads nothing back into the repository. Each tempo runs in a child process, so a
crash names its tempo and input. Usage: python -I gs_tempo.py DLL DATA CORPUS
"""
import ctypes
import subprocess
import sys


def child(dll, data, corpus, tempo):
    lib = ctypes.CDLL(dll)
    p = ctypes.c_void_p
    lib.gs_create.restype = p
    lib.gs_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
    lib.gs_set_rate.argtypes = [p, ctypes.c_double]
    lib.gs_set_deterministic.argtypes = [p, ctypes.c_int]
    lib.gs_speak.argtypes = [p, ctypes.c_char_p]
    lib.gs_pending.argtypes = [p]
    lib.gs_pending.restype = ctypes.c_size_t
    lib.gs_read.argtypes = [p, ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t]
    lib.gs_read.restype = ctypes.c_size_t
    err = ctypes.create_string_buffer(512)
    e = lib.gs_create(data.encode("mbcs"), err, 512)
    if not e:
        print("create failed", err.value)
        return 3
    lib.gs_set_rate(e, tempo)
    lib.gs_set_deterministic(e, 1)
    ok = fail = silent = 0
    for line in open(corpus, encoding="ascii"):
        line = line.rstrip("\r\n")
        if not line or line.startswith("#"):
            continue
        print("@", line[:50], flush=True)
        rc = lib.gs_speak(e, (line + " ").encode("ascii"))
        if rc != 0:
            fail += 1
            continue
        n = lib.gs_pending(e)
        buf = (ctypes.c_int16 * n)()
        got = lib.gs_read(e, buf, n)
        if not any(buf[:got]):
            silent += 1
        ok += 1
    print(f"RESULT tempo={tempo} ok={ok} fail={fail} silent={silent}", flush=True)
    return 0


if __name__ == "__main__":
    if sys.argv[1] == "--child":
        sys.exit(child(sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5])))
    dll, data, corpus = sys.argv[1:4]
    for t in (1.0, 2.0, 3.0, 3.8, 4.0, 5.0, 6.0, 8.0, 10.0):
        r = subprocess.run(
            [sys.executable, "-I", __file__, "--child", dll, data, corpus, str(t)],
            capture_output=True, text=True, timeout=300,
        )
        lines = [x for x in r.stdout.splitlines() if x.startswith(("@", "RESULT"))]
        last = lines[-1] if lines else "(no output)"
        print(f"tempo {t}: exit={r.returncode} last: {last}")
