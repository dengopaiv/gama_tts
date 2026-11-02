/* gama_api.h -- a C interface to GamaTTS, model 5.
 *
 * Copyright 2026 dengopaiv. GPL-3.0-or-later, like the engine it wraps
 * (Gnuspeech: Copyright 1991-2002 David R. Hill, Leonard Manzara, Craig Schock;
 * GamaTTS: Copyright 2014-2025 Marcelo Y. Matuda). See NOTICE.md.
 * Adapted from gnuspeech_api.h in GnuspeechSA-NVDA.
 *
 * Plain C17. The implementation is C++17 over the engine, and this library
 * exports nothing else. Only model 5's voices are offered, by the author's
 * decision of 2026-11-02 (docs/10).
 *
 * THE RULES
 *  1. One engine per handle. Nothing is shared between handles, so two handles
 *     may be used from two threads. One handle is used from one thread at a time.
 *  2. Every function tolerates NULL pointers: int functions return GAMA_ERR_NULL,
 *     size and count functions return 0, pointer functions return NULL, and void
 *     functions do nothing.
 *  3. A value out of range is refused with GAMA_ERR_RANGE and changes nothing.
 *     That includes a value that breaks a limit shared with another parameter:
 *     gama_last_error() then says which (rule 10).
 *  4. Settings take effect from the next gama_speak(). An utterance already
 *     synthesised keeps the settings it was made with.
 *  5. Output is mono, signed 16-bit, at gama_sample_rate(). gama_speak()
 *     synthesises a whole utterance and gama_read() hands it out in pieces of any
 *     size. The samples do not depend on how the reads are chunked.
 *  6. Volume is a gain applied after synthesis. A voice change cannot reset it. At
 *     gain 1.0, in GAMA_LEVEL_PEAK, with trimming off (the defaults) and at a tempo
 *     up to 3.5, the samples are exactly those of upstream's gama_tts (tests/golden).
 *  7. Trimming, when on, only shortens the silence before the first and after the
 *     last sound of an utterance. It never changes a sample it keeps. The decision
 *     is made on the engine's output before levelling and the volume gain, so an
 *     utterance has the same length at every volume and in every levelling mode.
 *  8. The engine's parameters (gama_param_*) are held by the API and given to the
 *     engine before every utterance. Until one is set, each has the value its data
 *     file gives.
 *  9. Text is made safe before the parser sees it (docs/10): any byte outside printable
 *     ASCII becomes a space, and a run without a space is broken with one after 100
 *     characters, or sooner if its spelling would pass 1000 bytes. The engine's parser
 *     spells what it cannot pronounce into a fixed buffer with no length check, and
 *     overruns it from 62 "w". Nothing shorter than that is touched. A phonetic
 *     string (gama_speak_phonetic) gets the first of these only.
 * 10. Limits shared between parameters: pulse fall time minimum <= maximum, and
 *     rise time + fall time maximum <= 100. When changing several, set them in
 *     whichever order keeps them valid at every step.
 * 11. Above tempo 6 the engine refuses some words, because two postures would fall
 *     too close together. gama_speak() then tries again at a lower tempo, so that
 *     the word is still said. gama_spoken_tempo() gives the tempo actually used.
 * 12. The engine ends about one utterance in five with a tick, in its last 5 ms, up to
 *     -35 dBFS. The last 6 ms are made silent, and trimming does not count them as sound,
 *     except in upstream's own mode (rule 6), which keeps them as upstream makes them.
 *
 * Version history: 1 (2026-11-02) first version.
 */
#ifndef GAMA_API_H
#define GAMA_API_H

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
#  if defined(GAMA_API_BUILD)
#    define GAMA_API __declspec(dllexport)
#  else
#    define GAMA_API __declspec(dllimport)
#  endif
#elif defined(GAMA_API_BUILD)
#  define GAMA_API __attribute__((visibility("default")))
#else
#  define GAMA_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define GAMA_API_VERSION 1

/* Trimming: a sample counts as sound when its magnitude in the engine's output,
 * before levelling and the volume gain, is above this, -60 dBFS. */
#define GAMA_TRIM_THRESHOLD_DBFS (-60)

/* Return codes. */
#define GAMA_OK          0
#define GAMA_ERR_NULL   -1   /* a required pointer was NULL */
#define GAMA_ERR_RANGE  -2   /* a value out of range; nothing changed */
#define GAMA_ERR_ENGINE -3   /* the engine failed; gama_last_error() says why */

typedef struct gama_engine gama_engine;

/* The API version this library was built as (GAMA_API_VERSION). */
GAMA_API int gama_api_version(void);

/* Load the data in data_dir, the folder holding "voice/english". Returns NULL on
 * failure. If err is not NULL, the reason is written to it, truncated to err_size
 * bytes and always NUL-terminated. */
GAMA_API gama_engine *gama_create(const char *data_dir, char *err, size_t err_size);
GAMA_API void         gama_destroy(gama_engine *e);

/* The message of the last failure on this handle, or "" if none. Valid until the
 * next call on the handle. */
GAMA_API const char *gama_last_error(const gama_engine *e);

/* Voices are model 5's folders, in the order male, female, large_child,
 * small_child, baby, without the "5_". Setting a voice gives the parameters kept in
 * the voice's variant file (gama_param_info.file "voice") that file's values. Every
 * other parameter keeps its value. */
GAMA_API int         gama_voice_count(const gama_engine *e);
GAMA_API const char *gama_voice_name(const gama_engine *e, int i);
GAMA_API int         gama_voice(const gama_engine *e);          /* current index, or -1 */
GAMA_API int         gama_set_voice(gama_engine *e, int i);

/* Rate: the engine's tempo, 1.0 = normal, 0.1 to 10.0. The same value as the
 * parameter "tempo". */
GAMA_API int    gama_set_rate(gama_engine *e, double tempo);
GAMA_API double gama_rate(const gama_engine *e);
/* The tempo the last utterance was made at (rule 11). */
GAMA_API double gama_spoken_tempo(const gama_engine *e);

/* Pitch: semitones added to the parameter "pitch_offset", -24.0 to +24.0. */
GAMA_API int    gama_set_pitch(gama_engine *e, double semitones);
GAMA_API double gama_pitch(const gama_engine *e);

/* Volume: a linear gain on the output, 0.0 (silence) to 1.0. */
GAMA_API int    gama_set_volume(gama_engine *e, double gain);
GAMA_API double gama_volume(const gama_engine *e);

/* Deterministic mode turns off random intonation and intonation drift, so the same
 * text gives the same samples. Off by default, as upstream ships. */
GAMA_API int gama_set_deterministic(gama_engine *e, int on);
GAMA_API int gama_deterministic(const gama_engine *e);

/* Trimming: keep at most lead_ms of the silence before the first sound and at most
 * trail_ms after the last (0 to 1000 each), or -1 to keep all of it (the default). */
GAMA_API int  gama_set_trim(gama_engine *e, int lead_ms, int trail_ms);
GAMA_API void gama_trim(const gama_engine *e, int *lead_ms, int *trail_ms);

/* Levelling: how each utterance's level is set.
 *  GAMA_LEVEL_PEAK      as upstream: its highest peak at 0.95 of full scale.
 *  GAMA_LEVEL_LOUDNESS  its A-weighted level of active speech at target_db, then any
 *                       peak above 0.95 of full scale brought down by a smooth gain.
 *  GAMA_LEVEL_CONSTANT  as LOUDNESS, and inside the utterance as well: wherever the
 *                       engine voices at full strength (glottal volume 57 dB or more),
 *                       each control period is brought to one A-weighted level.
 * The constants of the two levelled modes are measured for model 5: docs/10.
 * target_db is used only in the levelled modes, -40.0 to -10.0. The default is
 * GAMA_LEVEL_PEAK with GAMA_LEVEL_DEFAULT_TARGET. */
#define GAMA_LEVEL_PEAK     0
#define GAMA_LEVEL_LOUDNESS 1
#define GAMA_LEVEL_CONSTANT 2
#define GAMA_LEVEL_DEFAULT_TARGET (-22.0)
GAMA_API int  gama_set_leveling(gama_engine *e, int mode, double target_db);
GAMA_API void gama_leveling(const gama_engine *e, int *mode, double *target_db);

/* The engine's parameters: every value in model 5's data files that the engine
 * reads and that reaches the sound. Each was checked by changing it and comparing
 * the output (docs/09, section 7). The table is the same for every handle and lives
 * as long as the library. */
#define GAMA_PARAM_NUMBER 0   /* any value from min to max */
#define GAMA_PARAM_SWITCH 1   /* 0 (off) or 1 (on) */
#define GAMA_PARAM_CHOICE 2   /* one of choice_values */

typedef struct gama_param_info {
	const char *key;        /* the key in the data file: "glottal_pulse_tp" */
	const char *file;       /* "control", "vtm" or "voice" */
	const char *category;   /* "Speech", "Intonation", "Glottal source", ... */
	const char *label;      /* "Pulse rise time", without the unit */
	const char *unit;       /* "%", "cm", ...; "" if none */
	const char *help;       /* one or two sentences for a user */
	int kind;               /* GAMA_PARAM_NUMBER, _SWITCH or _CHOICE */
	double min, max;        /* the accepted range, inclusive */
	double step;            /* a sensible step for a spin control */
	int decimals;           /* digits worth showing after the point */
	int choice_count;       /* GAMA_PARAM_CHOICE only, else 0 */
	const double *choice_values;
	const char *const *choice_names;
} gama_param_info;

GAMA_API int                    gama_param_count(void);
GAMA_API const gama_param_info *gama_param_describe(int i);
GAMA_API int                    gama_param_index(const char *key);

/* Get and set parameter i (rule 3). */
GAMA_API int gama_get_param(const gama_engine *e, int i, double *value);
GAMA_API int gama_set_param(gama_engine *e, int i, double value);

/* The data files' value of parameter i, for the current voice. */
GAMA_API int gama_param_default(const gama_engine *e, int i, double *value);

/* Every parameter back to its data file's value, for the current voice. Volume, the
 * pitch of gama_set_pitch, trimming and deterministic mode are not parameters and
 * are left as they are. */
GAMA_API int gama_reset_params(gama_engine *e);

/* Synthesise one utterance from text, replacing any samples not yet read. Rule 9
 * applies. Text with nothing to say (for example "*") returns GAMA_ERR_ENGINE and
 * leaves nothing to read. */
GAMA_API int gama_speak(gama_engine *e, const char *text);

/* The phonetic string the text parser makes of text, in Gnuspeech's notation.
 * Writes it to out, truncated to out_size bytes and always NUL-terminated (out may
 * be NULL when out_size is 0), and returns its full length without the NUL. Returns
 * 0 on failure, with gama_last_error() saying why. */
GAMA_API size_t gama_text_to_phonetic(gama_engine *e, const char *text, char *out, size_t out_size);

/* gama_speak, from a phonetic string: the same samples as gama_speak(text) when
 * given gama_text_to_phonetic(text). */
GAMA_API int gama_speak_phonetic(gama_engine *e, const char *phonetic);

/* The parameter track of the last utterance: one line of 16 values per control
 * period, the text upstream's gama_tts writes with -p, byte for byte. Written and
 * returned like gama_text_to_phonetic. 0 if nothing has been spoken. */
GAMA_API size_t gama_track(const gama_engine *e, char *out, size_t out_size);

/* Copy up to n samples of the current utterance into out. Returns the number
 * copied; 0 means everything has been read. */
GAMA_API size_t gama_read(gama_engine *e, int16_t *out, size_t n);

/* Samples of the current utterance not yet read. */
GAMA_API size_t gama_pending(const gama_engine *e);

/* Drop whatever has not been read. */
GAMA_API void gama_stop(gama_engine *e);

/* The output sample rate in Hz of the last utterance, or before the first, the rate
 * the parameter "output_rate" gives (48000 with the shipped data). */
GAMA_API int gama_sample_rate(const gama_engine *e);

#ifdef __cplusplus
}
#endif

#endif /* GAMA_API_H */
