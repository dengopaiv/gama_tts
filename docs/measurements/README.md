# Measurement scripts

Used for [chapter A](../07-measurements.md). All three files are public
domain.

| File | What it does |
|---|---|
| `run_all.sh` | Reproduces every measurement: LF data export, deterministic voice copies, phonetic strings, parameter tracks, tube comparisons, internal rates, repeatability across builds, speed. Writes only into the scratch directory given as its first argument. |
| `compare_params.py` | Frame-by-frame comparison of two 16-parameter files (GnuspeechSA's or GamaTTS's format). |
| `compare_wav.py` | Aligns WAV files to a reference, removes the gain, and reports correlation, SNR and identical samples. With `--bands` it adds per-band level and coherence, plus a list of 50 ms stretches that do not match. |
| `results-2026-10-16.txt` | The output of `run_all.sh` behind chapter A. |

Requirements: a POSIX shell (Git Bash works), Python 3 with numpy, git, tar.
To compare against GnuspeechSA you need an unmodified build of GnuspeechSA
0.1.5 (`gnuspeech_sa`, `gnuspeech_sa_trm`) and its `data/en` directory.

Example, from the repository root in Git Bash:

```sh
export PATH=/c/msys64/ucrt64/bin:$PATH          # runtime DLLs of a MinGW build
PYTHON=python sh docs/measurements/run_all.sh /tmp/gama-work \
    build-gcc/gama_tts.exe build-msvc/Release/gama_tts.exe \
    /path/to/gnuspeech_sa.exe /path/to/gnuspeech_sa_trm.exe /path/to/gnuspeechsa/data/en
```

Pass `-` as the second executable to skip the build comparison.
