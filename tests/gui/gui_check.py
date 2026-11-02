#!/usr/bin/env python3
"""Check gama_gui.exe from outside, the way a screen reader sees it.

    python tests/gui/gui_check.py <gama_gui.exe> <gama_api.dll> <data> <golden.tsv>

Windows only; needs comtypes (for oleacc's IAccessible), numpy and scipy. docs/10 has
the results of the recorded run.

Adapted from GnuspeechSA-NVDA's tests/gui/gui_check.py, itself from rsynth-nvda's
tests/gui_check.py (LGPL-2.0-or-later, "the rsynth-nvda contributors"): the private desktop,
the process start, the key posting with an exact modifier state, and the file-dialog driving
are taken from it. wxWidgets gives its controls no fixed ids, so controls are found by
their MSAA names, and a field's group is the group box it is a child of.

The GUI runs on a desktop of its own (CreateDesktop), and this script's
thread moves there too: the machine is shared with someone using NVDA, whose
keystrokes would otherwise reach the window (rsynth docs/07). Its sound is
played at volume 0.

What it checks:
1. MSAA for every tab stop: role, name, value, description, and the group.
2. Tab order: forward round to the start, and backwards; hidden categories
   are out of it.
3. Every category (Ctrl+1 ... Ctrl+7): its fields, their names, units and
   group; all 49 parameters and the 6 output fields are reachable.
4. Number fields: Up steps; a typed value out of range is corrected on
   leaving, and the status says so.
5. Voice: choosing Female loads its tract length.
6. Phonetic string: Ctrl+P gives gama_text_to_phonetic's string.
7. Save as WAV and Save parameter track, through the real file dialogs,
   against the golden hashes of gama_tts; then the same through Use
   phonetic string as text.
8. Presets: save, reset, open.
9. Speaking at volume 0, Esc, and closing.
"""

import ctypes
import ctypes.wintypes as wt
import hashlib
import os
import sys
import tempfile
import time
import wave

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "measure"))
from levels import a_weighted_db, parse_track, voiced_frame_sd  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# The private desktop, entered before comtypes initialises COM: a thread can
# change desktop only while it owns no windows, and COM may create one.
DESKTOP_NAME = "gama_gui_check"
user32.CreateDesktopW.restype = wt.HANDLE
user32.CreateDesktopW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, ctypes.c_void_p, wt.DWORD, wt.DWORD, ctypes.c_void_p]
user32.SetThreadDesktop.argtypes = [wt.HANDLE]
user32.CloseDesktop.argtypes = [wt.HANDLE]
DESKTOP = user32.CreateDesktopW(DESKTOP_NAME, None, None, 0, 0x10000000, None)  # GENERIC_ALL
if not DESKTOP or not user32.SetThreadDesktop(DESKTOP):
	sys.exit(f"could not create or enter a private desktop (error {ctypes.get_last_error()})")

import comtypes  # noqa: E402
import comtypes.client  # noqa: E402

comtypes.client.GetModule("oleacc.dll")
from comtypes.gen.Accessibility import IAccessible  # noqa: E402

oleacc = ctypes.WinDLL("oleacc")


class STARTUPINFOW(ctypes.Structure):
	_fields_ = [
		("cb", wt.DWORD), ("lpReserved", wt.LPWSTR), ("lpDesktop", wt.LPWSTR),
		("lpTitle", wt.LPWSTR), ("dwX", wt.DWORD), ("dwY", wt.DWORD),
		("dwXSize", wt.DWORD), ("dwYSize", wt.DWORD), ("dwXCountChars", wt.DWORD),
		("dwYCountChars", wt.DWORD), ("dwFillAttribute", wt.DWORD), ("dwFlags", wt.DWORD),
		("wShowWindow", wt.WORD), ("cbReserved2", wt.WORD), ("lpReserved2", ctypes.c_void_p),
		("hStdInput", wt.HANDLE), ("hStdOutput", wt.HANDLE), ("hStdError", wt.HANDLE),
	]


class PROCESS_INFORMATION(ctypes.Structure):
	_fields_ = [("hProcess", wt.HANDLE), ("hThread", wt.HANDLE), ("dwProcessId", wt.DWORD), ("dwThreadId", wt.DWORD)]


kernel32.CreateProcessW.argtypes = [
	wt.LPCWSTR, wt.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, wt.BOOL, wt.DWORD,
	ctypes.c_void_p, wt.LPCWSTR, ctypes.POINTER(STARTUPINFOW), ctypes.POINTER(PROCESS_INFORMATION)]
kernel32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
kernel32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
kernel32.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
kernel32.CloseHandle.argtypes = [wt.HANDLE]
user32.WaitForInputIdle.argtypes = [wt.HANDLE, wt.DWORD]


class Process:
	"""A process started on the private desktop (subprocess cannot set
	STARTUPINFO.lpDesktop)."""

	def __init__(self, exe, args):
		si = STARTUPINFOW()
		si.cb = ctypes.sizeof(si)
		si.lpDesktop = DESKTOP_NAME
		pi = PROCESS_INFORMATION()
		cmd = ctypes.create_unicode_buffer(" ".join(f'"{a}"' for a in [exe] + args))
		if not kernel32.CreateProcessW(exe, cmd, None, None, False, 0, None, None, ctypes.byref(si), ctypes.byref(pi)):
			sys.exit(f"could not start {exe} (error {ctypes.get_last_error()})")
		kernel32.CloseHandle(pi.hThread)
		self.handle, self.pid = pi.hProcess, pi.dwProcessId

	def poll(self):
		code = wt.DWORD()
		kernel32.GetExitCodeProcess(self.handle, ctypes.byref(code))
		return None if code.value == 259 else code.value  # STILL_ACTIVE

	def wait(self, timeout):
		kernel32.WaitForSingleObject(self.handle, int(timeout * 1000))
		return self.poll()

	def kill(self):
		kernel32.TerminateProcess(self.handle, 1)


user32.SendMessageW.restype = ctypes.c_ssize_t
user32.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetParent.restype = wt.HWND
user32.GetParent.argtypes = [wt.HWND]
user32.GetAncestor.restype = wt.HWND
user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
user32.GetDlgItem.restype = wt.HWND
user32.GetDlgItem.argtypes = [wt.HWND, ctypes.c_int]
oleacc.GetRoleTextW.argtypes = [wt.DWORD, wt.LPWSTR, wt.UINT]

WM_SETTEXT, WM_GETTEXT, WM_GETTEXTLENGTH = 0x000C, 0x000D, 0x000E
WM_CLOSE = 0x0010
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP, WM_SYSCHAR = 0x0100, 0x0101, 0x0104, 0x0105, 0x0106
BM_GETCHECK, BM_CLICK = 0x00F0, 0x00F5
VK_TAB, VK_RETURN, VK_SHIFT, VK_CONTROL, VK_MENU, VK_ESCAPE = 0x09, 0x0D, 0x10, 0x11, 0x12, 0x1B
VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU = 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5
VK_UP, VK_DOWN, VK_SPACE = 0x26, 0x28, 0x20
OBJID_CLIENT = -4
GA_ROOT = 2
ROLE_GROUPING = 20

failures = 0
checks = 0


def check(cond, what):
	global failures, checks
	checks += 1
	print(f"  {'ok  ' if cond else 'FAIL'}  {what}")
	if not cond:
		failures += 1


class GUITHREADINFO(ctypes.Structure):
	_fields_ = [
		("cbSize", wt.DWORD), ("flags", wt.DWORD), ("hwndActive", wt.HWND),
		("hwndFocus", wt.HWND), ("hwndCapture", wt.HWND), ("hwndMenuOwner", wt.HWND),
		("hwndMoveSize", wt.HWND), ("hwndCaret", wt.HWND), ("rcCaret", wt.RECT),
	]


def text_of(hwnd):
	n = user32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)
	buf = ctypes.create_unicode_buffer(n + 2)
	user32.SendMessageW(hwnd, WM_GETTEXT, n + 1, ctypes.addressof(buf))
	return buf.value


def set_text(hwnd, s):
	buf = ctypes.create_unicode_buffer(s)
	user32.SendMessageW(hwnd, WM_SETTEXT, 0, ctypes.addressof(buf))


def class_of(hwnd):
	buf = ctypes.create_unicode_buffer(64)
	user32.GetClassNameW(hwnd, buf, 64)
	return buf.value


def children(parent):
	out = []
	proc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)(lambda h, _: out.append(h) or True)
	user32.EnumChildWindows(parent, proc, 0)
	return out


def top_windows(pid):
	out = []

	def cb(h, _):
		p = wt.DWORD()
		user32.GetWindowThreadProcessId(h, ctypes.byref(p))
		if p.value == pid:
			out.append(h)
		return True

	user32.EnumWindows(ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)(cb), 0)
	return out


def wait_for(fn, timeout=10.0, step=0.05):
	end = time.time() + timeout
	while time.time() < end:
		v = fn()
		if v:
			return v
		time.sleep(step)
	return fn()


def role_text(role):
	buf = ctypes.create_unicode_buffer(64)
	oleacc.GetRoleTextW(role, buf, 64)
	return buf.value


def msaa(hwnd):
	ptr = ctypes.POINTER(IAccessible)()
	hr = oleacc.AccessibleObjectFromWindow(hwnd, ctypes.c_long(OBJID_CLIENT), ctypes.byref(IAccessible._iid_),
										   ctypes.byref(ptr))
	if hr != 0 or not ptr:
		return {"role": None, "role_id": None, "name": None, "value": None, "description": None}
	acc = ptr

	def get(name):
		try:
			return getattr(acc, name)(0)
		except Exception:
			try:
				return getattr(acc, name)[0]
			except Exception:
				return None

	role = get("accRole")
	return {
		"role": role_text(role) if isinstance(role, int) else str(role),
		"role_id": role,
		"name": get("accName"),
		"value": get("accValue"),
		"description": get("accDescription"),
	}


def group_of(h):
	"""The name of the nearest ancestor window whose MSAA role is grouping:
	the group box a wxStaticBoxSizer makes its fields children of. NVDA
	announces such an ancestor when the focus enters it."""
	p = user32.GetParent(h)
	while p:
		info = msaa(p)
		if info["role_id"] == ROLE_GROUPING:
			return info["name"]
		p = user32.GetParent(p)
	return None


class Gui:
	def __init__(self, exe, data):
		self.proc = Process(exe, ["--data", data])
		self.main = wait_for(lambda: next(
			(h for h in top_windows(self.proc.pid) if user32.IsWindowVisible(h) and text_of(h) == "GamaTTS"), None),
			timeout=20)
		if not self.main:
			sys.exit("gama_gui did not open a window")
		self.tid = user32.GetWindowThreadProcessId(self.main, None)
		self.statusbar = wait_for(lambda: next(
			(h for h in children(self.main) if class_of(h) == "msctls_statusbar32"), None))
		wait_for(lambda: "Ready" in self.status())
		msg = wt.MSG()
		user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # a queue, to attach input
		self.my_tid = kernel32.GetCurrentThreadId()

	def status(self):
		return text_of(self.statusbar) if self.statusbar else ""

	def focus(self):
		gti = GUITHREADINFO()
		gti.cbSize = ctypes.sizeof(gti)
		user32.GetGUIThreadInfo(self.tid, ctypes.byref(gti))
		return gti.hwndFocus

	def settle(self):
		"""Wait until the GUI has handled everything posted to it (see
		rsynth's gui_check.py: a SendMessage round trip alone can return while
		posted keys are still queued)."""
		time.sleep(0.03)
		user32.WaitForInputIdle(self.proc.handle, 2000)
		user32.SendMessageW(self.main, WM_GETTEXTLENGTH, 0, 0)
		time.sleep(0.05)

	def _modifiers(self, held):
		state = (ctypes.c_ubyte * 256)()
		user32.GetKeyboardState(state)
		for m in (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU):
			state[m] = 0
		for m in held:
			state[m] = 0x80
		user32.SetKeyboardState(state)

	def key(self, vk, mods=(), target=None):
		"""Post a key to the focused control with exactly `mods` held in the
		GUI thread's key state (AttachThreadInput + SetKeyboardState)."""
		target = target or self.focus() or self.main
		alt = VK_MENU in mods
		user32.AttachThreadInput(self.my_tid, self.tid, True)
		self._modifiers(mods)
		lparam = 1 | (1 << 29 if alt else 0)
		user32.PostMessageW(target, WM_SYSKEYDOWN if alt else WM_KEYDOWN, vk, lparam)
		user32.PostMessageW(target, WM_SYSKEYUP if alt else WM_KEYUP, vk, lparam | 0xC0000000)
		self.settle()
		self._modifiers(())
		user32.AttachThreadInput(self.my_tid, self.tid, False)

	def dialog(self):
		return wait_for(lambda: next(
			(h for h in top_windows(self.proc.pid) if class_of(h) == "#32770" and user32.IsWindowVisible(h)), None))

	def file_dialog(self, path):
		"""Type a path into the open file dialog and press its OK button."""
		dlg = self.dialog()
		if not dlg:
			return False
		time.sleep(0.5)
		edits = [h for h in children(dlg) if class_of(h) == "Edit" and user32.IsWindowVisible(h)
				 and class_of(user32.GetParent(h)) in ("ComboBox", "ComboBoxEx32")]
		if not edits:
			edits = [h for h in children(dlg) if class_of(h) == "Edit" and user32.IsWindowVisible(h)]
		if not edits:
			return False
		set_text(edits[0], path)
		user32.PostMessageW(user32.GetDlgItem(dlg, 1), BM_CLICK, 0, 0)
		return wait_for(lambda: not user32.IsWindow(dlg), timeout=10)

	def type_into(self, h, text):
		"""Replace a field's text with real keystrokes. WM_SETTEXT will not do for a number:
		it clears the edit's modified flag, so wxSpinCtrlDouble then shows the text, but
		never commits it, and the value never reaches the engine."""
		user32.SendMessageW(h, EM_SETSEL, 0, -1)
		for ch in text:
			user32.PostMessageW(h, WM_CHAR, ord(ch), 1)
		self.settle()

	def by_name(self, name):
		"""The visible control whose MSAA name is `name` (for a composite
		such as wxSpinCtrlDouble, the edit inside it, which takes the focus)."""
		found = None
		for h in children(self.main):
			if user32.IsWindowVisible(h) and msaa(h)["name"] == name:
				found = h
				if class_of(h) == "Edit":
					return h
		return found

	def tab_cycle(self, start):
		"""Tab from `start` until the focus comes back to it; the windows seen."""
		seen = [self.focus()]
		for _ in range(200):
			self.key(VK_TAB)
			f = self.focus()
			if f == start:
				return seen, True
			seen.append(f)
		return seen, False


EM_SETSEL, WM_CHAR = 0x00B1, 0x0102


def read_wav(path):
	with wave.open(path, "rb") as w:
		return w.getframerate(), w.getnchannels(), w.getsampwidth(), w.readframes(w.getnframes())


def golden_row(path, row_id):
	with open(path, encoding="ascii") as f:
		for line in f:
			if line.startswith("#") or line.startswith("voice\t"):
				continue
			voice, tempo, i, pcm, trm, n, peak, rate, text = line.rstrip("\r\n").split("\t", 8)
			if voice == "5_male" and tempo == "1.0" and int(i) == row_id:
				return pcm, trm, int(n), int(rate), text
	sys.exit(f"golden row {row_id} not found")


def api_phonetic(dll, data, text):
	lib = ctypes.CDLL(dll)
	lib.gama_create.restype = ctypes.c_void_p
	lib.gama_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
	lib.gama_destroy.argtypes = [ctypes.c_void_p]
	lib.gama_text_to_phonetic.restype = ctypes.c_size_t
	lib.gama_text_to_phonetic.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
	e = lib.gama_create(data.encode("mbcs"), None, 0)
	buf = ctypes.create_string_buffer(8192)
	lib.gama_text_to_phonetic(e, text.encode("ascii"), buf, len(buf))
	lib.gama_destroy(e)
	return buf.value.decode("ascii")


# Each category with its fields, in order: the parameter table's labels and
# units as the GUI names them.
CATEGORIES = [
	("Speech", ["Tempo", "Pitch offset (semitones)", "Initial pitch (semitones)", "Control period"]),
	("Intonation", ["Micro intonation", "Macro intonation", "Smooth intonation", "Intonation drift", "Random intonation",
					"Drift deviation (semitones)", "Drift speed (Hz)", "Intonation range"]),
	("Glottal source", ["Glottal waveform", "Reference glottal pitch (semitones)", "Pulse rise time (%)",
						"Pulse fall time, minimum (%)", "Pulse fall time, maximum (%)", "Breathiness (%)",
						"Glottal loss, closed (%)", "Glottal loss, open (%)", "Glottal low-pass cutoff (Hz)"]),
	("Vocal tract", ["Tract length (cm)", "Tract length offset (cm)", "Temperature (degrees C)", "Junction loss (%)",
					 "Fixed mouth radiation", "Fixed mouth radius (cm)", "Global radius coefficient"]
	 + [f"Region {k} radius coefficient" for k in range(1, 9)]),
	("Nose", ["Global nose radius coefficient"] + [f"Nasal section {k} radius (cm)" for k in range(2, 8)]),
	("Noise", ["Pulse-modulated noise", "Noise crossmix offset (dB)", "Glottal noise cutoff (Hz)",
			   "Frication noise cutoff (Hz)", "Frication strength"]),
	("Output", ["Output sample rate", "Volume (%)", "Loudness", "Loudness target (dB)",
				"Trim the silence at both ends", "Silence kept before (ms)",
				"Silence kept after (ms)"]),
]
MAIN_STOPS = ["Text to speak", "Read as", "Voice", "Speak", "Stop", "Save as WAV...", "Show phonetic string",
			  "Use phonetic string as text", "Parameters for", "Reset all parameters"]


def main():
	if len(sys.argv) != 5:
		sys.exit(__doc__)
	exe, dll, data, golden = (os.path.abspath(p) for p in sys.argv[1:5])
	tmp = tempfile.mkdtemp(prefix="gama_gui_check_")
	g = Gui(exe, data)
	try:
		run(g, dll, data, golden, tmp)
	finally:
		if g.proc.poll() is None:
			g.proc.kill()
			g.proc.wait(5)
		kernel32.CloseHandle(g.proc.handle)
		user32.CloseDesktop(DESKTOP)
	print(f"\n{checks} checks, {failures} failed")
	return 1 if failures else 0


def run(g, dll, data, golden, tmp):
	text_box = g.by_name("Text to speak")
	print("1. The tab stops of the window as it opens, with MSAA's view of each")
	check(g.focus() == text_box, "the focus starts in the text box")
	seen, wrapped = g.tab_cycle(text_box)
	check(wrapped, f"Tab comes back round to the text box after {len(seen)} stops")
	names = []
	for h in seen:
		info = msaa(h)
		names.append(info["name"])
		print(f"      {class_of(h):18} role={info['role']!r:20} name={info['name']!r:38} "
			  f"value={info['value']!r} group={group_of(h)!r}")
	check(all(names), "every tab stop has a name")
	check(len(set(seen)) == len(seen), "no control is visited twice")
	want = MAIN_STOPS + CATEGORIES[0][1] + ["Phonetic string"]
	check(names == want, f"the tab stops are, in order: {want}")
	if names != want:
		print("        got:", names)
	descs = [msaa(h)["description"] for h in seen]
	check(all(descs), "every tab stop has a description (what NVDA reads after the value)")
	g.key(VK_TAB, (VK_SHIFT,))
	check(msaa(g.focus())["name"] == "Phonetic string", "Shift+Tab from the text box goes to the last stop")
	g.key(VK_TAB, (VK_SHIFT,))
	check(msaa(g.focus())["name"] == CATEGORIES[0][1][-1], "and one further back")

	print("2. Every category, through Ctrl+1 ... Ctrl+7")
	total = 0
	for n, (category, fields) in enumerate(CATEGORIES):
		g.key(ord("1") + n, (VK_CONTROL,))
		first = g.focus()
		check(msaa(first)["name"] == fields[0], f"Ctrl+{n + 1} moves to {fields[0]!r} ({msaa(first)['name']!r})")
		check(category in g.status(), f"the status names {category!r}: {g.status()!r}")
		got, groups = [], set()
		h = first
		for _ in fields:
			got.append(msaa(h)["name"])
			groups.add(group_of(h))
			g.key(VK_TAB)
			h = g.focus()
		check(got == fields, f"{category}: {len(fields)} fields, named with their units")
		if got != fields:
			print("        got:", got)
		check(groups == {category}, f"{category}: every field is in the group {category!r} ({groups})")
		check(msaa(h)["name"] == "Phonetic string", f"{category}: after its last field comes the phonetic string")
		total += len(fields)
	check(total == 49 + 6, f"{total} fields in all: the 49 parameters and 6 output settings")

	print("3. Number fields")
	g.key(ord("1"), (VK_CONTROL,))
	g.key(VK_TAB)
	pitch = g.focus()
	info = msaa(pitch)
	check(info["name"] == "Pitch offset (semitones)" and info["value"] == "-4.0",
		  f"pitch offset reads as {info['name']!r}, {info['value']!r}")
	check("From -24.0 to 24.0 semitones. Default -4.0." in (info["description"] or ""),
		  f"its description gives the range and default: {info['description']!r}")
	g.key(VK_UP)
	check(msaa(pitch)["value"] == "-3.5", f"Up steps to -3.5 ({msaa(pitch)['value']!r})")
	g.type_into(pitch, "99")
	g.key(VK_TAB)
	check(text_of(pitch) == "24.0", f"99 becomes 24.0 on leaving the field ({text_of(pitch)!r})")
	check("outside" in g.status() and "set to 24.0" in g.status(),
		  f"and the status says so, not the next field's help: {g.status()!r}")
	g.key(VK_TAB, (VK_SHIFT,))
	check(g.focus() == pitch, "Shift+Tab goes back to it")
	g.type_into(pitch, "abc")
	check(text_of(pitch) == "abc", f"letters reach the field, so that what was typed is what it says ({text_of(pitch)!r})")
	g.key(VK_TAB)
	check(text_of(pitch) == "24.0", f"and leaving it puts the value back ({text_of(pitch)!r})")
	check("is not a number" in g.status() and "24.0" in g.status(), f"and the status says so: {g.status()!r}")
	g.key(ord("R"), (VK_CONTROL,))
	check(text_of(pitch) == "-4.0", f"Ctrl+R resets it to -4.0 ({text_of(pitch)!r})")

	print("4. Voice")
	voice = g.by_name("Voice")
	g.key(ord("V"), (VK_MENU,))
	check(g.focus() == voice, f"Alt+V moves to Voice ({msaa(g.focus())['name']!r})")
	g.key(VK_DOWN)
	check(msaa(voice)["value"] == "Female", f"Down chooses Female ({msaa(voice)['value']!r})")
	g.key(ord("4"), (VK_CONTROL,))
	check(msaa(g.focus())["value"] == "15.0", f"the female tract length, 15.0, is loaded ({msaa(g.focus())['value']!r})")
	g.key(ord("V"), (VK_MENU,))
	g.key(VK_UP)
	check(msaa(voice)["value"] == "Male", "Up goes back to Male")

	print("5. Phonetic string")
	pcm, trm, n, rate, line = golden_row(golden, 39)
	set_text(text_box, line)
	g.key(ord("P"), (VK_CONTROL,))
	phon_box = g.by_name("Phonetic string")
	want_phon = api_phonetic(dll, data, line + " ")
	check(text_of(phon_box) == want_phon, f"Ctrl+P shows gama_text_to_phonetic's string: {text_of(phon_box)!r}")
	check(g.focus() == phon_box, "and moves the focus to it")

	print("6. Saving, against the golden traces of gama_tts")
	# The golden run had intonation drift and random intonation off.
	g.key(ord("2"), (VK_CONTROL,))
	g.key(VK_TAB)
	g.key(VK_TAB)
	g.key(VK_TAB)
	drift = g.focus()
	user32.SendMessageW(drift, BM_CLICK, 0, 0)
	g.key(VK_TAB)
	random_ = g.focus()
	user32.SendMessageW(random_, BM_CLICK, 0, 0)
	g.settle()
	check(user32.SendMessageW(drift, BM_GETCHECK, 0, 0) == 0 and user32.SendMessageW(random_, BM_GETCHECK, 0, 0) == 0,
		  "Intonation drift and Random intonation are off")

	# Loudness is steady throughout by default (docs/13), then even per
	# message (docs/12): both WAVs are at the target.
	def save_levelled(name, what):
		path = os.path.join(tmp, name)
		g.key(ord("S"), (VK_CONTROL,))
		check(g.file_dialog(path), f"saving with Loudness {what}")
		check(wait_for(lambda: os.path.exists(path) and "Saved" in g.status(), timeout=20), f"status: {g.status()!r}")
		r, _, _, frames_ = read_wav(path)
		x = np.frombuffer(frames_, dtype="<i2")
		level = a_weighted_db(x, r)
		check(abs(level - (-22.0)) <= 0.2 and int(np.max(np.abs(x))) <= 31129,
			  f"its A-weighted level is the target, -22 dB: {level:.2f} dB, peak {int(np.max(np.abs(x)))}")
		return x

	steady = save_levelled("gui_steady.wav", "steady throughout")
	g.key(ord("7"), (VK_CONTROL,))
	g.key(VK_TAB)
	g.key(VK_TAB)
	leveling = g.focus()
	check(msaa(leveling)["name"] == "Loudness" and msaa(leveling)["value"] == "Steady throughout",
		  f"Loudness is Steady throughout by default: {msaa(leveling)}")
	g.key(VK_DOWN)
	g.settle()
	check(msaa(leveling)["value"] == "Even per message", f"Down arrow: {msaa(leveling)['value']!r}")
	message = save_levelled("gui_message.wav", "even per message")
	check(len(message) == len(steady) and np.any(message != steady), "and it differs from steady throughout")
	# The golden run is the engine's own peak levelling.
	g.key(VK_DOWN)
	g.settle()
	check(msaa(leveling)["value"] == "The engine's own peaks", f"Down arrow again: {msaa(leveling)['value']!r}")
	wav = os.path.join(tmp, "gui.wav")
	g.key(ord("S"), (VK_CONTROL,))
	check(g.file_dialog(wav), "Ctrl+S opens the save dialog, which takes a file name")
	check(wait_for(lambda: "Saved" in g.status(), timeout=20), f"status: {g.status()!r}")
	r, ch, width, frames = read_wav(wav)
	check((r, ch, width) == (rate, 1, 2), f"the WAV is {r} Hz, {ch} channel, {8 * width}-bit")
	check(len(frames) // 2 == n and hashlib.sha256(frames).hexdigest() == pcm,
		  f"its {len(frames) // 2} samples are golden line 39's, byte for byte")
	track = os.path.join(tmp, "track.txt")
	g.key(ord("T"), (VK_CONTROL,))
	check(g.file_dialog(track), "Ctrl+T opens the track dialog")
	check(wait_for(lambda: os.path.exists(track) and "track" in g.status(), timeout=20), f"status: {g.status()!r}")
	with open(track, "rb") as f:
		track_bytes = f.read()
	check(hashlib.sha256(track_bytes).hexdigest() == trm, "the track is gama_tts -p's, byte for byte")
	# The track is the same in every levelling mode, so it says where the
	# voiced frames of the steady WAV are.
	track_rows = parse_track(track_bytes.decode("ascii"))
	sd_steady = voiced_frame_sd(steady / 32768, r, track_rows)
	sd_peak = voiced_frame_sd(np.frombuffer(frames, dtype="<i2") / 32768, r, track_rows)
	check(sd_steady is not None and sd_peak is not None and sd_steady <= 0.75 and sd_peak > 2 * sd_steady,
		  f"steady throughout holds one level inside: voiced frames move {sd_steady:.2f} dB (sd), against {sd_peak:.2f} as made")

	g.key(ord("U"), (VK_CONTROL,))
	check(text_of(text_box) == want_phon.strip(), "Ctrl+U puts the phonetic string in the text box")
	check(msaa(g.by_name("Read as"))["value"] == "Phonetic string", "and sets Read as to Phonetic string")
	wav2 = os.path.join(tmp, "gui_phonetic.wav")
	g.key(ord("S"), (VK_CONTROL,))
	check(g.file_dialog(wav2), "saving again")
	wait_for(lambda: os.path.exists(wav2), timeout=20)
	check(read_wav(wav2)[3] == frames, "speaking the phonetic string gives the same samples")

	print("7. Presets")
	preset = os.path.join(tmp, "test.gamapreset")
	g.key(ord("1"), (VK_CONTROL,))
	g.key(VK_TAB)
	pitch = g.focus()
	g.key(VK_UP)
	g.key(VK_UP)
	check(text_of(pitch) == "-3.0", f"pitch offset -3.0 ({text_of(pitch)!r})")
	g.key(ord("S"), (VK_CONTROL, VK_SHIFT))
	check(g.file_dialog(preset), "Ctrl+Shift+S saves a preset")
	check(wait_for(lambda: os.path.exists(preset)), "the preset file was written")
	with open(preset, encoding="utf-8") as f:
		body = f.read()
	check("loudness = peak\n" in body and "loudness_target_db = -22\n" in body,
		  "and loudness = peak, loudness_target_db = -22")
	check("pitch_offset = -3\n" in body and "intonation_drift = 0\n" in body and "voice = male\n" in body,
		  "it holds pitch_offset = -3, intonation_drift = 0 and voice = male")
	g.key(ord("R"), (VK_CONTROL,))
	check(text_of(pitch) == "-4.0", "Ctrl+R resets it")
	g.key(ord("O"), (VK_CONTROL,))
	check(g.file_dialog(preset), "Ctrl+O opens it")
	wait_for(lambda: "Opened" in g.status())
	check(text_of(pitch) == "-3.0" and "Opened test.gamapreset." == g.status(),
		  f"and brings back -3.0: {text_of(pitch)!r}, {g.status()!r}")
	g.key(ord("R"), (VK_CONTROL,))

	print("7b. Values that share a limit, which the status must explain")
	g.key(ord("3"), (VK_CONTROL,))
	for _ in range(3):
		g.key(VK_TAB)
	tn_min = g.focus()
	check(msaa(tn_min)["name"] == "Pulse fall time, minimum (%)", f"on the fall time minimum ({msaa(tn_min)['name']!r})")
	check(text_of(tn_min) == "24.0", f"it reads 24.0 ({text_of(tn_min)!r})")
	g.type_into(tn_min, "30")
	g.key(VK_TAB)
	g.settle()
	check(text_of(tn_min) == "24.0", f"30 is above the maximum, so it stays at 24.0 ({text_of(tn_min)!r})")
	check("refused" in g.status() and "may not pass" in g.status(),
		  f"and the status says why, not the next field's help: {g.status()!r}")
	g.key(VK_TAB, (VK_SHIFT,))
	g.type_into(tn_min, "20")
	g.key(VK_TAB)
	check(text_of(tn_min) == "20.0", f"20 is allowed ({text_of(tn_min)!r})")
	typed_preset = os.path.join(tmp, "typed.gamapreset")
	g.key(ord("S"), (VK_CONTROL, VK_SHIFT))
	check(g.file_dialog(typed_preset) and wait_for(lambda: os.path.exists(typed_preset)), "saving a preset after typing a value")
	with open(typed_preset, encoding="utf-8") as f:
		check("glottal_pulse_tn_min = 20\n" in f.read(), "and the typed value reached the engine, as 20")
	g.key(ord("R"), (VK_CONTROL,))
	# A preset holding values that can only be set in one order.
	limits = os.path.join(tmp, "limits.gamapreset")
	with open(limits, "w", encoding="ascii") as f:
		f.write("glottal_pulse_tn_min = 40\nglottal_pulse_tn_max = 45\nglottal_pulse_tp = 50\n")
	g.key(ord("O"), (VK_CONTROL,))
	check(g.file_dialog(limits), "opening a preset with the minimum before the maximum")
	wait_for(lambda: "Opened" in g.status())
	check(text_of(tn_min) == "40.0" and g.status() == "Opened limits.gamapreset.",
		  f"it takes every value in the end: {text_of(tn_min)!r}, {g.status()!r}")
	g.key(ord("R"), (VK_CONTROL,))
	check(text_of(tn_min) == "24.0", "Ctrl+R puts it back")

	print("8. Speaking (at volume 0), stopping, closing")
	g.key(ord("7"), (VK_CONTROL,))
	g.key(VK_TAB)
	volume = g.focus()
	g.type_into(volume, "0")
	g.key(VK_TAB)
	check(text_of(volume) == "0", f"volume 0 ({text_of(volume)!r})")
	g.key(ord("A"), (VK_MENU,))
	g.key(VK_UP)
	set_text(text_box, "Test.")
	# The speech below goes to the real output device: wxSound does not know about the
	# private desktop.
	# Before anything plays through the speakers, prove that it is silent.
	silent = os.path.join(tmp, "silent.wav")
	g.key(ord("S"), (VK_CONTROL,))
	check(g.file_dialog(silent) and wait_for(lambda: os.path.exists(silent), timeout=20), "saving at volume 0")
	silent_frames = read_wav(silent)[3]
	is_silent = len(silent_frames) > 0 and not any(silent_frames)
	check(is_silent, "and that WAV is silent, so the speakers will be")
	if not is_silent:
		sys.exit("volume 0 did not take effect, so nothing more is played")
	g.key(VK_RETURN, (VK_CONTROL,), target=text_box)
	check(wait_for(lambda: "Speaking," in g.status(), timeout=10), f"Ctrl+Enter speaks: {g.status()!r}")
	check(wait_for(lambda: g.status() == "Done.", timeout=10), f"and finishes: {g.status()!r}")
	set_text(text_box, "This is a long passage that goes on. " * 20)
	g.key(VK_RETURN, (VK_CONTROL,), target=text_box)
	wait_for(lambda: "Speaking," in g.status(), timeout=20)
	time.sleep(0.3)
	g.key(VK_ESCAPE, target=text_box)
	check(g.status() == "Stopped.", f"Esc stops: {g.status()!r}")
	time.sleep(0.5)
	check(g.status() == "Stopped.", f"and nothing finishes after it: {g.status()!r}")

	user32.PostMessageW(g.main, WM_CLOSE, 0, 0)
	code = g.proc.wait(10)
	check(code == 0, f"closes cleanly (exit code {code})")


if __name__ == "__main__":
	sys.exit(main())
