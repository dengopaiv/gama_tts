# 5. Editor, tools and accessibility

*This chapter is about upstream's own editor. This fork's accessible GUI, which does a different job, is in [chapter 11](11-using-it.md).*

## GamaTTS:Editor against Monet and TRAcT

`gama_tts_editor/README.md` calls it "an approximate clone of Monet". It is a
Qt Widgets program (Qt 5.15 by default, Qt 6 with `-DGAMATTS_QT_VERSION=6`).

The main window (`ui/MainWindow.ui`) opens these windows:

| GamaTTS:Editor window | Monet counterpart (Gnuspeech 0.9) | Notes |
|---|---|---|
| Data entry: categories, parameters, symbols (`DataEntryWindow`) | `MDataEntryController` | |
| Posture editor (`PostureEditorWindow`) | `MPostureEditor` | |
| Prototype manager: equations, transitions, special transitions (`PrototypeManagerWindow`) | Prototype manager | |
| Transition editor / special transition editor (`TransitionEditorWindow`, one class, `setSpecial()`) | Transition editors | Points can be added only by double-clicking the graph |
| Rule manager: expressions, symbol equations, parameter transitions, special transitions, comments (`RuleManagerWindow`) | Rule manager | |
| Rule tester (`RuleTesterWindow`) | Rule tester | |
| Synthesis window (`SynthesisWindow`) | Synthesis window, event table, graphs | Parameter graph drawn by hand |
| Intonation window and intonation parameters | Intonation window | |
| **Interactive VTM** (`interactive/InteractiveVTMWindow.cpp`) | TRAcT, partly | Sliders and text fields for every tube parameter, live audio through JACK. There is no tube drawing, velum slider or glottal-pulse view as in TRAcT. |
| **Analysis** (`interactive/AnalysisWindow.cpp`) | TRAcT's analysis, partly | Live spectrum or waveform of the interactive output (FFTW, five window types). No spectrograph. |
| **Parameter modification** | — | New: change a parameter in real time by moving the mouse while it plays |

Monet's separate event table, graph and display-parameter panels and its
inspectors have no window of their own. Some of that is probably inside the
synthesis window (inferred from file names only).

Each window has a page in the user manual, `doc/gama_tts_doc/data/content_editor_*.txt`.

## Build requirements and platforms

| Part | Needs | Tested by upstream | Windows outlook |
|---|---|---|---|
| Engine `gama_tts` | C++17 compiler, CMake ≥ 3.12 | GCC 12.2, Clang 14 on Linux x86-64 | **Works**: built and run here with MinGW-w64 GCC 16.2 and MSVC 19.51, both x64 ([chapter 6](06-building-and-running.md)) |
| Editor | Qt 5/6 (Core, Gui, Widgets, PrintSupport), FFTW 3.3 single precision, JACK, all through `pkg-config`; links `../build-gama_tts/libgamatts.a` by fixed path | GCC 12.2 on Linux | Possible but awkward (inferred): JACK2 for Windows exists, FFTW via MSYS2 or vcpkg, and the fixed `.a` path has to change for MSVC. All audio goes through JACK (`AudioPlayer.cpp:82`), so a JACK server must run. |
| Speech Dispatcher module | Speech Dispatcher 0.11, bundled RtAudio (ALSA, PulseAudio or JACK backends only) | GCC 12.2 on Linux | Linux only by nature |

## The Speech Dispatcher module

`speechd_module/` (status "alpha") speaks Speech Dispatcher's module protocol:
INIT, AUDIO, LOGLEVEL, SET, SPEAK, STOP, QUIT. CHAR, KEY and SOUND_ICON are
spoken as text. There is no PAUSE.

- **Applied:** pitch (`pitchOffset = default + pitch/10`), rate
  (`tempo = 10^(rate/100)`), and spelling mode.
- **Ignored:** volume, voice and language are parsed and stored but not used.
  The voice is fixed in `conf/gama_tts.conf.pre` (`english/5_male`).
- **SSML** tags are stripped. There are **no index marks**, only begin, end
  and stop events.
- **Not streamed:** it synthesises the whole utterance into a buffer
  (`synthesizePhoneticStringToBuffer`) before playing it through RtAudio,
  with a fade-out on STOP. Latency equals the synthesis time of the whole
  utterance: about 1/60 to 1/120 of its duration ([chapter A](07-measurements.md)).

## Accessibility of the editor

Checked by reading the `.ui` files and the widget code. **Not tested with a
screen reader.**

- There is **no** `QAccessible`, `setAccessibleName` or
  `setAccessibleDescription` anywhere in `src/` or `ui/`. Labels are not
  linked to their fields with `buddy`, so a screen reader may announce some
  fields without a name (inferred).
- **Standard Qt controls**, which Qt exposes through UI Automation and which
  NVDA should therefore read:
  - data entry: three `QTableView`;
  - posture editor: four `QTableWidget`;
  - prototype manager: three `QTreeWidget` and a `QPlainTextEdit`;
  - rule manager: tables, lists, trees and line edits;
  - rule tester: eleven line edits;
  - intonation parameters: spin boxes and check boxes;
  - transition editor: a table of points, a tree of equations and a type
    combo box;
  - interactive VTM: sliders and line edits.
- **Custom-painted widgets**, which NVDA cannot read: `TransitionWidget`,
  `ParameterWidget`, `IntonationWidget`, `ParameterModificationWidget` and
  `Figure2DWidget`.
  - Keyboard support: `IntonationWidget` handles Delete, Up/Down (one
    semitone) and Left/Right (move a point to another rule). But a point must
    first be **selected with the mouse**, and a new point needs a
    double-click.
  - `Figure2DWidget` handles only Space, to toggle point markers.
  - The other three widgets have no keyboard handling at all.
- **Mouse-only tasks:** adding points to transitions and to the intonation
  contour, selecting intonation points, real-time parameter modification, and
  reading values from any graph (hover readouts).

An estimate: about three quarters of the data editing can be done with
standard controls. The remaining quarter is mouse-only, and it includes the
core of designing transitions and intonation.

By the standard this collection holds itself to (every GUI fully usable from
the keyboard with NVDA), the editor would need, at least:

- accessible names on all fields;
- a keyboard way to add and select points;
- a text or table view of each graph, so that its values can be read.

## Other tools

- `script/python3/impedance_at_mouth/`: studies of the mouth radiation
  impedance, comparing models after Chalker, a circular piston, Flanagan,
  Laine, the pole-zero approximation and a spherical baffle. Two scripts find
  the constants model 5 uses. The folder holds an image, `kinsler.jpg`, of
  unknown origin. The name suggests Kinsler's *Fundamentals of Acoustics*
  (inferred, not checked).
- `doc/gen_site.py`: builds the HTML manual from `doc/gama_tts_doc/data/`.
