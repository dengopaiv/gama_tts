#!/bin/sh
# Every measurement and test behind docs/10, in one run, on the code as it stands.
#
# Usage, from the repository root, in Git Bash, after building build-x64 (docs/10):
#   sh docs/measurements/gama5/run_all.sh > docs/measurements/gama5/results-DATE.txt
#
# Writes only to standard output. Needs Python 3 with numpy and scipy. About 30 minutes.
# The engine's dictionary loader writes 45 "Duplicate word" lines to standard error each time
# an engine loads, which is harmless, so standard error goes to /dev/null. A crash still shows,
# as the stage's exit code. The GUI's check and AddressSanitizer are separate: see README.md.
# Public domain. Written 2026-11-02.

set -u
DLL=$(cygpath -w build-x64/Release/gama_api.dll)
DATA=data
CORPUS=tests/golden/corpus.txt
GOLDEN=tests/golden/msvc-x64.tsv

stage() { echo; echo "### $1"; }
done_() { echo "(exit $?)"; }

echo "### commit: $(git rev-parse --short HEAD); changed files: $(git status --short | wc -l)"

stage "1. C tests of the API"
build-x64/Release/gama_api_test "$DATA" 2>/dev/null; done_

stage "2. Against the golden traces of the unchanged engine"
python -I tests/api/check_golden.py "$DLL" "$DATA" "$GOLDEN" 2>/dev/null; done_

stage "3. Robustness, with --long"
python -I tests/api/check_robustness.py "$DLL" "$DATA" --long 2>/dev/null; done_

stage "4. Levelling against an independent measure, all five voices"
python -I tests/api/check_leveling.py "$DLL" "$DATA" "$CORPUS" 2>/dev/null; done_

stage "5. Noise against voice across pitch, 20 lines"
python -I tools/measure/pitch_balance.py "$DLL" "$DATA" "$CORPUS" 20 2>/dev/null; done_

stage "6. The tick at the end of an utterance"
python -I tools/measure/end_tick.py "$DLL" "$DATA" "$CORPUS" 2>/dev/null; done_

stage "7. The ends of a few utterances"
python -I tools/measure/edges.py "$DLL" "$DATA" 2>/dev/null; done_
python -I tools/measure/tail.py "$DLL" "$DATA" "no" "Button," "yes" 2>/dev/null; done_

stage "8. Spelled lengths, from the engine's source"
python -I tools/measure/spelled_lengths.py; done_

stage "9. The driver, with stand-ins for NVDA"
python -I tests/nvda/test_driver.py "$DLL" "$DATA" "$GOLDEN" 2>/dev/null; done_

echo; echo "### done"
