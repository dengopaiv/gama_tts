# Measurements for chapter 10: building model 5

Behind [`../../10-model5-api-gui-addon.md`](../../10-model5-api-gui-addon.md), taken on 2026-11-02 on Windows 11 x64, with Visual Studio 2026 (MSVC 19.51), CMake 4.4, Python 3.13.

| File | What it is |
|---|---|
| `results-2026-11-02.txt` | The output of `run_all.sh`: the C tests, the golden comparison, robustness with `--long`, levelling, the pitch balance, the end tick, the ends of utterances, spelled lengths, and the driver |
| `gui-check-2026-11-02.txt` | `tests/gui/gui_check.py`, the GUI read through MSAA on a private desktop. Local paths in its status lines were replaced with `<path>` |
| `robustness-asan-2026-11-02.txt` | `tests/api/check_robustness.py` against the API built with AddressSanitizer, in its routine length. Its 45 "Duplicate word" lines at each engine load are the engine's own, and harmless |
| `run_all.sh` | Makes the first file |
| `port/` | The scripts that made the first version of the GUI, the driver and the GUI's check from Gnuspeech's: below |
| `port/later-edits/` | The scripted edits made after that, in order, as a record of each: [README-later-edits](port/README-later-edits.md) |
| `raw/` | The logs of the long runs as they came out, failures included: [README](raw/README.md) |
| `check_record.py` | Checks that the session's facts are written where chapter 12 says |
| `check_shipped_gnuspeech.py`, `shipped-gnuspeech-2026-11-02.txt` | The long-token and tempo tests on the DLL unpacked from Gnuspeech add-on 1.2.0, and the run |
| `check_spelling_limit.py`, `spelling-limit-2026-11-02.txt` | Which spelled runs really overflow the unguarded parser, and the run |
| `session_audit.py` | Reads Claude Code's transcript: the full log of a session, and every result that looks like a failure, for comparing with chapter 12 |

`run_all.sh` says how to run it. It needs a build as in chapter 10. The other two have their commands in `tests/README.md`.

## `port/`: how the code was derived

The GUI, the driver and two of the tests began as Gnuspeech's, in `GnuspeechSA-NVDA` at its commit `be3dce8`, branch `gui`, plus its working tree of 2026-11-02. They were converted by these scripts, in which every replacement must apply or the script stops, so that nothing could be missed quietly.

They are kept as a record of how the code came to be, and they are not meant to be run again. They name absolute folders, and the code has moved on since. **The files themselves, and git, are the current truth.** Each change after the port is in chapter 10.

| Script | Made |
|---|---|
| `port_gui.py` | `gui/gama_gui.cpp` |
| `port_driver.py` | `nvda-addon/addon/synthDrivers/gamatts.py`, `tests/nvda/test_driver.py` |
| `port_guicheck.py` | `tests/gui/gui_check.py` |

`api/gama_api.cpp`, `api/gama_api.h`, `tests/api/*` and `nvda-addon/package.py` were written by hand with Gnuspeech's open beside them. The levelling in the API is carried over nearly as it was, and the tube and parameter handling are new.
