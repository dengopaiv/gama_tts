# 4. Differences from Gnuspeech

The comparison baseline is **GnuspeechSA 0.1.5** (`539d75a`), the C++ port
GamaTTS branched from. For the older Objective-C and NeXT systems, see the
last section. "Measured" refers to [chapter A](07-measurements.md); other
statements come from reading the code and `git log 539d75a..HEAD`.

## Summary

| Layer | Same as GnuspeechSA? | Evidence |
|---|---|---|
| Text parser, dictionary, number reading | **Yes, output identical** | Measured: identical phonetic strings for four test sentences |
| Rule database (`0_male/artic.xml` against `monet.xml`) | **Yes in substance** | Measured: 15 of 16 parameter tracks identical within the comparison's 0.006 tolerance over 875 frames, r8 apart (below) |
| Pitch / intonation | **No** | Measured: up to 22 semitones different at the start; code changes listed below |
| Classic tube (model 0) | **Same spectrum, different samples** | Measured: band levels within 0.2 dB from 50 Hz to 15 kHz; correlation 0.92 |
| New tubes (models 3–5) | New | [Chapter 3](03-vocal-tract-models.md) |
| Program interface | Changed | Below |
| Editor | New (Qt clone of Monet) | [Chapter 5](05-editor-and-accessibility.md) |

## Text front end

- **Dictionary:** the same 74,115 entries. The only change is that a control
  character was removed from the entry "marigolde" (`f6775ee`).
- **Abbreviations (89), abbreviations with numbers (3), special acronyms (4),
  suffixes (217):** the same content, now read from text files in
  `text_parser/` instead of compiled-in C tables (`6099e0e`, `7f137a8`).
- **Removed:** Gnuspeech's in-band escape modes (raw text, letter-by-letter
  spans, emphasis, silence) were replaced by one global mode,
  `mode = 0/1/2` in `text_parser.txt` or `TextParser::setMode()` (`5b21ebd`).
  A program can no longer switch to spelling for part of a sentence.
- **NumberParser, LetterToSound:** the roughly 20 source files of the original
  `letter_to_sound/` were merged into a few. The commits read show
  refactoring only, and the measured phonetic strings for years, money,
  phone numbers, dates, times, ordinals and percentages are identical.

## Rule database

Counted in the XML (helper's reading, cross-checked by the measured tracks):

| | Postures | Rules | Equations | Transitions | Special |
|---|---|---|---|---|---|
| GnuspeechSA `data/en/monet.xml` | 130 (65 + 65 "marked") | 47 | 114 | 71 | 41 |
| GamaTTS `0_male/artic.xml` | 65 | 47 | 110 | 62 | 32 |
| GamaTTS `5_male/artic.xml` | 65 | 47 | 92 | 36 | 22 |

- **Marked postures folded in.** Gnuspeech stored each phone twice, for
  example `d` and `d'`, the second used in the tonic foot. GamaTTS keeps one
  posture with `markedDuration`, `markedTransition`, `markedQssa` and
  `markedQssb` symbols, plus a `marked` operator for rules (`f0bd1d4`,
  `301fb42`). The timing values are carried over exactly. The spectral
  targets of the marked twins are lost where they differed: `d'` had
  r8 = 1.31 cm, where `d` has 1.3. **Measured:** R8 is up to 0.01 cm lower
  over 29 frames in "dog", the largest difference in the 15 non-pitch tracks. r3
  also differs, by up to 0.0051 cm, which passed the script's 0.006 tolerance
  *(inferred: the folded `o'`, 0.93 against 0.925, also in "dog")*. All six lost
  values are listed in Speechialization's docs/10 §2b.1.
- **18 dud transitions** and the equations dud1, dud11, Diphone and
  Tetraphone were removed (`1fd2a8c`).
- **Rewrite rules** that GnuspeechSA hard-coded in `PhoneticStringParser`
  are now data (`phonetic_string_parser/rewrite.txt`). New rules were added:
  `t v`, `t dh`, `k dh → insert q` (`1dc0621`, `656760b`).
- **Model 5's database** has the same rules with retuned targets and
  transitions. Frication volume goes up to 60 dB instead of 10. The changes
  are spread over many small, word-by-word commits from 2017, for example
  `666dfea` ("Increase the duration of very quick postures"), `c760225`
  ("Fix \"check\"") and the series "VTM5: Adjust dh / ch / hv / final k".

## Intonation and rhythm

The tables moved from code (GnuspeechSA `EventList.cpp:659–673, 827–876`) to
`intonation_rhythm/*.txt`, with the **same values**: rhythm 19.36 / −117.7 /
180 and 2.08 / −18.5 / 140, slopes 0.01 / 0.015 / 0.02 / 0.03, the −40 ms
offset, and the tone-group tables. But the behaviour changed:

| Change | Commit | Effect |
|---|---|---|
| GnuspeechSA truncated macro intonation to whole semitones (`static_cast<long>`, its `EventList.cpp:1029`) | fixed in `8bbd47c` | Smoother pitch. The bug is in GnuspeechSA 0.1.5 (introduced `7789b795`). |
| Smooth (cubic) intonation has its own switch; GnuspeechSA forced it on with macro intonation | `094ebe3` | Same default sound, more control. |
| The cubic is solved in milliseconds where GnuspeechSA used ms/4 | `7b85a7b` | Slopes at the points are effectively 4× steeper with the same numbers (inferred from code). |
| Pitch starts at `initial_pitch` (−20) and runs straight to the first point; held flat after the last | `2a1fd65`, `fc1d6e3` | Measured: the first frame is −36 in GamaTTS against −14 in GnuspeechSA. |
| `intonation_factor` per voice (0.8 female, 0.5 children in model 5) | `EventList.cpp:912` | Flatter intonation for those voices. |
| Pitch drift: ±4 semitones at its input (about 0.43 RMS at its output, computed 2026-11-02), low-passed at 4 Hz with a 2nd-order Butterworth. GnuspeechSA: ±0.5 at 0.5 Hz, 1st order | `d112550` | Much livelier, less robotic default pitch. |
| Foot tempo clamped to 0.2–2.0 before the global tempo is applied | — | Minor. |

## Timing and the tube interface

- **Interpolation moved** from the tube (`Tube.cpp` in GnuspeechSA) into
  `Controller::synthesize` (`cfddcb4`). The tube interface is now just
  `setAllParameters()` / `execSynthesisStep()`, which is what made several
  tube models possible.
- **Internal rate.** GnuspeechSA rounded the tube rate down to a whole
  multiple of the control rate (`Tube.cpp:518–520`): 20,000 Hz for the male
  voice, which implies a 17.53 cm tube. GamaTTS keeps the exact 20,034 Hz and
  uses 80 samples per 4 ms frame, so speech runs 0.17 % faster and formants
  are 0.17 % higher. **Measured:** output length ratio 0.99832 against the
  predicted 20,000/20,034 = 0.99830.
- **Control period** is configurable from 1 to 4 ms (`657f8ce`). The default of
  4 ms equals GnuspeechSA's 250 Hz.
- **Output** is 48 kHz by default; GnuspeechSA offered 22,050 or 44,100 Hz.
- **Minimum radius** is 0.01 cm instead of 0.001 cm (`6423352`).
- GamaTTS throws an exception when two postures fall too close in time
  (`5177e00`) instead of continuing.

## Program interface

| | GnuspeechSA 0.1.5 | GamaTTS |
|---|---|---|
| Command line | `gnuspeech_sa -c config_dir -p trm_param.txt -o out.wav "text"` | `gama_tts tts [-v] [-i in.txt] [-p params.txt] voice_dir [out.wav]`, plus `pho` (phonetic string in) and `vtm` (parameter file in) |
| Parameter file | Required, with a 25-line header (rates, voice, tube settings) | Optional; frames only, the voice comes from the voice directory |
| Library | Shared library, installed headers, `pkg-config` | Static `libgamatts`, not installed |
| C++ call sequence | `Controller` with a template text parser | `Index` → `Model::load` → `Controller(index, model)` → `TextParser::getInstance()->parse()` → `synthesizePhoneticStringToFile` / `…ToBuffer` |
| C API | None | None |
| Data directory | One `data/en` with all voices as config files | One directory per voice, with `_index.txt` pointing at shared parts |

## Compared with the older Gnuspeech systems

These notes concern the C++ line. Short pointers for the older systems,
kept in this collection as pristine references:

- **NeXT TextToSpeech Kit (1991–95):** the same TRM ran on the DSP56001, with
  a C software version beside it. The model-0 tube code still carries the
  "temporary fix only, to try to match dsp synthesizer" input scale (2⁻³
  instead of 2⁻⁵, `VocalTractModel0.h:47`) and the 1994–95 revision history
  in `gama_tts/doc/gnuspeech_trm_history.txt`.
- **Gnuspeech 0.9 for Mac OS X:** Monet (the rule editor and real-time
  synthesizer) and TRAcT (interactive tube control), in Objective-C with a C
  tube (`Applications/TRAcT/tube.c`). GamaTTS:Editor reproduces Monet's
  windows. Its interactive tube window stands in for TRAcT, without TRAcT's
  drawings ([chapter 5](05-editor-and-accessibility.md)). Gnuspeech 0.9 runs
  only on macOS; GamaTTS is plain C++ and builds anywhere with a C++17
  compiler.
