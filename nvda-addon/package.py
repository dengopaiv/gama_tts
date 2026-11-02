#!/usr/bin/env python3
"""Build the GamaTTS NVDA add-on.

    python -I nvda-addon/package.py [--skip-tests] [--generator "Visual Studio 17 2022"]

1. Configures and builds with CMake, 64-bit, Release, into build-addon-x64 (Visual
   Studio on Windows). The GUI is not needed here, so it is switched off.
2. Runs every CTest test unless --skip-tests: an add-on whose engine or driver fails
   them is not shipped.
3. Zips manifest.ini, the driver, gama_api.dll, the data model 5 needs and the licence
   files into nvda-addon/gamatts-<version>.nvda-addon.
4. Runs the driver tests again on that package, unzipped, unless --skip-tests: the
   package must hold everything the driver needs.

There is no 32-bit build and no x86 DLL: NVDA 2026 is 64-bit only, and nothing here
produces 32-bit artefacts.

Adapted from GnuspeechSA-NVDA's package.py, itself from rsynth-nvda's.
Copyright 2026 dengopaiv. GPL-3.0-or-later.
"""

import os
import subprocess
import sys
import zipfile

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ADDON_DIR)
BUILD = os.path.join(ROOT, "build-addon-x64")
DRIVER = os.path.join(ADDON_DIR, "addon", "synthDrivers", "gamatts.py")
VOICES = os.path.join(ROOT, "data", "voice", "english")

#: Files from the repository that go into the add-on, and where.
LICENCE_FILES = (
	(os.path.join(ROOT, "NOTICE.md"), "NOTICE.md"),
	(os.path.join(ROOT, "LICENSE.txt"), "COPYING.txt"),
	(os.path.join(ROOT, "data", "README.txt"), "DATA-LICENCE.txt"),
	(os.path.join(ROOT, "gama_tts", "src", "rapidxml", "license.txt"), "LICENSE-rapidxml.txt"),
)

#: Model 5's voices. Each names ../0_male/ for what they share, so those folders go too,
#: but not model 0's own rules (its artic.xml and vtm.txt).
MODEL_5 = ("5_male", "5_female", "5_large_child", "5_small_child", "5_baby")
SHARED = (("0_male", "intonation_rhythm"), ("0_male", "pho1_parser"), ("0_male", "phonetic_string_parser"),
	("0_male", "text_parser"), ("0_male", "jack.txt"))

MANIFEST_REQUIRED = ("name", "summary", "author", "version", "minimumNVDAVersion", "lastTestedNVDAVersion")


def run(cmd, **kw):
	print("+", " ".join(f'"{c}"' if " " in c else c for c in cmd))
	subprocess.run(cmd, check=True, **kw)


def read_manifest():
	"""Parse manifest.ini as NVDA's ConfigObj would, and refuse what NVDA would reject
	without saying why: a [section] header (NVDA's keys are top level), an unquoted value
	with a comma (read as a list), a missing required key."""
	values, errors = {}, []
	with open(os.path.join(ADDON_DIR, "manifest.ini"), encoding="utf-8") as f:
		for number, line in enumerate(f, 1):
			line = line.strip()
			if not line or line.startswith("#"):
				continue
			if line.startswith("["):
				errors.append(f"line {number}: sections are not allowed")
				continue
			key, _, value = line.partition("=")
			key, value = key.strip(), value.strip()
			if "," in value and value[:1] not in ('"', "'"):
				errors.append(f"line {number}: {key} has a comma and is not quoted")
			values[key] = value.strip('"').strip("'")
	missing = [k for k in MANIFEST_REQUIRED if not values.get(k)]
	if missing:
		errors.append(f"missing keys: {', '.join(missing)}")
	if errors:
		sys.exit("manifest.ini would be rejected by NVDA:\n  " + "\n  ".join(errors))
	return values


#: The generator on Windows. Named rather than left to CMake's default, because a MinGW
#: CMake first on PATH defaults to Ninja, which refuses -A.
DEFAULT_WINDOWS_GENERATOR = "Visual Studio 18 2026"


def generator_args():
	if os.name != "nt":
		return []
	gen = DEFAULT_WINDOWS_GENERATOR
	if "--generator" in sys.argv:
		gen = sys.argv[sys.argv.index("--generator") + 1]
	return ["-G", gen, "-A", "x64"]


def build():
	run(["cmake", "-S", ROOT, "-B", BUILD, *generator_args(), "-DGAMA_BUILD_GUI=OFF"])
	run(["cmake", "--build", BUILD, "--config", "Release", "--target", "gama_api", "gama_api_test"])


def test():
	run(["ctest", "--test-dir", BUILD, "-C", "Release", "--output-on-failure"])


def find_dll():
	for sub in ("Release", ""):
		path = os.path.join(BUILD, sub, "gama_api.dll")
		if os.path.isfile(path):
			return path
	sys.exit(f"no gama_api.dll under {BUILD}")


def is_pe64(path):
	"""True when the DLL is x64 or ARM64: check the PE machine field rather than trusting
	the build directory's name."""
	with open(path, "rb") as f:
		data = f.read(4096)
	if data[:2] != b"MZ":
		return False
	pe = int.from_bytes(data[0x3C:0x40], "little")
	machine = int.from_bytes(data[pe + 4 : pe + 6], "little")
	return data[pe : pe + 4] == b"PE\0\0" and machine in (0x8664, 0xAA64)


def add_data(z):
	"""The data files go in byte for byte: the engine refuses CRLF."""
	base = "synthDrivers/gamatts_data/voice/english"

	def add_path(rel):
		path = os.path.join(VOICES, rel)
		if os.path.isfile(path):
			with open(path, "rb") as f:
				if b"\r" in f.read() and path.endswith(".txt"):
					sys.exit(f"{path} has CRLF line endings: check out data/ as .gitattributes says")
			z.write(path, f"{base}/{rel.replace(os.sep, '/')}")
			return
		for name in sorted(os.listdir(path)):
			add_path(os.path.join(rel, name))

	for voice in MODEL_5:
		add_path(voice)
	for parts in SHARED:
		add_path(os.path.join(*parts))


def package(version, dll):
	if not is_pe64(dll):
		sys.exit(f"{dll} is not a 64-bit Windows DLL")
	out = os.path.join(ADDON_DIR, f"gamatts-{version}.nvda-addon")
	if os.path.exists(out):
		os.remove(out)
	with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
		z.write(os.path.join(ADDON_DIR, "manifest.ini"), "manifest.ini")
		z.write(DRIVER, "synthDrivers/gamatts.py")
		z.write(dll, "synthDrivers/gama_api.dll")
		add_data(z)
		for src, arc in LICENCE_FILES:
			z.write(src, arc)
	with zipfile.ZipFile(out) as z:
		infos = z.infolist()
	print(f"\n{os.path.relpath(out, ROOT)}: {len(infos)} files, {os.path.getsize(out) // 1024} KB")
	return out


def test_package(addon):
	"""The driver tests again, on the package itself, unzipped: proves the zip holds
	everything the driver needs."""
	run([sys.executable, "-I", os.path.join(ROOT, "tests", "nvda", "test_driver.py"), "--addon", addon,
		os.path.join(ROOT, "tests", "golden", "msvc-x64.tsv")])


def main():
	manifest = read_manifest()
	build()
	skip = "--skip-tests" in sys.argv
	if not skip:
		test()
	addon = package(manifest["version"], find_dll())
	if not skip:
		test_package(addon)


if __name__ == "__main__":
	main()
