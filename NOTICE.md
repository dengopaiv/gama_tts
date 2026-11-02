# Notices and attributions

This repository is a fork of GamaTTS with an NVDA add-on and a desktop GUI added.
Almost all of the speech in it is other people's work. This file records who made what,
and under what terms, as accurately as we can state it.

## Gnuspeech: David R. Hill, Leonard Manzara, Craig Schock

The vocal tract models, the control model, the English text front end and the data in
`data/` (the postures and rules, and the pronouncing dictionary) come from Gnuspeech. It
began as Trillium Sound Research's commercial text-to-speech system for NeXT computers,
and was later donated to the GNU project.

> Copyright 1991, 1992, 1993, 1994, 1995, 1996, 2001, 2002
> David R. Hill, Leonard Manzara, Craig Schock

The licence is the GNU General Public License, version 3 or (at your option) any later
version. The full text is in `LICENSE.txt`. `data/README.txt` gives the terms of the
data. Project home: <https://www.gnu.org/software/gnuspeech/>.

## GamaTTS: Marcelo Y. Matuda

GamaTTS is Marcelo Y. Matuda's continuation of his C++ port of Gnuspeech, GnuspeechSA, and
holds his work on the vocal tract models, among them model 5, the one this fork's add-on
and GUI use: <https://github.com/mym-br/gama_tts>.

Everything in `gama_tts/`, `gama_tts_editor/`, `speechd_module/`, `doc/`, `script/` and
`data/` is his, or comes through him, at upstream commit `b108ad6` (2025-09-12), under
GPL-3.0-or-later and the other terms given in those files, except for the changes
listed below. A few files are BSD-3-Clause, and say so.

**Changes of ours to his code**, in full:

- `gama_tts/src/vtm_control_model/EventList.cpp`: intonation points are sorted by time
  before interpolation, and two divisions by a time of zero are guarded (`docs/09`, section 2).
- `gama_tts/src/text_parser/english/IspTrans.cpp`: a bounds check on the trie
  (`docs/09`, section 3).
- `gama_tts/src/text_parser/english/ApplyStress.cpp`: a syllable with no vowel no longer sends
  `light()` past the end of the buffer (`docs/10`, section 5).

With these, the samples of model 5 are unchanged at tempos up to 3.5, which
`tests/golden` proves. Nothing else under those folders differs from upstream.

## RapidXml: Marcin Kalicinski

`gama_tts/src/rapidxml/`: Copyright 2006–2009 Marcin Kalicinski, under the Boost Software
License 1.0 or the MIT licence, at the user's choice. See its `license.txt`.

## RtAudio: Gary P. Scavone

`speechd_module/src/rtaudio/`: RtAudio's own MIT-style licence, in its files. It is not
part of the add-on or the GUI.

## Ours, from GnuspeechSA-NVDA

`api/`, `gui/`, `nvda-addon/`, `tests/` and `tools/` are adapted from our add-on and GUI for
GnuspeechSA, the private repository `dengopaiv/IveHeardOfWildebeest`, under
GPL-3.0-or-later. Copyright 2026 dengopaiv.

## rsynth-nvda

`nvda-addon/addon/synthDrivers/gamatts.py`, `tests/nvda/test_driver.py`, `nvda-addon/package.py`
and `tests/gui/gui_check.py` descend, through that add-on, from rsynth-nvda's files of the
same purposes ("the rsynth-nvda contributors", GNU Library General Public License version 2
or later). The LGPL allows that code to be used under the GPL-3.0-or-later of this repository.

## The test corpus

`tests/golden/corpus.txt` holds "The Chaos" by Gerard Nolst Trenité (Charivarius,
1870–1946), which is in the public domain.

## Studied, not included

Hill, Manzara and Schock's Monet and TRAcT, and Fastfinge's earlier GnuspeechSA-NVDA add-on,
informed the work on the Gnuspeech add-on this descends from. No code of theirs was taken
beyond what is named above.
