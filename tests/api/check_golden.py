"""The C API against the golden traces of the unchanged engine.

Usage: python -I check_golden.py <gama_api library> <data_dir> <golden.tsv>

Speaks every golden row through ONE engine, in deterministic mode at volume 1.0, the
way gama_tts does (text + " "), and compares a SHA-256 of the samples, the sample count,
the peak, the rate and a SHA-256 of the parameter track with tests/golden. Lines the
golden run could not speak must fail here too. Using one engine for every row also
shows whether anything carries over from one utterance, or one voice, to the next.

On one voice and tempo it also checks gama_speak_phonetic(gama_text_to_phonetic(text))
against the same samples.

Adapted from GnuspeechSA-NVDA's tests/api/check_golden.py.
Copyright 2026 dengopaiv. GPL-3.0-or-later.
"""

import ctypes
import hashlib
import sys

OK, ERR_ENGINE = 0, -3
p = ctypes.c_void_p


def load(path):
	lib = ctypes.CDLL(path)
	lib.gama_create.restype = p
	lib.gama_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
	lib.gama_destroy.argtypes = [p]
	lib.gama_set_deterministic.argtypes = [p, ctypes.c_int]
	lib.gama_set_voice.argtypes = [p, ctypes.c_int]
	lib.gama_voice_name.restype = ctypes.c_char_p
	lib.gama_voice_name.argtypes = [p, ctypes.c_int]
	lib.gama_voice_count.argtypes = [p]
	lib.gama_set_rate.argtypes = [p, ctypes.c_double]
	lib.gama_speak.argtypes = [p, ctypes.c_char_p]
	lib.gama_pending.restype = ctypes.c_size_t
	lib.gama_pending.argtypes = [p]
	lib.gama_read.restype = ctypes.c_size_t
	lib.gama_read.argtypes = [p, ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t]
	lib.gama_sample_rate.argtypes = [p]
	lib.gama_last_error.restype = ctypes.c_char_p
	lib.gama_last_error.argtypes = [p]
	lib.gama_track.restype = ctypes.c_size_t
	lib.gama_track.argtypes = [p, ctypes.c_char_p, ctypes.c_size_t]
	lib.gama_text_to_phonetic.restype = ctypes.c_size_t
	lib.gama_text_to_phonetic.argtypes = [p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
	lib.gama_speak_phonetic.argtypes = [p, ctypes.c_char_p]
	return lib


def read_all(lib, e):
	count = lib.gama_pending(e)
	buf = (ctypes.c_int16 * max(count, 1))()
	got = lib.gama_read(e, buf, count)
	return bytes(buf)[: got * 2], got


def track(lib, e):
	n = lib.gama_track(e, None, 0)
	buf = ctypes.create_string_buffer(n + 1)
	lib.gama_track(e, buf, n + 1)
	return buf.raw[:n]


def phonetic(lib, e, text):
	n = lib.gama_text_to_phonetic(e, text, None, 0)
	buf = ctypes.create_string_buffer(n + 1)
	lib.gama_text_to_phonetic(e, text, buf, n + 1)
	return buf.raw[:n]


def read_golden(path):
	rows = []
	with open(path, encoding="ascii") as f:
		for line in f:
			line = line.rstrip("\r\n")
			if not line or line.startswith("#") or line.startswith("voice\t"):
				continue
			voice, tempo, i, pcm, vtm, n, peak, rate, text = line.split("\t", 8)
			rows.append((voice, float(tempo), int(i), pcm, vtm, int(n), int(peak), rate, text))
	return rows


def main():
	if len(sys.argv) != 4:
		sys.exit(__doc__)
	lib = load(sys.argv[1])
	err = ctypes.create_string_buffer(512)
	e = lib.gama_create(sys.argv[2].encode(), err, len(err))
	if not e:
		sys.exit("cannot create the engine: " + err.value.decode(errors="replace"))
	lib.gama_set_deterministic(e, 1)
	voices = {lib.gama_voice_name(e, i).decode(): i for i in range(lib.gama_voice_count(e))}

	bad = []
	rows = read_golden(sys.argv[3])
	checked_phonetic = 0
	for voice, tempo, i, pcm, vtm, n, peak, rate, text in rows:
		lib.gama_set_voice(e, voices[voice.removeprefix("5_")])
		lib.gama_set_rate(e, tempo)
		line = (text + " ").encode("ascii")
		where = f"{voice} tempo {tempo} line {i}"
		rc = lib.gama_speak(e, line)
		if pcm == "FAIL":
			if rc != ERR_ENGINE:
				bad.append(f"{where}: golden has no audio, API returned {rc}")
			continue
		if rc != OK:
			bad.append(f"{where}: API failed ({lib.gama_last_error(e).decode(errors='replace')}) on {text!r}")
			continue
		data, got = read_all(lib, e)
		samples = memoryview(data).cast("h")
		actual = (hashlib.sha256(data).hexdigest(), got, max((abs(s) for s in samples), default=0), str(lib.gama_sample_rate(e)))
		if actual != (pcm, n, peak, rate):
			bad.append(f"{where}: {text!r}: samples {got} (golden {n}), peak {actual[2]} (golden {peak}), "
				f"rate {actual[3]} (golden {rate}), sha {actual[0][:12]} (golden {pcm[:12]})")
		if hashlib.sha256(track(lib, e)).hexdigest() != vtm:
			bad.append(f"{where}: {text!r}: gama_track differs from gama_tts -p")
		if voice == "5_male" and tempo == 1.0:
			phon = phonetic(lib, e, line)
			checked_phonetic += 1
			if lib.gama_speak_phonetic(e, phon) != OK or read_all(lib, e)[0] != data:
				bad.append(f"{where}: {text!r}: speaking the phonetic string {phon[:40]!r} gives other samples")
	lib.gama_destroy(e)

	for b in bad[:20]:
		print("FAIL", b)
	print(f"{len(rows)} golden rows (samples and track), {checked_phonetic} also through the phonetic string, {len(bad)} differences")
	sys.exit(1 if bad else 0)


if __name__ == "__main__":
	main()
