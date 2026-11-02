# 11. Using it: the add-on, the GUI and the API

The manual, for someone who wants to use what [chapter 10](10-model5-api-gui-addon.md) built. Chapter 10 says how it was
made and checked; this one says what it does. Written 2026-11-02.

**Status: add-on 0.1.0 and the GUI have been tested from outside, and neither has yet been used with NVDA.** Expect to find things.

## What you need

- **The add-on:** 64-bit NVDA, 2026.1 or later, on Windows. The file is `nvda-addon/gamatts-0.1.0.nvda-addon`, which `python -I nvda-addon/package.py`
  builds. No built add-on is in the repository.
- **The GUI:** 64-bit Windows. Built as in chapter 10, it is `build-gui/Release/gama_gui.exe`. It finds `data` by walking up from its own
  folder, so it runs from the build tree as it is. From anywhere else, give it `--data <folder holding voice/english>`.

## The add-on

Install the file as any NVDA add-on: press Enter on it, and restart NVDA. It installs **beside** the Gnuspeech add-on, not over it, under its own name `gamatts`. Then choose
**GamaTTS (articulatory)** in NVDA's synthesizer dialog (NVDA+Ctrl+S).

### Settings

In NVDA's voice settings (NVDA+Ctrl+V), and on the settings ring (NVDA+Ctrl+arrows):

| Setting | Choices | Default | What it does |
|---|---|---|---|
| Voice | Male, Female, Large child, Small child, Baby | Male | Model 5's five voices |
| Rate | 0 to 100 | 50 | The engine's tempo: below |
| Pitch | 0 to 100 | 50 | An octave down at 0, the voice's own at 50, an octave up at 100 |
| Volume | 0 to 100 | 100 | A gain on the finished speech. A voice change does not reset it |
| Vary intonation | On, off | On | Random variation in each sentence's melody, as GamaTTS ships. Off, the same text always sounds the same |
| Loudness | Steady throughout, Even per message, The engine's own peaks | Steady throughout | Below |
| Trim silence around each message | On, off | On | Below |

**Rate** goes to the engine's tempo, in equal ratios in each half: 0.5 at rate 0, 1.0 at 50 and 4.0 at 100. On one 15-second text, tempo 3 was 2.85 times faster and tempo 4 was 3.67 times faster than tempo 1. Whether speech can be followed at the top has not been judged. [Chapter 10](10-model5-api-gui-addon.md) says so.

**Loudness:**

- *Steady throughout:* every message at one loudness, and inside it every voiced moment at that loudness too, whatever its stress, pitch or vowel.
- *Even per message:* every message at one loudness, with louder and softer syllables inside it as the engine makes them.
- *The engine's own peaks:* each message scaled to its own peak, as the engine was made. Loudness then varies from message to message, and the higher voices are up to 7 dB louder than the male.

**Trimming** keeps only the outer edges short. It keeps 10 ms before the first sound. After the last it keeps 150 ms if the message ends in `. ! ? : ;`, 100 ms after a comma, and 30 ms otherwise, or for spelling. Between the sentences of one message, the engine's own pauses stay. These values were carried over from the Gnuspeech add-on and have not been tuned by ear for this voice.

### What it does with text

- Typographic punctuation becomes ASCII. Accents are dropped (`cafe` for `café`). Anything else outside ASCII becomes a space: **it reads English only**, and other scripts are skipped.
- Text is split at sentence ends, and any piece longer than 200 characters is split again, at a space if it has one. Ctrl and other interruptions are noticed between pieces.
- A long unbroken run, such as a base64 image or a hash, is broken up before the engine sees it, after 100 characters or sooner. It will be read as nonsense, which is what it is, and it cannot crash the engine.
- Spelling sends letters as capitals, since the engine reads a lone "a" as the article. Capital pitch, breaks and index marks all work, in NVDA's own way: a mark is reported when the audio before it has played.

**Numbers and words:** the dictionary and rules for turning text into sound are the same as Gnuspeech's, so the same words come out wrong. Numeric dates and unit abbreviations are read badly ("three slash four slash two zero two five", "k g").

### Not done

Translations (the strings are marked, and there is no `locale/`), and word-level index marks. Marks are exact at NVDA's own marks and at sentence ends.

## The GUI

A window in which you type text and hear it, or save it, with every setting of the voice to hand. Standard controls, no custom drawing, and all of it works from the keyboard. Every field has a name, a value and a description for a screen reader. The status bar reads back the focused field's help, and every result.

### Going through the window

From top to bottom:

| Control | What it is |
|---|---|
| Text to speak | Multi-line edit |
| Read as | Text, or Phonetic string, which is spoken as written, in Gnuspeech's notation |
| Voice | Loads that voice's own values into the parameters kept in its file. Every other parameter keeps its value |
| Speak, Stop, Save as WAV..., Show phonetic string, Use phonetic string as text | The buttons |
| Parameters for | Which category shows below. Only the chosen one's fields are in the Tab order |
| Reset all parameters | Everything back to the data files' value for the current voice |
| *the category's group* | Its fields |
| Phonetic string | Read-only: what the text parser made of the text |

### Keys

| Key | Action |
|---|---|
| Ctrl+Enter | Speak the selection, or all the text if nothing is selected |
| Esc | Stop |
| Ctrl+S | Save the speech as a WAV file: 16-bit, mono |
| Ctrl+T | Save the parameter track: one line of 16 values per control period |
| Ctrl+P | Show the phonetic string, and move there |
| Ctrl+U | Replace the text with its phonetic string, and read it as one |
| Ctrl+R | Reset every parameter |
| Ctrl+O, Ctrl+Shift+S | Open, save a voice preset |
| Ctrl+1 to Ctrl+7 | Show a category and move to its first field: Speech, Intonation, Glottal source, Vocal tract, Nose, Noise, Output |
| Up, Down | One step in a number. Page Up and Page Down: ten steps |
| Alt+T, A, V, M, N | Move to Text, Read as, Voice, Parameters for, Phonetic string |
| Alt+K, O, W, I, U, R | The buttons: Speak, Stop, Save as WAV, Show phonetic string, Use phonetic string as text, Reset |
| F1 | The key list |

The menus are on F, S, P and H (File, Speech, Parameters, Help).

### Typing a number

You can type a value, or use the arrows, and it takes effect when you leave the field. A value that cannot stand is not silently changed. The status bar says what happened, and a beep marks it:

- **Out of the field's range:** "Pitch offset (semitones): 99 is outside -24.0 to 24.0; set to 24.0."
- **Not a number:** "Pitch offset (semitones): abc is not a number. It stays at -4.0."
- **Breaks a limit shared with another field:** "Pulse fall time, minimum (%): 30 is refused. The pulse fall time minimum may not pass the maximum. It stays at 24.0."

**The limits that fields share:**

- Pulse fall time minimum may not pass the maximum. To raise both, raise the maximum first.
- Pulse rise time and fall time maximum together may not pass 100.
- Tract length, its offset and the temperature must keep the tube's internal rate from 50 kHz to 300 kHz. In practice, a tract much over 20 cm is refused.

### Saving

Save as WAV and Save parameter track render the text again with the settings as they are now, so what you save is what Speak would play. A file is written to `<name>.part` and renamed when complete, so a failure leaves nothing half-written.

With Loudness on The engine's own peaks, trimming off, Intonation drift and Random intonation off, and tempo up to 3.5, a saved WAV is exactly what upstream's own `gama_tts` writes for that line. That is checked.

### Voice presets

Plain text, `.gamapreset`, written like the engine's own data files: `key = value` per line, `#` for comments.

- The first lines are `voice` (`male`, `female`, `large_child`, `small_child`, `baby`), `volume_percent`, `trim`, `trim_lead_ms`, `trim_trail_ms`, `loudness` (`constant`, `message` or `peak`) and `loudness_target_db`.
- Then one line per parameter, by its key in the tables below.
- A key left out keeps its current value. An unknown line is skipped, and a value out of range is clamped. The status bar counts both, with a beep.
- The voice is applied first, so the preset's own values win over the voice file's. Values that share a limit may come in any order.

### The Output category's own fields

Besides the output rate, which is in the table below, these are not engine parameters:

| Field | Range | Default | What it does |
|---|---|---|---|
| Volume (%) | 0 to 100 | 100 | A gain on the finished speech |
| Loudness | As in the add-on | Steady throughout | |
| Loudness target (dB) | -40 to -10 | -22 | The A-weighted level of each utterance, unless Loudness is the engine's own peaks |
| Trim the silence at both ends | On, off | **Off** | Off here, on in the add-on |
| Silence kept before (ms) | 0 to 1000 | 10 | Used when trimming is on |
| Silence kept after (ms) | 0 to 1000 | 150 | Used when trimming is on |

## The parameters

Every value in model 5's data files that the engine reads and that reaches the sound: 49. Each was checked by changing it and comparing the output (chapter 9, section 7), and each has been run at both ends of its range (chapter 10). **Nobody has judged by ear what each one does at its limits.** The help text is what the GUI shows, and it was written from the source.

The ranges hold every shipped voice's value. Where the voices differ, the default says so. A value "kept in the voice's file" is reloaded on a change of voice: the variant files in `data/voice/english/5_male/variant/`. The table is made by `tools/param_table.py`.

### Speech

| Field | Key | Range | Default | What it does |
|---|---|---|---|---|
| Tempo | `tempo` | 0.10 to 10.00, step 0.05 | 1.00 | How fast the rules run: 1 is normal, 2 is twice as fast. |
| Pitch offset (semitones) | `pitch_offset` | -24.0 to 24.0, step 0.5 | -4.0 | Added to the voice's reference glottal pitch. |
| Initial pitch (semitones) | `initial_pitch` | -48.0 to 12.0, step 0.5 | -20.0 | Where the pitch starts, against the voice's own, before running to the first intonation point. |
| Control period | `control_period` | 1 ms, 2 ms, 3 ms, 4 ms | 4 ms | How often the rules give the tube new values. A shorter period costs more and is finer. |

### Intonation

| Field | Key | Range | Default | What it does |
|---|---|---|---|---|
| Micro intonation | `micro_intonation` | on or off | on | Small pitch movements made by individual sounds. |
| Macro intonation | `macro_intonation` | on or off | on | The rise and fall of pitch over each phrase. |
| Smooth intonation | `smooth_intonation` | on or off | on | Curves between the phrase's pitch points. Off, straight lines. |
| Intonation drift | `intonation_drift` | on or off | on | A slow random wander of the pitch. |
| Random intonation | `random_intonation` | on or off | on | Picks the phrase contours at random, so the same text varies from one utterance to the next. |
| Drift deviation (semitones) | `drift_deviation` | 0.0 to 10.0, step 0.1 | 4.0 | How far the drift may wander. |
| Drift speed (Hz) | `drift_lowpass_cutoff` | 1.0 to 20.0, step 0.1 | 4.0 | The low-pass cutoff of the drift: higher wanders faster. |
| Intonation range | `intonation_factor` | 0.00 to 2.00, step 0.05 | male 1.00; female 0.80; large child 0.50; small child 0.50; baby 0.50 | Scales the phrase's pitch movements: 1 as written, 0 flat. |

### Glottal source

| Field | Key | Range | Default | What it does |
|---|---|---|---|---|
| Glottal waveform | `waveform` | Pulse, Sine | Pulse | Pulse is the glottal pulse. Sine is a pure tone, for study. |
| Reference glottal pitch (semitones) | `reference_glottal_pitch` | -24.0 to 24.0, step 0.5 | male -12.0; female 0.0; large child 2.5; small child 5.0; baby 7.5 | The voice's own pitch. The pitch offset is added to it. |
| Pulse rise time (%) | `glottal_pulse_tp` | 5.0 to 70.0, step 0.5 | 40.0 | The rise of the glottal pulse, as a share of its period. Rise time and fall time maximum together may not pass 100. |
| Pulse fall time, minimum (%) | `glottal_pulse_tn_min` | 5.0 to 70.0, step 0.5 | male 24.0; female 32.0; large child 24.0; small child 24.0; baby 24.0 | The fall time moves between the minimum and the maximum with the voicing amplitude. The minimum may not pass the maximum. |
| Pulse fall time, maximum (%) | `glottal_pulse_tn_max` | 5.0 to 70.0, step 0.5 | male 24.0; female 32.0; large child 24.0; small child 24.0; baby 24.0 | The fall time moves between the minimum and the maximum with the voicing amplitude. Rise time and fall time maximum together may not pass 100. |
| Breathiness (%) | `breathiness` | 0.0 to 50.0, step 0.5 | male 5.0; female 15.0; large child 25.0; small child 30.0; baby 30.0 | Noise mixed into the glottal source. |
| Glottal loss, closed (%) | `min_glottal_loss` | 0.0 to 10.0, step 0.1 | male 0.0; female 2.0; large child 0.0; small child 0.0; baby 0.0 | Energy lost at the glottis while the pulse is low. |
| Glottal loss, open (%) | `max_glottal_loss` | 0.0 to 10.0, step 0.1 | male 2.0; female 5.0; large child 2.0; small child 2.0; baby 2.0 | Energy lost at the glottis at the top of the pulse. |
| Glottal low-pass cutoff (Hz) | `glottal_lowpass_cutoff` | 500 to 20000, step 100 | male 4000; female 3000; large child 3000; small child 3000; baby 3000 | Softens the glottal pulse. Lower is darker. |

### Vocal tract

| Field | Key | Range | Default | What it does |
|---|---|---|---|---|
| Tract length (cm) | `vocal_tract_length` | 5.0 to 20.0, step 0.1 | male 17.5; female 15.0; large child 12.5; small child 10.0; baby 7.5 | The length of the tube. Shorter sounds younger and higher. |
| Tract length offset (cm) | `vocal_tract_length_offset` | -3.0 to 3.0, step 0.1 | 0.0 | Added to the tract length of every voice. |
| Temperature (degrees C) | `temperature` | 25.0 to 40.0, step 0.5 | 35.0 | Sets the speed of sound in the tube. |
| Junction loss (%) | `loss_factor` | 0.00 to 5.00, step 0.05 | 0.40 | Energy lost at each junction of the tube. More loss gives wider, duller resonances. |
| Fixed mouth radiation | `constant_radius_mouth_impedance` | on or off | off | On, the lips radiate as if always at the radius below. Off, as the mouth opens and closes. |
| Fixed mouth radius (cm) | `mouth_impedance_radius` | 0.20 to 5.00, step 0.01 | male 2.00; female 1.71; large child 1.43; small child 1.14; baby 0.86 | Used only when Fixed mouth radiation is on. |
| Global radius coefficient | `global_radius_coef` | 0.20 to 2.00, step 0.01 | male 1.00; female 0.86; large child 0.71; small child 0.57; baby 0.43 | Scales every region's radius at once. |
| Region 1 radius coefficient | `radius_1_coef` | 0.20 to 2.00, step 0.05 | 1.00 | Scales the radius of region 1, at the glottis. |
| Region 2 radius coefficient | `radius_2_coef` | 0.20 to 2.00, step 0.05 | 1.00 | Scales the radius of region 2. |
| Region 3 radius coefficient | `radius_3_coef` | 0.20 to 2.00, step 0.05 | 1.00 | Scales the radius of region 3. |
| Region 4 radius coefficient | `radius_4_coef` | 0.20 to 2.00, step 0.05 | 1.00 | Scales the radius of region 4. |
| Region 5 radius coefficient | `radius_5_coef` | 0.20 to 2.00, step 0.05 | 1.00 | Scales the radius of region 5. |
| Region 6 radius coefficient | `radius_6_coef` | 0.20 to 2.00, step 0.05 | 1.00 | Scales the radius of region 6. |
| Region 7 radius coefficient | `radius_7_coef` | 0.20 to 2.00, step 0.05 | 1.00 | Scales the radius of region 7. |
| Region 8 radius coefficient | `radius_8_coef` | 0.20 to 2.00, step 0.05 | 1.00 | Scales the radius of region 8, at the lips. |

### Nose

| Field | Key | Range | Default | What it does |
|---|---|---|---|---|
| Global nose radius coefficient | `global_nasal_radius_coef` | 0.20 to 2.00, step 0.01 | male 1.00; female 0.86; large child 0.71; small child 0.57; baby 0.43 | Scales every nasal section's radius at once. |
| Nasal section 2 radius (cm) | `nasal_radius_2` | 0.01 to 3.00, step 0.01 | 1.35 | Section 1 is the velum, which the rules move. Section 2 is next to it. |
| Nasal section 3 radius (cm) | `nasal_radius_3` | 0.01 to 3.00, step 0.01 | 1.83 | The radius of nasal section 3. |
| Nasal section 4 radius (cm) | `nasal_radius_4` | 0.01 to 3.00, step 0.01 | 1.94 | The radius of nasal section 4. |
| Nasal section 5 radius (cm) | `nasal_radius_5` | 0.01 to 3.00, step 0.01 | 1.72 | The radius of nasal section 5. |
| Nasal section 6 radius (cm) | `nasal_radius_6` | 0.01 to 3.00, step 0.01 | 1.30 | The radius of nasal section 6. |
| Nasal section 7 radius (cm) | `nasal_radius_7` | 0.01 to 3.00, step 0.01 | 0.73 | Section 7 is at the nostrils. |

### Noise

| Field | Key | Range | Default | What it does |
|---|---|---|---|---|
| Pulse-modulated noise | `noise_modulation` | on or off | on | Modulates the noise sources with the glottal pulse. |
| Noise crossmix offset (dB) | `mix_offset` | 30.0 to 60.0, step 1 | 48.0 | The voicing level at which pulse-modulated noise crosses over to plain noise. |
| Glottal noise cutoff (Hz) | `glottal_noise_cutoff` | 50 to 10000, step 50 | 400 | The low-pass cutoff of the noise in the glottal source. |
| Frication noise cutoff (Hz) | `frication_noise_cutoff` | 500 to 20000, step 100 | 5500 | The low-pass cutoff of the noise behind s, f and sh. Higher is crisper. |
| Frication strength | `frication_factor` | 0.00 to 5.00, step 0.05 | 1.00 | Scales the frication noise. 1 is as the rules make it. |

### Output

| Field | Key | Range | Default | What it does |
|---|---|---|---|---|
| Output sample rate | `output_rate` | 22050 Hz, 44100 Hz, 48000 Hz | 48000 Hz | The rate of the finished speech. The tube runs at its own rate and is converted to this. |

**Left out, and why:** `notional_pitch`, `pretonic_pitch_range`, `pretonic_perturbation_range`, `tonic_pitch_range` and `tonic_perturbation_range` change nothing. `bypass` (the raw glottal waveform) and `log_parameters` are for debugging. `variant_name`, `model` and `phonetic_string_format` are chosen by the voice. The intonation tables and the posture and rule database are data, and are not parameters of this kind: editing them is the work of upstream's Qt editor.

## The C API

`api/gama_api.h` is the reference, with twelve numbered rules at its top. In outline:

```c
#include "gama_api.h"

char err[512];
gama_engine *e = gama_create("data", err, sizeof err);  /* the folder holding voice/english */
if (!e) { puts(err); return 1; }

gama_set_voice(e, 1);                  /* female */
gama_set_rate(e, 2.0);                 /* tempo */
gama_set_leveling(e, GAMA_LEVEL_CONSTANT, GAMA_LEVEL_DEFAULT_TARGET);
gama_set_trim(e, 10, 150);

if (gama_speak(e, "Hello world. ") == GAMA_OK) {
    int16_t block[2400];               /* mono, at gama_sample_rate(e) */
    size_t n;
    while ((n = gama_read(e, block, 2400)) > 0)
        play(block, n);
} else {
    puts(gama_last_error(e));          /* "*" alone has nothing to say */
}
gama_destroy(e);
```

- **One thread per handle.** Two handles may run on two threads; nothing is shared.
- **Settings apply from the next `gama_speak`.**
- **`gama_speak` makes a whole utterance before returning**, at about 69 times real time on the male voice and 27 on the baby. There is no streaming, so split long text yourself, as the driver does.
- **Paths are narrow strings.** On Windows, that is the ANSI code page. A path that cannot be written in it must go as its 8.3 short form: `_native_path` in the driver and `narrowPath` in the GUI both do this.
- **Parameters:** `gama_param_count`, `gama_param_describe`, `gama_get_param`, `gama_set_param`, `gama_param_default`, `gama_reset_params`. Build a UI from the table, as the GUI does.
- **Also:** `gama_text_to_phonetic`, `gama_speak_phonetic`, `gama_track`, `gama_set_deterministic`, `gama_spoken_tempo`.

From Python, declare every signature with `ctypes`: `_Lib` in `nvda-addon/addon/synthDrivers/gamatts.py` is the example. Undeclared, a handle is passed as a 32-bit int, and it crashes once the heap is above 4 GB.

The library holds the engine with a static runtime and needs only `KERNEL32.dll` on Windows. It needs `data/` beside it somewhere, with LF line endings. `nvda-addon/package.py` lists the part of it that model 5 needs.

## What is where

| Path | What it is |
|---|---|
| `nvda-addon/README.md` | The add-on's folder |
| `gui/README.md` | The GUI's folder |
| `tests/README.md` | What each test does and how to run it |
| `tools/README.md` | The scripts that make and measure things |
| `docs/10-model5-api-gui-addon.md` | How it was built and checked, and what is still open |
| `NOTICE.md` | Who made what, and on what terms |
