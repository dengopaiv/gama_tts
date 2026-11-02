/* gama_api.cpp -- the C interface over GamaTTS, model 5.
 *
 * Copyright 2026 dengopaiv. GPL-3.0-or-later. See gama_api.h for the rules, and
 * docs/10 for the record. The levelling is carried over from gnuspeech_api.cpp in
 * GnuspeechSA-NVDA, with its constants measured again for model 5.
 *
 * An utterance is made as upstream's Controller makes it, except that the API owns
 * the tube (docs/09, section 6):
 *
 *  1. Controller::synthesizePhoneticStringToFile with a null output file runs the
 *     rules and stops before the tube. vtmParameterList() then gives the track.
 *  2. A tube is built for the utterance from a ConfigurationData the API holds:
 *     the voice's vtm.txt and variant file, with any value the user has changed.
 *     Controller builds its tube once, in its constructor, so it cannot follow
 *     a change of breathiness or tract length. A tube costs about 0.2 ms.
 *  3. The loop of Controller::synthesize runs over the track.
 *  4. The output is scaled as Controller::writeOutputToBuffer scales it, and rounded
 *     as WAVEFileWriter::writeSample rounds it.
 *
 * With nothing changed this gives upstream's samples exactly: tests/api/check_golden.py.
 */
#define GAMA_API_BUILD
#include "gama_api.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <exception>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#include "ConfigurationData.h"
#include "Controller.h"
#include "Index.h"
#include "Model.h"
#include "TextParser.h"
#include "VTMControlModelConfiguration.h"
#include "VTMUtil.h"
#include "VocalTractModel.h"

// gama_spell.cpp: how long a character gets when the engine spells it.
int gamaSpelledLength(unsigned char c);

namespace {

using GS::VTMControlModel::Configuration;

// Model 5's voices, in upstream's order; each is the folder "5_<name>".
const char* const kVoiceNames[] = { "male", "female", "large_child", "small_child", "baby" };

// The same scale WAVEFileWriter uses.
const float kSampleScale = 32767.0f;

// The tube's internal rate must stay above PoleZeroRadiationImpedance's minimum;
// above kMaxInternalRate the voice costs too much to be of use.
const double kMinInternalRate = 50000.0;
const double kMaxInternalRate = 300000.0;

const double kWaveformValues[] = { 0.0, 1.0 };
const char* const kWaveformNames[] = { "Pulse", "Sine" };
const double kOutputRateValues[] = { 22050.0, 44100.0, 48000.0 };
const char* const kOutputRateNames[] = { "22050 Hz", "44100 Hz", "48000 Hz" };
const double kPeriodValues[] = { 1.0, 2.0, 3.0, 4.0 };
const char* const kPeriodNames[] = { "1 ms", "2 ms", "3 ms", "4 ms" };

#define NUMBER(min, max, step, dec) GAMA_PARAM_NUMBER, min, max, step, dec, 0, nullptr, nullptr
#define SWITCH GAMA_PARAM_SWITCH, 0.0, 1.0, 1.0, 0, 0, nullptr, nullptr
#define CHOICE(values, names, n) GAMA_PARAM_CHOICE, values[0], values[n - 1], 1.0, 0, n, values, names

// The order is the order of the GUI, category by category. Which keys reach the sound
// was measured (docs/09, section 7). The ranges hold every shipped voice's value, and
// were run at their extremes (tests/api/check_extremes.py, docs/10). Left out:
// notional_pitch and the other "fixed intonation" keys, which change nothing;
// bypass and log_parameters, for debugging; variant_name and model, chosen by the voice.
const gama_param_info kParams[] = {
	// Speech
	{ "tempo", "control", "Speech", "Tempo", "",
	  "How fast the rules run: 1 is normal, 2 is twice as fast.",
	  NUMBER(0.1, 10.0, 0.05, 2) },
	{ "pitch_offset", "control", "Speech", "Pitch offset", "semitones",
	  "Added to the voice's reference glottal pitch.",
	  NUMBER(-24.0, 24.0, 0.5, 1) },
	{ "initial_pitch", "control", "Speech", "Initial pitch", "semitones",
	  "Where the pitch starts, against the voice's own, before running to the first intonation point.",
	  NUMBER(-48.0, 12.0, 0.5, 1) },
	{ "control_period", "control", "Speech", "Control period", "",
	  "How often the rules give the tube new values. A shorter period costs more and is finer.",
	  CHOICE(kPeriodValues, kPeriodNames, 4) },

	// Intonation
	{ "micro_intonation", "control", "Intonation", "Micro intonation", "",
	  "Small pitch movements made by individual sounds.", SWITCH },
	{ "macro_intonation", "control", "Intonation", "Macro intonation", "",
	  "The rise and fall of pitch over each phrase.", SWITCH },
	{ "smooth_intonation", "control", "Intonation", "Smooth intonation", "",
	  "Curves between the phrase's pitch points. Off, straight lines.", SWITCH },
	{ "intonation_drift", "control", "Intonation", "Intonation drift", "",
	  "A slow random wander of the pitch.", SWITCH },
	{ "random_intonation", "control", "Intonation", "Random intonation", "",
	  "Picks the phrase contours at random, so the same text varies from one utterance to the next.", SWITCH },
	{ "drift_deviation", "control", "Intonation", "Drift deviation", "semitones",
	  "How far the drift may wander.",
	  NUMBER(0.0, 10.0, 0.1, 1) },
	{ "drift_lowpass_cutoff", "control", "Intonation", "Drift speed", "Hz",
	  "The low-pass cutoff of the drift: higher wanders faster.",
	  NUMBER(1.0, 20.0, 0.1, 1) },
	{ "intonation_factor", "voice", "Intonation", "Intonation range", "",
	  "Scales the phrase's pitch movements: 1 as written, 0 flat.",
	  NUMBER(0.0, 2.0, 0.05, 2) },

	// Glottal source
	{ "waveform", "vtm", "Glottal source", "Glottal waveform", "",
	  "Pulse is the glottal pulse. Sine is a pure tone, for study.",
	  CHOICE(kWaveformValues, kWaveformNames, 2) },
	{ "reference_glottal_pitch", "voice", "Glottal source", "Reference glottal pitch", "semitones",
	  "The voice's own pitch. The pitch offset is added to it.",
	  NUMBER(-24.0, 24.0, 0.5, 1) },
	{ "glottal_pulse_tp", "voice", "Glottal source", "Pulse rise time", "%",
	  "The rise of the glottal pulse, as a share of its period. Rise time and fall time maximum together may not pass 100.",
	  NUMBER(5.0, 70.0, 0.5, 1) },
	{ "glottal_pulse_tn_min", "voice", "Glottal source", "Pulse fall time, minimum", "%",
	  "The fall time moves between the minimum and the maximum with the voicing amplitude. The minimum may not pass the maximum.",
	  NUMBER(5.0, 70.0, 0.5, 1) },
	{ "glottal_pulse_tn_max", "voice", "Glottal source", "Pulse fall time, maximum", "%",
	  "The fall time moves between the minimum and the maximum with the voicing amplitude. Rise time and fall time maximum together may not pass 100.",
	  NUMBER(5.0, 70.0, 0.5, 1) },
	{ "breathiness", "voice", "Glottal source", "Breathiness", "%",
	  "Noise mixed into the glottal source.",
	  NUMBER(0.0, 50.0, 0.5, 1) },
	{ "min_glottal_loss", "voice", "Glottal source", "Glottal loss, closed", "%",
	  "Energy lost at the glottis while the pulse is low.",
	  NUMBER(0.0, 10.0, 0.1, 1) },
	{ "max_glottal_loss", "voice", "Glottal source", "Glottal loss, open", "%",
	  "Energy lost at the glottis at the top of the pulse.",
	  NUMBER(0.0, 10.0, 0.1, 1) },
	{ "glottal_lowpass_cutoff", "voice", "Glottal source", "Glottal low-pass cutoff", "Hz",
	  "Softens the glottal pulse. Lower is darker.",
	  NUMBER(500.0, 20000.0, 100.0, 0) },

	// Vocal tract
	{ "vocal_tract_length", "voice", "Vocal tract", "Tract length", "cm",
	  "The length of the tube. Shorter sounds younger and higher.",
	  NUMBER(5.0, 20.0, 0.1, 1) },
	{ "vocal_tract_length_offset", "vtm", "Vocal tract", "Tract length offset", "cm",
	  "Added to the tract length of every voice.",
	  NUMBER(-3.0, 3.0, 0.1, 1) },
	{ "temperature", "vtm", "Vocal tract", "Temperature", "degrees C",
	  "Sets the speed of sound in the tube.",
	  NUMBER(25.0, 40.0, 0.5, 1) },
	{ "loss_factor", "voice", "Vocal tract", "Junction loss", "%",
	  "Energy lost at each junction of the tube. More loss gives wider, duller resonances.",
	  NUMBER(0.0, 5.0, 0.05, 2) },
	{ "constant_radius_mouth_impedance", "voice", "Vocal tract", "Fixed mouth radiation", "",
	  "On, the lips radiate as if always at the radius below. Off, as the mouth opens and closes.", SWITCH },
	{ "mouth_impedance_radius", "voice", "Vocal tract", "Fixed mouth radius", "cm",
	  "Used only when Fixed mouth radiation is on.",
	  NUMBER(0.2, 5.0, 0.01, 2) },
	{ "global_radius_coef", "voice", "Vocal tract", "Global radius coefficient", "",
	  "Scales every region's radius at once.",
	  NUMBER(0.2, 2.0, 0.01, 2) },
	{ "radius_1_coef", "voice", "Vocal tract", "Region 1 radius coefficient", "",
	  "Scales the radius of region 1, at the glottis.", NUMBER(0.2, 2.0, 0.05, 2) },
	{ "radius_2_coef", "voice", "Vocal tract", "Region 2 radius coefficient", "",
	  "Scales the radius of region 2.", NUMBER(0.2, 2.0, 0.05, 2) },
	{ "radius_3_coef", "voice", "Vocal tract", "Region 3 radius coefficient", "",
	  "Scales the radius of region 3.", NUMBER(0.2, 2.0, 0.05, 2) },
	{ "radius_4_coef", "voice", "Vocal tract", "Region 4 radius coefficient", "",
	  "Scales the radius of region 4.", NUMBER(0.2, 2.0, 0.05, 2) },
	{ "radius_5_coef", "voice", "Vocal tract", "Region 5 radius coefficient", "",
	  "Scales the radius of region 5.", NUMBER(0.2, 2.0, 0.05, 2) },
	{ "radius_6_coef", "voice", "Vocal tract", "Region 6 radius coefficient", "",
	  "Scales the radius of region 6.", NUMBER(0.2, 2.0, 0.05, 2) },
	{ "radius_7_coef", "voice", "Vocal tract", "Region 7 radius coefficient", "",
	  "Scales the radius of region 7.", NUMBER(0.2, 2.0, 0.05, 2) },
	{ "radius_8_coef", "voice", "Vocal tract", "Region 8 radius coefficient", "",
	  "Scales the radius of region 8, at the lips.", NUMBER(0.2, 2.0, 0.05, 2) },

	// Nose
	{ "global_nasal_radius_coef", "voice", "Nose", "Global nose radius coefficient", "",
	  "Scales every nasal section's radius at once.", NUMBER(0.2, 2.0, 0.01, 2) },
	{ "nasal_radius_2", "voice", "Nose", "Nasal section 2 radius", "cm",
	  "Section 1 is the velum, which the rules move. Section 2 is next to it.", NUMBER(0.01, 3.0, 0.01, 2) },
	{ "nasal_radius_3", "voice", "Nose", "Nasal section 3 radius", "cm",
	  "The radius of nasal section 3.", NUMBER(0.01, 3.0, 0.01, 2) },
	{ "nasal_radius_4", "voice", "Nose", "Nasal section 4 radius", "cm",
	  "The radius of nasal section 4.", NUMBER(0.01, 3.0, 0.01, 2) },
	{ "nasal_radius_5", "voice", "Nose", "Nasal section 5 radius", "cm",
	  "The radius of nasal section 5.", NUMBER(0.01, 3.0, 0.01, 2) },
	{ "nasal_radius_6", "voice", "Nose", "Nasal section 6 radius", "cm",
	  "The radius of nasal section 6.", NUMBER(0.01, 3.0, 0.01, 2) },
	{ "nasal_radius_7", "voice", "Nose", "Nasal section 7 radius", "cm",
	  "Section 7 is at the nostrils.", NUMBER(0.01, 3.0, 0.01, 2) },

	// Noise
	{ "noise_modulation", "vtm", "Noise", "Pulse-modulated noise", "",
	  "Modulates the noise sources with the glottal pulse.", SWITCH },
	{ "mix_offset", "voice", "Noise", "Noise crossmix offset", "dB",
	  "The voicing level at which pulse-modulated noise crosses over to plain noise.",
	  NUMBER(30.0, 60.0, 1.0, 1) },
	{ "glottal_noise_cutoff", "voice", "Noise", "Glottal noise cutoff", "Hz",
	  "The low-pass cutoff of the noise in the glottal source.",
	  NUMBER(50.0, 10000.0, 50.0, 0) },
	{ "frication_noise_cutoff", "voice", "Noise", "Frication noise cutoff", "Hz",
	  "The low-pass cutoff of the noise behind s, f and sh. Higher is crisper.",
	  NUMBER(500.0, 20000.0, 100.0, 0) },
	{ "frication_factor", "voice", "Noise", "Frication strength", "",
	  "Scales the frication noise. 1 is as the rules make it.",
	  NUMBER(0.0, 5.0, 0.05, 2) },

	// Output
	{ "output_rate", "vtm", "Output", "Output sample rate", "",
	  "The rate of the finished speech. The tube runs at its own rate and is converted to this.",
	  CHOICE(kOutputRateValues, kOutputRateNames, 3) },
};

#undef NUMBER
#undef SWITCH
#undef CHOICE

const int kParamCount = static_cast<int>(sizeof kParams / sizeof kParams[0]);

int paramIndex(const char* key)
{
	for (int i = 0; i < kParamCount; ++i) {
		if (std::strcmp(kParams[i].key, key) == 0) return i;
	}
	return -1;
}

// Indices used when the values are written into the engine. Looked up once.
struct Index {
	int tempo, pitchOffset, initialPitch, period;
	int micro, macro, smooth, drift, random, driftDeviation, driftCutoff, intonationFactor;
	int glottalPitch, tp, tnMin, tnMax;
	int length, lengthOffset, temperature, outputRate;

	Index()
	{
		tempo = paramIndex("tempo"); pitchOffset = paramIndex("pitch_offset");
		initialPitch = paramIndex("initial_pitch"); period = paramIndex("control_period");
		micro = paramIndex("micro_intonation"); macro = paramIndex("macro_intonation");
		smooth = paramIndex("smooth_intonation"); drift = paramIndex("intonation_drift");
		random = paramIndex("random_intonation"); driftDeviation = paramIndex("drift_deviation");
		driftCutoff = paramIndex("drift_lowpass_cutoff"); intonationFactor = paramIndex("intonation_factor");
		glottalPitch = paramIndex("reference_glottal_pitch"); tp = paramIndex("glottal_pulse_tp");
		tnMin = paramIndex("glottal_pulse_tn_min"); tnMax = paramIndex("glottal_pulse_tn_max");
		length = paramIndex("vocal_tract_length"); lengthOffset = paramIndex("vocal_tract_length_offset");
		temperature = paramIndex("temperature"); outputRate = paramIndex("output_rate");
	}
};

const Index& idx()
{
	static const Index index;
	return index;
}

size_t copyOut(const std::string& s, char* out, size_t outSize)
{
	if (out && outSize > 0) {
		const size_t n = s.size() < outSize - 1 ? s.size() : outSize - 1;
		std::memcpy(out, s.data(), n);
		out[n] = '\0';
	}
	return s.size();
}

// Rule 9. The engine's parser copies words into fixed buffers with no length check, and
// indexes tables with signed characters. A word it cannot pronounce it spells, into a
// buffer of 1027 bytes (LetterToSound.cpp), so what fills that buffer is the spelled length: 17
// bytes for a "w", 43 for a "<". A run is broken before its spelling could fill it, and
// before it reaches the length at which the other buffers were found to overflow (docs/10,
// section 5). A run with no reason to be broken is left alone, since a broken word is read
// differently: "http://www.gnu.org/software/gnuspeech/" must stay whole.
constexpr int kMaxSpelledBytes = 1000;
constexpr int kMaxRunChars = 100;

std::string safeText(const char* text)
{
	std::string s;
	s.reserve(std::strlen(text) + 16);
	int spelled = 0, run = 0;
	for (const char* p = text; *p; ++p) {
		const unsigned char c = static_cast<unsigned char>(*p);
		if (c <= ' ' || c > '~') {
			s += ' ';
			spelled = run = 0;
			continue;
		}
		const int cost = gamaSpelledLength(c);
		if (spelled + cost > kMaxSpelledBytes || run == kMaxRunChars) {
			s += ' ';
			spelled = run = 0;
		}
		s += static_cast<char>(c);
		spelled += cost;
		++run;
	}
	return s;
}

std::string safePhonetic(const char* phonetic)
{
	std::string s(phonetic);
	for (char& c : s) {
		const unsigned char u = static_cast<unsigned char>(c);
		if (u < ' ' || u > '~') c = ' ';
	}
	return s;
}

} // namespace

struct gama_engine {
	std::string dataDir;
	std::vector<std::string> voices;
	int voice = -1;

	// The current voice. The Controller keeps references to the other two.
	std::unique_ptr<GS::Index> index;
	std::unique_ptr<GS::VTMControlModel::Model> model;
	std::unique_ptr<GS::VTMControlModel::Controller> controller;
	std::unique_ptr<GS::ConfigurationData> tubeData;  // vtm.txt and the variant file, as written

	// One dictionary for every voice: they all name ../0_male/text_parser/.
	std::unique_ptr<GS::Index> parserIndex;
	std::unique_ptr<GS::TextParser::TextParser> textParser;

	std::vector<double> values;     // the parameters as set (kParams order)
	std::vector<double> fileValues; // the parameters as the data files give them
	double pitch = 0.0;             // semitones added to pitch_offset
	double gain = 1.0;              // volume, outside the engine's configuration
	bool deterministic = false;
	int trimLeadMs = -1;            // -1: keep the engine's silence as made
	int trimTrailMs = -1;
	int levelMode = GAMA_LEVEL_PEAK;
	double levelTarget = GAMA_LEVEL_DEFAULT_TARGET;

	std::vector<int16_t> samples;
	size_t readPos = 0;
	int sampleRate = 0;
	double spokenTempo = 0.0;
	std::vector<std::vector<float>> track;  // the parameter track of the last utterance
	double trackRate = 0.0;                 // its control rate, in Hz

	std::string error;
};

namespace {

int fail(gama_engine* e, const std::string& message)
{
	e->error = message;
	return GAMA_ERR_ENGINE;
}

std::string voicePath(const gama_engine* e, int voice)
{
	return e->dataDir + "/voice/english/5_" + e->voices[voice];
}

bool fileExists(const std::string& path)
{
	std::FILE* f = std::fopen(path.c_str(), "rb");
	if (!f) return false;
	std::fclose(f);
	return true;
}

// Read one parameter from a data file, as the engine would read it.
double readValue(const GS::ConfigurationData& data, const gama_param_info& p)
{
	if (std::strcmp(p.key, "constant_radius_mouth_impedance") == 0) {
		return data.value<bool>(p.key) ? 1.0 : 0.0;
	}
	if (p.kind == GAMA_PARAM_SWITCH) {
		return data.value<int>(p.key) != 0 ? 1.0 : 0.0;
	}
	return data.value<double>(p.key);
}

// Give a parameter to the tube's data, as the data file would have written it.
void putValue(GS::ConfigurationData& data, const gama_param_info& p, double value)
{
	if (std::strcmp(p.key, "constant_radius_mouth_impedance") == 0) {
		data.put<bool>(p.key, value != 0.0);
	} else {
		// A whole number, for the keys the engine reads as int, prints as one.
		data.put<double>(p.key, value);
	}
}

// Load a voice into fresh objects, and only then replace the current ones, so that a
// voice which fails to load changes nothing.
void loadVoice(gama_engine* e, int voice)
{
	auto index = std::make_unique<GS::Index>(voicePath(e, voice));
	auto model = std::make_unique<GS::VTMControlModel::Model>();
	model->load(*index);
	auto controller = std::make_unique<GS::VTMControlModel::Controller>(*index, *model);
	const Configuration& config = controller->vtmControlModelConfiguration();
	auto tubeData = std::make_unique<GS::ConfigurationData>(index->entry("vtm_file"));
	tubeData->insert(*config.variantData);

	const GS::ConfigurationData control(index->entry("vtm_control_model_file"));
	std::vector<double> fileValues(kParamCount, 0.0);
	for (int i = 0; i < kParamCount; ++i) {
		const gama_param_info& p = kParams[i];
		if (std::strcmp(p.file, "control") == 0) {
			fileValues[i] = readValue(control, p);
		} else {
			fileValues[i] = readValue(*tubeData, p);
		}
	}

	// In this order: the Controller refers to the Model and the Index.
	e->controller.reset();
	e->model.reset();
	e->index = std::move(index);
	e->model = std::move(model);
	e->controller = std::move(controller);
	e->tubeData = std::move(tubeData);

	// The voice file's values replace the voice parameters, and nothing else changes.
	if (e->values.empty()) {
		e->values = fileValues;
	} else {
		for (int i = 0; i < kParamCount; ++i) {
			if (std::strcmp(kParams[i].file, "voice") == 0) e->values[i] = fileValues[i];
		}
	}
	e->fileValues = std::move(fileValues);
	e->voice = voice;
}

// Write the values into the Controller's configuration, before the rules run.
void applyControl(gama_engine* e, double tempo)
{
	const Index& x = idx();
	const std::vector<double>& v = e->values;
	Configuration& c = e->controller->vtmControlModelConfiguration();
	c.tempo = tempo;
	c.initialPitch = v[x.initialPitch];
	c.pitchOffset = v[x.pitchOffset] + e->pitch;
	c.driftDeviation = v[x.driftDeviation];
	c.driftLowpassCutoff = v[x.driftCutoff];
	c.intonationFactor = v[x.intonationFactor];
	c.microIntonation = v[x.micro] != 0.0;
	c.macroIntonation = v[x.macro] != 0.0;
	c.smoothIntonation = v[x.smooth] != 0.0;
	c.intonationDrift = v[x.drift] != 0.0 && !e->deterministic;
	c.randomIntonation = v[x.random] != 0.0 && !e->deterministic;
	const unsigned int period = static_cast<unsigned int>(v[x.period]);
	if (c.controlPeriod != period) {
		c.controlPeriod = period;
		c.controlRate = 1000.0 / period;
		e->controller->eventList().setControlPeriod(static_cast<int>(period));
	}
	// initUtterance reads this one from its own data.
	e->controller->vtmConfigData().put<double>("reference_glottal_pitch", v[x.glottalPitch]);
}

// The tube's data: the files' values, with what the user has changed. A value left
// alone stays as the file wrote it, so the tube is the one upstream builds.
GS::ConfigurationData tubeConfig(const gama_engine* e)
{
	GS::ConfigurationData data(*e->tubeData);
	for (int i = 0; i < kParamCount; ++i) {
		const gama_param_info& p = kParams[i];
		if (std::strcmp(p.file, "control") != 0 && e->values[i] != e->fileValues[i]) {
			putValue(data, p, e->values[i]);
		}
	}
	return data;
}

// Rule 10. Returns the reason, or nullptr if the values may stand together.
const char* sharedLimitBroken(const std::vector<double>& v)
{
	const Index& x = idx();
	if (v[x.tnMin] > v[x.tnMax]) return "The pulse fall time minimum may not pass the maximum.";
	if (v[x.tp] + v[x.tnMax] > 100.0) return "Pulse rise time and fall time maximum together may not pass 100.";
	// VocalTractModel5::initializeSynthesizer's rate, with Util::speedOfSound.
	const double length = v[x.length] + v[x.lengthOffset];
	if (length <= 0.0) return "The tract length and its offset must leave a positive length.";
	const double rate = (331.4 + 0.6 * v[x.temperature]) * 30.0 * 100.0 / length;
	if (rate < kMinInternalRate) return "That tract is too long for this tube at this temperature.";
	if (rate > kMaxInternalRate) return "That tract is too short for this tube at this temperature.";
	return nullptr;
}

bool validValue(const gama_param_info& p, double value)
{
	if (!(value >= p.min && value <= p.max)) return false;  // also refuses NaN
	switch (p.kind) {
	case GAMA_PARAM_SWITCH:
		return value == 0.0 || value == 1.0;
	case GAMA_PARAM_CHOICE:
		for (int k = 0; k < p.choice_count; ++k) {
			if (p.choice_values[k] == value) return true;
		}
		return false;
	default:
		return true;
	}
}

// ---- Loudness levelling -----------------------------------------------------
//
// Carried over from gnuspeech_api.cpp (GnuspeechSA-NVDA docs/12, docs/13). The measure
// is IEC 61672 A-weighting, then the mean power of the 20 ms frames within 30 dB of the
// loudest. The filter is the analogue prototype through the bilinear transform without
// prewarping, built as six first-order sections and normalised to 0 dB at 1 kHz.

struct Section {
	double b0, b1, a1;  // y[n] = b0 x[n] + b1 x[n-1] - a1 y[n-1]
};

std::vector<Section> aWeighting(double fs)
{
	const double pi = 3.14159265358979323846;
	const double w1 = 2 * pi * 20.598997, w2 = 2 * pi * 107.65265;
	const double w3 = 2 * pi * 737.86223, w4 = 2 * pi * 12194.217;
	const double k = 2 * fs;
	// s / (s + w) and 1 / (s + w) with s = k (1 - z^-1) / (1 + z^-1).
	auto highpass = [k](double w) { return Section{ k / (k + w), -k / (k + w), (w - k) / (k + w) }; };
	auto lowpass = [k](double w) { return Section{ 1 / (k + w), 1 / (k + w), (w - k) / (k + w) }; };
	std::vector<Section> sections = { highpass(w1), highpass(w1), highpass(w2), highpass(w3), lowpass(w4), lowpass(w4) };

	// |H| at 1 kHz, from each section's response at z = e^{j omega}.
	const double omega = 2 * pi * 1000.0 / fs;
	double magnitude = 1.0;
	for (const Section& q : sections) {
		const double nr = q.b0 + q.b1 * std::cos(omega), ni = -q.b1 * std::sin(omega);
		const double dr = 1 + q.a1 * std::cos(omega), di = -q.a1 * std::sin(omega);
		magnitude *= std::sqrt((nr * nr + ni * ni) / (dr * dr + di * di));
	}
	sections[0].b0 /= magnitude;
	sections[0].b1 /= magnitude;
	return sections;
}

std::vector<double> aWeighted(const std::vector<float>& x, double fs)
{
	std::vector<double> y(x.begin(), x.end());
	for (const Section& q : aWeighting(fs)) {
		double x1 = 0.0, y1 = 0.0;
		for (double& v : y) {
			const double out = q.b0 * v + q.b1 * x1 - q.a1 * y1;
			x1 = v;
			y1 = out;
			v = out;
		}
	}
	return y;
}

// The A-weighted level of active speech, in dB relative to full scale (1.0). Returns
// false if there is no sound to measure.
bool activeLevelDb(const std::vector<float>& x, double fs, double* level)
{
	const std::vector<double> y = aWeighted(x, fs);
	const size_t w = static_cast<size_t>(0.02 * fs);
	const size_t frames = w ? y.size() / w : 0;
	if (frames == 0) return false;
	std::vector<double> power(frames, 0.0);
	double loudest = 0.0;
	for (size_t f = 0; f < frames; ++f) {
		double sum = 0.0;
		for (size_t i = f * w; i < (f + 1) * w; ++i) sum += y[i] * y[i];
		power[f] = sum / w;
		if (power[f] > loudest) loudest = power[f];
	}
	if (!(loudest > 0.0)) return false;
	double sum = 0.0;
	size_t active = 0;
	for (double p : power) {
		if (p > loudest * 1e-3) {
			sum += p;
			++active;
		}
	}
	*level = 10.0 * std::log10(sum / active);
	return true;
}

// Brings every peak above `ceiling` down to it, with a gain that is smooth and reaches
// no further than 2 * half samples from the peak. The gain at n is the mean, over m
// within half of n, of the minimum over the samples within half of m of what each
// needs. Every such window holds n itself, so the gain at n never exceeds what n needs:
// no peak gets through, and away from peaks the gain is exactly 1.
void limitPeaks(std::vector<float>& y, float ceiling, size_t half)
{
	const size_t n = y.size();
	std::vector<double> least(n, 1.0);
	bool any = false;
	for (size_t i = 0; i < n; ++i) {
		const double a = std::fabs(y[i]);
		if (a > ceiling) {
			any = true;
			const double need = ceiling / a;
			const size_t lo = i > half ? i - half : 0, hi = std::min(n - 1, i + half);
			for (size_t m = lo; m <= hi; ++m) least[m] = std::min(least[m], need);
		}
	}
	if (!any) return;
	std::vector<double> prefix(n + 1, 0.0);
	for (size_t i = 0; i < n; ++i) prefix[i + 1] = prefix[i] + least[i];
	for (size_t i = 0; i < n; ++i) {
		const size_t lo = i > half ? i - half : 0, hi = std::min(n - 1, i + half);
		const double gain = (prefix[hi + 1] - prefix[lo]) / static_cast<double>(hi + 1 - lo);
		if (gain < 1.0) {
			const float v = static_cast<float>(y[i] * gain);
			y[i] = std::max(-ceiling, std::min(ceiling, v));  // rounding only
		}
	}
}

constexpr double kVoicedDb = 57.0;    // glottal volume counted as full voicing
constexpr double kMaxSwingDb = 12.0;  // no period is moved further than this from the median
constexpr double kWindowS = 0.03;     // the level is measured over this much

// Track column positions: the rules' parameters, in artic.xml's order.
constexpr size_t kPitchColumn = 0, kGlotVolColumn = 1, kAspVolColumn = 2, kFricVolColumn = 3;

// x times a gain given in dB at each control line, in a straight line (in dB) from one
// line to the next, sample by sample.
void applyLineGains(std::vector<float>& x, double period, const std::vector<double>& gain)
{
	const size_t n = gain.size();
	for (size_t i = 0; i < x.size(); ++i) {
		const double t = i / period;
		const size_t k = static_cast<size_t>(t);
		const double db = k + 1 >= n ? gain[n - 1] : gain[k] + (gain[k + 1] - gain[k]) * (t - k);
		x[i] = static_cast<float>(x[i] * std::pow(10.0, db / 20.0));
	}
}

// Where the engine voices at full strength, each control period is brought to one
// A-weighted level, measured over the 30 ms around it. A period whose 30 ms would reach
// outside its voiced stretch takes the level of the nearest one that does not, so that
// a quiet consonant beside a vowel does not lift the vowel's edge. Between voiced
// stretches the gain in dB goes in a straight line, so a consonant keeps its level
// relative to its neighbours.
void levelVoiced(std::vector<float>& x, double fs, const std::vector<std::vector<float>>& track, double controlRate)
{
	const size_t n = track.size();
	const double period = fs / controlRate;  // samples per control line
	const std::vector<double> y = aWeighted(x, fs);
	std::vector<double> energy(y.size() + 1, 0.0);
	for (size_t i = 0; i < y.size(); ++i) energy[i + 1] = energy[i] + y[i] * y[i];
	const size_t half = static_cast<size_t>(kWindowS / 2 * fs);
	auto levelAt = [&](size_t k) {
		const size_t c = std::min(y.size(), static_cast<size_t>(std::lround(k * period)));
		const size_t lo = c > half ? c - half : 0, hi = std::min(y.size(), c + half);
		if (hi <= lo) return -200.0;
		return 10.0 * std::log10(std::max((energy[hi] - energy[lo]) / (hi - lo), 1e-20));
	};
	auto voiced = [&](size_t k) { return track[k][kGlotVolColumn] >= kVoicedDb; };

	// The gain in dB of each voiced control line; NaN elsewhere.
	const size_t edge = static_cast<size_t>(std::ceil(kWindowS / 2 * controlRate));
	std::vector<double> gain(n, std::nan(""));
	std::vector<double> voicedGains;
	for (size_t k = 0; k < n;) {
		if (!voiced(k)) {
			++k;
			continue;
		}
		size_t j = k;
		while (j < n && voiced(j)) ++j;
		if (j - k > 2 * edge) {
			std::vector<double> level(j - k);
			for (size_t m = k + edge; m < j - edge; ++m) level[m - k] = levelAt(m);
			for (size_t m = k; m < j; ++m) {
				const size_t src = std::min(std::max(m, k + edge), j - 1 - edge);
				gain[m] = -level[src - k];
			}
		} else {
			double loudest = -200.0;
			for (size_t m = k; m < j; ++m) loudest = std::max(loudest, levelAt(m));
			for (size_t m = k; m < j; ++m) gain[m] = -loudest;
		}
		for (size_t m = k; m < j; ++m) voicedGains.push_back(gain[m]);
		k = j;
	}
	if (voicedGains.empty()) return;

	// No line more than kMaxSwingDb from the median, then the gaps filled.
	std::nth_element(voicedGains.begin(), voicedGains.begin() + voicedGains.size() / 2, voicedGains.end());
	const double median = voicedGains[voicedGains.size() / 2];
	size_t last = n;  // the last voiced line seen
	for (size_t k = 0; k < n; ++k) {
		if (std::isnan(gain[k])) continue;
		gain[k] = std::min(median + kMaxSwingDb, std::max(median - kMaxSwingDb, gain[k]));
		if (last == n) {
			for (size_t m = 0; m < k; ++m) gain[m] = gain[k];
		} else {
			for (size_t m = last + 1; m < k; ++m) {
				gain[m] = gain[last] + (gain[k] - gain[last]) * (m - last) / static_cast<double>(k - last);
			}
		}
		last = k;
	}
	for (size_t m = last + 1; m < n; ++m) gain[m] = gain[last];
	applyLineGains(x, period, gain);
}

// Noise against voice across pitch. The tube's voiced sound moves with the pitch, and
// its noise sources do not, so levelling to the voice moves every s and f as the pitch
// moves. Wherever the engine makes noise without voicing, the noise is moved by this
// much per semitone from the voice's own pitch. Measured for model 5 in docs/10.
constexpr double kNoiseDbPerSemitone = 0.80;

void balanceNoise(std::vector<float>& x, double fs, const std::vector<std::vector<float>>& track, double controlRate,
		const std::vector<double>& semitones)
{
	const size_t n = track.size();
	std::vector<double> gain(n, 0.0);
	bool any = false;
	for (size_t k = 0; k < n; ++k) {
		if (track[k][kAspVolColumn] <= 0.0f && track[k][kFricVolColumn] <= 0.0f) continue;
		const double unvoiced = std::min(1.0, std::max(0.0, (kVoicedDb - track[k][kGlotVolColumn]) / 27.0));
		gain[k] = unvoiced * kNoiseDbPerSemitone * semitones[k];
		any = any || gain[k] != 0.0;
	}
	if (any) applyLineGains(x, fs / controlRate, gain);
}

// The end of an utterance. SampleRateConverter::flushBuffer pads with zeros, and where the
// tube's output has not settled to zero, that step goes through the output differentiator
// and makes a tick, up to -35 dBFS, on about 22 % of the corpus, always within the last
// 5 ms (tools/measure/end_tick.py, docs/10).
constexpr double kEndTickMs = 6.0;

// The rules: the track of one utterance, at the tempo set, or lower if the engine
// refuses it (rule 11).
void makeTrack(gama_engine* e, const std::string& phoneticString)
{
	const double wanted = e->values[idx().tempo];
	double tempo = wanted;
	for (int attempt = 0;; ++attempt) {
		applyControl(e, tempo);
		try {
			e->controller->synthesizePhoneticStringToFile(phoneticString, nullptr, nullptr);
			e->spokenTempo = tempo;
			return;
		} catch (const std::exception& ex) {
			const bool tooSmall = std::strstr(ex.what(), "too small") != nullptr;
			if (!tooSmall || attempt == 8 || tempo <= 1.0) throw;
			tempo = std::max(1.0, tempo * 0.8);
		}
	}
}

// The rules and the tube, from a phonetic string (gama_speak and gama_speak_phonetic
// share everything after the text parser).
int speakPhonetic(gama_engine* e, const std::string& phoneticString)
{
	makeTrack(e, phoneticString);
	e->track = e->controller->vtmParameterList();
	const Configuration& config = e->controller->vtmControlModelConfiguration();
	e->trackRate = config.controlRate;

	const GS::ConfigurationData data = tubeConfig(e);
	std::unique_ptr<GS::VTM::VocalTractModel> vtm = GS::VTM::VocalTractModel::getInstance(data);
	e->sampleRate = static_cast<int>(vtm->outputSampleRate());

	// Controller::synthesize.
	if (!e->track.empty()) {
		std::vector<std::vector<float>> list = e->track;
		list.push_back(list.back());
		const unsigned int controlSteps = static_cast<unsigned int>(std::rint(vtm->internalSampleRate() / config.controlRate));
		const float coef = 1.0f / controlSteps;
		const size_t numParam = e->model->parameterList().size();
		std::vector<float> current(numParam), delta(numParam);
		for (size_t i = 1, size = list.size(); i < size; ++i) {
			for (size_t j = 0; j < numParam; ++j) {
				current[j] = list[i - 1][j];
				delta[j] = (list[i][j] - current[j]) * coef;
			}
			for (unsigned int j = 0; j < controlSteps; ++j) {
				vtm->setAllParameters(current);
				vtm->execSynthesisStep();
				for (size_t k = 0; k < numParam; ++k) current[k] += delta[k];
			}
		}
	}
	vtm->finishSynthesis();

	// Controller::writeOutputToBuffer. The scale is 0 for silence.
	const std::vector<float>& audio = vtm->outputBuffer();
	const float scale = GS::VTM::Util::calculateOutputScale(audio);
	std::vector<float> buffer(audio.size());
	for (size_t i = 0; i < audio.size(); ++i) buffer[i] = audio[i] * scale;
	if (scale == 0.0f) {
		e->samples.assign(buffer.size(), 0);
		return GAMA_OK;
	}

	// Levelling. The trimming below still looks at the engine's own output, so an
	// utterance has the same length in every mode.
	std::vector<float> levelled;
	const std::vector<float>* out = &buffer;
	if ((e->levelMode == GAMA_LEVEL_LOUDNESS || e->levelMode == GAMA_LEVEL_CONSTANT) && !e->track.empty()) {
		levelled = buffer;
		const Index& x = idx();
		const double own = e->fileValues[x.pitchOffset] + e->fileValues[x.glottalPitch];
		const double moved = e->values[x.pitchOffset] + e->values[x.glottalPitch] + e->pitch - own;
		std::vector<double> semitones(e->track.size(), moved);
		if (e->levelMode == GAMA_LEVEL_CONSTANT) {
			for (size_t k = 0; k < semitones.size(); ++k) semitones[k] = e->track[k][kPitchColumn] - own;
		}
		balanceNoise(levelled, e->sampleRate, e->track, config.controlRate, semitones);
		if (e->levelMode == GAMA_LEVEL_CONSTANT) levelVoiced(levelled, e->sampleRate, e->track, config.controlRate);
		double level = 0.0;
		if (activeLevelDb(levelled, e->sampleRate, &level)) {
			const float g = static_cast<float>(std::pow(10.0, (e->levelTarget - level) / 20.0));
			for (float& v : levelled) v *= g;
			limitPeaks(levelled, 0.95f, static_cast<size_t>(0.0025 * e->sampleRate));
			out = &levelled;
		}
	}

	// The tick at the very end (rule 12) is not sound to keep, or to trim up to.
	const size_t tick = std::min(buffer.size(), static_cast<size_t>(kEndTickMs * e->sampleRate / 1000.0));

	// Trimming (rule 7): the first and last sample above the threshold in the engine's
	// own output, and at most the requested silence around them.
	size_t begin = 0, end = buffer.size();
	if (e->trimLeadMs >= 0 || e->trimTrailMs >= 0) {
		const float threshold = std::pow(10.0f, GAMA_TRIM_THRESHOLD_DBFS / 20.0f);
		const size_t searched = buffer.size() - tick;
		size_t first = 0;
		while (first < searched && std::fabs(buffer[first]) <= threshold) ++first;
		if (first < searched) {
			size_t last = searched - 1;
			while (last > first && std::fabs(buffer[last]) <= threshold) --last;
			const double perMs = e->sampleRate / 1000.0;
			if (e->trimLeadMs >= 0) {
				const size_t keep = static_cast<size_t>(e->trimLeadMs * perMs);
				begin = first > keep ? first - keep : 0;
			}
			if (e->trimTrailMs >= 0) {
				const size_t keep = static_cast<size_t>(e->trimTrailMs * perMs);
				end = (buffer.size() - 1 - last > keep) ? last + 1 + keep : buffer.size();
			}
		}
	}

	// WAVEFileWriter::writeSample: round(sample * 32767.0f), in float. The gain is
	// applied in float first; at 1.0f it changes nothing.
	const float gain = static_cast<float>(e->gain);
	e->samples.resize(end - begin);
	for (size_t i = begin; i < end; ++i) {
		const float s = (*out)[i] * gain;
		int v = static_cast<int>(std::round(s * kSampleScale));
		if (v > 32767) v = 32767;
		else if (v < -32768) v = -32768;
		e->samples[i - begin] = static_cast<int16_t>(v);
	}

	// Rule 12. As upstream makes it only in its own mode, which the golden traces hold to.
	const bool upstream = e->levelMode == GAMA_LEVEL_PEAK && e->trimLeadMs < 0 && e->trimTrailMs < 0;
	if (!upstream && end == buffer.size()) {
		const size_t kept = end - begin;
		for (size_t i = kept - std::min(kept, tick); i < kept; ++i) e->samples[i] = 0;
	}
	return GAMA_OK;
}

// Start an utterance: drop the old one, and run fn with the exceptions turned into
// GAMA_ERR_ENGINE.
template<typename F>
int speakWith(gama_engine* e, const char* input, F fn)
{
	if (!e) return GAMA_ERR_NULL;
	e->samples.clear();
	e->readPos = 0;
	e->error.clear();
	if (!input) return GAMA_ERR_NULL;
	try {
		return fn();
	} catch (const std::exception& ex) {
		e->samples.clear();
		return fail(e, ex.what());
	} catch (...) {
		e->samples.clear();
		return fail(e, "unknown exception while speaking");
	}
}

} // namespace

extern "C" {

GAMA_API int gama_api_version(void)
{
	return GAMA_API_VERSION;
}

GAMA_API gama_engine* gama_create(const char* data_dir, char* err, size_t err_size)
{
	std::string message;
	if (!data_dir) {
		message = "data_dir is NULL";
	} else {
		try {
			std::unique_ptr<gama_engine> e(new gama_engine());
			e->dataDir = data_dir;
			for (const char* name : kVoiceNames) {
				if (fileExists(e->dataDir + "/voice/english/5_" + name + "/_index.txt")) e->voices.push_back(name);
			}
			if (e->voices.empty()) {
				message = "no model 5 voice in " + e->dataDir + "/voice/english";
			} else {
				loadVoice(e.get(), 0);
				e->parserIndex = std::make_unique<GS::Index>(voicePath(e.get(), 0));
				e->textParser = GS::TextParser::TextParser::getInstance(
						*e->parserIndex, GS::VTMControlModel::PhoneticStringFormat::gnuspeech);
				e->sampleRate = static_cast<int>(e->values[idx().outputRate]);
				return e.release();
			}
		} catch (const std::exception& ex) {
			message = ex.what();
		} catch (...) {
			message = "unknown exception while loading the engine";
		}
	}
	if (err && err_size > 0) {
		std::snprintf(err, err_size, "%s", message.c_str());
	}
	return nullptr;
}

GAMA_API void gama_destroy(gama_engine* e)
{
	delete e;
}

GAMA_API const char* gama_last_error(const gama_engine* e)
{
	return e ? e->error.c_str() : nullptr;
}

GAMA_API int gama_voice_count(const gama_engine* e)
{
	return e ? static_cast<int>(e->voices.size()) : 0;
}

GAMA_API const char* gama_voice_name(const gama_engine* e, int i)
{
	if (!e || i < 0 || i >= static_cast<int>(e->voices.size())) return nullptr;
	return e->voices[i].c_str();
}

GAMA_API int gama_voice(const gama_engine* e)
{
	return e ? e->voice : -1;
}

GAMA_API int gama_set_voice(gama_engine* e, int i)
{
	if (!e) return GAMA_ERR_NULL;
	if (i < 0 || i >= static_cast<int>(e->voices.size())) return GAMA_ERR_RANGE;
	if (i == e->voice) return GAMA_OK;
	try {
		loadVoice(e, i);
	} catch (const std::exception& ex) {
		return fail(e, ex.what());
	} catch (...) {
		return fail(e, "unknown exception while loading a voice");
	}
	return GAMA_OK;
}

GAMA_API int gama_set_rate(gama_engine* e, double tempo)
{
	return gama_set_param(e, idx().tempo, tempo);
}

GAMA_API double gama_rate(const gama_engine* e)
{
	return e ? e->values[idx().tempo] : 0.0;
}

GAMA_API double gama_spoken_tempo(const gama_engine* e)
{
	return e ? e->spokenTempo : 0.0;
}

GAMA_API int gama_set_pitch(gama_engine* e, double semitones)
{
	if (!e) return GAMA_ERR_NULL;
	if (!(semitones >= -24.0 && semitones <= 24.0)) return GAMA_ERR_RANGE;
	e->pitch = semitones;
	return GAMA_OK;
}

GAMA_API double gama_pitch(const gama_engine* e)
{
	return e ? e->pitch : 0.0;
}

GAMA_API int gama_set_volume(gama_engine* e, double gain)
{
	if (!e) return GAMA_ERR_NULL;
	if (!(gain >= 0.0 && gain <= 1.0)) return GAMA_ERR_RANGE;
	e->gain = gain;
	return GAMA_OK;
}

GAMA_API double gama_volume(const gama_engine* e)
{
	return e ? e->gain : 0.0;
}

GAMA_API int gama_set_deterministic(gama_engine* e, int on)
{
	if (!e) return GAMA_ERR_NULL;
	e->deterministic = on != 0;
	return GAMA_OK;
}

GAMA_API int gama_deterministic(const gama_engine* e)
{
	return e && e->deterministic ? 1 : 0;
}

GAMA_API int gama_set_trim(gama_engine* e, int lead_ms, int trail_ms)
{
	if (!e) return GAMA_ERR_NULL;
	if (lead_ms < -1 || lead_ms > 1000 || trail_ms < -1 || trail_ms > 1000) return GAMA_ERR_RANGE;
	e->trimLeadMs = lead_ms;
	e->trimTrailMs = trail_ms;
	return GAMA_OK;
}

GAMA_API void gama_trim(const gama_engine* e, int* lead_ms, int* trail_ms)
{
	if (!e) return;
	if (lead_ms) *lead_ms = e->trimLeadMs;
	if (trail_ms) *trail_ms = e->trimTrailMs;
}

GAMA_API int gama_set_leveling(gama_engine* e, int mode, double target_db)
{
	if (!e) return GAMA_ERR_NULL;
	if ((mode != GAMA_LEVEL_PEAK && mode != GAMA_LEVEL_LOUDNESS && mode != GAMA_LEVEL_CONSTANT) ||
			!(target_db >= -40.0 && target_db <= -10.0)) {
		return GAMA_ERR_RANGE;
	}
	e->levelMode = mode;
	e->levelTarget = target_db;
	return GAMA_OK;
}

GAMA_API void gama_leveling(const gama_engine* e, int* mode, double* target_db)
{
	if (!e) return;
	if (mode) *mode = e->levelMode;
	if (target_db) *target_db = e->levelTarget;
}

GAMA_API int gama_param_count(void)
{
	return kParamCount;
}

GAMA_API const gama_param_info* gama_param_describe(int i)
{
	return i >= 0 && i < kParamCount ? &kParams[i] : nullptr;
}

GAMA_API int gama_param_index(const char* key)
{
	return key ? paramIndex(key) : -1;
}

GAMA_API int gama_get_param(const gama_engine* e, int i, double* value)
{
	if (!e || !value) return GAMA_ERR_NULL;
	if (i < 0 || i >= kParamCount) return GAMA_ERR_RANGE;
	*value = e->values[i];
	return GAMA_OK;
}

GAMA_API int gama_set_param(gama_engine* e, int i, double value)
{
	if (!e) return GAMA_ERR_NULL;
	e->error.clear();
	if (i < 0 || i >= kParamCount || !validValue(kParams[i], value)) return GAMA_ERR_RANGE;
	std::vector<double> next = e->values;
	next[i] = value;
	if (const char* why = sharedLimitBroken(next)) {
		e->error = why;
		return GAMA_ERR_RANGE;
	}
	e->values[i] = value;
	return GAMA_OK;
}

GAMA_API int gama_param_default(const gama_engine* e, int i, double* value)
{
	if (!e || !value) return GAMA_ERR_NULL;
	if (i < 0 || i >= kParamCount) return GAMA_ERR_RANGE;
	*value = e->fileValues[i];
	return GAMA_OK;
}

GAMA_API int gama_reset_params(gama_engine* e)
{
	if (!e) return GAMA_ERR_NULL;
	e->values = e->fileValues;
	return GAMA_OK;
}

GAMA_API int gama_speak(gama_engine* e, const char* text)
{
	return speakWith(e, text, [&]() {
		return speakPhonetic(e, e->textParser->parse(safeText(text).c_str()));
	});
}

GAMA_API int gama_speak_phonetic(gama_engine* e, const char* phonetic)
{
	return speakWith(e, phonetic, [&]() {
		return speakPhonetic(e, safePhonetic(phonetic));
	});
}

GAMA_API size_t gama_text_to_phonetic(gama_engine* e, const char* text, char* out, size_t out_size)
{
	if (out && out_size > 0) out[0] = '\0';
	if (!e) return 0;
	e->error.clear();
	if (!text) {
		e->error = "text is NULL";
		return 0;
	}
	try {
		return copyOut(e->textParser->parse(safeText(text).c_str()), out, out_size);
	} catch (const std::exception& ex) {
		e->error = ex.what();
	} catch (...) {
		e->error = "unknown exception while parsing text";
	}
	return 0;
}

GAMA_API size_t gama_track(const gama_engine* e, char* out, size_t out_size)
{
	if (out && out_size > 0) out[0] = '\0';
	if (!e) return 0;
	// Controller::writeVTMParameterFile.
	std::ostringstream s;
	for (const std::vector<float>& line : e->track) {
		for (size_t i = 0; i < line.size(); ++i) {
			if (i) s << ' ';
			s << line[i];
		}
		s << '\n';
	}
	return copyOut(s.str(), out, out_size);
}

GAMA_API size_t gama_read(gama_engine* e, int16_t* out, size_t n)
{
	if (!e || !out) return 0;
	const size_t left = e->samples.size() - e->readPos;
	const size_t count = n < left ? n : left;
	if (count > 0) {
		std::memcpy(out, e->samples.data() + e->readPos, count * sizeof(int16_t));
		e->readPos += count;
	}
	return count;
}

GAMA_API size_t gama_pending(const gama_engine* e)
{
	return e ? e->samples.size() - e->readPos : 0;
}

GAMA_API void gama_stop(gama_engine* e)
{
	if (!e) return;
	e->samples.clear();
	e->readPos = 0;
}

GAMA_API int gama_sample_rate(const gama_engine* e)
{
	return e ? e->sampleRate : 0;
}

} // extern "C"
