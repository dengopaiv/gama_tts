import sys
p = r"C:\GIT\speech synthesis\gama_tts\tests\gui\gui_check.py"
s = open(p, encoding="utf-8", newline="").read()
a = """	if not check(len(silent_frames) > 0 and not any(silent_frames), "and that WAV is silent, so the speakers will be"):
		sys.exit("volume 0 did not take effect, so nothing more is played")
"""
b = """	is_silent = len(silent_frames) > 0 and not any(silent_frames)
	check(is_silent, "and that WAV is silent, so the speakers will be")
	if not is_silent:
		sys.exit("volume 0 did not take effect, so nothing more is played")
"""
if a not in s: sys.exit("MISSING")
open(p, "w", encoding="utf-8", newline="\n").write(s.replace(a, b))
