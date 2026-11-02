"""Is each thing this session did written down where the record says it is?

    python -I docs/measurements/gama5/check_record.py

A list of facts, each with the file that should hold it and a phrase that must appear there. It
shows these are recorded. It cannot show that the list is complete: see docs/12.
Public domain. Written 2026-11-02.
"""

import os
import re
import sys

R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
HEAD = os.path.dirname(R)
D9, D10, D11, D12 = "docs/09-addon-and-gui-feasibility.md", "docs/10-model5-api-gui-addon.md", "docs/11-using-it.md", "docs/12-record-of-2026-11-02.md"
GS9, GS10, SP = "../GnuspeechSA-NVDA/docs/09-open-items.md", "../GnuspeechSA-NVDA/docs/10-gui.md", "../speechialization/docs/10-how-each-engine-sounds.md"
FACTS = [
	# The findings
	("wild pitch from tempo 3.9", D9, "1,270 (6.8 %)"), ("the cause, a clamped correction", D9, "beat1 < 32"), ("model 0 crash, ASan's frame", D9, "WavetableGlottalSource.h:225"),
	("model 5 silent", D9, "all zeros"), ("Gnuspeech unaffected by it", D9, "tempos 1 to 10"), ("long-token overrun", D9, "STATUS_STACK_BUFFER_OVERRUN"),
	("trie read", D9, "global-buffer-overflow"), ("spectral balance", D9, "+4.6"), ("tempo reach", D9, "2.85"), ("49 and 45 parameters", D9, "**49** | **45**"),
	("wrapper owns the tube", D9, "Identical samples"), ("the guard was wrong, marked in place", D9, "this guard is not enough"), ("light() overread", D10, "light()"),
	("spelled lengths", D10, "1,027 bytes"), ("end tick", D10, "-35 dBFS"), ("noise slope", D10, "0.80"), ("validator swallows keys", D10, "wxFloatingPointValidator"),
	("cancel between pieces", D10, "_MAX_PIECE"), ("shared limits", D10, "Shared limits"), ("retry at high tempo", D10, "0.8 of the tempo"),
	# The results
	("golden result", D10, "1472 golden rows"), ("C tests", D10, "135 checks"), ("GUI check", D10, "109 checks"), ("ASan clean", D10, "0 failures"), ("fresh clone", D10, "fresh clone"),
	("--long figures", D10, "1,608 tokens"), ("scan before push", D10, "66 files"), ("the commits", D10, "28eef40"), ("the fourth commit", D10, "A fourth commit"), ("F31 paths in logs", D12, "F31"), ("step 41, quoted", D12, 'The author: "Commit and push."'), ("step 42, quoted", D12, "Copy docs and stuff there"), ("F32 stray CLAUDE copy", D12, "F32"),
	# The failures
	("F4 invalid run", D12, "comparison of missing files"), ("F5 golden start", D12, "FileNotFoundError"), ("F6 link error", D12, "convertValue<int>"), ("F7 guard", D12, "100 `w` overruns"),
	("F8 URL", D12, "http://www.gnu.org/software/gnuspeech/"), ("F9 no done", D12, "no done"), ("F11 speakers", D12, "played through the speakers"), ("F12 keys", D12, "Typing 99 left 9"),
	("F13 note lost", D12, "Status note lost"), ("F14 safeguard", D12, "always fired"), ("F15 DLL load", D12, "dependencies"), ("F16 own limit", D12, "exit 124"),
	("F19 pkill, in the record", D12, 'pkill -f "x"'), ("F19 pkill, in chapter 10", D10, 'pkill -f "x"'), ("Savannah's filler", D12, "web scrapers"),
	# The decisions and the author's words
	("verdict quoted", D10, "better in sound and clarity"), ("stays public quoted", D10, "I guess this stays public"), ("push quoted", D10, "I think we may push it"), ("document first quoted", D10, "First document everything"),
	("docs were Claude's reading", D10, "`docs/` goes too"), ("no NVDA test, on purpose", D10, "on purpose"),
	# Elsewhere
	("manual has the keys", D11, "Ctrl+Enter"), ("manual has the table", D11, "`glottal_pulse_tp`"), ("licence reading", GS9, "does not stand in the way"), ("Savannah, unverified", GS9, "not verified"),
	("GNU's grades", GS9, "grades Savannah A and GitHub F"), ("Gnuspeech crash", GS9, "### 14."), ("Gnuspeech test fault", GS9, "### 15."), ("Gnuspeech keys", GS10, "never arrives at all"),
	("dist version corrected", GS10, "1.2.0"), ("Speechialization's lessons", SP, "2b.11"), ("verdict for study", SP, "better in sound and clarity"),
	("the stale DLL", D12, "was not."), ("the symbol claim corrected", D10, "62 kills the process"), ("the real 1.2.0 DLL tested", GS9, "b67242f5f147"), ("stale build folder", GS9, "`build/Release` is stale"), ("tempo stops on short words", GS9, "19,638 samples"),
	("inventory", "../ENGINES.md", "`model5`"), ("tasks", "../TASKS.md", "Savannah"), ("overview", "../speech synths overview.md", "chosen by ear"),
]


def main():
	missing = 0
	for what, path, phrase in FACTS:
		full = os.path.normpath(os.path.join(R, path))
		text = open(full, encoding="utf-8", errors="replace").read() if os.path.exists(full) else ""
		if phrase not in text and re.sub(r"\s+", " ", phrase) not in re.sub(r"\s+", " ", text):
			missing += 1
			print(f"MISSING: {what}: {phrase!r} in {path}")
	print(f"{len(FACTS)} facts, {missing} missing")
	sys.exit(1 if missing else 0)


if __name__ == "__main__":
	main()
