#!/bin/sh
# Reproduce every measurement in docs/07-measurements.md.
#
# Usage:
#   run_all.sh WORK GAMA_EXE [GAMA_EXE_2] GS_EXE GS_TRM_EXE GS_DATA_EN
#
#   WORK        empty scratch directory (outside the repository)
#   GAMA_EXE    gama_tts executable (any build)
#   GAMA_EXE_2  optional second build (e.g. MSVC) for the build comparison;
#               pass "-" to skip
#   GS_EXE      gnuspeech_sa executable, unmodified GnuspeechSA 0.1.5
#   GS_TRM_EXE  gnuspeech_sa_trm executable, same source
#   GS_DATA_EN  GnuspeechSA's data/en directory
#
# Run from the root of the gama_tts repository. Writes only into WORK.
# Needs python3 with numpy (or set PYTHON=...), git, tar, sed, awk, cmp.
# Public domain. Written 2026-10-16.

set -u
WORK=$1; GAMA=$2; GAMA2=$3; GS=$4; GSTRM=$5; GSDATA=$6
HERE=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3}
mkdir -p "$WORK" && cd "$WORK" || exit 1

echo "== 1. Data with LF line endings (see 06, the CRLF trap)"
rm -rf lf && mkdir lf
git -C "$OLDPWD" -c core.autocrlf=false archive HEAD data | tar -x -C lf
V=lf/data/voice/english

echo "== 2. Deterministic copies: random intonation and drift off"
rm -rf det gs && cp -r "$V" det && mkdir gs && cp -r "$GSDATA" gs/en
for f in det/0_male/vtm_control_model.txt det/5_male/vtm_control_model.txt \
         gs/en/trm_control_model.config; do
    sed -i 's/^intonation_drift = 1/intonation_drift = 0/; s/^random_intonation = 1/random_intonation = 0/' "$f"
done

T1="The quick brown fox jumps over the lazy dog."
echo "== 3. Phonetic strings, GamaTTS against GnuspeechSA"
for T in "$T1" "In 1984, it cost \$3.25." "Call 555-1234 on 3/4/2025 at 10:30." \
         "It weighs 2.5 kg, 1st of 22nd, 45%."; do
    echo "-- $T"
    printf 'gama: '; echo "$T" | "$GAMA" tts -v det/0_male x.wav 2>&1 \
        | grep -m1 "Phonetic string chunk" | sed 's/.*chunk: //'
    printf 'gs:   '; "$GS" -v -c gs/en -p x.param -o x.wav "$T" 2>&1 \
        | grep -m1 "Phonetic string:" | sed 's/Phonetic string: //'
done

echo "== 4. Parameter tracks, GnuspeechSA reference"
"$GS" -c gs/en -p gs.param -o gs.wav "$T1" > /dev/null 2>&1
echo "$T1" | "$GAMA" tts -p gama.param det/0_male gama.wav > /dev/null 2>&1
"$PY" -I "$HERE/compare_params.py" gs.param gama.param

echo "== 5. The same parameter file through both tubes (44.1 kHz)"
"$GSTRM" gs.param gs_trm.wav > /dev/null 2>&1
awk 'NF==16' gs.param > frames.param
for m in 0 1 2 3 4; do
    rm -rf vtm$m && cp -r det/0_male vtm$m
    sed -i "s/^model = .*/model = $m/; s/^output_rate = .*/output_rate = 44100.0/" vtm$m/vtm.txt
    grep -q '^log_parameters' vtm$m/vtm.txt || echo "log_parameters = false" >> vtm$m/vtm.txt
    "$GAMA" vtm vtm$m frames.param vtm$m.wav > /dev/null 2>&1 || echo "model $m failed"
done
"$PY" -I "$HERE/compare_wav.py" --bands gs_trm.wav vtm0.wav
"$PY" -I "$HERE/compare_wav.py" gs_trm.wav vtm1.wav vtm2.wav vtm3.wav vtm4.wav
echo "-- against model 0"
"$PY" -I "$HERE/compare_wav.py" vtm0.wav vtm1.wav vtm2.wav vtm3.wav vtm4.wav
cmp -s vtm0.wav vtm2.wav && echo "model 0 and model 2: byte-identical"

echo "== 6. Internal sample rates"
for v in 0_male 0_female 2_male 3_male 4_male 5_male 5_female; do
    printf '%s ' $v
    echo "Hi." | "$GAMA" tts -v "$V/$v" x.wav 2>&1 | grep -m1 "Internal sample rate"
done

echo "== 7. Repeatability and builds (randomness off)"
T2="$T1 In 1984, it cost 3 dollars and 25 cents."
for v in 0_male 4_male 5_male; do
    for k in 1 2; do echo "$T2" | "$GAMA" tts -p a$k.param "$PWD/det/$v" a$k.wav > /dev/null 2>&1; done
    printf '%s: repeat %s' $v "$(cmp -s a1.wav a2.wav && echo same || echo DIFFERENT)"
    if [ "$GAMA2" != "-" ]; then
        echo "$T2" | "$GAMA2" tts -p b.param "$PWD/det/$v" b.wav > /dev/null 2>&1
        printf ', other build: params %s, wav %s' \
            "$(cmp -s a1.param b.param && echo identical || echo different)" \
            "$(cmp -s a1.wav b.wav && echo identical || echo different)"
    fi
    echo
done

echo "== 8. Speed, about 100 s of speech, best of 3"
L=""; for i in 1 2 3 4 5 6 7 8 9 10 11 12; do L="$L$T2 "; done
for v in 0_male 2_male 3_male 4_male 5_male; do
    best=999999
    for k in 1 2 3; do
        s=$(date +%s%N); echo "$L" | "$GAMA" tts "$V/$v" long.wav > /dev/null 2>&1; e=$(date +%s%N)
        t=$(( (e - s) / 1000000 )); [ $t -lt $best ] && best=$t
    done
    "$PY" -I -c "import wave; w = wave.open('long.wav'); d = w.getnframes() / w.getframerate(); print('$v: %.1f s of audio in $best ms, x%.0f real time' % (d, d * 1000 / $best))"
done
s=$(date +%s%N); echo "Hi." | "$GAMA" tts "$V/0_male" > /dev/null 2>&1; e=$(date +%s%N)
echo "a run without audio output (load + parse only): $(( (e - s) / 1000000 )) ms"
