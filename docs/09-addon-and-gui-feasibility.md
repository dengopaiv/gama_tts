# 9. Can it become an NVDA add-on and a GUI?

> **What came of this.** The author listened and decided, the same day: "Model 5 needs to be built, it's better in sound and clarity than the original gnuspeech." It was built, and
> [chapter 10](10-model5-api-gui-addon.md) is the record. **One thing here turned out wrong:** section 3's guard, breaking a run at 100 characters, is not enough, since 100 `w` still kills the process. Chapter 10, section 5 has
> the real limit. The section is left as written, with that marked, so that the reasoning can be followed.

Written 2026-11-02, at the author's request: study this repository alongside the
Gnuspeech GUI, and find out whether GamaTTS is functional enough to be turned into an
NVDA add-on and a GUI like Gnuspeech's. "Gnuspeech" in this chapter means the folder
`../GnuspeechSA-NVDA`: its C API, add-on 1.2.0 and GUI.

Nothing in the engine or in that folder's code was changed. Fixes were tried on scratch
copies. Every number here comes from
[`measurements/feasibility/`](measurements/feasibility/README.md), which also says how to
run it again. **Known** means measured or read in the source, **inferred** means reasoned
without a run, as in the rest of these notes.

## The answer

**Yes, technically: the engine is functional enough, once two defects are dealt with. Both
were reproduced here and both fixes were tested. Whether its voice is worth an add-on is
not settled, and only listening can settle it.**

- **The engine does what an add-on needs.** It builds as 64-bit with MSVC and the static
  runtime, without editing its CMake file. It starts in about 60 ms. Model 5 male runs
  at about 69× real time. Output repeats exactly, memory stays flat, it recovers from
  every exception, and two engines can run on two threads.
- **Two defects must be handled first, because each can bring down the host process, and
  in NVDA that process is the screen reader.** At tempo 3.9 and above, a bug in the
  intonation code produces absurd pitch: model 0 then crashes, and model 5 falls silent.
  And a long unbroken token overruns fixed buffers in the text parser. The first has a
  small patch and the second a guard of a few lines.
- **The Gnuspeech GUI and driver carry over well.** The GUI uses only the C API, and its
  controls are built from the API's parameter table. GamaTTS exposes more parameters (49
  for model 5, against 42), and the API can be written without changing the engine.
- **The quality question is still open.** Upstream itself calls the quality "much lower
  than that of the best speech synthesizers". Model 0 has Gnuspeech's spectrum, so it
  offers little that the existing add-on does not. Model 5 is the whole reason to do this,
  and nobody here has heard it. Listening files are in `build-listening/`, with a guide.

**Found on the way, and more urgent than anything above:** the long-token crash is in the
**shipped Gnuspeech add-on too**. See [section 3](#3-defect-long-tokens-overrun-the-text-parser).

## 1. The scoreboard

| What an add-on needs | State | Evidence |
|---|---|---|
| 64-bit build with MSVC, static runtime | **Yes** | The probe builds it through `add_subdirectory`, setting C++17 and `_USE_MATH_DEFINES` from outside |
| Fast enough | **Yes** | 27× to 69× for model 5's voices, about 170× for model 0 |
| Starts quickly, changes voice quickly | **Yes** | About 6 ms for rules and tube, about 50 ms for the dictionary |
| One engine per handle, no shared state | **Yes** | Two threads gave the same samples as one, on 60 utterances and 3 voices |
| Same text gives same samples | **Yes** | With randomness off, the same engine and a fresh one both match exactly |
| Recovers from errors | **Yes** | After engine exceptions, the next utterance is identical |
| Stable over time | **Yes** | 19.0 MB after 2,944 utterances, unchanged from round 5 on (19.3 in another run) |
| Stable across pitch | **Yes** | ±12 and ±24 semitones, 7 voices, 182 lines: no NaN, no silence |
| Rates a screen reader uses | **After the fix** | Fails from tempo 3.9; with the patch, clean to tempo 6 |
| Survives what a screen reader meets | **After the guard** | Long tokens kill it; with a guard, clean under ASan |
| A C API | **No, to be written** | None exists. It can be written with no engine change ([section 6](#6-the-c-api)) |
| Index marks | **As in Gnuspeech** | The driver splits at NVDA's marks, so the engine need not report them |
| Streaming | **No, as in Gnuspeech** | Whole utterance first. The longest corpus line took about 100 ms for model 5 male |
| Good sound | **Unknown** | Measured below; nobody has listened |
| Works inside NVDA | **Untested** | No add-on exists yet |

## 2. Defect: high tempo breaks the intonation

### What happens

Measured over the 184-line corpus of `GnuspeechSA-NVDA/tests/golden/corpus.txt` and over every
fourth dictionary word (18,596 words, letters and numbers included), randomness off:

| Tempo | Corpus lines with wild pitch | Dictionary words with wild pitch | Lowest and highest pitch (semitones) |
|---|---|---|---|
| up to 3.85 | 0 | 0 | about −38 to −5, as expected |
| 3.9 | 20 | 1,270 (6.8 %) | −707,252 to 210,828 |
| 4.0 | 20 | 1,270 | −670,988 to 184,219 |

Non-finite pitch appears as well from tempo 5. Short words are the ones hit: "a", "I", "OK",
"abbot", which is what a screen reader says most, at the speed fast users choose. What
follows depends on the tube:

- **Model 0** reads past the end of its glottal wavetable and crashes. ASan's report:
  `heap-buffer-overflow` in `WavetableGlottalSource::getSample`
  (`src/vtm/WavetableGlottalSource.h:225`). `mod0` subtracts the table length only once, so a
  huge frequency leaves the position outside the table. In the Release build "OK" at tempo 4
  ends the process. Tempo 5 happened not to crash on the same corpus, because whether an
  out-of-bounds read crashes is a matter of chance.
- **Model 5** has no wavetable and does not crash. It gives **silence** instead: at tempo 5 "a",
  "I" and "e-mail" come out as all zeros, and more words at higher tempos. Why silence, and
  not noise, was not traced. *(Inferred: the non-finite pitch of the first frame stops the
  glottal source.)*

Gnuspeech does not have this bug. Its DLL went through the same corpus at tempos 1 to 10 with
no crash, no silence and no new failures; the pitch it produced was not inspected.

### Why

Upstream's `EventList::addIntonationPoint` keeps each point at least two control periods after
the previous one. It works out the correction from `IntonationPoint::absoluteTime()`, which
returns 0 for a negative time. The correction is therefore computed from the clamped value and
falls short by the amount that was clamped:

```
point 1's true time   = beat1 - 40                        (the -40 ms intonation offset)
absoluteTime() says   = 0
correction            = (point0 + 8) - 0
final time of point 1 = beat1 - 40 + point0 + 8
```

So point 1 lands **before** point 0 exactly when `beat1 < 32` ms. This predicts the printed times
exactly, for the word "a" and for "OK":

| Tempo, word | Point 0 | Beat of rule 1 | Predicted point 1 | Printed point 1 | |
|---|---|---|---|---|---|
| 3.8, "a" | 8.80 | 32.62 | 9.42 | 9.42 | in order |
| 3.9, "a" | 8.57 | 31.43 | 8.00 | 8.00 | **reversed** |
| 4.0, "OK" | 8.36 | 30.24 | 6.60 | 6.60 | **reversed** |

`prepareMacroIntonationInterpolation` then solves a cubic over a **backward** interval (a
dump showed it from 8 ms to 4 ms), and `generateOutput` evaluates it from 8 ms to the next point,
at 60 ms: the track for "a" at 3.9 runs −23, −66, −165 … −7,253 semitones. The coefficients
in the dump match the formula with `dx = −4`.

Just below the threshold both points fall in one 4 ms event (at 3.8, both at 8 ms). The first cubic
then has `dx = 0`, and it is overwritten by the next one before it is ever used. It works by luck
*(inferred from the code and the dump; the overwritten values were not printed)*.

The non-finite values from tempo 5 are a second bug beside it: `generateOutput` computes the first
segment as `(y2 - y1) / x2` (`EventList.cpp:971`, and `:975` for the linear case), and `x2` is 0
when the first point falls in the first control period.

### The fix, tested

`measurements/feasibility/engine-fixes.patch` holds the fix: sort the points by time before
interpolating, and guard the two divisions. With it:

| Check | Result |
|---|---|
| Dictionary, tempos 1 to 10 | No wild pitch, no non-finite value, pitch within −38 to −5 at every tempo |
| Corpus through the full tube, models 0 and 5, tempos 1 to 10 | No crash, no NaN, no silence |
| 930 dictionary words through the tube, 3 voices, tempos 1, 3, 4 | The same |
| WAVs against the unchanged engine, tempos 1, 2, 3, 3.5, models 0 and 5, 182 lines each | **Byte-identical, all of them** |

A sort was chosen over correcting `addIntonationPoint`, because a corrected spacing would also move
points that are in order but clamped, at tempos near the threshold, and so change output that works
today. Correcting it is arguably the truer fix, and that is upstream's call.

### What remains: "too small"

With the patch, the engine's own check on rule timing is what limits the speed:

| Tempo | Dictionary words refused: "The time interval between two postures is too small" |
|---|---|
| up to 6 | 0 |
| 8 | 12 of 18,596 |
| 10 | 668 of 18,596 |

It is a clean exception, and the next utterance is unharmed. The driver's top of 4.0 would never
reach it. If the top ever rises past 6, the API must retry at a lower tempo, so that a word is
never lost.

**Without the patch** the only safe course is to cap the tempo at 3.85. That was measured on
every fourth dictionary word only, and the cause depends on timing, so a margin is needed, 3.5
say. Sentences would be slower than the driver's present top. The patch is better.

## 3. Defect: long tokens overrun the text parser

### What happens

A screen reader meets long unbroken tokens: base64 images, minified URLs, hashes, digit strings.
The text parser copies words into fixed buffers with no length check, among them `tstr[1024]` and
`mstr[1024]` in `ispTrans`, `spellIt`'s `hold`, and the buffers of `NumberParser`. Parser only, under
AddressSanitizer, three random tokens at each length, with the trie check below applied:

| Alphabet | First length with a memory error | Where |
|---|---|---|
| Consonants only | **200** | `spellIt`, `LetterToSound.cpp:222`, stack overflow |
| Digits | **256** | `NumberParser::initialParse`, access violation, then heap overflow |
| Hex | **400** | The same functions *(inferred from the digit and letter runs)* |
| Base64 | 1,000 | |
| Lower case, upper case, vowels, mixed | none up to 1,000 | |

**Up to 128 characters, nothing failed in any alphabet** *(random tokens; a single repeated letter fails sooner: chapter 10)*. In the Release build this shows up as
`STATUS_STACK_BUFFER_OVERRUN` or an access violation, depending on the text.

The first kind is the worse one. It is the C runtime's fail-fast, **which cannot be caught**: the
process ends at once. An access violation, by contrast, is turned into an `OSError` by Python's `ctypes`.

### The shipped Gnuspeech add-on has it too

The same code is in `GnuspeechSA-NVDA/src/en/letter_to_sound/`. Three random tokens at each
length through its DLL, unchanged, in a child Python process:

| Alphabet | First failure |
|---|---|
| Consonants only | **200 characters: the process dies** |
| Vowels | 600: the process dies |
| Lower case | 1,500: the process dies |
| Digits | 256: access violation |
| Hex | 500: access violation |
| Mixed | 300: access violation |
| Base64 | 1,500: access violation |
| Upper case | none up to 1,500 |

The driver gives it no protection. `_engine_text` folds characters and collapses spaces, and
neither it nor `gs_speak` limits the length of a word.

**Not tried inside NVDA, on purpose,** since that could kill the screen reader of the person
using it. That NVDA would die is therefore **inferred**, from a Python host dying the same way. It
is recorded in `GnuspeechSA-NVDA/docs/09`, item 14. Nothing there was changed.

### The fix, tested

**Corrected the same day: this guard is not enough. See [chapter 10, section 5](10-model5-api-gui-addon.md#5-long-tokens-the-guard-that-was-wrong-first).** Random tokens did not show it, since they average too few bytes per letter when spelled.

A guard before the parser: break any run of more than 100 characters with a space. Long tokens
of 500, 2,000 and 8,000 characters in all eight alphabets, 48 cases, were parsed clean under ASan
that way. The speech of such a token is nonsense either way. The guard only has to keep it from being
dangerous, and a driver might well choose to skip or abbreviate such a token instead.

The guard belongs in the API, so that the GUI gets it as well.

### A smaller one: the trie

Random printable ASCII found a third problem. `ispTrans` indexes its trie with
`trie[INDEX(*string) + i]` and no bounds check, so a character such as `}` near the end of the trie
reads past it (ASan: `global-buffer-overflow`, 30 bytes past `trie`). Input
`j}A44[\{OT?'UkYyo\KQ;!h/yaA?` triggers it. It is a read, and it caused no crash in 4,500 Release
fuzz inputs, but what it then reads steers the parser. `engine-fixes.patch` adds the check. The same
code is in Gnuspeech *(read, not run under ASan there)*.

After that patch, ASan found nothing more in about 2,000 further utterances. Those runs ended at
their time limit, not at an error, so this is not exhaustive.

## 4. Speed and start-up

Corpus at tempo 1, MSVC x64, `/MT`, randomness off, best of three, run alone. "Longest" is the
synthesis time of the longest corpus line, the wait before its first sound. Treat these as ±15 %: within the same
run, section 13 of the results gives ×33 for the baby voice and ×43 for the small child, and an earlier run gave ×32 and ×41.

| Voice | Internal rate | Real-time factor | Longest line |
|---|---|---|---|
| `0_male` | 20,034 Hz | ×170 | 40 ms |
| `4_male` | 60,102 Hz | ×61 | 115 ms |
| `5_male` | 60,411 Hz | ×69 | 99 ms |
| `5_female` | 70,480 Hz | ×60 | 109 ms |
| `5_large_child` | 84,576 Hz | ×52 | 138 ms |
| `5_small_child` | 105,720 Hz | ×39 | 166 ms |
| `5_baby` | 140,960 Hz | ×27 | 216 ms |

Gnuspeech's own notes give about ×75 (its `docs/03`). Model 5 male is in the same class, so sentence
splitting serves as well as it does there. Chapter 8's open item on the child and baby voices can close:
they are stable and fast enough.

- **Loading a voice:** 5–7 ms for index, rules and tube; 49–54 ms for the text parser and
  its dictionary. All voices share one dictionary (`text_parser_dir = ../0_male/text_parser/`), so a
  voice change should not need to reload it *(inferred, not run)*.
- **Rebuilding the tube alone:** about 0.2 ms. A GUI can apply a tube setting at every Speak without a
  noticeable cost.
- **Data:** 3.0 MB.

## 5. The sound, as far as numbers go

This section can say how the sound differs, and it cannot say whether the voice is good.

**Balance.** The method is Gnuspeech's `tools/measure/loudness.py`: A-weighted level of active speech,
each band against it. 182 corpus lines, randomness off, each engine peak-normalised as shipped.

| Voice | A-weighted level (dB) | SD between lines | Below 500 Hz | 1–4 kHz | 4–10 kHz | Silence before / after (ms) |
|---|---|---|---|---|---|---|
| Gnuspeech male | −19.9 | 1.10 | +8.2 | −6.8 | −16.7 | 121 / 188 |
| `0_male` | −19.9 | 1.11 | +7.8 | −6.8 | −17.0 | 121 / 185 |
| `4_male` | −19.8 | 1.13 | +7.1 | −7.5 | −18.5 | 121 / 183 |
| `5_male` | −20.3 | 1.42 | **+4.6** | −6.7 | **−13.6** | 126 / 185 |
| `5_female` | −16.6 | 1.26 | +3.1 | −7.1 | −19.9 | 124 / 185 |
| `5_large_child` | −15.1 | 1.14 | +0.4 | −7.1 | −20.6 | 125 / 184 |
| `5_small_child` | −13.8 | 1.19 | −2.3 | −6.4 | −19.3 | 122 / 182 |
| `5_baby` | −13.2 | 1.15 | −4.0 | −4.2 | −18.5 | 121 / 182 |

On the 30 short menu items of Gnuspeech's listening test, which eSpeak klatt5 also has a file for:

| Voice | Below 500 Hz | 1–4 kHz | 4–10 kHz |
|---|---|---|---|
| eSpeak klatt5 | +1.2 | −5.9 | −15.2 |
| Gnuspeech male | +9.0 | −6.8 | −15.6 |
| `0_male` | +8.3 | −6.6 | −16.3 |
| `5_male` | +5.6 | −6.9 | −12.6 |
| `5_female` | +3.7 | −7.2 | −19.5 |

What this says:

- `0_male` matches Gnuspeech, as chapter 7 found by other means.
- **`5_male` has about 3.5 dB less weight below 500 Hz and about 3 dB more at 4–10 kHz than Gnuspeech.**
  That is the direction Gnuspeech's `docs/09` item 5 wanted from a "brightness" option: it called
  the voice dull, with too much below 500 Hz. *(Inferred: model 5 may need less of that correction.)* It
  does not gain in the 1–4 kHz band, where eSpeak still leads by about 1 dB. Note that eSpeak's file is
  one continuous file at 22,050 Hz, so its between-lines and edge columns in the script's output mean nothing.
- **These figures and Gnuspeech's "about 6 dB less presence than eSpeak" do not conflict.** Against the A-weighted
  level, its `docs/08` table gives −6.8 for Gnuspeech and −5.3 for klatt5, close to what is here. The 6 dB is
  against LUFS (−11.5 and −7.0 for klatt5, −4.6 for eSpeak `en`), which `<500 Hz` energy inflates. LUFS was not
  measured here, so model 5 cannot be placed on that scale.
- The silence at the edges is about the same as Gnuspeech's, so the add-on's trimming fits.
- Levels differ between voices by up to 7 dB under peak normalisation, so levelling matters here as well.

**Tempo goes further than Gnuspeech's.** One 15.4 s text, the same words:

| Tempo | GamaTTS model 5 male | Gnuspeech male |
|---|---|---|
| 1.0 | 15.4 s | 15.4 s |
| 2.0 | 7.9 s | not measured |
| 3.0 | 5.4 s (2.85× faster) | 7.6 s (2.03× faster) |
| 4.0 | 4.2 s (3.67× faster) | not measured |

Over the corpus, tempo 4 is 3.55× faster. So GamaTTS's tempo reaches the 3–4× that Speechialization's
`studies/03` sets as the screen-reader target, where Gnuspeech's tempo 3 does not. This also answers part of
Gnuspeech's `docs/09` item 4. Why they differ was not traced, and the Gnuspeech figure rests on one text.
Whether the speech can be followed at that speed is a question for the ear.

**Not measured:** intelligibility, any listening judgement, formant tracks, and model 5 against model 0 in
intonation. Chapter 8's first open item is therefore only half closed.

## 6. The C API

GamaTTS's C++ interface passes C++ objects, and Gnuspeech's own reasoning (its `docs/10`) applies: a plain C
boundary with its own runtime inside lets the DLL sit beside wxWidgets and inside NVDA. `gnuspeech_api.h` is
the right model, and most of it carries over unchanged.

**It can be written with no change to the engine.** Gnuspeech's API needed to write its parameters into the
engine's configuration before every utterance. Here the tube is built once in `Controller`'s constructor, so a
tube setting cannot be changed there. But a wrapper can own the tube. Tested (`probe ownloop`):

1. `controller.synthesizePhoneticStringToFile(phonetic, nullptr, nullptr)` runs the rules and stops, because a
   null output file skips the tube. `vtmParameterList()` then gives the track.
2. The wrapper keeps its own `ConfigurationData` and builds `VocalTractModel::getInstance(data)`.
3. It runs the 20-line loop of `Controller::synthesize` itself.

| Check | Result |
|---|---|
| Same configuration, against `Controller`'s own output | **Identical samples**, models 0 and 5 |
| Breathiness 25 and tract 16 cm | Different samples, as it should be; tube rebuilt in about 0.2 ms |
| `reference_glottal_pitch`, through `vtmConfigData().put` | The track moves by the right amount |
| `*`, then two refused utterances, then the same text | Identical to before |

This has further benefits. Owning the loop allows streaming later, and the track is at hand for levelling
without parsing text, as Gnuspeech's `parseTrack` must.

What differs from `gs_*`:

- **A voice is a directory, with its own rules and tube model.** Changing voice builds a new `Index`, `Model`
  and `Controller`: 5–7 ms.
- **The parameter table depends on the voice's model**, so `gs_param_count` and `gs_param_describe` need a voice
  or model argument, and the GUI must rebuild its fields on a change of family.
- **Combined limits.** The tube's constructor throws if `tn_min > tn_max` or `tp + tn_max > 100`. Each field's own
  range is not enough. The API must check the combination, and catch the exception. A probe with no handler dies
  there, which is how section 7's failed row came about.
- **The guard, the patch and the retry** of sections 2 and 3.
- **The build:** C++17 and `_USE_MATH_DEFINES` are set from the wrapper's CMake. The data needs LF endings: a
  `.gitattributes` with `data/** -text`, as Gnuspeech has, or packaging through `git -c core.autocrlf=false archive`.

## 7. What a GUI can expose

Each key was changed by itself, a sentence rendered with randomness off, and the WAV compared with a baseline
(`perturb.py`). Tempo, drift and randomness are overridden by the probe, so those were tested separately, with
the configuration as written.

| Group | Model 5 | Model 0 |
|---|---|---|
| Speech and intonation | tempo, pitch offset, initial pitch, intonation factor, micro, macro, smooth, drift, random, drift deviation, drift cutoff, control period (12) | the same (12) |
| Glottal source | waveform, reference pitch, tp, tn min, tn max, breathiness (6) | the same (6) |
| Tract | length, length offset, temperature, loss factor, radius coefficients 1–8, global radius (13) | the same 13, plus aperture radius |
| Nose | nasal radii 2–7 (6), global nasal (7) | nasal radii 1–5 (5), global nasal (6), plus nose coefficient |
| Mouth and throat | glottal lowpass, min and max glottal loss, constant-radius mouth impedance, impedance radius (5) | mouth coefficient, throat cutoff, throat volume (3) |
| Noise | noise modulation, mix offset, glottal noise cutoff, frication noise cutoff, frication factor (5) | noise modulation, mix offset (2) |
| Output | output rate (1) | output rate (1) |
| **Total** | **49** | **45** |

Left out, and why:

- `notional_pitch`, `pretonic_pitch_range`, `pretonic_perturbation_range`, `tonic_pitch_range`,
  `tonic_perturbation_range`: **no effect**, in both models, as in Gnuspeech's `docs/10`.
- `bypass` (the raw glottal waveform) and `log_parameters`: for debugging.
- `variant_name`, `model`, `phonetic_string_format`: chosen by the voice.

Notes on the table:

- `glottal_pulse_tn_min` raised from 24 to 27.6 failed in the first run. That is the combined limit, since it
  exceeded `tn_max`. Lowered to 20, it changes the sound.
- `mouth_impedance_radius` acts only when `constant_radius_mouth_impedance` is true *(read, `VocalTractModel5.h:420–422`)*.
- `control_period` needs the event list's period set too, not just the field *(read, not run)*.
- **Not done: the extremes run.** Gnuspeech ran every parameter at its minimum and maximum. Model 5 has new
  parameters, for which ranges have yet to be chosen, and their stability at the edges is not known.

## 8. The add-on and the GUI

### The driver

`gnuspeech.py` (585 lines) is written against the API, and almost all of it carries over: the queue, epochs, cancel,
index marks on the player, spelling, breaks, capital pitch, ASCII folding, sentence splitting, trimming, narrow paths.
Since the text parser is the same, its workarounds stay right too, such as letters sent in capitals. What changes:

| Item | Why |
|---|---|
| `_BLOCK = 2205` | 50 ms at 44.1 kHz; output here is 48 kHz by default |
| `_tempo()` | Tempo reaches further here, so the curve should be chosen by ear |
| Level constants: `_FULL_VOLUME_GAIN`, `_LOUDNESS_TARGET_DB` | Calibrated on Gnuspeech's balance |
| Voices | Names, and which of the 14 to offer |
| `check()`, data path, add-on name | Must not install over Gnuspeech: a distinct name |

**The steady-loudness work needs measuring again, not just copying.** It was fitted to this tube's relation between
voice and pitch: its gate at glottal volume 57 dB, its 0.85 dB per semitone for noise, its ISO 532-1 target
(Gnuspeech `docs/13`). Model 5's vowels have the same glottal volume target of 60 *(read in `5_male/artic.xml`, one posture
checked)*, but its radiation, its losses and its frication differ, and its SD between lines is larger. The method
carries over, not the constants.

### The GUI

`gnuspeech_gui.cpp` (1,456 lines, C++17, wxWidgets) is a good fit:

- **It reaches the engine only through the API**, about 30 distinct `gs_` names. The fields are built from
  `gs_param_describe`. So nothing about tubes is hard-coded.
- **About 30 lines name Gnuspeech** (a search for its name, `monet.xml`, `data/en`, and the rates), nearly all of them
  labels, messages and file filters, plus finding the data folder. That is a count of lines found, not a finished port.
- **Accessibility carries over,** as it lives in the window code: standard controls, `NamedAccessible`, a combo box
  for categories, group boxes, Alt+letter accelerators, typed values out of range announced. So does
  `tests/gui/gui_check.py`, the outside check through MSAA.
- **New work:** rebuild the fields when the voice's family changes, since Gnuspeech's window builds every category
  once, at start-up, and its table never changes. A longer voice list. A message for the combined limits. The parameter
  track is frames only, with no header (chapter 4).

GamaTTS's own editor is not an alternative. It needs Qt, FFTW and a running JACK server, and its main graphs are
mouse-only ([chapter 5](05-editor-and-accessibility.md)). It stays what it is, a Monet clone for study.

**Tawkative does not apply:** it drives only our own C rewrites, and this is neither ours nor C. So this GUI is a
stand-alone program, as Gnuspeech's is, for the same reason.

**Chapter 8 said a C17 rewrite would be needed. That was too strong.** The collection's C17 direction is for
its own engines. GamaTTS is Matuda's, under the GPL. Gnuspeech's `docs/09`
item 10 reads the same rule the same way: allowed, not required. C++17 can stay, with C at the boundary.

## 9. What GamaTTS would not bring

So that no one expects it:

- **Pronunciation.** The dictionary and parser give the same strings as Gnuspeech (chapter 7), so the same words come out
  wrong, and numeric dates and units are read as badly.
- **English only.**
- **Word-level index marks.** The driver's sentence and mark splitting serves, as in Gnuspeech.
- **Less wait on long sentences.** Same model, about the same speed, until someone does streaming.

## 10. Decisions for the author

1. **Is model 5 worth it, by ear?** `build-listening/README.txt` is the guide. This comes first, since a "no" makes the
   rest moot. If model 5 is no better than A1, then the Gnuspeech add-on already does this job.
2. **The Gnuspeech add-on's crash.** A guard in `gs_speak` or `_engine_text` is small, but it means a new version and a run
   inside NVDA (head `CLAUDE.md` §3). This stands whatever is decided about GamaTTS.
3. **Where it lives. Decided 2026-11-02: here, in `dengopaiv/gama_tts`, which stays public.** The author: "I guess this stays public."
   The fork already existed, level with upstream at `b108ad6`, so nothing had to be created. The API, driver and GUI start from `GnuspeechSA-NVDA`'s
   code, which is in a private repository, and the author agreed to publishing them here the same day: "I think we may push it." That repository itself stays private.
4. **Patching the engine.** Gnuspeech's add-on keeps its engine unchanged, and proves it with golden traces. Here the engine needs a
   patch. Golden traces from the unchanged engine at tempos up to 3.5 would still hold, so the claim becomes "unchanged in sound up to
   tempo 3.5". The patches could also go to Matuda (`mym-br/gama_tts`), together with the MSVC fixes.
5. **One add-on or two.** Separate add-ons repeat a driver and a dictionary. One add-on with both engines is a larger change to one that
   is tested and working. Separate is the smaller risk.
6. **Which voices.** Model 5's five, surely. Model 0's only if A2 earns a place, since its sound is what the add-on already has. Models 1–4 are
   for study; 4 is close to 0 in the numbers above, and costs what 5 costs.

## 11. The order of work, if it goes ahead

Following the tree's usual order, with an add-on last (head `CLAUDE.md` §3):

1. **Golden traces** of the unchanged engine, first, as in Gnuspeech's `docs/07`.
2. **The patches,** checked against those traces.
3. **The C API**, on `gnuspeech_api.h`'s model: guard, combined limits, parameter tables per model, tests.
4. **The extremes run** across all 49 and 45 parameters, then the ranges.
5. **The GUI** from `gnuspeech_gui.cpp`, with `gui_check.py`, and then a real session with NVDA, which Gnuspeech's GUI itself still lacks.
6. **Loudness:** measure again for model 5, and by ear.
7. **The driver**, tested with stand-ins, then inside NVDA, with long tokens among the test inputs (in a throwaway portable copy).

## 12. How these results could mislead

Recorded so they are not misread later:

- **Fuzzing was not exhaustive.** ASan runs ended at their time limits: about 2,000 utterances after the last patch, on `5_male`, and fewer before it,
  on `5_male` and `0_male`. Tube and rules were exercised on short random text, and long utterances only in the fixed cases.
- **The dictionary scan used every fourth word**, and only the track. The tube was run on every 80th word. Randomness shifts timing, and it was switched on only for 5 rounds of the corpus.
- **The threshold is for control period 4 ms.** By the arithmetic above it would differ at other periods. This was not run.
- **Timing is for this machine,** a modern x64 desktop, and from one build with the default Release flags.
- **Comparing Gnuspeech's tempo** rests on one text.
- **The listening files use the patched build.** It changes no sample up to tempo 3.5, so only the tempo 4.0 file depends on it.
- **Pitfalls met while measuring:**
  - One run of the key test silently used a binary that had failed to link, because another job held the file open. Every key then "changed the sound". It was noticed, thrown away and run
    again, and the script now checks that the file exists.
  - `grep -v "e.g."` over the output also drops any line with "dengo" in a path, since `.` matches any character. It hid some error lines, though not the counts on each result line.
  - `probe.exe` under Git Bash reports a fail-fast as exit 127, and a segmentation fault as 139. Python's `subprocess` shows the real status.
