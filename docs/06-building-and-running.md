# 6. Building and running

Upstream documents only Linux (`gama_tts/INSTALL.txt`: GCC 12.2 or Clang
14.0.6, CMake 3.25). This chapter records what was needed on **Windows 11
x64** on 2026-10-16. Every build here is 64-bit; no 32-bit build was made or
is wanted. All builds went to a scratch directory outside the repository, so
the tree was not touched.

Tools: CMake 4.4.4, Ninja 1.12.1, MinGW-w64 GCC 16.2.0 (MSYS2 UCRT64),
Visual Studio Community 2026 with MSVC 19.51.36260.

## With MinGW-w64 GCC: works as is

```sh
export PATH=/c/msys64/ucrt64/bin:$PATH
cmake -S gama_tts -B build-gcc -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=g++
cmake --build build-gcc
```

- It builds with 18 warnings and gives `gama_tts.exe` (1.18 MB) and `libgamatts.a`.
- The program links `libstdc++-6.dll` and `libgcc_s_seh-1.dll` dynamically,
  so the UCRT64 `bin` directory must be on `PATH` when it runs. Without it,
  the program exits with code 127 and **prints nothing**, which is easy to
  mistake for a synthesis failure.
- `CMakeLists.txt` sets `-std=c++17 -Wall -Wextra -march=native` only
  `if(UNIX)`. MinGW is not `UNIX` to CMake, so none of these flags is used.
  GCC 16 defaults to C++17, and the build therefore has no
  `-march=native`.

## With MSVC: works with two extra settings

Out of the box, configuring with `-A x64` and building `Release` fails with
194 errors, all of the same kind:

```
RapidXmlUtil.h(64,59): error C2039: 'string_view': is not a member of 'std'
RapidXmlUtil.h(68,7):  error C2065: 'optional': undeclared identifier
```

**Cause:** the C++17 flag is set only for `UNIX`, so MSVC compiles as C++14.
With the standard forced, five more errors appear: `M_PI` is undefined,
because MSVC's `<cmath>` defines it only with `_USE_MATH_DEFINES`. With both
settings it builds:

```sh
cmake -S gama_tts -B build-msvc -A x64 -DCMAKE_CXX_STANDARD=17 \
      "-DCMAKE_CXX_FLAGS=-DWIN32 -D_WINDOWS -EHsc -D_USE_MATH_DEFINES"
cmake --build build-msvc --config Release
```

- The result is `gama_tts.exe` (550 KB), with 8 distinct warnings: C4244 and
  C4267 (narrowing), and C4477 (a `%ld` format given a `size_t`,
  `EnglishTextParser.cpp:188`).
- Write the flags with `-` and not `/` when running from Git Bash, which
  rewrites `/D…` as a path.
- A proper fix in the source would be `set(CMAKE_CXX_STANDARD 17)` and
  `add_compile_definitions(_USE_MATH_DEFINES)` for MSVC in
  `gama_tts/CMakeLists.txt`. It is not applied: this repository is kept as
  upstream has it.

**GCC and MSVC give byte-identical output.** With randomness off, the
parameter files and WAV files of the two builds match byte for byte for
models 0, 4 and 5 ([chapter A](07-measurements.md)).

## The CRLF trap

Git for Windows with `core.autocrlf=true` checks out the data files with CRLF
line endings. GamaTTS's configuration reader then rejects the first empty
line:

```
Exception: [ConfigurationData] Error in file …/0_male/_index.txt (line 6): Space at the beginning of the line.
```

The `\r` counts as a space. The repository has no `.gitattributes`. Ways
around it:

- check out with `core.autocrlf=false` or `input`;
- export the data with LF endings:
  `git -c core.autocrlf=false archive HEAD data | tar -x -C <dir>`. A plain
  `git archive` applies the same conversion, so the `-c` matters;
- (not applied) add a `.gitattributes` with `data/** -text`, or make
  `ConfigurationData.cpp` strip `\r`.

## Running

```sh
echo "Hello world." | gama_tts tts data/voice/english/5_male out.wav
gama_tts tts -v -p params.txt data/voice/english/0_male out.wav < text.txt
gama_tts pho data/voice/english/0_male out.wav < phonetic.txt
gama_tts vtm data/voice/english/0_male params.txt out.wav
```

- `-v` prints the whole loaded database (every posture with its targets,
  every equation and evaluated value, every rule). It then prints the
  cleaned text, both parser streams, the phonetic string chunks and the
  tube's internal sample rate. That is about 6,000 lines before synthesis.
- `-p` writes the 16-parameter frames, one line per control period. `vtm`
  reads such a file back, which is how the tube can be tested on its own.
- The voice directory is chosen by path; there is no voice option.
- Every run loads the 2.3 MB dictionary first. It prints "Duplicate word"
  for 45 entries that appear twice with different parts of speech, which is
  harmless. Loading and parsing take about 145 ms before synthesis starts.

### Making runs repeatable

By default every rendering differs, because `random_intonation = 1` in
`vtm_control_model.txt` draws from `std::random_device`. `intonation_drift = 1`
has a fixed seed, so by the code it repeats (read 2026-11-02, not run). For tests, copy the voice
directory and set both to 0. Then:

- repeated runs give byte-identical files (checked with GCC and with MSVC);
- GCC and MSVC builds give byte-identical files (models 0, 4 and 5).

Model 5's voice directory has its own `vtm_control_model.txt`. Models 1–4
read `0_male`'s.

### Pitfalls

- `2_male/vtm.txt` and `3_male/vtm.txt` contain `log_parameters = false`. A
  copy of `0_male/vtm.txt` switched to `model = 2` fails with "Key
  'log_parameters' not found", because models 2 and 3 require the key and
  model 0 does not.
- The WAV is always scaled so that the loudest sample of the utterance
  reaches a fixed peak. Levels between files are therefore not comparable
  without rescaling.
