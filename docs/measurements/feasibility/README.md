# Measurements for chapter 9: can it become an add-on and a GUI?

Behind [`../../09-addon-and-gui-feasibility.md`](../../09-addon-and-gui-feasibility.md). Taken on 2026-11-02
at `b108ad6`, on Windows 11 x64, with Visual Studio 2026 (MSVC 19.51), CMake 4.4.

Nothing here changes the engine. The scripts are public domain. A `probe.exe`, once built, links
`libgamatts` and so is GPL-3.0-or-later like the engine.

| File | What it is |
|---|---|
| `results-2026-11-02.txt` | The output of `run_feasibility.sh`: every number in chapter 9 except the robustness ones |
| `results-robustness-2026-11-02.txt` | Long tokens and fuzzing, as they came out |
| `results-safe-token-2026-11-02.txt` | The table of token lengths under AddressSanitizer |
| `run_feasibility.sh` | Runs the main measurements, one after another |
| `probe.cpp`, `CMakeLists.txt` | The harness: one long-lived engine, many utterances, every exception caught and counted |
| `engine-fixes.patch` | Three small fixes in two files, **tried only on scratch copies**. Not applied to this repository |
| `perturb.py` | Changes each configuration key by itself and compares the WAV with a baseline |
| `gs_tempo.py` | Gnuspeech's DLL through the same tempos, one process per tempo |
| `audio_metrics.py` | Level, spectral balance, edge silence, by the method of Gnuspeech's `tools/measure/loudness.py` |
| `longtokens.py` | Long tokens through both engines, one process per token |
| `safe_token.py` | The parser under ASan: the first token length with a memory error, per alphabet |
| `guard_check.py` | Tokens broken every 100 characters under ASan; and where Gnuspeech's DLL first fails |
| `make_kit.py` | The listening files in `build-listening/`, which git ignores |

## Building

Git Bash, from the root of this repository. Two builds, outside it:

```sh
M=docs/measurements/feasibility
cmake -S $M -B /tmp/plain -G "Visual Studio 18 2026" -A x64
cmake --build /tmp/plain --config Release --target probe

# The same over a patched copy of the engine:
mkdir /tmp/patched && git -c core.autocrlf=false archive HEAD gama_tts | tar -x -C /tmp/patched
(cd /tmp/patched && patch -p1 < "$OLDPWD/$M/engine-fixes.patch")
cmake -S $M -B /tmp/fixed -G "Visual Studio 18 2026" -A x64 -DGAMA=C:/path/to/patched/gama_tts
cmake --build /tmp/fixed --config Release --target probe
```

The data must have LF line endings ([chapter 6](../../06-building-and-running.md)). The script exports it itself.

## Running

```sh
sh $M/run_feasibility.sh WORK /tmp/plain/Release/probe.exe /tmp/fixed/Release/probe.exe ../GnuspeechSA-NVDA > results.txt
```

It takes about half an hour. Nothing else should be running, since section 2 times things. It needs a
built `GnuspeechSA-NVDA` and its `dist/listening/5-menu-espeak-klatt5.wav`.

## The AddressSanitizer build

Flags are written with `-`, because Git Bash rewrites `/fsanitize` as a path:

```sh
cmake -S $M -B /tmp/asan -G "Visual Studio 18 2026" -A x64 -DGAMA=C:/path/to/patched/gama_tts \
  "-DCMAKE_CXX_FLAGS=-fsanitize=address -Zi -EHsc -DWIN32 -D_WINDOWS" \
  "-DCMAKE_CXX_FLAGS_RELWITHDEBINFO=-O1 -DNDEBUG -Zi" "-DCMAKE_EXE_LINKER_FLAGS=-DEBUG -INCREMENTAL:NO"
cmake --build /tmp/asan --config RelWithDebInfo --target probe
export PATH="<VC>/Tools/MSVC/<version>/bin/Hostx64/x64:$PATH"     # for clang_rt.asan_dynamic-x86_64.dll
export ASAN_OPTIONS=symbolize=1:halt_on_error=1 PROBE_STDERR=1    # PROBE_STDERR keeps ASan's report
```

Then:

```sh
probe fuzz DATA 5_male SEED COUNT MODE lastinput.txt    # mode 0 printable ASCII, 1 any bytes, 2 screen-reader fragments
python -I safe_token.py ASAN_PROBE DATA ASAN_BIN_DIR
python -I guard_check.py ASAN_PROBE DATA ASAN_BIN_DIR GS_DLL GS_DATA
python -I longtokens.py PROBE DATA GS_DLL GS_DATA OUTDIR
```

`fuzz` writes each input, in hex, to `lastinput.txt` before trying it, so a crash leaves its input behind. Under
ASan it manages about 3 to 6 utterances a second, so it was given a time limit, and exit 124 in the results is that
limit.

`results-robustness-2026-11-02.txt` section A says "error return" for Gnuspeech where the child Python process
exited with 1. That is an access violation, which `ctypes` turned into an `OSError`; `guard_check.py` labels it
`AV`. Checked by hand on `hex-1000`: `OSError: exception: access violation reading 0x000000AFF2141D55`.

## The probe's commands

`probe <command> DATA ...`, where DATA is the `data` folder with LF endings:

| Command | Does |
|---|---|
| `load VOICE...` | Load time per voice |
| `corpus VOICE FILE TEMPO PITCH DET` | Synthesise a file of lines; report failures, NaN, silence, speed |
| `sweep VOICE FILE TEMPO...` | The same at each tempo, randomness off |
| `pitchsweep VOICE FILE SEMITONES...` | The same at each pitch offset |
| `lines VOICE FILE TEMPO PITCH` | One line of output per utterance, flushed first, so a crash names its input |
| `track VOICE FILE ROUNDS DET TEMPO...` | The rule engine only. Non-finite and wild values in the parameter track |
| `dump VOICE TEXT TEMPO` | Intonation points, interpolation data and the pitch track of one text |
| `repeat VOICE TEXT` | The same text twice on one engine, and once on a fresh one |
| `threads VOICE FILE` | Two engines on two threads, against one engine alone |
| `leak VOICE FILE ROUNDS` | Working set over many rounds |
| `ownloop VOICE TEXT` | A wrapper's own tube and loop, against the Controller; recovery after exceptions |
| `fuzz VOICE SEED COUNT MODE FILE` | Random input |
| `wav VOICE OUT TEMPO PITCH DET TEXT` | One WAV. `wavs` does one per line of a file. `wavcfg` overrides nothing in the configuration |
| `ph VOICE TEXT` | The parser alone: print the phonetic string |
