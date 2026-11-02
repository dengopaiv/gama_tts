"""Which configuration keys reach the sound?

Changes one key at a time in a private copy of the data, renders one sentence with
randomness off through the unmodified probe, and compares it with the baseline.
Usage: python -I perturb.py PROBE DATA_COPY VOICE
Public domain. Written 2026-11-02 for gama_tts docs/09.
"""
import filecmp
import os
import re
import shutil
import subprocess
import sys
import tempfile

PROBE, DATA, VOICE = sys.argv[1:4]
TEXT = "The quick brown fox jumps over the lazy dog. Is it, she asked, 25 percent?"
KEY = re.compile(r"^(\w[\w-]*)\s*=\s*(.+?)\s*$")


def render(out):
    r = subprocess.run([PROBE, "wav", DATA, VOICE, out, "1", "0", "1", TEXT], capture_output=True, text=True)
    return r.returncode, (r.stdout.strip().splitlines() or [""])[-1]


def changed(key, value):
    if key == "variant_name":
        return "female" if value != "female" else "male"
    if key == "control_period":
        return "2"
    if key == "phonetic_string_format":
        return None
    if key == "model":
        return None
    if value in ("true", "false"):
        return "false" if value == "true" else "true"
    if key in ("micro_intonation", "macro_intonation", "smooth_intonation", "intonation_drift",
               "random_intonation", "noise_modulation", "waveform", "bypass"):
        return "0" if value != "0" else "1"
    try:
        v = float(value)
    except ValueError:
        return None
    if key == "output_rate":
        return "44100.0"
    return repr(v * 1.15 if v else 1.0)


root = os.path.join(DATA, "voice", "english", VOICE)
index = dict(m.groups() for m in (KEY.match(x) for x in open(os.path.join(root, "_index.txt"))) if m)
ctl_path = os.path.normpath(os.path.join(root, index["vtm_control_model_file"]))
vtm_path = os.path.normpath(os.path.join(root, index["vtm_file"]))
ctl = dict(m.groups() for m in (KEY.match(x) for x in open(ctl_path)) if m)
var_path = os.path.normpath(os.path.join(root, index["variant_dir"], ctl["variant_name"] + ".txt"))

tmp = tempfile.mkdtemp(prefix="perturb")
base = os.path.join(tmp, "base.wav")
print("baseline:", render(base))
print(f"{'file':8} {'key':34} {'from':>10} {'to':>10}  result")
reach = silent = 0
for label, path in (("control", ctl_path), ("vtm", vtm_path), ("variant", var_path)):
    original = open(path, newline="").read()
    for line in original.split("\n"):
        m = KEY.match(line)
        if not m:
            continue
        key, value = m.groups()
        new = changed(key, value)
        if new is None:
            print(f"{label:8} {key:34} {value:>10} {'-':>10}  skipped")
            continue
        try:
            open(path, "w", newline="").write(original.replace(line, f"{key} = {new}", 1))
            out = os.path.join(tmp, "t.wav")
            if os.path.exists(out):
                os.remove(out)
            rc, msg = render(out)
            if rc != 0 or not os.path.exists(out):
                print(f"{label:8} {key:34} {value:>10} {new:>10}  FAILED rc={rc}: {msg[:70]}")
            elif filecmp.cmp(base, out, shallow=False):
                silent += 1
                print(f"{label:8} {key:34} {value:>10} {new:>10}  no effect")
            else:
                reach += 1
                print(f"{label:8} {key:34} {value:>10} {new:>10}  changes the sound")
        finally:
            open(path, "w", newline="").write(original)
print(f"reach the sound: {reach}; no effect: {silent}")
shutil.rmtree(tmp, ignore_errors=True)
