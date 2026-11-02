# 10. Building model 5: the API, the GUI and the add-on

*To use them, see [chapter 11](11-using-it.md). For every step in order and every failed attempt, [chapter 12](12-record-of-2026-11-02.md).*

Started 2026-11-02, when the author, having listened to the files of
[chapter 9](09-addon-and-gui-feasibility.md), said: "Model 5 needs to be built, it's better in sound and
clarity than the original gnuspeech." That settled decision 1 and decision 6 of that chapter: **model 5's five
voices only**. This chapter is the record of what was built, and how it was checked.

**Status: built and tested from outside, not yet used in NVDA.** Add-on 0.1.0 is a test build. It has not been
inside NVDA, so its manifest's `lastTestedNVDAVersion` is the intended version and not yet a fact. A person has not used the
GUI with NVDA either.

**Where it is:** the branch `model5` of the public fork, by the author's decision of 2026-11-02. `master` stays level with upstream. The code is adapted from
`GnuspeechSA-NVDA`, whose own repository stays private. No packaged add-on or built program is in the repository: `package.py` and the build below make them.

## The decisions, and who made them

| Date | Decision | By | Words, where they were recorded |
|---|---|---|---|
| 2026-11-02 | The fork stays public | The author | "I guess this stays public." The fork already existed, so there was nothing to create |
| 2026-11-02 | Build model 5, and no other | The author, by ear, after the files of `build-listening/` | "Model 5 needs to be built, it's better in sound and clarity than the original gnuspeech." |
| 2026-11-02 | Publish this work, though it comes from the private Gnuspeech add-on | The author | "I think we may push it." Taken to mean this work on this fork, and not that repository, which stayed private |
| 2026-11-02 | `docs/` goes too | Claude, on that sentence, since the README and `NOTICE.md` point to it. **Said so to the author, who has not objected and can still reverse it.** | |
| 2026-11-02 | A branch, not `master`, which stays level with upstream | Claude, following this collection's habit | |
| 2026-11-02 | No built add-on or program in the repository | Claude: `package.py` makes them, and a release should wait for a test in NVDA | |
| 2026-11-02 | Everything documented before anything further is done | The author | "First document everything." |

Engineering choices, all open to change: a C API over the unchanged C++ engine (`docs/09`, section 6); a tube of the API's own; wxWidgets, as Gnuspeech's GUI; Steady throughout as the default, as Gnuspeech's add-on; the driver's rate curve unchanged. The levelling's constant was measured again. Trimming's were not.

**Not done, on purpose:** testing inside NVDA, since that means restarting the screen reader the author is using; merging to `master`; sending anything upstream; and any change to Gnuspeech's code, whose problems are recorded in its `docs/09`, items 14 and 15.

## What was pushed

To `dengopaiv/gama_tts`, branch `model5`, three commits on upstream's `b108ad6`: `4dfc1c8` (the engine's fixes, `.gitattributes`), `302d8bd` (the API, GUI, add-on, tests, tools) and `28eef40` (`docs/`). A fourth commit followed the same day, on the author's "Commit and push.": everything in `docs/` since, the READMEs of `gui/`, `nvda-addon/`, `tests/` and `tools/`, the measurement scripts, and the corrections of comments in `api/` and `tests/`. Later changes are in `git log`, which is the truth.

**Before the push,** per the head directory's rule: 66 files, none of them a binary, a ROM, audio or an archive (`git diff --name-only`, by extension, and by size). No local paths, and no email address of ours but the commits' own author line. Other private projects of ours are named, and not described: two passages that said too much about them were reworded first. **After it,** a fresh clone with `core.autocrlf=true` built and passed the C tests, the golden traces and the driver test.

**Before the fourth commit,** the same scan over its 55 paths: no binary, ROM, audio or archive, no user name, no email address and no secret. It found one thing, F31 in chapter 12: logs described as having their paths replaced still held them. Those were cleaned first. The scripts in `measurements/gama5/port/` keep theirs, as their README says. Private projects are named as before: `IveHeardOfWildebeest`, which `NOTICE.md` already named, and Tawkative.

## What is here

| Path | What it is |
|---|---|
| `gama_tts/` | The engine, with the patch of [section 2](#2-the-engine-patch). Nothing else differs from upstream `b108ad6` |
| `api/gama_api.h`, `.cpp` | The C API: `gama_api.dll`, 64-bit, static runtime, depending only on `KERNEL32.dll` |
| `gui/gama_gui.cpp` | The desktop GUI, C++17 and wxWidgets, over the API |
| `nvda-addon/` | The driver `addon/synthDrivers/gamatts.py`, `manifest.ini`, `package.py` |
| `tests/api/` | `api_test.c`, `check_golden.py`, `check_robustness.py`, `check_leveling.py` |
| `tests/nvda/test_driver.py` | The driver, with stand-ins for NVDA |
| `tests/gui/gui_check.py` | The GUI from outside, through MSAA, on a private desktop |
| `tests/golden/` | The corpus, and the frozen output of the unchanged engine |
| `tools/` | The scripts that make and measure things: [tools/README.md](../tools/README.md) |
| `docs/measurements/gama5/` | The results behind this chapter, and the scripts that derived the code: [README](measurements/gama5/README.md) |
| `CMakeLists.txt` | The root build. Upstream's own builds are not touched by it |
| `.gitattributes` | Keeps `data/` byte for byte, since the engine refuses CRLF |
| `NOTICE.md` | Who made what |

## Building and testing

Windows, x64. Everything is 64-bit, and the root `CMakeLists.txt` refuses to configure otherwise.

```sh
cmake -S . -B build-x64 -G "Visual Studio 18 2026" -A x64 -DGAMA_BUILD_GUI=OFF
cmake --build build-x64 --config Release
ctest --test-dir build-x64 -C Release --output-on-failure

# With the GUI (wxWidgets from vcpkg):
cmake -S . -B build-gui -G "Visual Studio 18 2026" -A x64 \
      -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake -DVCPKG_TARGET_TRIPLET=x64-windows
cmake --build build-gui --config Release --target gama_gui
build-gui/Release/gama_gui.exe

# The add-on: builds, runs every test, packages, then tests the package unzipped.
python -I nvda-addon/package.py
```

`git status` shows nothing of these, since `.gitignore` has `/build-*` and the packaged add-on.

**A checkout made before `.gitattributes` existed has CRLF in `data/`.** After adding it: `rm -rf data; git checkout -- data`.
That was done here, with `git diff --quiet -- data` first, to be sure nothing was lost.

## 0. The listening test that started this

`docs/measurements/feasibility/make_kit.py` made 20 files, in `build-listening/`, which git ignores: the same sentences through each voice and through the Gnuspeech add-on's engine, model 5 male at rising tempos, and 30 short screen-reader items. `build-listening/README.txt` is the guide. All were made with the patched engine, varied intonation, and the engine's own peak levelling. The author listened and chose. That is the only judgement by ear so far, and it was of the voice in those files: not of steady loudness, trimming or the rates.

## 1. The order, and why

1. **Golden traces first,** from the unchanged engine, before any change to it.
2. **Then the patch,** checked against them.
3. **Then the API,** checked against them too.

That order is what lets this chapter say the patch changes no sample at normal speed, rather than hope so.

## 2. The engine patch

`docs/measurements/feasibility/engine-fixes.patch` holds the first two, applied to `gama_tts/src/`; [chapter 9](09-addon-and-gui-feasibility.md) gives their
causes. The third came from running the robustness test under ASan ([section 5](#5-long-tokens-the-guard-that-was-wrong-first)). `git diff b108ad6 -- gama_tts` shows them all: four fixes in three files.

- `EventList.cpp`: intonation points sorted by time; two divisions by a zero time guarded.
- `IspTrans.cpp`: a bounds check on the trie.
- `ApplyStress.cpp`: `light()` stops at the end of a syllable with no vowel.

## 3. Golden traces

`python -I tools/golden/make_golden.py <gama_tts.exe> msvc-x64`, with `gama_tts` built from the source at `b108ad6`.

- **It refuses to run** if `gama_tts/` or `data/` differ from `b108ad6`.
- It takes the data from git with LF endings, and in the copy sets `random_intonation = 0` and `intonation_drift = 0`.
- The 184 lines of `tests/golden/corpus.txt` (the same corpus as Gnuspeech's) go through upstream's own command line, one process per line.
- **Voices and tempos:** all five voices at tempo 1, and male at tempos 2, 3 and 3.5. That is 1,472 rows, of which 16 have no audio (`*` and `...`, which the engine refuses).
- Everything was run twice, and nothing is written unless the two runs agree. They agreed.
- A row holds a SHA-256 of the samples and of the parameter file, the sample count, the peak and the rate.

**Result:** `check_golden.py`, through one engine for all rows, on the patched engine:

```
1472 golden rows (samples and track), 182 also through the phonetic string, 0 differences
```

Only MSVC x64 was checked here. Chapter 7 found GCC's output byte-identical for the unpatched command line, but the API has not been built with GCC.

## 4. The API

`api/gama_api.h` has the rules, numbered, and is the reference. It is adapted from `gnuspeech_api.h`, with these differences.

**It owns the tube.** `Controller` builds its tube once in its constructor, so it cannot follow a change of breathiness. So the
Controller is used for the rules only (`synthesizePhoneticStringToFile` with a null output file stops before the tube), and the API runs
`Controller::synthesize`'s loop itself over a tube of its own, at about 0.2 ms per tube. The golden traces show this is the same arithmetic.

**Voices** are the folders `5_male` and so on. A voice change builds a new `Index`, `Model` and `Controller`, in 5 to 7 ms. The text parser
stays, since all the voices name one dictionary.

**Parameters:** the 49 of `docs/09` section 7, in 7 categories. The ranges hold every shipped voice's value (`api_test.c` checks this), and were then run at their extremes.

**Shared limits (rule 10).** Some values are valid only together, and the tube's constructor throws otherwise:
fall time minimum ≤ maximum; rise time + fall time maximum ≤ 100; and the tract's length and temperature must keep the internal rate at or above
50 kHz, below which `PoleZeroRadiationImpedance` refuses. `gama_set_param` refuses such a value, with a reason in `gama_last_error`. A top limit of 300 kHz was added too, since
beyond it the voice costs too much to be of use. A caller setting several values may have to go round twice, as the GUI does.

**Safe text (rule 9).** See [section 5](#5-long-tokens-the-guard-that-was-wrong-first).

**High tempo (rule 11).** Above tempo 6 the engine refuses some words ("the time interval between two postures is too small"). The API tries again at 0.8 of the tempo, down to tempo 1,
so a word is never lost. `gama_spoken_tempo` says what was used. 10 of 918 utterances in the robustness test's tempo stage needed it.

## 5. Long tokens: the guard that was wrong first

[Chapter 9](09-addon-and-gui-feasibility.md) said that breaking any run at 100 characters was enough, on the evidence of random tokens in eight alphabets under ASan. **That was wrong.** A test that repeated
one letter killed the process: 100 `w` gives `STATUS_STACK_BUFFER_OVERRUN`.

The reason: a word the parser cannot pronounce is spelled letter by letter (`spellIt`, `LetterToSound.cpp`) into a buffer of 1,027 bytes, and what limits it is the *spelled* length, not the
number of characters. From `NumberPronunciations.h`, per character:

| Character | Bytes when spelled |
|---|---|
| `<` | 43 |
| `>` | 42 |
| `[` | 40 |
| `(` | 38 |
| `w` | 17 ("'d_a.b_uh_l.y_uu ") |

The table predicts about 60 `w`, and **tested on the unchanged parser, 61 `w` is parsed and 62 kills the process** ([spelling-limit](measurements/gama5/spelling-limit-2026-11-02.txt)). Random tokens averaged too few bytes per letter to show this before 200 characters.

**The table's symbols do not behave that way.** This chapter first said that 24 `<` would overrun it, which was calculated and not seen. Tested, `<` parsed at every length up to 1,000, and so did `b<` and `b(` repeated up to 100 characters: symbols do not reach that buffer in those forms. So the guard is stricter on symbols than the tests show it needs to be. That costs little, and was left so, since a symbol that does reach it has not been ruled out.

**The guard now counts by spelling,** with the engine's own table (`api/gama_spell.cpp`): a run is broken before its spelled length would pass 1,000 bytes, and in any case after 100 characters, where the other buffers were found to hold. So 58 `w`, or 23 of a costly symbol,
or 100 of anything cheap. **It leaves alone anything shorter,** and that matters: a first version charged every symbol the worst cost, and broke `http://www.gnu.org/software/gnuspeech/`, a line of the corpus, which changed how it was read. The golden test caught that at the package build.

**ASan found one thing more.** `light()` in `ApplyStress.cpp` begins `while (!isvowel(*sb)) sb++;`, with no check for the end of the string. A syllable with no vowel sends it through the rest of the
buffer and off its end (`heap-buffer-overflow`, reading). The fix is one condition, and it cannot change the result for a syllable with a vowel, which the golden traces confirm. The same line is in Gnuspeech's `apply_stress.cpp`
*(read, not run under ASan there)*.

**What it was checked with** (`check_robustness.py`): every printable character repeated at lengths around each limit, random mixtures of the most expensive characters at the edge of the budget, and tokens in
eight alphabets up to 8,000 characters. Under ASan: see [section 9](#9-how-it-was-checked).

**There is a second problem with long tokens: time.** 3,000 `w` spells to about 25 minutes of speech, which takes about 25 s to synthesize, and nothing can interrupt the engine during that. So the
driver gives the engine at most 200 characters at a time (`_MAX_PIECE`), splitting at a space if it can, and cancel is noticed between pieces. Measured with the test's stand-ins for NVDA: 0.04 s from cancelling such a token to the end of the next word. A
piece of 200 `w` is the worst case, about 1.5 s. Text with sentence ends is split there anyway, and nothing under 200 characters is split.

The GUI's worker has no such split. A long render there can be abandoned with Stop, and its result is dropped when it arrives, but it runs to its end.

## 6. The tick at the end of an utterance

Found because the driver's trimming test failed on "Button,". About one utterance in five ends with a tick:

```
'no': peak in each of the last 5 ms bins, newest last
  ... 0 0 0 3 7 12 4 6 12 4 6 12 4 6 12 5 6 12 6 561
```

`SampleRateConverter::flushBuffer` pads with zeros at the end of synthesis. Where the tube's output has not settled to zero, that step goes through the output differentiator
(`outputDiffFilter_` in `VocalTractModel5.h`). *(Cause read in the code and consistent with the numbers. Not isolated by experiment.)*

`tools/measure/end_tick.py`, 182 lines, peak mode:

| Voice | Lines ending above -60 dBFS | Largest, last 5 ms | Largest, the 5 ms before |
|---|---|---|---|
| male | 41 | 599 (-35 dBFS) | 33 |
| female | 41 | 382 | 24 |
| large child | 42 | 281 | 17 |
| small child | 41 | 238 | 30 |
| baby | 36 | 257 | 36 |

It was also why trimming failed: the tick looked like the last sound, so nothing was cut. **Rule 12:** the last 6 ms do not count as sound when trimming, and they are made silent, except in upstream's own mode
(peak levelling, no trimming), which the golden traces hold to. Whether the tick could be heard before was not tested by ear. Nobody reported it.

## 7. Loudness, measured again for model 5

`docs/09` said the steady-loudness constants could not simply be copied. `tools/measure/pitch_balance.py`, 20 lines, shows the noise consonants against the voice as the pitch moves, in peak mode:

| Semitones from the voice's own | Male: change in N-V, dB | dB per semitone | Female: change | dB per semitone |
|---|---|---|---|---|
| -12 | +8.92 | -0.74 | +8.95 | -0.75 |
| -6 | +4.53 | -0.76 | +4.44 | -0.74 |
| +6 | -5.15 | -0.86 | -4.68 | -0.78 |
| +12 | -10.40 | -0.87 | -9.24 | -0.77 |

So model 5 behaves like Gnuspeech's tube (0.76), a little steeper upward on the male voice. **`kNoiseDbPerSemitone` is 0.80** where Gnuspeech has 0.85, which splits the error. With it, an octave down and up on the male voice:

```
loudness mode: noise against voice moves -0.46 dB an octave down, -0.94 dB an octave up
constant mode: noise against voice moves -1.14 dB an octave down, -0.55 dB an octave up
```

The levelling itself, `check_leveling.py`, all 182 lines of all five voices at -22 dB:

| Voice | Steady mode, level | Moves inside an utterance, sd: as made → steady | Lines limited |
|---|---|---|---|
| male | -22.21 to -22.00 | 3.13 → 0.33 dB | 1, by 0.21 dB |
| female | -22.03 to -22.00 | 2.50 → 0.18 | 0 |
| large child | -22.00 | 1.84 → 0.17 | 0 |
| small child | -22.00 | 1.72 → 0.14 | 0 |
| baby | -22.00 to -21.95 | 1.25 → 0.12 | 0 |

The gate at glottal volume 57 dB stands, since model 5's vowels have the same target of 60.

**Left out, on purpose:** Gnuspeech's `pitchLoudnessDb`, its correction from ISO 532-1 (Zwicker) loudness across pitch. That was measured on its own tube, and has not been measured on this one. So here the A-weighted level is
held constant across the pitch setting, and the ear may find a small difference, about a decibel at the octave in Gnuspeech's case.

**The levels at NVDA's volume 100:**

- In the levelled modes, the default: -22 dB, the target the Gnuspeech add-on settled on by ear.
- In the engine's own peak mode: `_FULL_VOLUME_GAIN = 0.94`, which brings model 5 male's -20.3 dB to klatt5's -20.8. It was calculated, and not checked by ear. The higher voices are louder in this mode.

## 8. The GUI and the driver

**The GUI** is `gnuspeech_gui.cpp`, ported by a script whose every replacement had to apply. What changed beyond names:

- Finding the data; the 49 parameters come from the table, so no code changed for them.
- The worker and preset loading go round up to three times, for the shared limits.
- A refused value says why, in the status bar, and the note survives the move to the next field.
- **The validator is gone from the number fields.** See below.
- Presets are `.gamapreset`, and write 20 as `20`, where the Gnuspeech GUI writes `2e+01` (it reads back the same).

**wxWidgets swallows keys.** `wxSpinCtrlDouble` 3.3 sets a `wxFloatingPointValidator` with its range on its inner edit. That validator drops a keystroke which would put the value out of range, with no message. Typing 99 into a field
that stops at 24 leaves 9, while a screen reader has echoed both nines. That is a silent wrong value. So `addSpin` removes the validator, after `SetDigits`, which would set it again. Then the text says what was typed, and the status says what became of it: "99 is outside -24.0 to 24.0; set to 24.0",
or "abc is not a number. It stays at 24.0." The same defect is in the Gnuspeech GUI (its `docs/09`, item 15).

**The outside check** was wrong in a way that mattered. It set number fields with `WM_SETTEXT`, which clears the edit's modified flag, so wxWidgets reformatted the text but never told the program. So "99 becomes 24.0" tested only the text, and "volume 0" did not set
volume 0, and **its Speak step played through the speakers at full volume, on the author's machine, once during this work.** It now types with `WM_CHAR`, and before playing anything it saves a WAV and stops unless that is silent.

**The driver** is `gnuspeech.py`, ported the same way. What changed beyond names: the block is 50 ms at whatever the output rate is, `_MAX_PIECE`, the gain above, and the data path.

**The tempo curve is unchanged:** 0.5 at NVDA rate 0, 1 at 50, 4 at 100. GamaTTS's tempo goes further than Gnuspeech's (`docs/09` section 5), so rate 100 is about 3.7× here. **Whether that is comfortable is a question for the ear.** The API allows up to 10.

**The package** is 47 files, 1.1 MB: the driver, the DLL, model 5's voices, what they share from `0_male` (the dictionary, the intonation tables, the phonetic string rules), and the notices. Not model 0's rules. The driver tests pass on it unzipped.

## 9. How it was checked

| Check | Result |
|---|---|
| `api_test.c`, in C17 | 135 checks, 0 failed |
| `check_golden.py` | 1,472 rows, 0 differences |
| `check_robustness.py` | 0 failures: see below |
| `check_leveling.py` | Above |
| `test_driver.py`, from the source and from the package | All passed |
| `gui_check.py` | 109 checks, 0 failed: [measurements/gama5/gui-check-2026-11-02.txt](measurements/gama5/gui-check-2026-11-02.txt) |
| `gama_gui --smoke` | 63,865 samples at 48000 Hz |

**The record:** [measurements/gama5/results-2026-11-02.txt](measurements/gama5/results-2026-11-02.txt) holds every test and measurement of this chapter but the GUI's check and the ASan run, from one run on the final code. `check_robustness.py`, stage by stage, in its routine length, in Release and under AddressSanitizer alike. `ctest` runs this. Its `--long` figures are in the record:

| Stage | What | Result |
|---|---|---|
| tempo | 18 short texts, 5 voices, tempos 0.1 to 10 | 918 spoken; 10 at a lower tempo than asked |
| tokens | Long tokens, every printable character repeated at each limit, mixtures | 848, no crash |
| text | Random text: printable, any bytes, fragments | 418 spoken, 32 with nothing to say |
| phonetic | Malformed phonetic strings | 95 spoken, 55 refused, no crash |
| params | Each parameter at each end, male and baby | 196 spoken, 6 refused by a shared limit |
| random | Random settings of all parameters | 100 spoken |

With `--long`, in the record: 1,608 tokens; 4,275 texts spoken and 225 with nothing to say; 975 phonetic strings spoken and 525 refused; 1,000 random settings. No crash, 0 failures. Not under ASan, which would take hours at that length, and ASan's own run is the routine one. The tempo and parameter stages are the same at either length.

The slowest extreme was the baby voice at tempo 0.1: 1.8 to 1.9 s for one sentence, in Release. That is the extremes run `docs/09` asked for, and it found no instability, at those voices. Whether each extreme *sounds* right was not judged.

**Under AddressSanitizer:** `api_test.c` passes, and so does the whole robustness suite, 0 failures: [measurements/gama5/robustness-asan-2026-11-02.txt](measurements/gama5/robustness-asan-2026-11-02.txt). It runs in Python, so the ASan runtime `clang_rt.asan_dynamic-x86_64.dll` must be copied beside `gama_api.dll`, since Python no longer looks on `PATH` for a DLL's dependencies. ASan found one thing the Release runs could not, `light()`, and nothing since.

**The package build** (`python -I nvda-addon/package.py`) ran all five `ctest` groups on the final code, all passed, then the driver tests on the unzipped package, all passed: 47 files, 1.1 MB, at `nvda-addon/gamatts-0.1.0.nvda-addon`.

Build with `-fsanitize=address` as in `measurements/feasibility/README.md`, on the root `CMakeLists.txt`, and put the VC tools folder on `PATH` for its runtime.

## 10. Not yet verified

In the order that matters:

1. **Inside NVDA.** Everything so far is stand-ins. Not done here, on purpose: testing it means restarting the screen reader the author is using. Say-all, pause, cancelling mid-word and the settings ring all want a person.
2. **The GUI with NVDA speaking.** MSAA says what NVDA would read. Nobody has heard it.
3. **By ear:** the 49 parameters, steady loudness on model 5, the 0.94 gain, how far up the rate range is comfortable, and whether trimming's constants (carried over from Gnuspeech's add-on, on a different tube) suit it.
4. **Other compilers and Linux.** Only MSVC x64 has built the API. The CMake has been written for GCC and Unix, and not run there.
5. **Loudness against pitch** by ISO 532-1, as above.
6. **Translations.** The strings are marked, and there is no `locale/`.
7. **Upstream.** The patch could go to Matuda. Nothing has been sent.
8. **The Gnuspeech add-on's crash** on long tokens, which this chapter describes and this code avoids, is not yet fixed there (its `docs/09`, item 14).

## 11. The record of this chapter's own mistakes

So that no one trusts them later:

- The "100 characters" guard of chapter 9 and the Gnuspeech open item, corrected in both, and above.
- A golden run failed at first, because the probe's build had not built the `gama_tts` target. It failed loudly, and nothing was written.
- `gui_check.py`'s two faults, above, and a safeguard of mine that always fired, because that script's `check()` returns nothing.
- A first focus test in the GUI's text handler compared with the inner edit, where the event comes through the outer spin control, so the handler never ran and two checks caught it.
- The first version of the spelling guard charged every symbol the worst cost, and broke a URL in the corpus. It was not checked against the golden traces when written. The package build was, and refused it. **After changing anything in the text path, run the golden test.**
- One command given to the shell during this work held a stray `pkill -f "x"`, which would have matched nearly every process on the machine, the screen reader among them. Claude Code's permission check refused the whole command, and nothing ran. It is recorded because the author's screen reader is what it put at risk, and because it had no purpose at all.
