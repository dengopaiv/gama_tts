# NVDA synthesizer driver for GamaTTS, model 5, over gama_api.dll.
#
# Copyright 2026 dengopaiv. GPL-3.0-or-later, like the engine: Gnuspeech is by
# David R. Hill, Leonard Manzara and Craig Schock (1991-2002); GamaTTS, the engine
# inside the DLL with its model 5 tube, is by Marcelo Y. Matuda (2014-2025). See
# NOTICE.md in the add-on.
#
# Adapted from gnuspeech.py in GnuspeechSA-NVDA, whose structure follows rsynth-nvda's
# driver (rsynth.py), which follows NVDA's own eSpeak and OneCore drivers.
"""NVDA driver for GamaTTS, an articulatory text-to-speech system.

Everything that makes speech is inside gama_api.dll and its data folder: the English
text parser and dictionary, the rules and the 30-section tube, model 5.
This file turns NVDA's speech sequences into work for that library and its
audio into NVDA's player.

  gama_api.dll (ctypes)      -- gama_* in api/gama_api.h
  SynthDriver                -- NVDA-facing; queues work, never synthesizes
  _speak_thread              -- the only thread that calls the engine after start

The library synthesizes a whole utterance in gama_speak() and hands it out with
gama_read(). To keep the wait before the first sound short, text is split at
sentence ends, and each sentence is one utterance.

Cancellation is an epoch counter. cancel() bumps it; queued work from an older
epoch is dropped, and the feeding loop stops at the next block. Settings
changes are queued with no epoch, so a cancel never loses one.

The add-on is 64-bit only, as NVDA 2026 is.
"""

import collections
import ctypes
import os
import queue
import re
import threading
import unicodedata

import addonHandler
import config
import nvwave
from autoSettingsUtils.driverSetting import BooleanDriverSetting, DriverSetting
from autoSettingsUtils.utils import StringParameterInfo
from logHandler import log
from speech.commands import (
	BreakCommand,
	CharacterModeCommand,
	IndexCommand,
	PitchCommand,
)
from synthDriverHandler import SynthDriver as BaseSynthDriver
from synthDriverHandler import VoiceInfo, synthDoneSpeaking, synthIndexReached

addonHandler.initTranslation()

_DIR = os.path.dirname(os.path.abspath(__file__))
_DLL = os.path.join(_DIR, "gama_api.dll")
_DATA = os.path.join(_DIR, "gamatts_data")

#: The oldest GAMA_API_VERSION (gama_api.h) with everything this driver uses.
_API_VERSION = 1
_GS_OK = 0

#: Handed to the player at a time: 50 ms. Cancel is noticed between blocks.
_BLOCKS_PER_SECOND = 20

#: Display names of the voices upstream ships, by the name of their file.
_VOICE_NAMES = {
	# Translators: a GamaTTS voice.
	"male": _("Male"),
	# Translators: a GamaTTS voice.
	"female": _("Female"),
	# Translators: a GamaTTS voice.
	"large_child": _("Large child"),
	# Translators: a GamaTTS voice.
	"small_child": _("Small child"),
	# Translators: a GamaTTS voice.
	"baby": _("Baby"),
}

#: Typographic characters NVDA often sends, mapped to the ASCII the engine reads.
_ASCII_MAP = str.maketrans({
	"‘": "'", "’": "'", "‚": "'", "′": "'",
	"“": '"', "”": '"', "„": '"', "″": '"',
	"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": " - ", "−": "-",
	"…": "...", " ": " ", "­": "",
})

#: A sentence end: . ! or ? followed by space. The split keeps the punctuation.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

#: The longest piece of text given to the engine at once. It cannot be interrupted while it
#: synthesizes, and cancel is noticed between pieces. A run of 200 "w" is about 100 s of
#: speech, about 1.5 s of synthesis (docs/10). A sentence shorter than this is not split.
_MAX_PIECE = 200

#: The gain at NVDA volume 100 in the engine's own peak levelling, so that switching
#: synthesizers keeps the level. It matches the A-weighted level of eSpeak NG en+klatt5
#: at volume 100 (the author's everyday voice): -20.8 dB, against model 5 male's -20.3 at
#: gain 1.0 over the corpus (docs/10).
_FULL_VOLUME_GAIN = 0.94

#: With Loudness "steady throughout" or "even per message", every utterance is
#: levelled to this A-weighted level (dB), and volume 100 is gain 1.0: the calibration
#: is in the target. -22 dB is 1.2 dB below eSpeak NG en+klatt5 at volume 100, the value
#: the Gnuspeech add-on chose by ear. How often the peak limiter acts for model 5: docs/10.
_LOUDNESS_TARGET_DB = -22.0
_GS_LEVEL_PEAK, _GS_LEVEL_LOUDNESS, _GS_LEVEL_CONSTANT = 0, 1, 2

#: The Loudness setting's choices, by the id NVDA saves, with the engine's
#: levelling mode for each (docs/10).
_LEVELINGS = {
	# Translators: a choice of the GamaTTS Loudness setting: every syllable
	# of every message at the same loudness, whatever its stress, pitch or vowel.
	"constant": (_("Steady throughout"), _GS_LEVEL_CONSTANT),
	# Translators: a choice of the GamaTTS Loudness setting: every message at
	# the same loudness, while inside a message stressed and open vowels are
	# louder, as the engine makes them.
	"message": (_("Even per message"), _GS_LEVEL_LOUDNESS),
	# Translators: a choice of the GamaTTS Loudness setting: each message
	# scaled to its own peak, as the engine was made, so the loudness varies
	# from message to message and inside each.
	"peak": (_("The engine's own peaks"), _GS_LEVEL_PEAK),
}

#: Silence kept before the first sound of a message, in ms. The engine leaves
#: about 120 ms there, which is only delay.
_LEAD_KEEP_MS = 10
#: Silence kept after the last sound of a message, by how the message ends.
#: The engine leaves 190-230 ms whatever the punctuation; inside an utterance
#: it pauses about 300 ms between sentences and 190-365 ms at a comma, colon
#: or semicolon. These are starting values, to be tuned by ear.
_TRAIL_KEEP_SENTENCE_MS = 150   # . ! ? : ;
_TRAIL_KEEP_COMMA_MS = 100      # ,
_TRAIL_KEEP_WORD_MS = 30        # anything else: a word, a number, a control name


def _trail_keep_ms(text, spell):
	"""How much silence to keep after the last sound of a message."""
	if spell:
		return _TRAIL_KEEP_WORD_MS
	end = text.rstrip()[-1:]
	if end in (".", "!", "?", ":", ";"):
		return _TRAIL_KEEP_SENTENCE_MS
	if end == ",":
		return _TRAIL_KEEP_COMMA_MS
	return _TRAIL_KEEP_WORD_MS


def _pieces(sentence):
	"""A sentence, in pieces of at most _MAX_PIECE characters, at spaces where it has any."""
	while len(sentence) > _MAX_PIECE:
		cut = sentence.rfind(" ", 1, _MAX_PIECE + 1)
		if cut <= 0:
			cut = _MAX_PIECE
		yield sentence[:cut]
		sentence = sentence[cut:].lstrip()
	if sentence:
		yield sentence


def _tempo(rate):
	"""NVDA rate 0..100 to the engine's tempo: 0.5 at 0, 1.0 (as upstream
	ships) at 50, 4.0 at 100. Exponential in each half, so equal steps sound
	like equal ratios."""
	if rate <= 50:
		return 0.5 * 2.0 ** (rate / 50.0)
	return 4.0 ** ((rate - 50) / 50.0)


def _semitones(pitch):
	"""NVDA pitch 0..100 to semitones from the configured pitch: an octave
	down at 0, as configured at 50, an octave up at 100."""
	return (pitch - 50) * 12.0 / 50.0


def _engine_text(text):
	"""Fold text to the ASCII the engine reads: typographic punctuation to its
	ASCII form, accents dropped (cafe for café), anything else a space."""
	text = unicodedata.normalize("NFKD", text.translate(_ASCII_MAP))
	out = []
	for ch in text:
		if unicodedata.combining(ch):
			continue
		out.append(ch if " " <= ch <= "~" else " ")
	return " ".join("".join(out).split())


def _spelled(text):
	"""Character mode: one character per word. Letters in capitals, because
	the engine reads a lone lowercase "a" as the article, not the letter."""
	return " ".join(ch.upper() for ch in text if not ch.isspace())


def _native_path(path):
	"""The engine opens its files through narrow paths, which Windows reads in
	the ANSI code page. A path that does not fit (a user name in another
	script) is replaced by its 8.3 short form."""
	try:
		return path.encode("mbcs")
	except UnicodeEncodeError:
		pass
	buf = ctypes.create_unicode_buffer(32768)
	if ctypes.windll.kernel32.GetShortPathNameW(path, buf, len(buf)):
		try:
			return buf.value.encode("mbcs")
		except UnicodeEncodeError:
			pass
	raise RuntimeError(f"GamaTTS cannot open its data through a narrow path: {path}")


def _output_device():
	try:
		return config.conf["audio"]["outputDevice"]
	except KeyError:
		return config.conf["speech"]["outputDevice"]


class _Lib:
	"""gama_api.dll with every signature declared. Undeclared, ctypes
	would pass the engine handle as a 32-bit int: a crash once the heap is
	above 4 GB."""

	def __init__(self, path):
		lib = self.lib = ctypes.CDLL(path)
		p = ctypes.c_void_p
		d = ctypes.c_double
		i = ctypes.c_int
		for name, res, args in (
			("gama_api_version", i, []),
			("gama_create", p, [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]),
			("gama_destroy", None, [p]),
			("gama_last_error", ctypes.c_char_p, [p]),
			("gama_voice_count", i, [p]),
			("gama_voice_name", ctypes.c_char_p, [p, i]),
			("gama_voice", i, [p]),
			("gama_set_voice", i, [p, i]),
			("gama_set_rate", i, [p, d]),
			("gama_set_pitch", i, [p, d]),
			("gama_set_volume", i, [p, d]),
			("gama_set_deterministic", i, [p, i]),
			("gama_set_trim", i, [p, i, i]),
			("gama_set_leveling", i, [p, i, d]),
			("gama_speak", i, [p, ctypes.c_char_p]),
			("gama_read", ctypes.c_size_t, [p, ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t]),
			("gama_pending", ctypes.c_size_t, [p]),
			("gama_stop", None, [p]),
			("gama_sample_rate", i, [p]),
		):
			fn = getattr(lib, name)
			fn.restype, fn.argtypes = res, args
		if lib.gama_api_version() < _API_VERSION:
			raise RuntimeError(
				f"gama_api.dll speaks API {lib.gama_api_version()}, driver wants {_API_VERSION} or later",
			)


class SynthDriver(BaseSynthDriver):
	name = "gamatts"
	# Translators: the name of the GamaTTS synthesizer in NVDA's list.
	description = _("GamaTTS (articulatory)")

	supportedSettings = (
		BaseSynthDriver.VoiceSetting(),
		BaseSynthDriver.RateSetting(),
		BaseSynthDriver.PitchSetting(),
		BaseSynthDriver.VolumeSetting(),
		BooleanDriverSetting(
			"varyIntonation",
			# Translators: a GamaTTS setting: random variation in the intonation
			# of each sentence, as GamaTTS ships. Off, the same text always
			# sounds the same.
			_("Var&y intonation"),
			defaultVal=True,
		),
		DriverSetting(
			"leveling",
			# Translators: a GamaTTS setting: how the loudness is kept, from
			# steady throughout to as the engine makes it.
			_("Lo&udness"),
			defaultVal="constant",
		),
		BooleanDriverSetting(
			"trimSilence",
			# Translators: a GamaTTS setting: shorten the silence the engine leaves
			# before and after everything it says (about 0.3 s), so short
			# messages come quicker. Off, the pauses are as the engine makes them.
			_("Tri&m silence around each message"),
			defaultVal=True,
		),
	)
	supportedCommands = {IndexCommand, CharacterModeCommand, BreakCommand, PitchCommand}
	supportedNotifications = {synthIndexReached, synthDoneSpeaking}

	@classmethod
	def check(cls):
		return (
			ctypes.sizeof(ctypes.c_void_p) == 8
			and os.path.isfile(_DLL)
			and os.path.isfile(os.path.join(_DATA, "voice", "english", "5_male", "_index.txt"))
		)

	def __init__(self):
		# Driver.__init__ registers the config save action; without it no
		# setting of this driver survives a restart.
		super().__init__()
		self._lib = _Lib(_DLL).lib
		err = ctypes.create_string_buffer(1024)
		self._engine = self._lib.gama_create(_native_path(_DATA), err, len(err))
		if not self._engine:
			raise RuntimeError("GamaTTS: " + err.value.decode("utf-8", "replace"))
		self._voiceIds = [
			self._lib.gama_voice_name(self._engine, i).decode("ascii")
			for i in range(self._lib.gama_voice_count(self._engine))
		]
		start = self._lib.gama_voice(self._engine)
		self._voice = self._voiceIds[start] if 0 <= start < len(self._voiceIds) else self._voiceIds[0]
		self._rate = 50
		self._pitch = 50
		self._volume = 100
		self._varyIntonation = True
		self._leveling = "constant"
		self._trimSilence = True
		self._epoch = 0
		self._queue = queue.Queue()
		self._player = None
		# Created here, on the main thread, before the speak thread exists;
		# afterwards only the speak thread touches the engine and player.
		self._apply_all()
		self._open_player()
		log.info(
			f"GamaTTS: API {self._lib.gama_api_version()}, voices {', '.join(self._voiceIds)}, "
			f"{self._lib.gama_sample_rate(self._engine)} Hz",
		)
		self._thread = threading.Thread(target=self._speak_thread, name="gamatts", daemon=True)
		self._thread.start()

	def terminate(self):
		self.cancel()
		self._queue.put(None)
		self._thread.join(timeout=3)
		if self._player:
			self._player.close()
			self._player = None
		if self._engine:
			self._lib.gama_destroy(self._engine)
			self._engine = None
		super().terminate()

	# ---- engine and player -------------------------------------------

	def _open_player(self):
		rate = self._lib.gama_sample_rate(self._engine)
		if self._player is None or self._player.samplesPerSec != rate:
			old = self._player
			self._player = nvwave.WavePlayer(
				channels=1,
				samplesPerSec=rate,
				bitsPerSample=16,
				outputDevice=_output_device(),
			)
			if old:
				old.close()

	def _apply_all(self):
		lib, e = self._lib, self._engine
		lib.gama_set_voice(e, self._voiceIds.index(self._voice))
		lib.gama_set_rate(e, _tempo(self._rate))
		lib.gama_set_pitch(e, _semitones(self._pitch))
		mode = _LEVELINGS[self._leveling][1]
		lib.gama_set_leveling(e, mode, _LOUDNESS_TARGET_DB)
		if mode == _GS_LEVEL_PEAK:
			lib.gama_set_volume(e, self._volume / 100.0 * _FULL_VOLUME_GAIN)
		else:
			lib.gama_set_volume(e, self._volume / 100.0)
		lib.gama_set_deterministic(e, 0 if self._varyIntonation else 1)

	# ---- settings ----------------------------------------------------
	# Setters record the value and queue an "apply" with no epoch; the
	# speak thread applies it between utterances.

	def _changed(self):
		self._queue.put((None, "apply", None))

	def _getAvailableVoices(self):
		return collections.OrderedDict(
			(v, VoiceInfo(v, _VOICE_NAMES.get(v, v), "en")) for v in self._voiceIds
		)

	def _get_voice(self):
		return self._voice

	def _set_voice(self, value):
		if value in self._voiceIds:
			self._voice = value
			self._changed()

	def _get_rate(self):
		return self._rate

	def _set_rate(self, value):
		self._rate = max(0, min(100, int(value)))
		self._changed()

	def _get_pitch(self):
		return self._pitch

	def _set_pitch(self, value):
		self._pitch = max(0, min(100, int(value)))
		self._changed()

	def _get_volume(self):
		return self._volume

	def _set_volume(self, value):
		self._volume = max(0, min(100, int(value)))
		self._changed()

	def _get_varyIntonation(self):
		return self._varyIntonation

	def _set_varyIntonation(self, value):
		self._varyIntonation = bool(value)
		self._changed()

	def _get_availableLevelings(self):
		return collections.OrderedDict(
			(key, StringParameterInfo(key, name)) for key, (name, mode) in _LEVELINGS.items()
		)

	def _get_leveling(self):
		return self._leveling

	def _set_leveling(self, value):
		if value in _LEVELINGS:
			self._leveling = value
			self._changed()

	def _get_trimSilence(self):
		return self._trimSilence

	def _set_trimSilence(self, value):
		# Read by the speak thread for each utterance; no engine call needed.
		self._trimSilence = bool(value)

	# ---- speaking ----------------------------------------------------

	def speak(self, speechSequence):
		epoch = self._epoch
		spell = False
		pitch = None
		text = []
		work = []

		def flush():
			if text:
				joined = " ".join(text)
				if joined.strip():
					for sentence in _SENTENCE_END.split(joined):
						if sentence.strip():
							for piece in _pieces(sentence):
								work.append(["text", piece, spell, pitch, -1, -1])
				text.clear()

		for item in speechSequence:
			if isinstance(item, str):
				text.append(item)
			elif isinstance(item, IndexCommand):
				flush()
				work.append(["index", item.index])
			elif isinstance(item, CharacterModeCommand):
				flush()
				spell = item.state
			elif isinstance(item, BreakCommand):
				flush()
				work.append(["break", item.time])
			elif isinstance(item, PitchCommand):
				flush()
				pitch = item.newValue
		flush()

		# Trim only the outer edges of the message: the silence before its
		# first sound and after its last. Between its sentences the engine's
		# own pauses stay, so splitting at sentence ends changes no rhythm.
		texts = [w for w in work if w[0] == "text"]
		if texts:
			texts[0][4] = _LEAD_KEEP_MS
			texts[-1][5] = _trail_keep_ms(texts[-1][1], texts[-1][2])
		for w in work:
			if w[0] == "text":
				self._queue.put((epoch, "text", tuple(w[1:])))
			else:
				self._queue.put((epoch, w[0], w[1]))
		self._queue.put((epoch, "done", None))

	def cancel(self):
		self._epoch += 1
		# Drop queued speech but keep settings changes: a rate change queued
		# just before a cancel must still happen.
		keep = []
		try:
			while True:
				item = self._queue.get_nowait()
				if item is None or item[0] is None:
					keep.append(item)
		except queue.Empty:
			pass
		for item in keep:
			self._queue.put(item)
		if self._player:
			self._player.stop()

	def pause(self, switch):
		if self._player:
			self._player.pause(switch)

	# ---- the speak thread --------------------------------------------

	def _speak_thread(self):
		while True:
			item = self._queue.get()
			if item is None:
				return
			epoch, kind, payload = item
			try:
				if epoch is not None and epoch != self._epoch:
					continue
				if kind == "apply":
					self._apply_all()
				elif kind == "text":
					self._say(epoch, *payload)
				elif kind == "index":
					# Reached when the audio before it has played, not when it
					# was synthesized: an empty chunk carries the callback.
					self._player.feed(
						b"",
						onDone=lambda index=payload: synthIndexReached.notify(synth=self, index=index),
					)
				elif kind == "break":
					self._silence(epoch, payload)
				elif kind == "done":
					self._player.idle()
					if epoch == self._epoch:
						synthDoneSpeaking.notify(synth=self)
			except Exception:
				log.error("GamaTTS speak thread", exc_info=True)

	def _say(self, epoch, text, spell, pitch, lead_ms=-1, trail_ms=-1):
		lib, e = self._lib, self._engine
		text = _engine_text(_spelled(text) if spell else text)
		if not text:
			return
		if self._trimSilence:
			lib.gama_set_trim(e, lead_ms, trail_ms)
		else:
			lib.gama_set_trim(e, -1, -1)
		if pitch is not None:
			lib.gama_set_pitch(e, max(-24.0, min(24.0, _semitones(pitch))))
		try:
			# The engine's own command line adds a space after the text; so
			# does this, and the golden traces were made that way.
			rc = lib.gama_speak(e, (text + " ").encode("ascii"))
		finally:
			if pitch is not None:
				lib.gama_set_pitch(e, _semitones(self._pitch))
		if rc != _GS_OK:
			# Punctuation-only text has nothing to say; that is not an error.
			log.debug(f"GamaTTS: nothing spoken for {text!r}: {lib.gama_last_error(e)!r}")
			return
		self._open_player()
		block = max(1, self._player.samplesPerSec // _BLOCKS_PER_SECOND)
		buf = (ctypes.c_int16 * block)()
		while epoch == self._epoch:
			n = lib.gama_read(e, buf, block)
			if not n:
				break
			self._player.feed(ctypes.string_at(buf, n * 2))
			if epoch != self._epoch:
				# cancel() ran while this block was being fed, so its stop()
				# may have come first and this block would sound at the head
				# of the next utterance. Stop again.
				self._player.stop()
				break
		lib.gama_stop(e)

	def _silence(self, epoch, ms):
		rate = self._player.samplesPerSec
		remaining = max(0, int(rate * ms / 1000))
		block = rate // 50
		while remaining > 0 and epoch == self._epoch:
			n = min(block, remaining)
			self._player.feed(bytes(2 * n))
			remaining -= n
