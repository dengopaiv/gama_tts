"""How long does each character get when the engine spells a word it cannot pronounce?

    python -I tools/measure/spelled_lengths.py

Reads the table straight from the engine's source: the order of letters[] in LetterToSound.cpp
and the strings in NumberPronunciations.h. spellIt() copies the result into a buffer of 1,027
bytes, with no length check, so this table decides how long a run can safely be. It is what
api/gama_spell.cpp counts with (docs/10, section 5).

Run from the repository root. Copyright 2026 dengopaiv. GPL-3.0-or-later.
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENGLISH = os.path.join(ROOT, "gama_tts", "src", "text_parser", "english")
BUFFER = 1027


def main():
	with open(os.path.join(ENGLISH, "NumberPronunciations.h"), encoding="latin-1") as f:
		header = f.read()
	with open(os.path.join(ENGLISH, "LetterToSound.cpp"), encoding="latin-1") as f:
		source = f.read()
	# A string may hold an escaped quote.
	defines = {k: bytes(v, "latin-1").decode("unicode_escape") for k, v in re.findall(r'#define\s+(\w+)\s+"((?:[^"\\]|\\.)*)"', header)}
	names = re.findall(r"\w+", re.search(r"letters\[\]\s*=\s*\{(.*?)\};", source, re.S).group(1))
	rows = sorted(((len(defines[n]), chr(32 + i), n) for i, n in enumerate(names)), reverse=True)
	print(f"{len(rows)} entries, in bytes when spelled; a run of one character overflows {BUFFER} bytes at the count shown")
	print(f"{'bytes':>6} {'overflows at':>13}  char  name")
	for length, ch, name in rows:
		if length:
			print(f"{length:6d} {BUFFER // length + 1:13d}  {ch!r:5} {name}")


if __name__ == "__main__":
	main()
