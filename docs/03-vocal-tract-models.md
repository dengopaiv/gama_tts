# 3. The vocal tract models

GamaTTS has six built-in tube models, chosen with `model = N` in a voice's
`vtm.txt`. `VocalTractModel::getInstance` (`gama_tts/src/vtm/VocalTractModel.cpp:40`)
maps the number to a class. Upstream's own list is
`gama_tts/doc/vocal_tract_models.txt`. This chapter adds what was measured
and read.

| Model | Class | Oral / nasal sections | Section delay | Precision | Voice dirs | Internal rate, male (measured) |
|---|---|---|---|---|---|---|
| 0 | `VocalTractModel0<double>` | 10 / 6 | 1 | double | `0_*` | 20,034 Hz |
| 1 | `VocalTractModel0<float>` | 10 / 6 | 1 | float | `1_male` | 20,034 Hz |
| 2 | `VocalTractModel2<double, 1>` | 10 / 6 | 1 | double | `2_male` | 20,034 Hz |
| 3 | `VocalTractModel2<double, 3>` | 10 / 6 | 3 samples | double | `3_male` | 60,102 Hz |
| 4 | `VocalTractModel4<double, 1>` | 30 / 18 | 1 | double | `4_male` | 60,102 Hz |
| 5 | `VocalTractModel5<double, 1>` | 30 / 21 | 1 | double | `5_*` | 60,411 Hz (35 °C) |
| 2000 | plugin, loaded from `dll_path` | — | — | — | — | only with `GAMATTS_ENABLE_VTM_PLUGINS=ON` |

All models take the same 16 parameters (glottal pitch and volume, aspiration,
four frication parameters, r1–r8, velum). Voices `1_male` to `4_male` borrow
everything except `vtm.txt` from `0_male`, so models 0–4 share one rule
database. Model 5 has its own (`5_male/artic.xml`).

## Model 0 and 1: the Gnuspeech tube

This is **Leonard Manzara's TRM** as ported in GnuspeechSA, with these
changes since 0.1.5 (from `git log`, each checked in the diff):

| Change | Commit | Effect on sound |
|---|---|---|
| Minimum radius 0.001 → 0.01 cm ("probably was considering m, not cm") | `6423352` | Full closures (stops) leak slightly more. |
| The internal rate is no longer rounded to a whole multiple of the control rate | `cfddcb4` (interpolation moved to the Controller) | GnuspeechSA used 20,000 Hz and silently lengthened the tube to 17.53 cm. GamaTTS uses the exact 20,034 Hz and steps `rint(20034/250) = 80` samples per frame, so each 4 ms frame lasts 3.993 ms: speech is 0.17 % faster. Measured: output length ratio 0.99832 (chapter A). |
| Per-sample linear interpolation moved from the tube into `Controller::synthesize` | `cfddcb4` | None intended. |
| The glottal source was replaced by Rosenberg-B, then restored for models 0, 2, 4 | `a4618e1`, `6d0d1ef` | None: model 0 uses the original wavetable again. |
| Output rate 48 kHz by default (was 44.1 or 22.05) | `vtm.txt` | None audible; a different resampling ratio. |

Model 1 is the same code in single precision. Measured against model 0 on the
same parameter file, it correlates 0.99942 at a best alignment of one sample,
an SNR of 29.3 dB (chapter A). That is close, but not the same samples:
float rounding builds up over a sentence, most likely in the glottal phase
(inferred).

## Model 2: model 0 rewritten for clarity

The same algorithm, with sections and junctions as small structs
(`Section`, `Junction2`, `Junction3`) and the propagation loop written out.
Measured: **bit-identical** to model 0 on the same parameter file (chapter A).
This makes model 2 the easiest place to read the classic tube.

## Model 3: three samples per section

Model 2 with `SectionDelay = 3`: each section delays the wave three samples
instead of one, so the internal rate triples (60,102 Hz). The tube geometry
is the same. What changes is everything designed per sample: the one-pole lip
and nose filters and the noise filter now run at three times the rate, so
their responses differ. Upstream says of the noise filter that it "has not been
adapted for SectionDelay > 1" (`VocalTractModel2.h:35-36`), and the lip and nose
coefficients are recomputed from the new Nyquist. Neither was measured per filter.
Measured on the same parameter file: correlation 0.973 against model 0
(SNR 12.8 dB), and 0.900 against GnuspeechSA, where model 0 gets 0.918.

## Model 4: thirty sections

Model 2 with 30 oral sections, grouped into the same 8 regions as 3, 2, 4, 6,
6, 4, 2, 3 sections. The radius of each region is still one parameter
(r1–r8). **It is a different staircase, not a finer one** (corrected 2026-11-02):
region shares are 10, 6.67, 13.33, 20, 20, 13.33, 6.67, 10 % against model 0's
10, 10, 10, 20, 20, 10, 10, 10 %, and the new set is exactly the Distinctive
Region Model's lengths, so the same radii give a different tract. The nasal
tract has 18 sections, 6 regions of 3 (`VocalTractModel4.h:20-24,115-135,202`),
the same 10.5 cm for a 17.5 cm tract. Speed: about half of model 0 (chapter A).

## Model 5: flow, radiation impedance, and a longer nose

`VocalTractModel5.h` (797 lines) is the model the `5_*` voices use. They are the
default only by convention (`INSTALL.txt`, the Speech Dispatcher config): `model`
is a required key, and the code has no default. It
is built on model 4. Each item below was checked in the source:

**Geometry.**

- 30 oral sections in 8 regions, as in model 4.
- The velum junction sits between S12 and S13, the middle of region 4.
- The nasal tract has 21 sections in 7 regions of 3. The first region's
  radius is the velum. The others are fixed per voice
  (`nasal_radius_2` … `_7` in `variant/*.txt`: 1.35, 1.83, 1.94, 1.72, 1.3,
  0.73 cm for male), times `global_nasal_radius_coef`.
- Each region's radius is multiplied by `radius_N_coef` and
  `global_radius_coef`. The female voice uses 0.86, which makes a smaller
  tract all round rather than just a shorter one.

**Junctions.** `Junction2` uses `(r₀² − r₁²)/(r₀² + r₁²)` and `Junction3`
splits by area, but the update has a different form from models 0–4
(`VocalTractModel5.h:263-272,296-307` against `VocalTractModel4.h:269-277,306-321`).
Upstream's model list (`gama_tts/doc/vocal_tract_models.txt`) says model 5 "uses
flow equations". **Settled by algebra, 2026-11-02:** with net flow = top − bottom,
`delta = k(top + bottom)` conserves flow by construction and gives pressure
continuity for this k, and the three-way coefficients sum to −1. Model 0's waves
are pressures, so its junctions do the reverse. Both satisfy both conditions.

**Glottis.**

- `RosenbergBGlottalSource`: rise `x²(3 − 2x)` over `tp`, fall `1 − x²` over
  `tn`, then closed. It is computed analytically at the tube rate, so there
  is no wavetable or FIR. The fall time is updated once per period from the
  voicing amplitude (`setup` → `nextT2_`). In the shipped voices this does
  nothing: every variant has `tn_min` = `tn_max`, so `setup` returns at once.
- A 1st-order Butterworth low-pass at `glottal_lowpass_cutoff` (4 kHz) on the
  pulse.
- **Glottal loss** varies with the pulse: the backward wave is reflected with
  factor `1 − A · loss`, where `loss` moves from `min_glottal_loss` (0 %)
  with the glottis closed to `max_glottal_loss` (2 %) with it fully open (the
  female voice has 2 % to 5 %), and
  A is the voicing amplitude.

**Noise.**

- One generator, filtered twice: glottal noise through a 1st-order
  Butterworth at 400 Hz (for breathiness), and frication noise through a
  2nd-order Butterworth at 5.5 kHz.
- Frication noise is modulated by the noisy pulse when voicing is present
  (cross-mix, `mix_offset` 48 dB), then band-passed at `fricCF`/`fricBW`.
- Frication is injected at `fricPos` mapped linearly onto S6–S28 and split
  between two neighbouring sections. In model 0 it is injected only in
  sections 3 to 10 of 10.

**Ends.**

- Lips and nostrils end in `PoleZeroRadiationImpedance`. The formula, from the
  file's header, is `Zr = (ρc/A) · a(1 − z⁻¹)/(1 − b z⁻¹)` (Liljencrants 1985,
  Laine 1992).
- a and b are fitted to a circular piston in a spherical baffle (radius 9 cm,
  c = 352.4 m/s; Chalker & Mackerras 1985; Morse & Ingard 1968), with
  `Zr = 1` at fs/2 and Re(Zr) = 0.5 at a transition frequency of
  `62.3371/r + 320.204` Hz, with r in metres.
- Below a lip radius of 0.5 cm, a alone is multiplied by 40391.2·r², with b kept
  (`PoleZeroRadiationImpedance.h:161-165`).
- It needs at least 50 kHz internally (`GS_VTM_POLE_ZERO_RAD_IMPED_MIN_SAMPLE_RATE`),
  which is why model 5 cannot run at the 20 kHz of a 10-section tube.
- The impedance gives a transmitted flow and a reflected wave at the same
  time (`process(in, outT, outR)`). The reflected part is damped by
  `loss_factor`: 0.4 % in every section for model 5. That is half of model 0's
  0.8 % per step but not in total, since model 0 damps at 9 steps: one way through
  the mouth, about 0.890 for model 5 against 0.930 (computed 2026-11-02).
- The Python scripts in `script/python3/impedance_at_mouth/` compare this
  approximation with Chalker's, Flanagan's, Laine's, the piston's and the
  spherical-baffle models.

**Output.**

- Mouth flow plus nose flow goes through the sample-rate converter. It is
  then differentiated with a central difference
  (`y = x[n] − x[n−2]`, `DifferenceFilter.h`) and multiplied by the output
  rate, because radiated pressure is proportional to the derivative of
  the flow.
- In the interactive editor the signal is divided by f0 first, to keep the
  level steady across pitch.
- `bypass = 1` outputs the glottal source alone.

**No throat path.** Model 5 removed the throat emission (`git log`:
"vtm5: Remove throat emission", 2017-05-04).

**Configuration.** Model 5 reads more keys than model 0. All are in
`5_male/vtm.txt` and `5_male/variant/*.txt`; the key-value reading is in
`VocalTractModel5.h:380–430`.

## Speed

Measured on about 100 s of speech (chapter A), MinGW-w64 GCC 16.2, `-O3`, no
`-march=native`, one core:

| Model | Real-time factor |
|---|---|
| 0 | ×118 |
| 2 | ×117 |
| 3 | ×61 |
| 4 | ×58 |
| 5 | ×65 |

The cost follows the internal sample rate: models 3–5 run three times as many
tube steps as model 0. Model 5 is slightly faster than model 4 despite more
nasal sections (21 against 18), possibly because it has no throat filter and a simpler glottal
source (inferred, not profiled).

## Plugins

`VocalTractModelPlugin.{h,cpp}` (BSD-3-Clause) loads a tube from a shared
library when `model = 2000`. The library exports two `extern "C"` functions,
but they create and destroy a C++ `VocalTractModel` object, so a plugin must
be built with a compatible C++ compiler and standard library. The loader uses
POSIX `dlopen`, so plugins do not work on Windows as written. It is off by
default (`GAMATTS_ENABLE_VTM_PLUGINS`). History: added `2fa051c`, removed
`678a5aa`/`cbe28fc`, re-added `2427bdb` (2023-07-29).
