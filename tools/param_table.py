"""The API's parameter table, as Markdown: what docs/11 shows.

    python -I tools/param_table.py <gama_api library> <data_dir>

Everything comes from the library itself, so the manual can be made again when the table
changes: name, unit, range, step, and the value in each voice's data files.

Copyright 2026 dengopaiv. GPL-3.0-or-later.
"""

import ctypes
import sys

p = ctypes.c_void_p


class Info(ctypes.Structure):
	_fields_ = [("key", ctypes.c_char_p), ("file", ctypes.c_char_p), ("category", ctypes.c_char_p),
		("label", ctypes.c_char_p), ("unit", ctypes.c_char_p), ("help", ctypes.c_char_p), ("kind", ctypes.c_int),
		("min", ctypes.c_double), ("max", ctypes.c_double), ("step", ctypes.c_double), ("decimals", ctypes.c_int),
		("choice_count", ctypes.c_int), ("choice_values", ctypes.POINTER(ctypes.c_double)),
		("choice_names", ctypes.POINTER(ctypes.c_char_p))]


def main():
	lib = ctypes.CDLL(sys.argv[1])
	lib.gama_create.restype = p
	lib.gama_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
	lib.gama_param_describe.restype = ctypes.POINTER(Info)
	lib.gama_param_describe.argtypes = [ctypes.c_int]
	lib.gama_param_default.argtypes = [p, ctypes.c_int, ctypes.POINTER(ctypes.c_double)]
	lib.gama_set_voice.argtypes = [p, ctypes.c_int]
	lib.gama_voice_count.argtypes = [p]
	e = lib.gama_create(sys.argv[2].encode(), None, 0)
	count = lib.gama_param_count()
	voices = lib.gama_voice_count(e)

	def fmt(info, v):
		if info.kind == 1:
			return "on" if v else "off"
		if info.kind == 2:
			for k in range(info.choice_count):
				if info.choice_values[k] == v:
					return info.choice_names[k].decode()
		return f"{v:.{info.decimals}f}"

	category = None
	for i in range(count):
		info = lib.gama_param_describe(i).contents
		if info.category != category:
			category = info.category
			print(f"\n### {category.decode()}\n")
			print("| Field | Key | Range | Default | What it does |")
			print("|---|---|---|---|---|")
		defaults = []
		for v in range(voices):
			lib.gama_set_voice(e, v)
			d = ctypes.c_double()
			lib.gama_param_default(e, i, ctypes.byref(d))
			defaults.append(d.value)
		lib.gama_set_voice(e, 0)
		unit = f" ({info.unit.decode()})" if info.unit else ""
		if info.kind == 0:
			what = f"{info.min:.{info.decimals}f} to {info.max:.{info.decimals}f}, step {info.step:g}"
		elif info.kind == 1:
			what = "on or off"
		else:
			what = ", ".join(info.choice_names[k].decode() for k in range(info.choice_count))
		if len(set(defaults)) == 1:
			default = fmt(info, defaults[0])
		else:
			names = ("male", "female", "large child", "small child", "baby")
			default = "; ".join(f"{names[v]} {fmt(info, defaults[v])}" for v in range(voices))
		print(f"| {info.label.decode()}{unit} | `{info.key.decode()}` | {what} | {default} | {info.help.decode()} |")


if __name__ == "__main__":
	main()
