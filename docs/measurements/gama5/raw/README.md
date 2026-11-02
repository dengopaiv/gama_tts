# Raw logs of 2026-11-02

The long runs of [chapter 12](../../../12-record-of-2026-11-02.md), as they came out, with local paths replaced by `<path>`, failures included. The final results are in `../results-2026-11-02.txt`, and chapter 9's in `../../feasibility/`.

Output that went only to the screen is not here, and its results are in chapters 9, 10 and 12.

| File | What it is |
|---|---|
| `01-golden-first-attempt-failed.txt` | `make_golden.py`, before `gama_tts` was built: F5 |
| `02-golden-made.txt` | The golden traces made: 1,472 rows, two runs identical |
| `03-robustness-died-in-tokens.txt` | Robustness with the 100-character guard: the process dies, exit 127. F7 |
| `04-robustness-first-pass.txt` | After the first spelling guard, with the longer token stage |
| `05-asan-dll-would-not-load.txt` | Python could not load the ASan DLL: F15 |
| `06-asan-stopped-at-time-limit.txt` | Exit 124, my time limit, every stage so far clean: F16 |
| `07-package-golden-failed.txt` | The package build's golden test refusing the guard that broke a URL: F8 |
| `08-final-asan-and-package.txt` | The final ASan run and the final package build, all passed |
| `09-study-byte-identity-threads-memory.txt` | Chapter 9: patch against unchanged, repeatability, threads, memory, pitch |
| `10-study-asan-fuzz.txt` | Chapter 9: the ASan fuzz that found the trie read |
| `11-study-asan-fuzz-after-trie-fix.txt` | Chapter 9: ASan fuzz after that fix, ended by time limits |
