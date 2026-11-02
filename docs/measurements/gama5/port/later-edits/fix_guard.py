"""The guard counts real spelled lengths. Every replacement must apply."""
import sys

ROOT = r"C:\GIT\speech synthesis\gama_tts\\"


def edit(path, R):
	s = open(ROOT + path, encoding="utf-8", newline="").read()
	crlf = "\r\n" in s
	s = s.replace("\r\n", "\n")
	for a, b in R:
		if a not in s:
			sys.exit(f"MISSING in {path}:\n{a}")
		s = s.replace(a, b)
	if crlf:
		s = s.replace("\n", "\r\n")
	open(ROOT + path, "w", encoding="utf-8", newline="").write(s)


s = open(ROOT + "api/gama_api.cpp", encoding="utf-8", newline="").read()
start = s.index("// Rule 9. The engine's parser")
end = s.index("std::string safePhonetic")
s = s[:start] + """// Rule 9. The engine's parser copies words into fixed buffers with no length check, and
// indexes tables with signed characters. A word it cannot pronounce it spells, into a
// buffer of 1027 bytes (LetterToSound.cpp), so what fills that buffer is the spelled length: 17
// bytes for a "w", 43 for a "<". A run is broken before its spelling could fill it, and
// before it reaches the length at which the other buffers were found to overflow (docs/10,
// section 5). A run with no reason to be broken is left alone, since a broken word is read
// differently: "http://www.gnu.org/software/gnuspeech/" must stay whole.
constexpr int kMaxSpelledBytes = 1000;
constexpr int kMaxRunChars = 100;

std::string safeText(const char* text)
{
	std::string s;
	s.reserve(std::strlen(text) + 16);
	int spelled = 0, run = 0;
	for (const char* p = text; *p; ++p) {
		const unsigned char c = static_cast<unsigned char>(*p);
		if (c <= ' ' || c > '~') {
			s += ' ';
			spelled = run = 0;
			continue;
		}
		const int cost = gamaSpelledLength(c);
		if (spelled + cost > kMaxSpelledBytes || run == kMaxRunChars) {
			s += ' ';
			spelled = run = 0;
		}
		s += static_cast<char>(c);
		spelled += cost;
		++run;
	}
	return s;
}

""" + s[end:]
a = """namespace {

using GS::VTMControlModel::Configuration;
"""
if a not in s:
	sys.exit("namespace")
s = s.replace(a, """// gama_spell.cpp: how long a character gets when the engine spells it.
int gamaSpelledLength(unsigned char c);

""" + a, 1)
open(ROOT + "api/gama_api.cpp", "w", encoding="utf-8", newline="\n").write(s)

s = open(ROOT + "api/gama_api.h", encoding="utf-8", newline="").read()
start = s.index(" *  9. Text is made safe")
end = s.index(" * 10. Limits shared")
s = s[:start] + """ *  9. Text is made safe before the parser sees it (docs/10): any byte outside printable
 *     ASCII becomes a space, and a run without a space is broken with one after 100
 *     characters, or sooner if its spelling would pass 1000 bytes. The engine's parser
 *     spells what it cannot pronounce into a fixed buffer with no length check, and
 *     overruns it on 100 "w" or 24 "<". Nothing shorter than that is touched. A phonetic
 *     string (gama_speak_phonetic) gets the first of these only.
""" + s[end:]
open(ROOT + "api/gama_api.h", "w", encoding="utf-8", newline="\n").write(s)

edit("CMakeLists.txt", [
("add_library(gama_api SHARED api/gama_api.cpp api/gama_api.h)", "add_library(gama_api SHARED api/gama_api.cpp api/gama_spell.cpp api/gama_api.h)"),
])

edit("tests/api/check_robustness.py", [
("""		for n in ((19, 20, 21, 44, 45, 46, 100, 101, 500) if scale > 1 else (20, 21, 45, 46, 100)):""",
 """		for n in ((22, 23, 24, 25, 45, 57, 58, 59, 60, 61, 99, 100, 101, 500) if scale > 1 else (23, 24, 25, 58, 59, 60, 100, 101)):"""),
("""	# Mixtures at the edge of the budget, cut where the guard cuts.""", """	# Mixtures at the edge of what the guard allows, cut where it cuts."""),
])

edit("docs/10-model5-api-gui-addon.md", [
("""**The guard now costs by spelling:** 20 for a letter or digit, 45 for anything else, a budget of 900. That is 45 letters or digits, or 20 other characters. The longest word in the dictionary has 31 letters, so no
real word is touched. A URL or a hash is broken in places, which changes how it is read and not whether.
""", """**The guard now counts by spelling,** with the engine's own table (`api/gama_spell.cpp`): a run is broken before its spelled length would pass 1,000 bytes, and in any case after 100 characters, where the other buffers were found to hold. So 23 `<`, or 58 `w`,
or 100 of anything cheap. **It leaves alone anything shorter,** and that matters: a first version charged every symbol the worst cost, and broke `http://www.gnu.org/software/gnuspeech/`, a line of the corpus, which changed how it was read. The golden test caught that at the package build.
"""),
])

edit("README.md", [
("""> - **The engine has four small fixes,** listed in `NOTICE.md`.""", """> - **The engine has four small fixes, in three files,** listed in `NOTICE.md`."""),
])
print("ok")
