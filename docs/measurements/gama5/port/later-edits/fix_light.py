import sys
p = r"C:\GIT\speech synthesis\gama_tts\gama_tts\src\text_parser\english\ApplyStress.cpp"
s = open(p, encoding="utf-8", newline="").read()
a = "\twhile (!isvowel(*sb)) {\r\n\t\tsb++;\r\n\t}\r\n\twhile (isvowel(*sb) || (*sb == '_')"
if a not in s: sys.exit("MISSING")
b = "\t// A syllable may have no vowel: stop at its end, not somewhere past it.\r\n\twhile (*sb && !isvowel(*sb)) {\r\n\t\tsb++;\r\n\t}\r\n\twhile (isvowel(*sb) || (*sb == '_')"
open(p, "w", encoding="utf-8", newline="").write(s.replace(a, b))
