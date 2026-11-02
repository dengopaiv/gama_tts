# 8. Open items

What these notes do not settle, roughly in order of usefulness.

## Not measured

1. **Model 5 against model 0, by ear and by spectrum.** Model 5 is the
   default and the reason GamaTTS exists, yet chapter A only compares the
   classic tubes. Wanted: the same sentences through `0_male` and `5_male`,
   with formant tracks (Praat) and a listening note. *Partly done 2026-11-02:
   the spectral balance is in [chapter 9](09-addon-and-gui-feasibility.md), section 5,
   and listening files are in `build-listening/`. Not done: formant tracks, and
   anyone's listening note. This now decides whether an add-on is worth making.*
2. **Why the classic tube's samples drift from GnuspeechSA.** The spectrum
   matches within 0.2 dB and the length difference is explained exactly by
   the rate rounding. The phase drift in voiced speech and the mismatch in
   noise are only explained by inference. A test would be to patch a scratch
   copy of GamaTTS to use GnuspeechSA's rounded rate (20,000 Hz) and see
   whether the files become identical. Any difference that remains would
   then come from the minimum-radius change or from the order of the noise
   samples.
3. **The R8 difference in "dog".** It is attributed to the marked `d'`
   posture (r8 1.31 against 1.3). Not confirmed by switching the posture.
4. **Intonation side by side.** The pitch tracks differ by up to 22
   semitones. Plot both contours over a few sentence types (statement,
   question, continuation) to see what the 2017 intonation changes do in
   practice.
5. **The editor with NVDA.** Chapter 5 is a reading of the code. A real
   session would show which tables and fields NVDA names correctly.
6. **Model 5 at other voice sizes.** The child and baby variants have
   internal rates above 70 kHz; their speed and stability were not checked.
   *Closed 2026-11-02: about ×27 to ×52, and stable across ±24 semitones
   ([chapter 9](09-addon-and-gui-feasibility.md), sections 1 and 4). How they sound is still not known.*

## Not known

- What "GAMA" stands for.
- The origin and licence of `script/python3/impedance_at_mouth/kinsler.jpg`.
- Whether upstream (Matuda) would take the two MSVC fixes, a
  `.gitattributes` for `data/`, or a fix for the CRLF parsing.

## Possible uses here

These are only possibilities. None of them is decided, and each one is a
decision for the author.

- **A second voice for a Gnuspeech-based NVDA add-on.** Model 5 is GPL like
  the rest of Gnuspeech. It needs a C API: GamaTTS has none, and its
  interface passes C++ objects. Under this collection's direction it would
  also need a C17 rewrite of the engine. *Corrected 2026-11-02: that last sentence
  was too strong. The collection's C17 direction is for its own engines, and this one is
  Matuda's. [Chapter 9](09-addon-and-gui-feasibility.md) studies this possibility in full.*
- **A reference for articulatory study.** The model list in chapter 3 is a
  clean sequence of single changes on one tube: precision, time step, number
  of sections, then flow, radiation and glottis together. That makes it good
  teaching material for what each refinement does.
- **Upstream contributions.** The MSVC fixes in chapter 6 are small and
  self-contained. So are the fixes in `measurements/feasibility/engine-fixes.patch`
  ([chapter 9](09-addon-and-gui-feasibility.md)), for the intonation order, a division by
  zero and a trie index. The long-token overruns have no such patch yet. Nothing has been
  sent upstream.
