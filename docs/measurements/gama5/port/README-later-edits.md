# The scripted edits after the port

One-time scripts, in the order they were applied, in which every replacement had to apply or the script stopped. They are a record, not to be run again. Two earlier code changes were made directly: the API's guard of 45 letters, and the value conversion (`docs/12`, F6, F7).

These scripts, and the `port_*.py` beside them, keep the absolute paths they ran with, `C:\GIT\speech synthesis\...`, because they are a record of what was run. No user name is in them.

Scripts that changed only documents are not kept: the documents, and `git log`, show their effect.

| Script | What it did |
|---|---|
| `later-edits/fix_tick.py` | The end tick (rule 12), `_MAX_PIECE`, and the tests of both |
| `later-edits/fix_guicheck.py` | The GUI check types real keys; `formatExact`; Gnuspeech's item 15 |
| `later-edits/fix_validator.py` | The validator removed from number fields |
| `later-edits/fix_note.py` | First focus test in the text handler (wrong object: F13) |
| `later-edits/fix_note2.py` | The focus test corrected |
| `later-edits/fix_silent.py` | The check's safeguard corrected: F14 |
| `later-edits/fix_light.py` | `light()` in the engine |
| `later-edits/fix_guard.py` | The guard by spelled length, after F8 |
