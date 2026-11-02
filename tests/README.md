# The tests

`ctest --test-dir build-x64 -C Release --output-on-failure` runs all but the GUI's outside check, in about 10 minutes. Results and how they are recorded: [docs/10](../docs/10-model5-api-gui-addon.md), section 9.

| Test | `ctest` name | What it holds to |
|---|---|---|
| `api/api_test.c` | `api` | Ranges, NULLs, the error path, chunked reading, volume across voice changes, trimming, the parameter table and its shared limits, the tick, two independent engines. Plain C17 |
| `api/check_golden.py` | `golden` | Samples and tracks identical to the unchanged engine on 1,472 rows. **Run this after any change in the text path or the engine.** It has caught what nothing else would |
| `api/check_robustness.py` | `robustness` | Tempos 0.1 to 10, hostile tokens and text, malformed phonetic strings, every parameter at its limits, random settings. `--long` takes longer, and goes further |
| `api/check_leveling.py` | `leveling` | The levelled modes against an independent measure, all five voices. Needs numpy and scipy |
| `nvda/test_driver.py` | `driver` | The driver's queue, index marks, cancel, settings, spelling and text folding, against the real DLL with stand-ins for NVDA. `--addon <file>` runs it on a package, unzipped |
| `gui/gui_check.py` | not in `ctest` | The window as NVDA would read it, through MSAA, on a private desktop. Needs comtypes, numpy, scipy |
| `golden/` | | The frozen reference: [golden/README.md](golden/README.md) |

**The GUI's check:**

```sh
python tests/gui/gui_check.py build-gui/Release/gama_gui.exe build-gui/Release/gama_api.dll "$PWD/data" tests/golden/msvc-x64.tsv
```

It runs on a private desktop, so your keys cannot reach it and NVDA never sees it. **Its sound still goes to the real output device,** since `wxSound` knows nothing of desktops, so it saves a WAV first, and proves that it is silent, before playing anything.

**Under AddressSanitizer:** see [docs/measurements/feasibility/README.md](../docs/measurements/feasibility/README.md) for the flags. Add `-DGAMA_BUILD_GUI=OFF`, and copy `clang_rt.asan_dynamic-x86_64.dll` beside `gama_api.dll`, because Python does not look on `PATH` for a DLL's dependencies. `check_robustness.py` found a bug this way that Release runs could not.

**Writing tests here:** type into a number field with `WM_CHAR`, not `WM_SETTEXT`, which never reaches the engine. And when checking the text path, use one letter repeated as well as random text, since random tokens hid the worst case.
