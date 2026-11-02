# Golden traces

The frozen reference for this repository's additions, taken on 2026-11-02, before any change to the engine.
Everything since is checked against them. See [`../../docs/10-model5-api-gui-addon.md`](../../docs/10-model5-api-gui-addon.md), section 3.

**What they are:** the output of the unchanged GamaTTS engine at upstream's `b108ad6`, through upstream's own command line `gama_tts`, for the 184
lines of [`corpus.txt`](corpus.txt): all five model 5 voices at tempo 1, and the male voice at tempos 2, 3 and 3.5.

`corpus.txt` is the same file as `GnuspeechSA-NVDA`'s, byte for byte, so its header names that project. 38 lines are screen-reader strings, and 146 are *The Chaos*, by Gerard
Nolst Trenité, in the public domain.

**What a row of `msvc-x64.tsv` holds:** voice, tempo, line number, a SHA-256 of the 16-bit samples, a SHA-256 of the file `-p` writes, the sample count, the peak, the rate, and the text.
`FAIL` means the engine refused the line (`*` and `...`).

**How they were made,** with `gama_tts` built from unchanged source by MSVC 19.51, x64, Release:

```
python -I tools/golden/make_golden.py <gama_tts.exe> msvc-x64
```

The script refuses to run if `gama_tts/` or `data/` differ from `b108ad6`, so it cannot be run again in this tree as it stands, now that the patch is applied. To make them again, work on a
checkout of `b108ad6`. It takes the data from git with LF endings, turns off random intonation and drift in its copy, passes the text with `-i`, and runs everything twice, writing nothing unless both agree.

**What holds them:** `tests/api/check_golden.py`. The API, at gain 1.0 in peak mode with trimming off, must give these samples and these tracks exactly. They do not reach above tempo 3.5, since the
patch changes the output from about 3.85, where the unchanged engine goes wrong.
