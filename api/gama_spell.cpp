/* gama_spell.cpp -- how long each character gets when the engine spells it.
 *
 * Copyright 2026 dengopaiv. GPL-3.0-or-later. A file of its own because the engine's header
 * defines macros named A, B and so on, which must not reach the rest of the API.
 *
 * The list is the engine's own, in the order of letters[] in LetterToSound.cpp, whose
 * entries it spells a word with when it cannot pronounce it. The API's guard (rule 9) counts
 * with these, so that it breaks a run just before its spelling could overflow that function's
 * buffer, and leaves an ordinary URL alone (docs/10, section 5).
 */
#include "english/NumberPronunciations.h"

#include <cstring>

int gamaSpelledLength(unsigned char c)
{
	static const char* const letters[] = {
		BLANK, EXCLAMATION_POINT, DOUBLE_QUOTE, NUMBER_SIGN, DOLLAR_SIGN,
		PERCENT_SIGN, AMPERSAND, SINGLE_QUOTE, OPEN_PARENTHESIS, CLOSE_PARENTHESIS,
		ASTERISK, PLUS_SIGN, COMMA, HYPHEN, PERIOD, SLASH,
		ZERO, ONE, TWO, THREE, FOUR, FIVE, SIX, SEVEN, EIGHT, NINE,
		COLON, SEMICOLON, OPEN_ANGLE_BRACKET, EQUAL_SIGN, CLOSE_ANGLE_BRACKET,
		QUESTION_MARK, AT_SIGN,
		A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z,
		OPEN_SQUARE_BRACKET, BACKSLASH, CLOSE_SQUARE_BRACKET, CARET, UNDERSCORE,
		GRAVE_ACCENT,
		A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z,
		OPEN_BRACE, VERTICAL_BAR, CLOSE_BRACE, TILDE, UNKNOWN
	};
	if (c < ' ' || c > 0x7f) return static_cast<int>(std::strlen(UNKNOWN));
	return static_cast<int>(std::strlen(letters[c - ' ']));
}
