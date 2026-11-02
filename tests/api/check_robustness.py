"""The API against what would break the engine: docs/09's two defects, and the limits.

Usage: python -I check_robustness.py <gama_api library> <data_dir> [--long]

Everything runs through one engine in this process, so a crash fails the test as
a crash. Each stage says what it does:

  tempo     short words and lines, every voice, tempos 0.1 to 10. Before the fix,
            tempo 3.9 and above gave pitch of +-700,000 semitones, and silence.
  tokens    long unbroken tokens in eight alphabets. Before the guard, some of
            these overran the parser's buffers from 200 characters.
  text      random text: printable, any bytes, screen-reader fragments.
  phonetic  malformed phonetic strings: an error or speech, never a crash.
  params    each parameter at its minimum and maximum, male and baby voices.
  random    random settings of all parameters together.

A sample of -32768 is what a NaN becomes on the way to 16 bits, and the peak of every
utterance is at most 0.95 of full scale in peak mode, so the check below sees a NaN.

--long makes the token and text stages longer: nine minutes, against under two.
Copyright 2026 dengopaiv. GPL-3.0-or-later.
"""

import ctypes
import math
import random
import string
import sys
import time

OK, ERR_RANGE, ERR_ENGINE = 0, -2, -3
p = ctypes.c_void_p
MAX_PEAK = 31129

ALPHABETS = {
	"lower": string.ascii_lowercase,
	"consonants": "bcdfghjklmnpqrstvwxz",
	"vowels": "aeiou",
	"upper": string.ascii_uppercase,
	"base64": string.ascii_letters + string.digits + "+/",
	"hex": "0123456789abcdef",
	"digits": string.digits,
	"mixed": string.ascii_letters + string.digits + "-_.~%&=?#:@!$'()*+,;[]{}|^`<>\\\"",
}
FRAGMENTS = ["Button", "a", "I", "1", "1.5", "$3", "%", "@", "#", "/", "\\", "(", "*", "--", "...", "e.g.", "Mr.",
	"www.example.com", "C:\\Windows", "x86_64", "3/4", "10:30", "'", '"', "A", "B", "Z", "?", "!", ";", ":", ",", "the",
	"of", "Alt+F4", "blank", "unlabelled", "heading level 2", "R2D2", "iOS", "NVDA", "co-op", "1st", "22nd", "100%",
	"-5", "+7", "0", "0.", "1,000,000", "1e9", "Ctrl", "_", "~", "^", "&", "=", "<", ">", "[", "]", "{", "}", "|", "`",
	"/c", "/f", "/w", "/l", "//", "%", "'", "www", "http://a.b/c?d=e&f=g#h"]
SHORT = ["a", "I", "A", "OK", "1", "42", "100", "e-mail", "Yes", "No", "b", "z", "Edit, multi line",
	"Muscle, muscular; goal and iron;", "Golf, wolf; countenants; lieutenants", "abbot", "abb", "The quick brown fox."]

failures = 0


def check(cond, msg):
	global failures
	if not cond:
		failures += 1
		if failures <= 40:
			print("FAIL", msg, flush=True)
	return cond


def load(path):
	lib = ctypes.CDLL(path)
	lib.gama_create.restype = p
	lib.gama_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
	lib.gama_destroy.argtypes = [p]
	lib.gama_set_deterministic.argtypes = [p, ctypes.c_int]
	lib.gama_set_voice.argtypes = [p, ctypes.c_int]
	lib.gama_voice_count.argtypes = [p]
	lib.gama_set_rate.argtypes = [p, ctypes.c_double]
	lib.gama_spoken_tempo.restype = ctypes.c_double
	lib.gama_spoken_tempo.argtypes = [p]
	lib.gama_speak.argtypes = [p, ctypes.c_char_p]
	lib.gama_speak_phonetic.argtypes = [p, ctypes.c_char_p]
	lib.gama_pending.restype = ctypes.c_size_t
	lib.gama_pending.argtypes = [p]
	lib.gama_read.restype = ctypes.c_size_t
	lib.gama_read.argtypes = [p, ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t]
	lib.gama_last_error.restype = ctypes.c_char_p
	lib.gama_last_error.argtypes = [p]
	lib.gama_reset_params.argtypes = [p]
	lib.gama_set_param.argtypes = [p, ctypes.c_int, ctypes.c_double]
	lib.gama_get_param.argtypes = [p, ctypes.c_int, ctypes.POINTER(ctypes.c_double)]
	lib.gama_param_describe.restype = ctypes.POINTER(Info)
	lib.gama_param_describe.argtypes = [ctypes.c_int]
	return lib


class Info(ctypes.Structure):
	_fields_ = [("key", ctypes.c_char_p), ("file", ctypes.c_char_p), ("category", ctypes.c_char_p),
		("label", ctypes.c_char_p), ("unit", ctypes.c_char_p), ("help", ctypes.c_char_p), ("kind", ctypes.c_int),
		("min", ctypes.c_double), ("max", ctypes.c_double), ("step", ctypes.c_double), ("decimals", ctypes.c_int),
		("choice_count", ctypes.c_int), ("choice_values", ctypes.POINTER(ctypes.c_double)),
		("choice_names", ctypes.POINTER(ctypes.c_char_p))]


def samples(lib, e):
	n = lib.gama_pending(e)
	buf = (ctypes.c_int16 * max(n, 1))()
	got = lib.gama_read(e, buf, n)
	return memoryview(buf).cast("B").cast("h")[:got]


def peak(s):
	return max((abs(v) for v in s), default=0)


def say(lib, e, data, where, must_speak=None):
	"""Speak bytes. Returns the peak, or None if the engine said no."""
	rc = lib.gama_speak(e, data)
	if rc != OK:
		check(rc == ERR_ENGINE, f"{where}: return code {rc}")
		check(lib.gama_last_error(e), f"{where}: an error with no message")
		check(must_speak is not True, f"{where}: refused: {lib.gama_last_error(e)!r}")
		return None
	s = samples(lib, e)
	pk = peak(s)
	check(pk <= MAX_PEAK, f"{where}: peak {pk}: a NaN, or no scaling")
	if must_speak:
		check(pk > 0, f"{where}: silence")
	return pk


def stage_tempo(lib, e):
	count = 0
	refused_at_ten = 0
	for v in range(lib.gama_voice_count(e)):
		lib.gama_set_voice(e, v)
		for tempo in (0.1, 0.5, 1.0, 3.0, 3.85, 3.9, 4.0, 5.0, 6.0, 8.0, 10.0):
			if tempo == 0.1 and v:
				continue  # slow, and the male voice has shown it
			lib.gama_set_rate(e, tempo)
			for text in SHORT:
				say(lib, e, (text + " ").encode(), f"voice {v} tempo {tempo} {text!r}", must_speak=True)
				count += 1
				if lib.gama_spoken_tempo(e) < tempo:
					refused_at_ten += 1
	lib.gama_set_rate(e, 1.0)
	lib.gama_set_voice(e, 0)
	print(f"tempo: {count} utterances, every one spoken; {refused_at_ten} needed a lower tempo than asked (rule 11)", flush=True)


def stage_tokens(lib, e, scale):
	rng = random.Random(1)
	count = 0
	lengths = (64, 100, 101, 128, 200, 256, 400, 1000, 1024)
	if scale > 1:
		lengths += (2000, 8000)
	lib.gama_set_rate(e, 4.0)  # the same parser, for a quarter of the tube's work
	for name, alpha in ALPHABETS.items():
		for n in lengths:
			tok = "".join(rng.choice(alpha) for _ in range(n))
			say(lib, e, tok.encode(), f"token {name} {n}")
			count += 1
	# Every printable character, repeated: what its spelling costs decides. Before the
	# guard was sized by spelling, 100 "w" killed the process, and 24 "<" would have.
	for code in range(33, 127):
		ch = chr(code)
		for n in ((22, 23, 24, 25, 45, 57, 58, 59, 60, 61, 99, 100, 101, 500) if scale > 1 else (23, 24, 25, 58, 59, 60, 100, 101)):
			say(lib, e, (ch * n).encode(), f"repeated {ch!r} {n}")
			count += 1
	# Mixtures at the edge of what the guard allows, cut where it cuts.
	for k in range(20 * scale):
		tok = "".join(rng.choice("wW<>[]()!'%&mx1") for _ in range(rng.randrange(1, 200)))
		say(lib, e, tok.encode(), f"mixture {tok!r}")
		count += 1
	k = 8 * scale
	say(lib, e, ("https://example.com/" + "path-segment_" * 5 * k).encode(), "long url", must_speak=True)
	say(lib, e, ("The quick brown fox. " * 4 * k).encode(), "many sentences", must_speak=True)
	say(lib, e, ("the quick brown fox " * 4 * k).encode(), "no stop", must_speak=True)
	say(lib, e, (" ".join(["1,234,567.89"] * 3 * k)).encode(), "many numbers", must_speak=True)
	lib.gama_set_rate(e, 1.0)
	print(f"tokens: {count + 4} utterances, no crash", flush=True)


def stage_text(lib, e, scale):
	rng = random.Random(2)
	counts = {"spoken": 0, "refused": 0}
	lib.gama_set_rate(e, 3.0)
	for mode in ("printable", "bytes", "fragments"):
		for k in range(150 * scale):
			if mode == "printable":
				data = "".join(chr(32 + rng.randrange(95)) for _ in range(1 + rng.randrange(40))).encode()
			elif mode == "bytes":
				data = bytes(1 + rng.randrange(255) for _ in range(1 + rng.randrange(40)))
			else:
				data = " ".join(rng.choice(FRAGMENTS) for _ in range(1 + rng.randrange(8))).encode()
			r = say(lib, e, data, f"{mode} {data!r}")
			counts["refused" if r is None else "spoken"] += 1
	lib.gama_set_rate(e, 1.0)
	print(f"text: {counts['spoken']} spoken, {counts['refused']} with nothing to say, no crash", flush=True)


def stage_phonetic(lib, e, scale):
	rng = random.Random(3)
	good = "/c // /0 # /w h_e./_l_uh_uu /w /l /*w_er_r_ll_d # // /c "
	pieces = ["/c", "//", "/0", "/1", "/w", "/l", "/*", "/_", "/f", "/r", "#", "^", "_", ".", "'", "\"", "%", "h", "uh", "aa",
		"no_such_posture", "/", "/x", "e_i", " ", "  ", "/f1", "/f100", "/r0.5", "/f-1"]
	spoken = refused = 0
	for k in range(150 * scale):
		mode = k % 3
		if mode == 0:
			data = "".join(rng.choice(pieces) + " " for _ in range(rng.randrange(20))).encode()
		elif mode == 1:
			c = bytearray(good.encode())
			for _ in range(1 + rng.randrange(6)):
				c[rng.randrange(len(c))] = rng.randrange(32, 127)
			data = bytes(c)
		else:
			data = bytes(1 + rng.randrange(255) for _ in range(rng.randrange(60)))
		rc = lib.gama_speak_phonetic(e, data)
		if rc == OK:
			pk = peak(samples(lib, e))
			check(pk <= MAX_PEAK, f"phonetic {data!r}: peak {pk}")
			spoken += 1
		else:
			check(rc == ERR_ENGINE, f"phonetic {data!r}: return code {rc}")
			refused += 1
	print(f"phonetic: {spoken} spoken, {refused} refused, no crash", flush=True)


def stage_params(lib, e):
	count = lib.gama_param_count()
	line = b"The quick brown fox jumps over the lazy dog. Is it? "
	done = refused = silent = 0
	slowest = (0.0, "")
	for voice in (0, lib.gama_voice_count(e) - 1):
		lib.gama_set_voice(e, voice)
		for i in range(count):
			info = lib.gama_param_describe(i).contents
			key = info.key.decode()
			values = [info.min, info.max]
			if info.kind == 2:
				values = [info.choice_values[k] for k in range(info.choice_count)]
			for value in values:
				lib.gama_reset_params(e)
				if lib.gama_set_param(e, i, value) != OK:
					refused += 1  # a shared limit: the API said so, and that is the answer
					check(lib.gama_last_error(e), f"{key} = {value} refused without a reason")
					continue
				t = time.perf_counter()
				pk = say(lib, e, line, f"voice {voice}: {key} = {value}", must_speak=True)
				spent = time.perf_counter() - t
				if spent > slowest[0]:
					slowest = (spent, f"voice {voice}: {key} = {value}")
				done += 1
				if pk == 0:
					silent += 1
	lib.gama_reset_params(e)
	lib.gama_set_voice(e, 0)
	lib.gama_reset_params(e)
	print(f"params: {done} extremes spoken, {refused} refused by a shared limit; slowest {slowest[0]:.2f} s ({slowest[1]})", flush=True)


def stage_random(lib, e, scale):
	rng = random.Random(4)
	count = lib.gama_param_count()
	done = refused = 0
	for k in range(100 * scale):
		lib.gama_set_voice(e, rng.randrange(lib.gama_voice_count(e)))
		lib.gama_reset_params(e)
		for i in rng.sample(range(count), rng.randrange(1, count)):
			info = lib.gama_param_describe(i).contents
			if info.kind == 0:
				value = info.min + rng.random() * (info.max - info.min)
			elif info.kind == 1:
				value = float(rng.randrange(2))
			else:
				value = info.choice_values[rng.randrange(info.choice_count)]
			if info.key == b"tempo":
				value = max(value, 1.0)  # the slowest tempos make this stage long, and tempo has its own
			if info.key == b"control_period":
				value = max(value, 2.0)
			lib.gama_set_param(e, i, value)
		rc = lib.gama_speak(e, b"Check the bright red bicycle, 25 times. ")
		if rc == OK:
			pk = peak(samples(lib, e))
			check(pk <= MAX_PEAK, f"random {k}: peak {pk}")
			done += 1
		else:
			refused += 1
			print(f"info: random {k}: {lib.gama_last_error(e)!r}")
	lib.gama_reset_params(e)
	lib.gama_set_voice(e, 0)
	lib.gama_reset_params(e)
	print(f"random: {done} settings spoken, {refused} not", flush=True)


def main():
	args = [a for a in sys.argv[1:] if not a.startswith("--")]
	if len(args) != 2:
		sys.exit(__doc__)
	scale = 10 if "--long" in sys.argv else 1
	lib = load(args[0])
	err = ctypes.create_string_buffer(512)
	e = lib.gama_create(args[1].encode(), err, len(err))
	if not e:
		sys.exit("cannot create the engine: " + err.value.decode(errors="replace"))
	lib.gama_set_deterministic(e, 1)
	for name, stage in (("tempo", lambda: stage_tempo(lib, e)), ("tokens", lambda: stage_tokens(lib, e, scale)),
			("text", lambda: stage_text(lib, e, scale)), ("phonetic", lambda: stage_phonetic(lib, e, scale)),
			("params", lambda: stage_params(lib, e)), ("random", lambda: stage_random(lib, e, scale))):
		t = time.perf_counter()
		stage()
		print(f"  ({name} took {time.perf_counter() - t:.0f} s)", flush=True)
	lib.gama_destroy(e)
	print(f"{failures} failures")
	sys.exit(1 if failures else 0)


if __name__ == "__main__":
	main()
