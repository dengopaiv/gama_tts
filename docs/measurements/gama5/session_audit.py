"""Audit a Claude Code session from its transcript, instead of from memory.

    python -I docs/measurements/gama5/session_audit.py <session.jsonl> <full-log.txt> [--errors]

Reads every tool call and its result. Writes to <full-log.txt> the whole sequence in order: the
author's messages, each command with its description and its full output, and for a file written
or edited, its path and size, since the file itself holds the content. Prints a count by tool, and
with --errors, every result that the harness marked as an error, or whose text shows a non-zero
exit or a failed check, so that each can be compared with docs/12's list of failed attempts.

The log can hold private paths and other private material, so it does not belong in a public
repository: docs/12 says where it was put.
Public domain. Written 2026-11-02.
"""

import json
import re
import sys
from collections import Counter

SIGNS = re.compile(r"Exit code [1-9]|\bexit [1-9]\d*\b|exit=[1-9]|Traceback|fatal:|FAIL\b|ERROR: AddressSanitizer|Segmentation fault|"
	r"error LNK|error C\d|MISSING|denied|NO FILE|FileNotFoundError|CRASH|DEAD ", re.I)


def text_of(content):
	if isinstance(content, str):
		return content
	out = []
	for part in content or []:
		if isinstance(part, dict) and part.get("type") == "text":
			out.append(part.get("text", ""))
	return "\n".join(out)


def main():
	path, log_path = sys.argv[1:3]
	want_errors = "--errors" in sys.argv
	calls = {}
	counts = Counter()
	seq = 0
	findings = []
	with open(path, encoding="utf-8") as f, open(log_path, "w", encoding="utf-8", newline="\n") as log:
		for line in f:
			try:
				rec = json.loads(line)
			except ValueError:
				continue
			if rec.get("type") not in ("user", "assistant") or rec.get("isSidechain"):
				continue
			when = rec.get("timestamp", "")[:19]
			content = rec.get("message", {}).get("content")
			if rec["type"] == "user" and isinstance(content, str) and not content.lstrip().startswith("<"):
				log.write(f"\n===== {when} THE AUTHOR =====\n{content}\n")
			if not isinstance(content, list):
				continue
			for part in content:
				if not isinstance(part, dict):
					continue
				if part.get("type") == "text" and rec["type"] == "user" and not part["text"].lstrip().startswith("<"):
					log.write(f"\n===== {when} THE AUTHOR =====\n{part['text']}\n")
				elif part.get("type") == "tool_use":
					seq += 1
					name = part.get("name", "?")
					counts[name] += 1
					inp = part.get("input", {})
					calls[part.get("id")] = (seq, name, inp)
					log.write(f"\n===== {when} #{seq} {name} =====\n")
					if name in ("Write",):
						log.write(f"{inp.get('file_path')} ({len(inp.get('content', ''))} characters)\n")
					elif name == "Edit":
						log.write(f"{inp.get('file_path')}\n--- old\n{inp.get('old_string', '')}\n--- new\n{inp.get('new_string', '')}\n")
					elif name == "Bash":
						log.write(f"# {inp.get('description', '')}\n{inp.get('command', '')}\n")
					else:
						log.write(json.dumps(inp, ensure_ascii=False)[:2000] + "\n")
				elif part.get("type") == "tool_result":
					seq_name = calls.get(part.get("tool_use_id"), (0, "?", {}))
					body = text_of(part.get("content"))
					log.write(f"--- result of #{seq_name[0]}{' (ERROR)' if part.get('is_error') else ''}\n{body}\n")
					if seq_name[1] in ("Read", "Write", "Edit", "Grep", "ToolSearch", "WebFetch"):
						sign = None if not part.get("is_error") else "marked as an error"
					else:
						m = SIGNS.search(body)
						sign = "marked as an error" if part.get("is_error") else (m.group(0) if m else None)
					if sign:
						findings.append((seq_name[0], seq_name[1], sign, seq_name[2].get("description", ""), when))
	print(f"{seq} tool calls: " + ", ".join(f"{k} {v}" for k, v in counts.most_common()))
	print(f"{len(findings)} results show a failure or a failed check")
	if want_errors:
		for s, name, sign, desc, when in findings:
			print(f"#{s:4d} {when[11:]} {name:10} {sign[:30]:30} {desc[:70]}")


if __name__ == "__main__":
	main()
