# 1. What it is

## In one sentence

GamaTTS is an **articulatory** text-to-speech system. It produces speech by
simulating air pressure waves travelling through a model of the human vocal
tract (a tube whose cross-sections change over time), not by filtering a
source through formant resonators and not by joining recordings.

## Lineage

Each step below is documented in the source or the history; the reference is
given.

| Year | Stage | Language | Where it is recorded |
|---|---|---|---|
| 1991–1995 | **Trillium TextToSpeech Kit** for NeXTSTEP, by David R. Hill, Leonard Manzara and Craig Schock. The tube ran on the NeXT's Motorola DSP56001; a C "software TRM" also existed. The rule editor was **Monet**. | Objective-C, C, DSP56001 assembly | Gnuspeech Subversion repository, `nextstep/` |
| 2002 onward | Released as **GNU Gnuspeech** under the GPL. Later ported to Mac OS X (Gnuspeech 0.9: Monet, TRAcT, frameworks). | Objective-C, C | Copyright lines in every engine header: "1991 … 2002 David R. Hill, Leonard Manzara, Craig Schock" |
| 2014-08-02 | Matuda takes Subversion **revision 672**, directories `nextstep/trunk/ObjectiveC/Monet.realtime` and `nextstep/trunk/src/SpeechObject/postMonet/server.monet`, and starts a C++ port. | — | `gama_tts/README.md` |
| 2014-09-26 → 2015-08-23 | **GnuspeechSA** ("stand-alone"), versions up to 0.1.5. Published on GNU Savannah. | C++11 | First commit `7ea175b`; tag commit `539d75a` |
| 2015-08 → 2025-09 | **GamaTTS**: same repository, renamed and developed further, through versions 0.1.7, 0.2 … 0.9 (2019-12-22) and "2023_07_16". The editor and the Speech Dispatcher module were merged in on 2023-07-15. | C++17 | `git log 539d75a..HEAD`: 347 commits, all by Matuda |

So the first commit of GamaTTS **is** the first commit of GnuspeechSA, with the
same hash. `git merge-base --is-ancestor 539d75a HEAD` succeeds.

The name: "GAMA" is not explained in the repository (unknown).

## What it is written in

Counted over tracked files (`git ls-files`) on 2026-10-16 at `b108ad6`:

| Part | Language | Files | Lines | Notes |
|---|---|---|---|---|
| `gama_tts/` — engine library and command-line program | **C++17** | 106 `.cpp`/`.h`/`.hpp` | 25,822 | No dependencies outside the C++ standard library. Includes RapidXml (2,648 lines, header-only, third-party). |
| `gama_tts_editor/` — GamaTTS:Editor | **C++17** with **Qt** 5 or 6 | 75 `.cpp`/`.h`, 12 Qt Designer `.ui` | 14,868 + 4,571 | Also needs FFTW 3 (single precision) and JACK. |
| `speechd_module/` — Speech Dispatcher output module | **C++17** | 11 | 13,469 | Of which 12,277 are the bundled RtAudio library. |
| `script/python3/`, `doc/gen_site.py` | **Python 3** | 16 | 606 | Analysis scripts for mouth radiation impedance, and the documentation-site generator. Not needed at run time. |
| Build | **CMake** | 3 | 485 | One `CMakeLists.txt` per part. |
| `data/` | Data: **XML** and key = value text | 2 XML, 69 text | 11,114 XML | The articulatory database (`artic.xml`), voice and model configuration, the 74,115-entry dictionary (`main_dictionary.txt`, 2.3 MB). |
| `doc/` | Plain text with light markup, rendered to HTML by `gen_site.py` | 32 | 1,202 | The user manual for the program and the editor. |

The C++ standard is set to 17 in all three `CMakeLists.txt` (for the engine,
only under `if(UNIX)`; see [chapter 6](06-building-and-running.md)).
GnuspeechSA used C++11 (`reference repositories/gnuspeechsa/CMakeLists.txt`).

**Style of the C++.** Classes and templates over the floating-point type
(`VocalTractModel0<double>`, `VocalTractModel0<float>`), `std::unique_ptr`
everywhere, exceptions for errors, and header-only DSP classes in `src/vtm/`.
The tube code keeps the original's capitalised comment banners ("CALCULATE THE
SCATTERING JUNCTIONS FOR S1-S2"), which makes it easy to compare with the C
original line by line.

## Repository layout

```
gama_tts/            engine library (libgamatts, static) + gama_tts command-line program
  src/text_parser/       English text normalisation, dictionary lookup, letter-to-sound
  src/vtm_control_model/ the Monet rule engine: postures, rules, transitions, intonation
  src/vtm/               the vocal tract models (tubes) and their filters
  src/xml/, rapidxml/    XML reading for artic.xml
  doc/                   two short notes: the model list, and old TRM revision history
gama_tts_editor/     GamaTTS:Editor (Qt), "an approximate clone of Monet"
speechd_module/      Speech Dispatcher module (Linux), links libgamatts
data/voice/english/  the voices: 0_* use model 0, 1_male to 4_male models 1–4, 5_* model 5
doc/                 user documentation (website source)
script/python3/      radiation-impedance studies (Chalker, Flanagan, Laine, piston models)
docs/                these study notes (not upstream)
```

## Size of the data

- `data/voice/english/0_male/artic.xml` (287 KB): 65 postures, 47 rules, 110
  equations, 62 transitions, 32 special transitions, 16 parameters.
- `data/voice/english/5_male/artic.xml` (257 KB): the same 65 postures and 47
  rules, retuned for model 5; 92 equations, 36 transitions, 22 special transitions.
- `main_dictionary.txt`: 74,115 lines, one word per line with its
  pronunciation in Gnuspeech notation and a part-of-speech code, for example
  `abbreviate uh.'b_r_ee.v_i."e_i_t%b`.

## Licences

| What | Licence | Holder |
|---|---|---|
| Almost all source (about 182 file headers), including editor and module | GPL-3.0-or-later | Hill, Manzara, Schock (engine code derived from Gnuspeech) and Matuda |
| `data/` | GPL-3.0-or-later (`data/README.txt`) | Hill, Manzara, Schock; "modified by Marcelo Y. Matuda" |
| `ConfigurationData.{h,cpp}`, `Exception.h`, `vtm/VocalTractModel.h`, `vtm/VocalTractModelPlugin.{h,cpp}` | BSD-3-Clause (relicensed by the author so that tube plugins can be written under other terms) | Matuda |
| `gama_tts/src/rapidxml/` | Boost 1.0 or MIT | Marcin Kalicinski |
| `speechd_module/src/rtaudio/` | MIT-style (RtAudio) | Gary P. Scavone |
| `doc/gen_site.py`, `script/python3/` | Public domain (stated in the files) | Matuda |
| User documentation | CC BY-SA 4.0 | Matuda |
| Intel One Mono font in the documentation site | SIL OFL 1.1 | Intel |

The repository's `LICENSE.txt` is the GPLv3 text.

## This copy

`dengopaiv/gama_tts` on GitHub is a **public fork** of `mym-br/gama_tts`,
created 2026-10-16. Its `master` stays level with upstream's `b108ad6` (2025-09-12). Its
branch `model5` holds this `docs/` folder and the work of [chapter 10](10-model5-api-gui-addon.md).
