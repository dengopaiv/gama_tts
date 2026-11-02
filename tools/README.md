# Tools

| File | What it does |
|---|---|
| `golden/make_golden.py` | Makes `tests/golden/`, from the unchanged engine. It refuses to run on a changed one |
| `param_table.py` | The API's parameter table as Markdown, for `docs/11` |
| `measure/levels.py` | A-weighting, the active level, and what is voiced and what is noise. The tests and the scripts below share it |
| `measure/pitch_balance.py` | Noise consonants against the voice, as the pitch moves. It set `kNoiseDbPerSemitone` |
| `measure/end_tick.py` | How common the tick at the end of an utterance is, and how far back it reaches |
| `measure/edges.py` | Where the first and last sound of a few utterances fall |
| `measure/tail.py` | The last 100 ms of an utterance, against the rules' track |
| `measure/token_hunt.py` | Each hard token in a child process: which one kills it? It found 100 `w`. It names the API's exports, and takes the DLL and the data |
| `measure/spelled_lengths.py` | Each character's length when the engine spells it, read from the source. It sized the guard |

Each says at its top how to run it. `docs/measurements/gama5/run_all.sh` runs them all, and its output is the record of `docs/10`.

The scripts from before the API existed, which work through a probe linked to the engine, are in `docs/measurements/feasibility/`.
