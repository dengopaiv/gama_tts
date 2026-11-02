# A. Measurements

Every number in these documents comes from here. All measurements were taken
on 2026-10-16 on Windows 11 Pro x64 (build 26340). Everything can be rerun with
one script:

```sh
sh docs/measurements/run_all.sh WORK GAMA_EXE GAMA_EXE_2 GS_EXE GS_TRM_EXE GS_DATA_EN
```

Its full output from this run is in
[`measurements/results-2026-10-16.txt`](measurements/results-2026-10-16.txt).
The two analysis scripts it calls are `compare_params.py` and
`compare_wav.py`, in the same folder.

## Setup

| Item | Value |
|---|---|
| GamaTTS | `b108ad6` (upstream master, 2025-09-12), unmodified |
| GamaTTS build A | MinGW-w64 GCC 16.2.0, `Release` (CMake 4.4.4, Ninja) |
| GamaTTS build B | MSVC 19.51, `Release`, x64, with `CMAKE_CXX_STANDARD=17` and `_USE_MATH_DEFINES` ([chapter 6](06-building-and-running.md)) |
| Reference | Unmodified GnuspeechSA 0.1.5 (`539d75a`): `gnuspeech_sa` (text to speech) and `gnuspeech_sa_trm` (parameter file to speech), MSVC x64 build, with GnuspeechSA's own `data/en` |
| Data | GamaTTS's `data/` exported with LF endings (`git -c core.autocrlf=false archive`) |
| Determinism | For sections 1–4 and 6, copies of the configuration with `random_intonation = 0` and `intonation_drift = 0`, in both systems |
| Main test sentence | "The quick brown fox jumps over the lazy dog." |

## 1. The text front end gives identical phonetic strings

Four sentences, each through GamaTTS (`tts -v`, voice `0_male`) and
GnuspeechSA (`-v`). The phonetic string printed by each was compared by eye
and character by character. GamaTTS prints each chunk without the final
`/c`; otherwise the strings are identical in all four cases:

| Input | Read as (both systems) |
|---|---|
| The quick brown fox jumps over the lazy dog. | as written |
| In 1984, it cost $3.25. | nineteen eighty-four … three dollars and twenty-five cents |
| Call 555-1234 on 3/4/2025 at 10:30. | five five five, one two three four … **three slash four slash two zero two five** … ten thirty |
| It weighs 2.5 kg, 1st of 22nd, 45%. | two point five **k g**, first of twenty-second, forty-five percent |

The two weak readings (bold) are inherited from Gnuspeech; neither system
handles numeric dates or unit abbreviations.

## 2. The rule engine gives identical tracks, except pitch

`gnuspeech_sa -p gs.param` and `gama_tts tts -p gama.param`, main sentence,
compared with `compare_params.py`:

| Parameter | Largest difference over 875 frames |
|---|---|
| glotVol, aspVol, fricVol, fricPos, r2, r4–r7, velum | ≤ 0.0005 (print rounding: GnuspeechSA writes 3 decimals) |
| fricCF, fricBW | 0.005 (rounding, on values in the thousands) |
| r1 | 0 |
| r3 | 0.0051 |
| **r8** | **0.0101 cm**, in frames 728–756 only |
| **pitch** | **22 semitones**; range −25.65…−7.00 (GnuspeechSA) against −36.00…−7.09 (GamaTTS) |

- **Frame count:** 875 in both, that is 3.5 s at 4 ms.
- **R8:** the 29 frames lie in "dog", where GamaTTS is up to 0.01 cm
  lower. This is very likely the folded-in marked posture: GnuspeechSA's
  marked `d'` has r8 = 1.31 cm, where `d` has 1.3
  ([chapter 4](04-differences-from-gnuspeech.md)). The cause was not traced
  further.
- **Pitch:** the difference is largest at the start. GamaTTS's first frame is
  −36 and GnuspeechSA's is −14, because of the new `initial_pitch` ramp and
  the changed intonation code.

## 3. The tube: same spectrum, not the same samples

GnuspeechSA's parameter file (header included) was rendered by
`gnuspeech_sa_trm`. Its 875 frames (header removed) were rendered by
`gama_tts vtm` with models 0 to 4, at the same 44.1 kHz output rate.
`compare_wav.py` searches the best alignment within ±400 samples, removes
the level difference with a least-squares gain (both programs normalise to
peak), and skips 1,000 samples at each end.

**Against GnuspeechSA:**

| GamaTTS model | Length (samples) | Lag | Correlation | SNR |
|---|---|---|---|---|
| (GnuspeechSA) | 154,405 | — | — | — |
| 0 | 154,146 | −6 | 0.91837 | 8.1 dB |
| 1 | 154,146 | −7 | 0.91841 | 8.1 dB |
| 2 | 154,146 | −6 | 0.91837 | 8.1 dB |
| 3 | 154,115 | −37 | 0.89983 | 7.2 dB |
| 4 | 154,115 | −37 | 0.88990 | 6.8 dB |

**Length.** 154,146 / 154,405 = 0.99832. GnuspeechSA runs its tube at 20,000
Hz, a whole multiple of 250 Hz (`Tube.cpp:518`). GamaTTS runs at 20,034 Hz
with 80 samples per frame. The predicted ratio is 20,000 / 20,034 = 0.99830,
which matches to the fourth decimal: the whole length difference comes from
the rate rounding.

**Per band** (model 0 against GnuspeechSA; 2,048-point Hann windows, 50 %
overlap):

| Band | Level difference | Coherence | Share of energy |
|---|---|---|---|
| 50–300 Hz | −0.2 dB | 0.84 | 54.8 % |
| 300–1,000 Hz | −0.2 dB | 0.73 | 24.3 % |
| 1–2 kHz | −0.2 dB | 0.58 | 1.9 % |
| 2–4 kHz | 0.0 dB | 0.14 | 0.7 % |
| 4–6 kHz | −0.1 dB | 0.09 | 0.2 % |
| 6–8 kHz | −0.1 dB | 0.07 | < 0.1 % |
| 8–10 kHz | +0.1 dB | 0.07 | < 0.1 % |
| 10–15 kHz | 0.0 dB | 0.01 | < 0.1 % |

**What this means.** The average spectrum is the same within 0.2 dB
everywhere, so the filter is the same: same formants, same tilt. But the
waveforms do not line up sample by sample. Of 61 stretches of 50 ms, the
median correlation is 0.93. The poorly correlated ones are the noise-driven
sounds (around 0.3, 1.1, 1.3–1.4 and 1.8 s: k, f/ks, s in "jumps", z in
"lazy") and the last half second ("dog", from 2.7 s on), where correlation
falls steadily from 0.9 to near 0. That is consistent with a phase that
drifts slowly: the 0.17 % timing difference above, and the noise generator
being sampled at a different point. Both are inferred causes, not traced.

**Against model 0:**

| Model | Lag | Correlation | SNR | Note |
|---|---|---|---|---|
| 1 (float) | −1 | 0.99942 | 29.3 dB | |
| 2 | 0 | 1.00000 | ∞ | **byte-identical file** (`cmp`) |
| 3 | −31 | 0.97335 | 12.8 dB | 3 samples per section |
| 4 | −31 | 0.96832 | 12.1 dB | 30 sections |

Model 5 was not compared this way. Its database `5_male/artic.xml` keeps the
same radius scale (the vowel `aa` has the same r1–r8 in both), but frication
volume runs 0–60 instead of 0–10, and the frication and aspiration targets
were retuned. A GnuspeechSA parameter file would therefore drive model 5 with
frication far too quiet, and the comparison would show nothing useful.

## 4. Internal sample rates

Read from `gama_tts tts -v` ("Internal sample rate"):

| Voice | Model | Rate | Check |
|---|---|---|---|
| 0_male | 0 | 20,034 Hz | (331.4 + 0.6·32) · 10 · 100 / 17.5 = 20,034.3 |
| 0_female | 0 | 23,373 Hz | the same with 15 cm |
| 2_male | 2 | 20,034 Hz | |
| 3_male | 3 | 60,102 Hz | 3 × 20,034 |
| 4_male | 4 | 60,102 Hz | 30 sections |
| 5_male | 5 | 60,411.4 Hz | 352.4 · 30 · 100 / 17.5 (35 °C) |
| 5_female | 5 | 70,480 Hz | the same with 15 cm |

## 5. Repeatability and compilers

With randomness off, the main sentence plus "In 1984, it cost 3 dollars and
25 cents." was rendered twice with each build, through voices 0_male, 4_male
and 5_male:

- two runs of the same build: **identical** WAV files (`cmp`);
- GCC build against MSVC build: **identical** parameter files and
  **identical** WAV files, for all three models.

With the default configuration (`random_intonation = 1`), no two runs are
alike, by design.

## 6. Speed

Twelve copies of the two test sentences (about 100 s of speech), through the
GCC build, one process per run, best of three, wall-clock time including
start-up:

| Voice | Audio | Time | Real-time factor |
|---|---|---|---|
| 0_male | 101.3 s | 856 ms | ×118 |
| 2_male | 101.3 s | 864 ms | ×117 |
| 3_male | 101.3 s | 1,658 ms | ×61 |
| 4_male | 101.3 s | 1,738 ms | ×58 |
| 5_male | 101.7 s | 1,564 ms | ×65 |

A run that loads the voice and parses "Hi." but writes no audio takes
145 ms; most of that is reading the dictionary. An earlier run the same day
gave ×120, ×118, ×61, ×59 and ×65, and 157 ms, so treat the figures as ±3 %.

The GCC build had no `-march=native` (see [chapter 6](06-building-and-running.md)).
The MSVC build was not timed.

## Pitfalls met while measuring

Recorded so they are not met again:

- **The GCC build fails silently without its runtime DLLs.** It exits with
  code 127 and writes nothing. One early comparison was briefly wrong
  because of this: it compared stale files and seemed to show GCC
  output changing between runs. It was repeated with `PATH` set and
  the result is the one above.
- **CRLF data files** are rejected ([chapter 6](06-building-and-running.md)).
- **Model 2 and 3** need the `log_parameters` key in `vtm.txt`.
- **Both programs normalise each file to peak**, so levels must be matched
  with a gain before comparing.
