"""Golden traces from the unchanged GamaTTS engine, model 5.

Runs upstream's own command-line program, gama_tts, once per corpus line, with
random intonation and intonation drift switched off, so that the same text always
gives the same samples. For each line it records a SHA-256 of the PCM samples and of
the VTM parameter file, the sample count and the peak.

It refuses to run if gama_tts/ or data/ differ from upstream's b108ad6, so the
reference can only come from the engine as released. It takes the data with LF line
endings from git, since the engine refuses CRLF. It runs everything twice, in fresh
processes, and writes nothing unless the two runs agree.

Usage, from the repository root, with a gama_tts built from the unchanged source:
    python -I tools/golden/make_golden.py <gama_tts.exe> <label>

Writes tests/golden/<label>.tsv. Work files go to build-golden/, which git ignores.

Adapted from GnuspeechSA-NVDA's tools/golden/make_golden.py.
Copyright 2026 dengopaiv. GPL-3.0-or-later.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS = os.path.join(ROOT, "tests", "golden", "corpus.txt")
UPSTREAM = "b108ad6"

#: Every voice at normal speed; the male voice at the higher tempos the patch must not change.
RUNS = (
    ("5_male", 1.0), ("5_female", 1.0), ("5_large_child", 1.0), ("5_small_child", 1.0), ("5_baby", 1.0),
    ("5_male", 2.0), ("5_male", 3.0), ("5_male", 3.5),
)


def check_pristine():
    r = subprocess.run(["git", "-C", ROOT, "diff", "--quiet", UPSTREAM, "--", "gama_tts", "data"])
    if r.returncode != 0:
        sys.exit(f"gama_tts/ or data/ differ from {UPSTREAM}: golden traces must come from the released engine.")


def read_corpus():
    lines = []
    with open(CORPUS, encoding="ascii") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            if line.strip() and not line.startswith("#"):
                lines.append(line)
    return lines


def export_data(work):
    """The data as git holds it, LF endings, whatever this checkout's are."""
    dest = os.path.join(work, "data")
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    archive = os.path.join(work, "data.tar")
    subprocess.run(["git", "-C", ROOT, "-c", "core.autocrlf=false", "archive", "-o", archive, UPSTREAM, "data"], check=True)
    with tarfile.open(archive) as t:
        t.extractall(work, filter="data")
    os.remove(archive)
    return dest


def set_control(data, voice, tempo):
    """Randomness off and the tempo set, in this voice's vtm_control_model.txt."""
    path = os.path.join(data, "voice", "english", voice, "vtm_control_model.txt")
    wanted = {"intonation_drift": "0", "random_intonation": "0", "tempo": repr(tempo)}
    with open(path, encoding="ascii", newline="") as f:
        lines = f.read().split("\n")
    seen = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in wanted and not line.startswith("#"):
            lines[i] = f"{key} = {wanted[key]}"
            seen.add(key)
    if seen != set(wanted):
        sys.exit(f"could not find {set(wanted) - seen} in {path}")
    with open(path, "w", encoding="ascii", newline="") as f:
        f.write("\n".join(lines))


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def run_once(exe, data, work, lines):
    rows = []
    for voice, tempo in RUNS:
        set_control(data, voice, tempo)
        voice_dir = os.path.join(data, "voice", "english", voice)
        for i, text in enumerate(lines, 1):
            wav = os.path.join(work, "t.wav")
            vtm = os.path.join(work, "t.vtm")
            txt = os.path.join(work, "t.txt")
            for p in (wav, vtm):
                if os.path.exists(p):
                    os.remove(p)
            # Through -i, not as an argument: Windows passes arguments through the
            # ANSI code page, and MinGW's runtime expands wildcards in them. gama_tts
            # appends a space to each line, so the engine sees text + " ".
            with open(txt, "wb") as f:
                f.write(text.encode("ascii") + b"\n")
            r = subprocess.run([exe, "tts", "-i", txt, "-p", vtm, voice_dir, wav], capture_output=True)
            if r.returncode != 0 or not os.path.exists(wav):
                rows.append((voice, tempo, i, "FAIL", "", 0, 0, "", text))
                continue
            with wave.open(wav, "rb") as w:
                assert w.getnchannels() == 1 and w.getsampwidth() == 2
                rate = w.getframerate()
                pcm = w.readframes(w.getnframes())
            n = len(pcm) // 2
            peak = max((abs(int.from_bytes(pcm[k : k + 2], "little", signed=True)) for k in range(0, len(pcm), 2)), default=0)
            rows.append((voice, tempo, i, hashlib.sha256(pcm).hexdigest(), sha256_file(vtm), n, peak, rate, text))
        set_control(data, voice, 1.0)
        print(f"  {voice} at tempo {tempo}: done", flush=True)
    return rows


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    exe, label = os.path.abspath(sys.argv[1]), sys.argv[2]
    check_pristine()
    lines = read_corpus()
    work = os.path.join(ROOT, "build-golden", label)
    os.makedirs(work, exist_ok=True)
    data = export_data(work)

    first = run_once(exe, data, work, lines)
    second = run_once(exe, data, work, lines)
    if first != second:
        bad = [a[:3] for a, b in zip(first, second) if a != b]
        sys.exit(f"not deterministic: {bad[:10]} differ between two runs")

    out = os.path.join(ROOT, "tests", "golden", f"{label}.tsv")
    with open(out, "w", encoding="ascii", newline="\n") as f:
        f.write(f"# Golden traces: GamaTTS at {UPSTREAM}, gama_tts command line, label {label}\n")
        f.write(f"# gama_tts/ and data/ identical to {UPSTREAM}; intonation_drift = 0, random_intonation = 0; two runs identical.\n")
        f.write("# Text is passed with -i (one line per file), so the engine sees text + ' '.\n")
        f.write("voice\ttempo\tid\tpcm_sha256\tvtm_sha256\tsamples\tpeak\trate\ttext\n")
        for voice, tempo, i, pcm, vtm, n, peak, rate, text in first:
            f.write(f"{voice}\t{tempo}\t{i}\t{pcm}\t{vtm}\t{n}\t{peak}\t{rate}\t{text}\n")
    fails = sum(1 for r in first if r[3] == "FAIL")
    print(f"{len(first)} utterances, {fails} produced no audio, two runs identical -> {out}")


if __name__ == "__main__":
    main()
