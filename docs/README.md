# GamaTTS: notes and record

**To use the add-on or the GUI, start at [chapter 11](11-using-it.md).** To see how they were made and checked, [chapter 10](10-model5-api-gui-addon.md).

Chapters 1 to 9 are a study of **GamaTTS**, Marcelo Y. Matuda's experimental
articulatory text-to-speech system. They cover how it makes sound, what it is
written in, and how it differs from the Gnuspeech it grew out of. Chapters 1 to 8 were
written on 2026-10-16 from reading the source and from measurements on Windows
11 x64. They are not upstream's documentation: that is in `../doc/` (the
GamaTTS website source) and `../gama_tts/doc/`.

Nothing in GamaTTS was changed for chapters 1 to 9. All builds and runs took place
outside the repository, and every number below says how it was obtained.

**Status of the engine (upstream's words):** alpha. English only. "The quality
of the synthesized speech is much lower than that of the best speech
synthesizers."

## Contents

| # | Document | What it covers |
|---|----------|----------------|
| 1 | [What it is](01-what-it-is.md) | Lineage from NeXT Gnuspeech, languages, size, licences, repository layout |
| 2 | [How it makes sound](02-how-it-makes-sound.md) | Text in, samples out, stage by stage |
| 3 | [The vocal tract models](03-vocal-tract-models.md) | The six tube models, 0 to 5, and what each one changes |
| 4 | [Differences from Gnuspeech](04-differences-from-gnuspeech.md) | What changed since GnuspeechSA 0.1.5, what did not, and how much it matters |
| 5 | [Editor, tools and accessibility](05-editor-and-accessibility.md) | GamaTTS:Editor against Monet and TRAcT, the Speech Dispatcher module, screen-reader use |
| 6 | [Building and running](06-building-and-running.md) | 64-bit builds with GCC and MSVC on Windows, the CRLF trap, the command line |
| A | [Measurements](07-measurements.md) | Every number in these documents, and how it was obtained |
| 8 | [Open items](08-open-items.md) | What is still unknown or untested |
| 9 | [Can it become an add-on and a GUI?](09-addon-and-gui-feasibility.md) | The study of 2026-11-02: what works, the defects and their fixes, the C API and GUI plan |
| 10 | [Building model 5](10-model5-api-gui-addon.md) | What was built after the author chose model 5 by ear: the API, the GUI, the add-on, how each was checked, and what is still open |
| 11 | [Using it](11-using-it.md) | The manual: the add-on's settings, the GUI's keys, all 49 parameters, the C API |
| 12 | [The record of 2026-11-02](12-record-of-2026-11-02.md) | Every step in order, every failed attempt, every decision and whose it was |

The scripts behind the measurements are in [`measurements/`](measurements/), those of chapter 9 in [`measurements/feasibility/`](measurements/feasibility/README.md), and those of chapter 10 in [`measurements/gama5/`](measurements/gama5/README.md), with `../tools/` and `../tests/`.

## One-paragraph summary

GamaTTS shares its git history with GnuspeechSA up to `539d75a` ("Version
0.1.5", 2015). It then adds 347 commits of its own, the last in 2025. Its
classic path ("model 0", the `0_*` voices) still makes the same sound as Gnuspeech. The text
front end and dictionary give identical phonetic strings. The Monet rule
database gives identical articulatory tracks, within print rounding. The
classic 10-section tube gives the same spectrum, within 0.2 dB in every band.
What is new: a 30-section tube with flow equations and a physically fitted
lip-radiation impedance (model 5, the default voice by convention only); retuned and less
monotone intonation; MBROLA `.pho` input; and a cross-platform Qt clone of
Monet. Everything is C++17, it builds 64-bit with GCC and, with two flags, with
MSVC, and the two builds give byte-identical output.

## Conventions

- **Known** means checked in source or measured, with the reference given.
  **Inferred** means reasoned from the code without a run. **Unknown** means
  just that.
- Paths are relative to the repository root unless they begin with a drive
  letter. Commit hashes are this repository's.
- "GnuspeechSA" means upstream GnuspeechSA 0.1.5 (`539d75a`), the C++ port from
  which GamaTTS branched. "Gnuspeech" means the family as a whole.
- **Corrected 2026-11-02** from the source, while writing Speechialization's
  docs/10 §2b, which also holds what these notes left out: chapter 3 on model 4's
  18-section nose and its different grid, and on model 5's junctions; chapters 1
  and 4 on the special-transition counts; chapter 2 on `duration`. The measurements
  in chapter 7 were not re-run.
