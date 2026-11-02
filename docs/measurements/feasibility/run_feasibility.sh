#!/bin/sh
# Reproduce the measurements of docs/09-addon-and-gui-feasibility.md, except the
# fuzzing under AddressSanitizer, whose commands are in README.md.
#
# Usage, from the root of the gama_tts repository, in Git Bash:
#   sh docs/measurements/feasibility/run_feasibility.sh WORK PROBE PROBE_PATCHED GS_DIR > results.txt
#
#   WORK           empty scratch directory, outside the repository
#   PROBE          probe.exe built over the unchanged engine
#   PROBE_PATCHED  probe.exe built over a copy with engine-fixes.patch applied
#   GS_DIR         the GnuspeechSA-NVDA folder, with build/Release/gnuspeech_api.dll
#
# Writes only into WORK and to standard output. Needs Python 3 with numpy and scipy.
# Public domain. Written 2026-11-02.

set -u
WORK=$1; P=$2; P2=$3; GS=$4
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(pwd)
C="$GS/tests/golden/corpus.txt"
w() { cygpath -w "$1"; }

mkdir -p "$WORK" && cd "$WORK" || exit 1
rm -rf lf && mkdir lf
git -C "$ROOT" -c core.autocrlf=false archive HEAD data | tar -x -C lf
D="$WORK/lf/data"

awk 'NR%4==1{print $1}' "$D/voice/english/0_male/text_parser/main_dictionary.txt" | tr -d '\r' > words.txt
for c in a b c d e f g h i j k l m n o p q r s t u v w x y z \
         A B C D E F G H I J K L M N O P Q R S T U V W X Y Z \
         0 1 2 3 4 5 6 7 8 9 10 42 100 OK Yes No; do echo "$c" >> words.txt; done
awk 'NR%20==1' words.txt > w20.txt

echo "### git: $(git -C "$ROOT" rev-parse --short HEAD); corpus: $(grep -vc '^#' "$C") lines including blanks; words: $(wc -l < words.txt); sample: $(wc -l < w20.txt)"

echo; echo "### 1. Load time per voice, the second of two loads"
"$P" load "$D" 0_male 0_female 1_male 2_male 3_male 4_male 5_male 5_female 5_large_child 5_small_child 5_baby

echo; echo "### 2. Speed: corpus, tempo 1, randomness off, best of three; run alone"
for v in 0_male 4_male 5_male 5_female 5_large_child 5_small_child 5_baby; do
    for i in 1 2 3; do "$P" corpus "$D" $v "$C" 1 0 1 | grep 'rtf='; done
done

echo; echo "### 3. Unchanged engine, full synthesis, corpus: tempo against failures"
"$P" sweep "$D" 5_male "$C" 1 2 3 3.8 3.9 4 5 6 8 10

echo; echo "### 4. Unchanged engine, model 0: each tempo in its own process; exit 139 or 127 is a crash"
for t in 3 3.8 3.9 4 5 6 8; do
    "$P" lines "$D" 0_male "$C" $t 0 > tmp.txt 2>&1; rc=$?
    echo "0_male tempo $t: exit $rc, $(wc -l < tmp.txt) lines of output, last: $(tail -1 tmp.txt | cut -c1-60)"
done

echo; echo "### 5. Unchanged engine, rule engine only: pitch tracks over the corpus"
"$P" track "$D" 5_male "$C" 1 1 1 2 3 3.8 3.9 4 5 6 8 10

echo; echo "### 6. Unchanged engine, rule engine only: every fourth dictionary word"
"$P" track "$D" 5_male words.txt 1 1 1 2 3 3.5 3.85 3.9 4

echo; echo "### 7. Where it comes from: the word 'a' at either side of the threshold"
"$P" dump "$D" 5_male a 3.8 | cut -c1-120
"$P" dump "$D" 5_male a 3.9 | cut -c1-120

echo; echo "### 8. With engine-fixes.patch: dictionary, rule engine only"
"$P2" track "$D" 5_male words.txt 1 1 1 2 3 3.85 3.9 4 5 6 8 10

echo; echo "### 9. With the patch: full synthesis, corpus"
"$P2" sweep "$D" 0_male "$C" 1 3.8 4 5 6 8 10
"$P2" sweep "$D" 5_male "$C" 1 3.8 4 5 6 8 10

echo; echo "### 10. With the patch: full synthesis, dictionary sample"
for v in 5_male 5_female 0_male; do "$P2" sweep "$D" $v w20.txt 1 3 4; done

echo; echo "### 11. Does the patch change anything at ordinary tempos? WAVs compared byte for byte"
for v in 5_male 0_male; do for t in 1 2 3 3.5; do
    rm -rf wa wb; mkdir wa wb
    "$P" wavs "$D" $v wa $t 0 1 "$C"; "$P2" wavs "$D" $v wb $t 0 1 "$C"
    n=0; b=0; for f in wa/*.wav; do n=$((n+1)); cmp -s "$f" "wb/$(basename "$f")" || b=$((b+1)); done
    echo "$v tempo $t: compared $n, differ $b"
done; done

echo; echo "### 12. Repeatability, threads, memory"
for v in 5_male 0_male 5_female; do
    "$P2" repeat "$D" $v "The quick brown fox jumps over the lazy dog."
    "$P2" threads "$D" $v "$C"
done
"$P2" leak "$D" 5_male "$C" 16

echo; echo "### 13. Pitch against the tube"
for v in 5_male 5_female 5_large_child 5_small_child 5_baby 0_male 4_male; do
    "$P2" pitchsweep "$D" $v "$C" -24 -12 12 24
done

echo; echo "### 14. A wrapper that owns the tube, with the engine unchanged"
"$P" ownloop "$D" 5_male "The quick brown fox jumps over the lazy dog."
"$P" ownloop "$D" 0_male "The quick brown fox jumps over the lazy dog."

echo; echo "### 15. Which keys reach the sound (the probe overrides tempo and randomness: see section 16)"
rm -rf pdata; cp -r lf/data pdata
python -I "$(w "$HERE/perturb.py")" "$(w "$P")" "$(w "$WORK/pdata")" 5_male
python -I "$(w "$HERE/perturb.py")" "$(w "$P")" "$(w "$WORK/pdata")" 0_male

echo; echo "### 16. The keys section 15 cannot see: configuration as written, random intonation off"
rm -rf masked; cp -r lf/data masked
CF=masked/voice/english/5_male/vtm_control_model.txt
T="The quick brown fox jumps over the lazy dog. Is it, she asked, 25 percent?"
sed -i 's/^random_intonation = 1/random_intonation = 0/' "$CF"
"$P" wavcfg masked 5_male base.wav "$T" > /dev/null
"$P" wavcfg masked 5_male base2.wav "$T" > /dev/null
cmp -s base.wav base2.wav && echo "drift on, random off: repeatable" || echo "drift on, random off: NOT repeatable"
for spec in "tempo = 1.0|tempo = 1.15" "drift_deviation = 4.0|drift_deviation = 4.6" \
            "drift_lowpass_cutoff = 4.0|drift_lowpass_cutoff = 4.6" "intonation_drift = 1|intonation_drift = 0" \
            "notional_pitch = 2.0|notional_pitch = 2.3"; do
    a=${spec%|*}; b=${spec#*|}; cp "$CF" cf.bak
    sed -i "s/^$a\$/$b/" "$CF"; rm -f t.wav
    "$P" wavcfg masked 5_male t.wav "$T" > /dev/null
    if [ ! -f t.wav ]; then r="NO FILE"; elif cmp -s base.wav t.wav; then r="no effect"; else r="changes the sound"; fi
    echo "$b: $r"; cp cf.bak "$CF"
done
sed -i 's/^random_intonation = 0/random_intonation = 1/' "$CF"
"$P" wavcfg masked 5_male r1.wav "$T" > /dev/null; "$P" wavcfg masked 5_male r2.wav "$T" > /dev/null
cmp -s r1.wav r2.wav && echo "random_intonation = 1: repeats" || echo "random_intonation = 1: differs from run to run"

echo; echo "### 17. Level, spectral balance, edge silence"
python -I "$(w "$HERE/audio_metrics.py")" "$(w "$P")" "$(w "$D")" "$(w "$GS/build/Release/gnuspeech_api.dll")" \
    "$(w "$GS/data/en")" "$(w "$C")" "$(w "$GS/dist/listening/5-menu-espeak-klatt5.wav")" "$(w "$WORK/metrics")" 2>/dev/null \
    | grep -v '^Equation\|^Duplicate'

echo; echo "### 18. The shipped Gnuspeech DLL through the same tempos"
python -I "$(w "$HERE/gs_tempo.py")" "$(w "$GS/build/Release/gnuspeech_api.dll")" "$(w "$GS/data/en")" "$(w "$C")"

echo; echo "### done"
