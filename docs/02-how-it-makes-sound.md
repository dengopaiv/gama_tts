# 2. How it makes sound

This chapter follows one sentence from text to samples. Each stage names the
file that does the work. Paths are under `gama_tts/src/` unless stated
otherwise. The default voice used by the Speech Dispatcher module is
`english/5_male` (model 5). The classic Gnuspeech voice is `english/0_male`
(model 0). The two differ only in the last stage, the tube, and in the data
that drives it.

## Overview

```
text (UTF-8, English)
  │ 1. text parser            text_parser/english/EnglishTextParser.cpp
  │    clean up, expand numbers and abbreviations, look up the dictionary,
  │    letter-to-sound for unknown words, stress, feet, tone groups
  ▼
phonetic string     /c // /0 # /w dh_uh /w /_k_w_i_k ... /l /*d_o_g # // /c
  │ 2. phonetic string parser vtm_control_model/PhoneticStringParser.cpp
  │    postures (phones), feet, tone groups, rhythm; rewrite rules (rewrite.txt)
  ▼
posture sequence with timing
  │ 3. Monet rule engine      vtm_control_model/EventList.cpp, Rule.cpp, Model.cpp
  │    match rules over 2–4 postures, apply parameter transitions
  │    (artic.xml), evaluate timing equations
  ▼
events → 16 parameter tracks, one value per control period (4 ms)
  │ 4. intonation              EventList.cpp, IntonationRhythm.cpp, DriftGenerator.cpp
  │    micro-intonation + macro-intonation (cubic curve) + drift + mean pitch
  ▼
parameter frames            (the file written by  gama_tts tts -p params.txt)
  │ 5. controller              vtm_control_model/Controller.cpp:278
  │    linear interpolation of every parameter to every tube sample
  ▼
per-sample parameters
  │ 6. vocal tract model       vtm/VocalTractModel0.h … VocalTractModel5.h
  │    glottal pulse + noise → waveguide tube (oral + nasal) → radiation
  ▼
samples at the tube's own rate (20,034 Hz for model 0 male, 60,411 Hz for model 5 male)
  │ 7. sample-rate converter   vtm/SampleRateConverter.h
  ▼
48,000 Hz float → scaled to peak → 16-bit WAV   WAVEFileWriter.cpp
```

## 1. From text to a phonetic string

`EnglishTextParser::parse()` (`text_parser/english/EnglishTextParser.cpp:1165`)
runs in three passes. This is Gnuspeech's NeXT `server.monet` parser, ported
to C++.

1. `conditionInput` turns non-printable characters into spaces and joins words
   hyphenated across a line break.
2. `stripPunctuation` decides what each punctuation mark means: a sentence
   end, a medial pause, part of a number, or nothing. It also deletes ellipses,
   converts dashes, and recognises telephone numbers.
3. `finalConversion` handles one word at a time:
   - abbreviations (`abbreviations.txt`, `abbreviations_with_number.txt`),
     special acronyms (`special_acronyms.txt`), and all-capital words spelled
     out letter by letter;
   - `lookupWord` tries sources in order (`EnglishTextParser.cpp:1225`): the
     **number parser** (`NumberParser.cpp`, years, money, ordinals,
     fractions, percentages, times), then up to three dictionaries
     (`main_dictionary.txt`), and then **letter-to-sound** rules
     (`LetterToSound.cpp`, using `suffix_list.txt`). Letter-to-sound always
     returns something;
   - `ApplyStress.cpp` and `Syllabify.cpp` place stress and syllable marks on
     words built by rule;
   - the parser then marks feet, the tonic (most prominent) foot, tone groups
     and chunks.

`safetyCheck` finally caps the number of feet and phones per chunk.

The result uses Gnuspeech's own notation:

| Mark | Meaning |
|---|---|
| `/c` | chunk boundary (the unit synthesised in one go) |
| `//` | tone-group boundary |
| `/0` … `/4` | tone-group type: statement, exclamation, question, continuation, semicolon |
| `#` | utterance boundary (silence) |
| `^` | medial pause |
| `/w` | word begins |
| `/l` | last word of the tone group |
| `/_` | a new foot (stressed syllable) begins |
| `/*` | the tonic foot begins |
| `.` | syllable boundary |
| `_` | separates phones: `k_w_i_k` is k, w, i, k |

For "The quick brown fox jumps over the lazy dog." the result is (measured,
[chapter A](07-measurements.md)):

```
/c // /0 # /w dh_uh /w /_k_w_i_k /w /_b_r_ah_uu_n /w /_f_o_k_s /w /_j_a_m_p_s
/w /_uh_uu.v_uh_r /w dh_uh /w /_l_e_i.z_i /w /l /*d_o_g # // /c
```

Numbers: "In 1984, it cost $3.25." becomes *nineteen eighty-four … three
dollars and twenty-five cents*. Some cases are weak, the same as in
Gnuspeech: "3/4/2025" is read "three slash four slash two zero two five", and
"kg" is spelled "k g".

Other inputs: `gama_tts pho` takes a phonetic string directly. With
`phonetic_string_format = mbrola`, `Pho1Parser.cpp` reads MBROLA `.pho` lines
(phoneme, duration, pitch points), mapped through
`pho1_parser/phoneme_map-festival_us1.txt`. `ExternalTextParser.cpp` can hand
the text to an outside program that returns `.pho`.

## 2. From a phonetic string to postures

`PhoneticStringParser.cpp` reads the string. Every phone name is a
**posture**, a target shape of the vocal tract defined in `artic.xml`
(65 postures in English: vowels such as `aa`, consonants, and the silence
`^`/`#`). For each posture the parser:

- records the word, foot, tonic and tone-group membership;
- applies the **rewrite rules** in `phonetic_string_parser/rewrite.txt`. These
  insert or replace postures between neighbours, for example `t v > insert q`,
  which puts a glottal-stop-like closure `q` between t and v;
- sets the posture's **tempo** from the foot rhythm in
  `intonation_rhythm/rhythm.txt`. For a foot of *n* postures the tempo rises
  by `(19.36 n − 117.7) / 180` if the foot is marked (tonic) and by
  `(2.08 n − 18.5) / 140` otherwise, clamped to 0.2–2.0, then multiplied by
  the user's global tempo.

## 3. The Monet rule engine: from postures to parameter tracks

This is the heart of Gnuspeech's approach, and GamaTTS keeps it as it was.

Every posture in `artic.xml` has:

- a **target** for each of the 16 control parameters (below);
- **symbol targets:** `transition`, `qssa` and `qssb` (the quasi-steady-state
  parts), used for timing, with marked versions of each for postures in the tonic
  foot. `duration` and `markedDuration` are in the file too, but nothing reads
  them (`Posture.h:41,46`, `Pho1Parser.cpp:185`).

For `aa`, for example, the targets are glottal volume 60 dB, aspiration 0,
r1…r8 = 0.8, 0.65, 0.84, 1.15, 1.31, 1.59, 1.59, 2.61 cm, velum 0.1 cm, and
the unused `duration` target is 84 (122 when marked).

A **rule** (`Rule.cpp`) has two to four boolean expressions over posture
categories, for example `silence`, `m`, `(vocoid or glide)`. `EventList`
walks along the posture list. At each position, `Model::findFirstMatchingRule`
(`Model.cpp:687`) takes the **first** rule in list order whose expressions
match the next 2, 3 or 4 postures. So a rule covers a diphone, triphone or
tetraphone, and rule order sets priority. The English database has 47 rules: 16 of two postures, 31 of three, none of four.

For each of the 16 parameters, the rule names a **transition**: a list of
points, each with a *value* given as a percentage of the way from one
posture's target to the next, and a *time* given by an **equation**. The
equations use the symbols above, for example `QssbOne` or `EndTrans`. A
transition can also carry slopes. One example is `newDiphoneDefault`: 0 %,
1.9 %, 8.3 %, 85 %, 96.6 % and 100 %, at six equation-defined times. A
**special transition** adds an offset on top of the normal track, used for
bursts and frication events. The rule also sets the rule's duration and its
"beat" (the rhythmic anchor) through symbol equations.

`EventList` turns all this into **events**: time-stamped parameter values. It
then steps through time one **control period** (4 ms by default,
`control_period` in `vtm_control_model.txt`; 1–4 ms allowed). At each period
it interpolates every parameter between its events, which gives one frame of
16 numbers.

The 16 parameters (`artic.xml`, the same in GnuspeechSA):

| # | Name | Unit | What it controls |
|---|---|---|---|
| 0 | `microInt` | semitones | micro-intonation, small pitch movements caused by the consonants |
| 1 | `glotVol` | dB (0–60) | voicing amplitude |
| 2 | `aspVol` | dB | aspiration (breath noise at the glottis) |
| 3 | `fricVol` | dB | frication amplitude |
| 4 | `fricPos` | section index | where in the tube frication noise is injected |
| 5 | `fricCF` | Hz | frication noise centre frequency |
| 6 | `fricBW` | Hz | frication noise bandwidth |
| 7–14 | `r1` … `r8` | cm | radius of the eight tube regions, glottis (r1) to lips (r8) |
| 15 | `velum` | cm | radius of the opening into the nasal cavity |

## 4. Intonation

Parameter 0 is turned into the final pitch in `EventList.cpp:990–1000`:

```
pitch = microInt            (if micro_intonation = 1)
      + drift               (if intonation_drift = 1; DriftGenerator, low-passed noise)
      + macro intonation    (if macro_intonation = 1; cubic or linear curve over time)
      + mean pitch          (pitch_offset + the variant's reference_glottal_pitch)
```

**Macro intonation** follows Hill's model. Each tone group gets pitch points
on the feet, with a pretonic slope and a tonic movement. Their values come
from `intonation_rhythm/intonation.txt` and the five
`tone_group_param-*.txt` files, so a statement falls, a question rises, and
so on. With `random_intonation = 1`, the slopes and perturbations get random
components, so no two renderings are the same. With `smooth_intonation = 1`,
a cubic curve passes through the points. Before the first point, pitch runs
in a straight line from `initial_pitch` (−20 semitones by default).
Semitone 0 is middle C: `frequency = 220 · 2^((pitch + 3)/12)` Hz
(`vtm/VTMUtil.h`).

Defaults (`0_male/vtm_control_model.txt`): every flag on, drift ±4
semitones low-passed at 4 Hz, pitch offset −4, male reference pitch −12. The
male voice therefore centres on about 220 · 2^((−16 + 3)/12) ≈ 104 Hz.

## 5. From frames to samples: the controller

The tube runs at its own internal sample rate, which comes from the physics
(below). `Controller::synthesize` (`Controller.cpp:278`) computes
`controlSteps = rint(tube rate / control rate)`. For each control period, it
then steps every parameter linearly from this frame's value to the next one,
calling `setAllParameters()` and `execSynthesisStep()` once per tube sample.
So the tube sees smoothly changing radii, not 4 ms steps.

## 6. The vocal tract model (model 0, the Gnuspeech tube)

All six models are described in [chapter 3](03-vocal-tract-models.md). This
section explains the classic one, `VocalTractModel0` (`vtm/VocalTractModel0.h`),
which is a C++ port of Leonard Manzara's TRM ("tube resonance model").

### The sources

Per tube sample (`execSynthesisStep`, `VocalTractModel0.h:396`):

1. **Glottal pulse.** `WavetableGlottalSource` holds one period of the pulse
   in a 512-entry table. The opening phase is `3x² − 2x³` over `tp` = 40 % of
   the period, the closing phase is `1 − x²` over `tn` = 24 %, and the rest is
   closed (zero). The code can shorten the closing time as voicing gets louder
   (between `tnMax` and `tnMin`), but every shipped voice sets the two equal. The table is read with linear interpolation and 2×
   oversampling through an FIR filter, at the frequency given by pitch.
2. **Noise.** A deterministic generator (`NoiseSource.h`):
   `seed = frac(seed · 377)`, starting at 0.7892347, minus 0.5. It is
   smoothed by a two-point sum (`NoiseFilter.h`).
3. **Breathiness.** The pulse is mixed with noise modulated by the pulse:
   `pulse · (1 − b) + noise · pulse · b`, with b = 0.5 % for the male voice.
4. **Aspiration.** The noise is cross-mixed between pure and pulse-modulated,
   depending on voicing amplitude (`mix_offset` = 48 dB), and added at the
   glottis at `aspVol`.
5. **Frication.** The same noise, band-passed (`BandpassFilter.h`, a
   2nd-order resonator at `fricCF`/`fricBW`), is injected **inside** the tube
   at `fricPos`. The value is split between the two neighbouring sections
   (`setFricationTaps`).

Volumes in dB (0–60) become amplitudes as `10^((dB − 60)/20)`.

### The tube

The oral tract is **8 regions** of fixed proportions, divided into **10
sections**. The nasal tract is 6 sections with fixed radii (1.35, 1.96,
1.91, 1.3, 0.73 cm for the male voice). They meet at a **three-way junction**
in the middle of region 4, whose third branch is the velum.

Each section is a delay line carrying two travelling pressure waves, one
toward the lips (`TOP`) and one back toward the glottis (`BOTTOM`). Between
sections of radius r₁ and r₂ the wave partly reflects. The
**Kelly–Lochbaum** scattering coefficient is

```
k = (r₁² − r₂²) / (r₁² + r₂²)        (VocalTractModel0.h:484)
```

and at every junction, every sample:

```
Δ          = k · (top_i − bottom_{i+1})
top_{i+1}  = (top_i + Δ) · damping
bottom_i   = (bottom_{i+1} + Δ) · damping
```

`damping = 1 − loss_factor/100` (0.8 % per step in models 0–3; model 4 damps only at region junctions and taps) models wall and viscous
losses. The three-way velum junction splits the pressure by area
(`alpha_` coefficients).

**Why the internal rate is what it is.** A wave must cross one section per
sample. With 10 sections, a tube of length L and the speed of sound c, the
rate is `c · 10 / L`. At 32 °C, c = 331.4 + 0.6 · 32 = 350.6 m/s; with
L = 17.5 cm that gives **20,034 Hz** (measured in the log). A female voice
(15 cm) runs at 23,373 Hz. Shorter tubes mean higher rates, and so higher
formants.

**The ends.**

- At the **glottis**, the backward wave is reflected into the tube almost
  unchanged and the source is added.
- At the **lips**, part of the wave reflects back through a one-pole low-pass
  (`ReflectionFilter.h`) and the rest leaves through a matching one-pole
  high-pass (`RadiationFilter.h`). Both use the mouth coefficient of 5,000 Hz
  scaled to the Nyquist frequency. The mouth aperture radius (3.05 cm)
  defines the last scattering coefficient.
- The **nose** works the same way.
- The **throat** (`Throat.h`): a low-passed copy of the glottal pulse
  (1,500 Hz, volume 6 on the 0–60 scale, so a gain of −54 dB) is added to the output, imitating sound radiated through
  the neck.

The output sample is the mouth output plus the nose output plus the throat.

## 7. Output

`SampleRateConverter.h` converts from the tube rate to the output rate (48 kHz
by default) with a Kaiser-windowed sinc interpolator (13 zero crossings,
β = 5.658, 8-bit phase table). This is Gnuspeech's converter.
`Controller::writeOutputToFile` (`Controller.cpp:320`) scales the whole
utterance to a fixed peak (`calculateOutputScale`) and writes a mono 16-bit
WAV (`WAVEFileWriter.cpp`).

So every file is normalised to the same peak. Loudness does not depend on
the text, but a quiet sentence and a loud one come out equally loud.

## What makes model 5 sound different

The pipeline is the same. In stage 6, model 5 (`VocalTractModel5.h`) changes
the physics:

- **30 oral sections and 21 nasal sections**, at 60,411 Hz for the male voice
  (35 °C, 17.5 cm). Region boundaries fall on sections 3, 5, 9, 15, 21, 25 and
  27 (diagram at the top of the file). Frication can then sit at any point
  between sections 6 and 28, interpolated.
- **Flow instead of pressure, and a real radiation impedance.** Lips and
  nostrils end in `PoleZeroRadiationImpedance` (after Liljencrants 1985 and
  Laine 1992), `Zr = (ρc/A) · a(1 − z⁻¹)/(1 − b z⁻¹)`. Its constants are
  fitted to a piston in a spherical baffle (9 cm sphere, Chalker &
  Mackerras 1985). Every sample it is checked against the current lip radius
  r8, and recomputed when that has changed. The output is the time derivative (central difference) of the
  volume flow leaving mouth and nose, which approximates radiated pressure.
  The Python studies behind the fit are in `script/python3/impedance_at_mouth/`.
- **A Rosenberg-B pulse** (`RosenbergBGlottalSource.h`; Rosenberg 1971, though the header says 1970) is
  computed directly rather than read from a table. It is low-passed at 4 kHz
  (`glottal_lowpass_cutoff`).
- **Glottal loss that follows the pulse.** The reflection at the glottis loses
  between 0 % and 2 % (female voice: 2 % to 5 %) depending on how far the glottis is open at that
  instant, so the open phase damps the formants more than the closed phase,
  as in a real larynx.
- **Separate noise filters** for glottal noise (1st-order Butterworth,
  400 Hz) and frication noise (2nd-order Butterworth, 5.5 kHz). Breathiness
  is 5 % for the male voice and 15 % for the female.
- **No throat path.**

Details and the other models are in [chapter 3](03-vocal-tract-models.md).
