# The NVDA add-on

The synthesizer driver for GamaTTS, model 5. **Version 0.1.0: tested with stand-ins for NVDA, and not yet used inside NVDA.**

| File | What it is |
|---|---|
| `addon/synthDrivers/gamatts.py` | The driver. Everything that makes speech is in `gama_api.dll` and the data |
| `manifest.ini` | NVDA's manifest. `lastTestedNVDAVersion` is the version it is meant for, and not yet a fact |
| `package.py` | Builds, tests, packages, then tests the package |
| `gamatts-<version>.nvda-addon` | What `package.py` makes. Git ignores it, so it is not in the repository |

```sh
python -I nvda-addon/package.py                # about 15 minutes, with every test
python -I nvda-addon/package.py --skip-tests   # builds and packages only
```

It needs CMake, Visual Studio 2026 (or `--generator "..."`), and Python 3 with numpy and scipy. 64-bit only.

What goes in the package: the driver, the DLL, model 5's five voices, what they share from `data/voice/english/0_male` (the dictionary, the intonation tables, the phonetic string rules), and the licence files. Not model 0's rules. `package.py` refuses a data file with CRLF endings, since the engine would refuse it.

How to use it: [docs/11](../docs/11-using-it.md). How it was built and checked: [docs/10](../docs/10-model5-api-gui-addon.md). It is adapted from the Gnuspeech add-on: [NOTICE.md](../NOTICE.md).

**Testing it inside NVDA is still to do.** Use a portable copy where you can, and try long unbroken text among the rest.
