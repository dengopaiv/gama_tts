
GamaTTS
=======

> **This is a fork,** `dengopaiv/gama_tts` of Marcelo Y. Matuda's `mym-br/gama_tts`, with a C API, a desktop GUI and
> an NVDA add-on for **model 5**, the 30-section tube.
>
> **Status (2026-11-02): built and tested from outside, not yet used in NVDA.** The API reproduces the unchanged engine
> sample for sample on 1,472 golden rows at tempos up to 3.5. The add-on (`nvda-addon/`, version 0.1.0) passes its tests with
> stand-ins for NVDA, and the GUI (`gui/`) passes a check through MSAA. Neither has been used with a screen reader yet, and
> nothing here has been judged by ear except the voice itself.
>
> - **Build, test and what was checked:** [docs/10](docs/10-model5-api-gui-addon.md). **Who made what:** [NOTICE.md](NOTICE.md).
> - **The engine has four small fixes, in three files,** listed in `NOTICE.md`. Without them it crashes or falls silent at high tempo, and reads
>   past its buffers on some text. At tempos up to 3.5 they change no sample.
>
> 64-bit only. Windows only so far: the engine is portable, the API has been written for Unix and not built there, and the
> add-on is for NVDA. Everything below is upstream's own text.

GamaTTS is an *experimental* articulatory synthesizer that converts text to
speech, derived from [Gnuspeech][].

[Gnuspeech]: http://www.gnu.org/software/gnuspeech/

Status
------

**alpha**

Only english is supported.

The quality of the synthesized speech is much lower than that of the best speech
synthesizers. This software is mostly for people interested in articulatory
speech synthesis.

Contents
--------

- gama_tts/ - Library and command-line application. This module contains the
  synthesis code.
- gama_tts_editor/ - GamaTTS:Editor, the editor for the articulatory database,
  which is used by gama_tts.
- speechd_module/ - Module for Speech Dispatcher.
- data/ - The articulatory database and other data.
- doc/ - The documentation for GamaTTS and GamaTTS:Editor.

OS support
----------

- GamaTTS: Multiplatform software developed in C++ with no external
  dependencies.
- GamaTTS:Editor: Multiplatform software developed in C++.
  It may work on any OS supported by Qt (5 or 6), FFTW and JACK Audio Connection
  Kit.
- Module for Speech Dispatcher: Multiplatform software developed in C++. It may
  work on any OS supported by Speech Dispatcher and RtAudio.

License
-------

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
LICENSE.txt file for more details.
