/* api_test.c -- tests for gama_api.h. Plain C17.
 *
 * Copyright 2026 dengopaiv. GPL-3.0-or-later.
 * Adapted from GnuspeechSA-NVDA's tests/api/api_test.c.
 *
 * Usage: gama_api_test <data_dir>
 *
 * Covers ranges, NULL handling, the error path, chunked reading, volume across voice
 * changes, trimming, the parameter table with its shared limits, the phonetic string
 * and the track, and the independence of two engines. The golden comparison is
 * tests/api/check_golden.py, and hostile input is tests/api/check_robustness.py.
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "gama_api.h"

static int failures = 0;
static int checks = 0;

#define CHECK(cond, ...) do { \
	++checks; \
	if (!(cond)) { \
		++failures; \
		printf("FAIL %s:%d: ", __FILE__, __LINE__); \
		printf(__VA_ARGS__); \
		printf("\n"); \
	} \
} while (0)

typedef struct {
	int16_t *s;
	size_t n;
} pcm;

static void pcm_free(pcm *p)
{
	free(p->s);
	p->s = NULL;
	p->n = 0;
}

/* Read the whole current utterance, chunk samples at a time. */
static int collect(gama_engine *e, size_t chunk, pcm *out)
{
	out->s = NULL;
	out->n = 0;
	size_t cap = gama_pending(e);
	out->s = malloc((cap ? cap : 1) * sizeof(int16_t));
	if (!out->s) return GAMA_ERR_ENGINE;
	size_t got;
	while ((got = gama_read(e, out->s + out->n, chunk)) > 0) {
		out->n += got;
	}
	return GAMA_OK;
}

static int speak(gama_engine *e, const char *text, size_t chunk, pcm *out)
{
	out->s = NULL;
	out->n = 0;
	int rc = gama_speak(e, text);
	return rc != GAMA_OK ? rc : collect(e, chunk, out);
}

static int peak(const pcm *p)
{
	int m = 0;
	for (size_t i = 0; i < p->n; ++i) {
		int v = abs(p->s[i]);
		if (v > m) m = v;
	}
	return m;
}

static int same(const pcm *a, const pcm *b)
{
	return a->n == b->n && memcmp(a->s, b->s, a->n * sizeof(int16_t)) == 0;
}

/* Every sample of scaled is round(g * full) within 1. */
static int scaled_by(const pcm *full, const pcm *scaled, double g)
{
	if (full->n != scaled->n) return 0;
	for (size_t i = 0; i < full->n; ++i) {
		double want = g * full->s[i];
		if (fabs(scaled->s[i] - want) > 1.0) return 0;
	}
	return 1;
}

int main(int argc, char **argv)
{
	if (argc != 2) {
		fprintf(stderr, "usage: gama_api_test <data_dir>\n");
		return 2;
	}
	const char *dir = argv[1];
	/* As upstream's gama_tts feeds it: the text plus one space. */
	const char *hello = "Hello world. ";
	char err[512];

	CHECK(gama_api_version() == GAMA_API_VERSION, "api version %d", gama_api_version());

	/* ---- creation failures and NULL handling */
	err[0] = 'x';
	CHECK(gama_create(NULL, err, sizeof err) == NULL, "create(NULL) returned an engine");
	CHECK(strlen(err) > 0 && err[0] != 'x', "create(NULL) gave no message");
	CHECK(gama_create("no/such/folder", err, sizeof err) == NULL, "create(bad dir) returned an engine");
	CHECK(strlen(err) > 0, "create(bad dir) gave no message");
	CHECK(gama_create("no/such/folder", NULL, 0) == NULL, "create without err buffer");
	{
		char tiny[4];
		gama_create("no/such/folder", tiny, sizeof tiny);
		CHECK(strlen(tiny) == 3, "err not truncated and terminated");
	}
	int16_t buf[16];
	CHECK(gama_speak(NULL, "x") == GAMA_ERR_NULL, "speak(NULL engine)");
	CHECK(gama_read(NULL, buf, 16) == 0, "read(NULL engine)");
	CHECK(gama_set_volume(NULL, 0.5) == GAMA_ERR_NULL, "set_volume(NULL)");
	CHECK(gama_set_voice(NULL, 0) == GAMA_ERR_NULL, "set_voice(NULL)");
	CHECK(gama_voice_name(NULL, 0) == NULL, "voice_name(NULL)");
	CHECK(gama_last_error(NULL) == NULL, "last_error(NULL)");
	gama_destroy(NULL);
	gama_stop(NULL);

	/* ---- a real engine */
	gama_engine *e = gama_create(dir, err, sizeof err);
	if (!e) {
		printf("FAIL: cannot create the engine: %s\n", err);
		return 1;
	}
	CHECK(gama_voice_count(e) == 5, "voice count %d", gama_voice_count(e));
	CHECK(gama_voice(e) == 0 && strcmp(gama_voice_name(e, 0), "male") == 0, "starting voice is not male");
	CHECK(gama_voice_name(e, 1) && strcmp(gama_voice_name(e, 1), "female") == 0, "voice 1 is not female");
	CHECK(gama_voice_name(e, 5) == NULL && gama_voice_name(e, -1) == NULL, "voice_name out of range");
	CHECK(gama_sample_rate(e) == 48000, "sample rate %d", gama_sample_rate(e));
	CHECK(gama_volume(e) == 1.0 && gama_rate(e) == 1.0 && gama_pitch(e) == 0.0, "defaults");
	CHECK(gama_deterministic(e) == 0, "deterministic should be off by default, as upstream ships");
	CHECK(gama_speak(e, NULL) == GAMA_ERR_NULL, "speak(NULL text)");
	CHECK(gama_read(e, NULL, 16) == 0, "read(NULL out)");

	/* ---- ranges: refused, nothing changed */
	CHECK(gama_set_volume(e, -0.01) == GAMA_ERR_RANGE, "volume -0.01");
	CHECK(gama_set_volume(e, 1.01) == GAMA_ERR_RANGE, "volume 1.01");
	CHECK(gama_set_volume(e, NAN) == GAMA_ERR_RANGE, "volume NaN");
	CHECK(gama_volume(e) == 1.0, "volume changed by a refused value");
	CHECK(gama_set_rate(e, 0.0) == GAMA_ERR_RANGE && gama_set_rate(e, 10.5) == GAMA_ERR_RANGE, "rate range");
	CHECK(gama_set_pitch(e, 24.5) == GAMA_ERR_RANGE && gama_set_pitch(e, NAN) == GAMA_ERR_RANGE, "pitch range");
	CHECK(gama_set_voice(e, 5) == GAMA_ERR_RANGE && gama_set_voice(e, -1) == GAMA_ERR_RANGE, "voice range");
	CHECK(gama_voice(e) == 0, "voice changed by a refused value");

	CHECK(gama_set_deterministic(e, 1) == GAMA_OK && gama_deterministic(e) == 1, "deterministic on");

	/* ---- the reference utterance, and chunked reading */
	pcm full = {0}, again = {0}, small = {0};
	CHECK(speak(e, hello, 4096, &full) == GAMA_OK && full.n > 0, "speak hello");
	int p1 = peak(&full);
	CHECK(p1 == 31129, "peak at volume 1.0 is %d, expected 31129 (0.95 of full scale)", p1);
	CHECK(speak(e, hello, 1, &small) == GAMA_OK && same(&full, &small), "reading 1 sample at a time changed the samples");
	pcm_free(&small);
	CHECK(speak(e, hello, 777, &again) == GAMA_OK && same(&full, &again), "deterministic mode is not repeatable");
	pcm_free(&again);

	/* ---- volume */
	pcm half = {0}, zero = {0};
	CHECK(gama_set_volume(e, 0.5) == GAMA_OK, "volume 0.5");
	CHECK(speak(e, hello, 4096, &half) == GAMA_OK, "speak at 0.5");
	CHECK(scaled_by(&full, &half, 0.5), "volume 0.5 is not a gain of 0.5 on every sample");
	pcm_free(&half);
	CHECK(gama_set_volume(e, 0.0) == GAMA_OK, "volume 0");
	CHECK(speak(e, hello, 4096, &zero) == GAMA_OK && zero.n == full.n && peak(&zero) == 0,
			"volume 0 is not silence of the same length (n=%zu, peak=%d)", zero.n, peak(&zero));
	pcm_free(&zero);

	/* The bug of the first Gnuspeech add-on: a voice change must not reset the volume. */
	pcm female_full = {0}, female_40 = {0};
	CHECK(gama_set_volume(e, 1.0) == GAMA_OK && gama_set_voice(e, 1) == GAMA_OK, "female at 1.0");
	CHECK(speak(e, hello, 4096, &female_full) == GAMA_OK, "speak female");
	CHECK(gama_set_voice(e, 0) == GAMA_OK && gama_set_volume(e, 0.4) == GAMA_OK && gama_set_voice(e, 1) == GAMA_OK,
			"volume 0.4, then change voice");
	CHECK(gama_volume(e) == 0.4, "volume after a voice change is %g", gama_volume(e));
	CHECK(speak(e, hello, 4096, &female_40) == GAMA_OK, "speak female at 0.4");
	CHECK(scaled_by(&female_full, &female_40, 0.4), "volume 0.4 did not survive the voice change");
	pcm_free(&female_full);
	pcm_free(&female_40);

	/* Random voice and volume sequences: the gain always holds. */
	{
		pcm ref[5] = {{0}};
		CHECK(gama_set_volume(e, 1.0) == GAMA_OK, "volume back to 1");
		for (int v = 0; v < 5; ++v) {
			gama_set_voice(e, v);
			CHECK(speak(e, "Button, OK ", 4096, &ref[v]) == GAMA_OK, "reference for voice %d", v);
		}
		unsigned state = 12345u;
		int bad = 0;
		for (int k = 0; k < 60; ++k) {
			state = state * 1103515245u + 12345u;
			int v = (int)((state >> 16) % 5u);
			state = state * 1103515245u + 12345u;
			double g = (double)((state >> 16) % 21u) / 20.0;
			if (k % 2) {
				gama_set_volume(e, g);
				gama_set_voice(e, v);
			} else {
				gama_set_voice(e, v);
				gama_set_volume(e, g);
			}
			pcm got = {0};
			if (speak(e, "Button, OK ", 4096, &got) != GAMA_OK || !scaled_by(&ref[v], &got, g)) ++bad;
			pcm_free(&got);
		}
		CHECK(bad == 0, "%d of 60 random voice and volume sequences broke the gain", bad);
		for (int v = 0; v < 5; ++v) pcm_free(&ref[v]);
		gama_set_voice(e, 0);
		gama_set_volume(e, 1.0);
	}

	/* ---- the error path leaves the engine usable */
	CHECK(gama_speak(e, "* ") == GAMA_ERR_ENGINE, "speaking \"*\" should fail as upstream does");
	CHECK(strlen(gama_last_error(e)) > 0, "no message after a failure");
	CHECK(gama_pending(e) == 0 && gama_read(e, buf, 16) == 0, "samples left after a failure");
	CHECK(speak(e, hello, 4096, &again) == GAMA_OK && same(&full, &again), "a failure changed the next utterance");
	CHECK(strlen(gama_last_error(e)) == 0, "error not cleared by a good utterance");
	pcm_free(&again);

	/* ---- stop */
	CHECK(gama_speak(e, hello) == GAMA_OK && gama_pending(e) > 0, "speak before stop");
	gama_stop(e);
	CHECK(gama_pending(e) == 0 && gama_read(e, buf, 16) == 0, "stop left samples");

	/* ---- rate and pitch take effect, and undo exactly */
	{
		pcm fast = {0}, high = {0}, back = {0};
		CHECK(gama_set_rate(e, 2.0) == GAMA_OK && speak(e, hello, 4096, &fast) == GAMA_OK, "rate 2.0");
		double ratio = (double)fast.n / (double)full.n;
		CHECK(ratio > 0.4 && ratio < 0.7, "rate 2.0 gave %.3f of the length", ratio);
		CHECK(gama_spoken_tempo(e) == 2.0, "spoken tempo %g", gama_spoken_tempo(e));
		CHECK(gama_set_rate(e, 1.0) == GAMA_OK && gama_set_pitch(e, 5.0) == GAMA_OK, "pitch +5");
		CHECK(speak(e, hello, 4096, &high) == GAMA_OK && !same(&full, &high), "pitch +5 changed nothing");
		CHECK(gama_set_pitch(e, 0.0) == GAMA_OK && speak(e, hello, 4096, &back) == GAMA_OK && same(&full, &back),
				"rate and pitch did not undo exactly");
		pcm_free(&fast);
		pcm_free(&high);
		pcm_free(&back);
	}

	/* ---- trimming (rule 7) */
	{
		int lead = 99, trail = 99;
		gama_trim(e, &lead, &trail);
		CHECK(lead == -1 && trail == -1, "trimming should be off by default (got %d, %d)", lead, trail);
		CHECK(gama_set_trim(e, -2, 0) == GAMA_ERR_RANGE && gama_set_trim(e, 0, 1001) == GAMA_ERR_RANGE, "trim range");
		CHECK(gama_set_trim(NULL, 0, 0) == GAMA_ERR_NULL, "set_trim(NULL)");

		const int threshold = 33;   /* -60 dBFS of 32767, rounded up */
		pcm trimmed = {0}, quiet = {0}, silent = {0}, untrimmed = {0};
		CHECK(gama_set_trim(e, 10, 30) == GAMA_OK, "trim 10/30");
		CHECK(speak(e, hello, 4096, &trimmed) == GAMA_OK, "speak trimmed");
		CHECK(trimmed.n < full.n, "trimming made it no shorter (%zu vs %zu)", trimmed.n, full.n);

		/* Rule 12: the tick at the end. "No." has the largest in the corpus but one. */
		{
			pcm plain = {0}, cut = {0}, level = {0};
			gama_set_trim(e, -1, -1);
			CHECK(speak(e, "No. ", 4096, &plain) == GAMA_OK && plain.n > 300, "No, as upstream");
			int tail = 0, before = 0;
			for (size_t i = plain.n - 240; i < plain.n; ++i) if (abs(plain.s[i]) > tail) tail = abs(plain.s[i]);
			for (size_t i = plain.n - 960; i < plain.n - 240; ++i) if (abs(plain.s[i]) > before) before = abs(plain.s[i]);
			CHECK(tail > 300 && before < 100, "upstream's mode keeps the tick: %d in the last 5 ms, %d before", tail, before);
			gama_set_trim(e, 10, 30);
			CHECK(speak(e, "No. ", 4096, &cut) == GAMA_OK && cut.n < plain.n - 4800, "trimming stops at the sound, not the tick (%zu of %zu)", cut.n, plain.n);
			gama_set_trim(e, -1, -1);
			gama_set_leveling(e, GAMA_LEVEL_CONSTANT, GAMA_LEVEL_DEFAULT_TARGET);
			CHECK(speak(e, "No. ", 4096, &level) == GAMA_OK && level.n == plain.n, "levelled, the same length");
			tail = 0;
			for (size_t i = level.n - 288; i < level.n; ++i) if (abs(level.s[i]) > tail) tail = abs(level.s[i]);
			CHECK(tail == 0, "levelled, the last 6 ms should be silent, and reach %d", tail);
			gama_set_leveling(e, GAMA_LEVEL_PEAK, GAMA_LEVEL_DEFAULT_TARGET);
			gama_set_trim(e, 10, 30);
			pcm_free(&plain);
			pcm_free(&cut);
			pcm_free(&level);
		}
		size_t at = (size_t)-1;
		for (size_t off = 0; trimmed.n && off + trimmed.n <= full.n; ++off) {
			if (memcmp(full.s + off, trimmed.s, trimmed.n * sizeof(int16_t)) == 0) { at = off; break; }
		}
		CHECK(at != (size_t)-1, "trimmed samples are not a slice of the untrimmed ones");
		if (at != (size_t)-1) {
			int cut_loud = 0;
			for (size_t i = 0; i < at; ++i) cut_loud |= abs(full.s[i]) > threshold;
			for (size_t i = at + trimmed.n; i < full.n; ++i) cut_loud |= abs(full.s[i]) > threshold;
			CHECK(!cut_loud, "trimming cut away a sample above -60 dBFS");
			size_t first = 0, last = trimmed.n - 1;
			while (first < trimmed.n && abs(trimmed.s[first]) <= threshold) ++first;
			while (last > first && abs(trimmed.s[last]) <= threshold) --last;
			/* 10 ms and 30 ms at 48 kHz, give or take the threshold's rounding. */
			CHECK(first <= 480 + 2, "%zu samples of silence kept before the sound, want at most 480", first);
			CHECK(trimmed.n - 1 - last <= 1440 + 2, "%zu samples kept after the sound, want at most 1440",
					trimmed.n - 1 - last);
			printf("info: \"Hello world.\" trimmed 10/30 ms: %zu -> %zu samples (%.0f ms saved)\n",
					full.n, trimmed.n, (full.n - trimmed.n) / 48.0);
		}
		CHECK(gama_set_volume(e, 0.5) == GAMA_OK && speak(e, hello, 4096, &quiet) == GAMA_OK, "trimmed at 0.5");
		CHECK(scaled_by(&trimmed, &quiet, 0.5), "trimmed volume 0.5 is not a gain of 0.5 on the same samples");
		CHECK(gama_set_volume(e, 0.0) == GAMA_OK && speak(e, hello, 4096, &silent) == GAMA_OK, "trimmed at 0");
		CHECK(silent.n == trimmed.n && peak(&silent) == 0, "trimmed at volume 0: %zu samples, want %zu of silence",
				silent.n, trimmed.n);
		gama_set_volume(e, 1.0);
		CHECK(gama_set_trim(e, -1, -1) == GAMA_OK && speak(e, hello, 4096, &untrimmed) == GAMA_OK && same(&full, &untrimmed),
				"trimming off does not give back the untrimmed samples");
		pcm_free(&trimmed);
		pcm_free(&quiet);
		pcm_free(&silent);
		pcm_free(&untrimmed);
	}

	/* ---- the parameter table */
	{
		gama_set_pitch(e, 0.0);
		gama_set_voice(e, 0);
		CHECK(gama_reset_params(e) == GAMA_OK, "reset_params");
		const int count = gama_param_count();
		CHECK(count == 49, "%d parameters, docs/09 counted 49", count);
		int table_ok = 1;
		for (int v = 0; v < gama_voice_count(e); ++v) {
			gama_set_voice(e, v);
			gama_reset_params(e);
			for (int i = 0; i < count; ++i) {
				const gama_param_info *p = gama_param_describe(i);
				double value = NAN, d = NAN;
				if (!p || !p->key[0] || !p->label[0] || !p->category[0] || !p->help[0] || !(p->min <= p->max)
						|| gama_param_index(p->key) != i
						|| gama_get_param(e, i, &value) != GAMA_OK || gama_param_default(e, i, &d) != GAMA_OK || value != d) {
					table_ok = 0;
					printf("bad entry %d (%s), voice %d\n", i, p ? p->key : "NULL", v);
					continue;
				}
				/* Every value every shipped voice gives lies in the declared range. */
				if (gama_set_param(e, i, d) != GAMA_OK) {
					table_ok = 0;
					printf("voice %d: the data file's %s = %g is outside %g..%g (%s)\n", v, p->key, d, p->min, p->max,
							gama_last_error(e));
				}
			}
		}
		gama_set_voice(e, 0);
		gama_reset_params(e);
		CHECK(table_ok, "the parameter table is inconsistent (see above)");
		CHECK(gama_param_describe(-1) == NULL && gama_param_describe(count) == NULL, "describe out of range");
		CHECK(gama_param_index("no_such_key") == -1 && gama_param_index(NULL) == -1, "index of unknown key");
		CHECK(gama_param_index("notional_pitch") == -1, "notional_pitch is offered, but it changes nothing (docs/09)");
		CHECK(gama_param_index("bypass") == -1, "bypass is offered, but it is for debugging");

		const int tempo = gama_param_index("tempo"), length = gama_param_index("vocal_tract_length");
		const int breath = gama_param_index("breathiness"), temp = gama_param_index("temperature");
		const int rate = gama_param_index("output_rate"), micro = gama_param_index("micro_intonation");
		const int tp = gama_param_index("glottal_pulse_tp"), tmin = gama_param_index("glottal_pulse_tn_min");
		const int tmax = gama_param_index("glottal_pulse_tn_max"), offset = gama_param_index("vocal_tract_length_offset");
		double v = 0.0;
		CHECK(gama_get_param(e, length, &v) == GAMA_OK && v == 17.5, "male tract length %g, want 17.5", v);
		CHECK(gama_get_param(e, gama_param_index("pitch_offset"), &v) == GAMA_OK && v == -4.0, "pitch offset %g", v);
		CHECK(gama_get_param(e, rate, &v) == GAMA_OK && v == 48000.0, "output rate %g", v);

		/* Refusals, which change nothing. */
		CHECK(gama_set_param(e, length, 25.0) == GAMA_ERR_RANGE, "tract length 25 accepted");
		CHECK(gama_set_param(e, length, NAN) == GAMA_ERR_RANGE, "NaN accepted");
		CHECK(gama_set_param(e, micro, 0.5) == GAMA_ERR_RANGE, "switch 0.5 accepted");
		CHECK(gama_set_param(e, rate, 30000.0) == GAMA_ERR_RANGE, "output rate 30000 accepted");
		CHECK(gama_set_param(e, count, 1.0) == GAMA_ERR_RANGE && gama_set_param(e, -1, 1.0) == GAMA_ERR_RANGE, "bad index");
		CHECK(gama_set_param(NULL, 0, 1.0) == GAMA_ERR_NULL && gama_get_param(e, 0, NULL) == GAMA_ERR_NULL, "NULLs");
		CHECK(gama_get_param(e, length, &v) == GAMA_OK && v == 17.5, "a refused value changed the tract length");

		/* Shared limits (rule 10): refused, with a reason, and nothing changed. */
		CHECK(gama_set_param(e, tmin, 30.0) == GAMA_ERR_RANGE && strlen(gama_last_error(e)) > 0, "tn_min above tn_max accepted");
		CHECK(gama_get_param(e, tmin, &v) == GAMA_OK && v == 24.0, "a refused tn_min changed it to %g", v);
		CHECK(gama_set_param(e, tmax, 30.0) == GAMA_OK && gama_set_param(e, tmin, 30.0) == GAMA_OK, "raising max, then min");
		CHECK(gama_set_param(e, tp, 70.5) == GAMA_ERR_RANGE, "tp 70.5 accepted");
		CHECK(gama_set_param(e, tp, 70.0) == GAMA_OK, "tp 70 with tn_max 30 refused: it makes 100");
		CHECK(gama_set_param(e, tmax, 31.0) == GAMA_ERR_RANGE, "tp + tn_max above 100 accepted");
		gama_reset_params(e);
		CHECK(gama_set_param(e, length, 20.0) == GAMA_OK && gama_set_param(e, offset, 3.0) == GAMA_ERR_RANGE,
				"a tract of 23 cm accepted: the tube would refuse its rate");
		gama_reset_params(e);

		/* tempo is gama_rate. */
		CHECK(gama_set_param(e, tempo, 1.5) == GAMA_OK && gama_rate(e) == 1.5, "tempo is not gama_rate");
		CHECK(gama_set_rate(e, 1.0) == GAMA_OK && gama_get_param(e, tempo, &v) == GAMA_OK && v == 1.0, "gama_rate is not tempo");

		/* A change changes the samples; putting it back gives them back exactly. */
		pcm changed = {0}, restored = {0};
		CHECK(gama_set_param(e, breath, 25.0) == GAMA_OK && speak(e, hello, 4096, &changed) == GAMA_OK
				&& !same(&full, &changed), "breathiness 25 changed nothing");
		CHECK(gama_reset_params(e) == GAMA_OK && speak(e, hello, 4096, &restored) == GAMA_OK && same(&full, &restored),
				"reset did not restore the samples");
		pcm_free(&changed);
		pcm_free(&restored);

		/* A voice change replaces only the voice file's values. */
		CHECK(gama_set_param(e, temp, 30.0) == GAMA_OK && gama_set_voice(e, 1) == GAMA_OK, "temperature 30, female");
		CHECK(gama_get_param(e, temp, &v) == GAMA_OK && v == 30.0, "the voice change reset the temperature to %g", v);
		CHECK(gama_get_param(e, length, &v) == GAMA_OK && v == 15.0, "female tract length %g, want 15", v);
		CHECK(gama_param_default(e, length, &v) == GAMA_OK && v == 15.0, "female default tract length %g", v);
		gama_set_voice(e, 0);
		gama_reset_params(e);

		/* The output rate. */
		pcm p = {0};
		CHECK(gama_set_param(e, rate, 22050.0) == GAMA_OK && speak(e, hello, 4096, &p) == GAMA_OK
				&& gama_sample_rate(e) == 22050, "22050 gave %d Hz", gama_sample_rate(e));
		pcm_free(&p);
		gama_reset_params(e);

		/* Phonetic string and track. */
		char phon[2048];
		size_t n = gama_text_to_phonetic(e, hello, phon, sizeof phon);
		CHECK(n > 0 && n < sizeof phon && strlen(phon) == n, "phonetic string of hello: %zu", n);
		CHECK(gama_text_to_phonetic(e, hello, NULL, 0) == n, "length query differs");
		char tiny[5];
		CHECK(gama_text_to_phonetic(e, hello, tiny, sizeof tiny) == n && strlen(tiny) == 4, "truncation");
		printf("info: phonetic string of \"Hello world.\": %s\n", phon);
		pcm ph = {0};
		CHECK(gama_speak_phonetic(e, phon) == GAMA_OK, "speak_phonetic: %s", gama_last_error(e));
		collect(e, 4096, &ph);
		CHECK(same(&full, &ph), "speaking the phonetic string gave other samples");
		pcm_free(&ph);
		size_t t = gama_track(e, NULL, 0);
		CHECK(t > 1000, "track of hello is %zu bytes", t);
		CHECK(gama_speak_phonetic(e, NULL) == GAMA_ERR_NULL && gama_track(NULL, NULL, 0) == 0, "NULL phonetic and track");

		/* Levelling: the default and the NULL cases (the rest is check_leveling.py). */
		int mode = -1;
		double target = 0.0;
		gama_leveling(e, &mode, &target);
		CHECK(mode == GAMA_LEVEL_PEAK && target == GAMA_LEVEL_DEFAULT_TARGET, "leveling default %d %g", mode, target);
		CHECK(gama_set_leveling(NULL, GAMA_LEVEL_LOUDNESS, -22.0) == GAMA_ERR_NULL, "set_leveling(NULL)");
		CHECK(gama_set_leveling(e, 7, -22.0) == GAMA_ERR_RANGE, "leveling mode 7 accepted");
		CHECK(gama_set_leveling(e, GAMA_LEVEL_CONSTANT, -9.0) == GAMA_ERR_RANGE, "target -9 accepted");
		CHECK(gama_set_leveling(e, GAMA_LEVEL_CONSTANT, -25.0) == GAMA_OK, "GAMA_LEVEL_CONSTANT refused");
		gama_leveling(e, &mode, &target);
		CHECK(mode == GAMA_LEVEL_CONSTANT && target == -25.0, "leveling read back %d %g", mode, target);
		CHECK(gama_set_leveling(e, GAMA_LEVEL_PEAK, GAMA_LEVEL_DEFAULT_TARGET) == GAMA_OK, "back to GAMA_LEVEL_PEAK");
		gama_leveling(NULL, &mode, &target);
		gama_leveling(e, NULL, NULL);
	}

	/* ---- two engines are independent */
	{
		gama_engine *e2 = gama_create(dir, err, sizeof err);
		CHECK(e2 != NULL, "second engine: %s", err);
		if (e2) {
			pcm other = {0};
			gama_set_deterministic(e2, 1);
			gama_set_volume(e, 0.25);                 /* must not leak into e2 */
			CHECK(speak(e2, hello, 4096, &other) == GAMA_OK && same(&full, &other), "second engine differs");
			pcm_free(&other);
			gama_destroy(e2);
		}
	}

	pcm_free(&full);
	gama_destroy(e);
	printf("%d checks, %d failed\n", checks, failures);
	return failures ? 1 : 0;
}
