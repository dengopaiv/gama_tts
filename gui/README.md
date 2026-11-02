# The desktop GUI

`gama_gui.cpp`, one file: C++17 and wxWidgets, over the C API in `../api` and nothing else of the engine. **Checked from outside through MSAA, and not yet used with NVDA speaking.**

```sh
cmake -S . -B build-gui -G "Visual Studio 18 2026" -A x64 \
      -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake -DVCPKG_TARGET_TRIPLET=x64-windows
cmake --build build-gui --config Release --target gama_gui
build-gui/Release/gama_gui.exe
```

Without wxWidgets, CMake says so and builds the rest without it. `--smoke` builds the window hidden, renders one utterance and exits 0 if it came back, which `ctest` runs. `--data <folder>` says where the data is.

**Why it is built the way it is:**

- **Two engine handles:** the window's, which holds the settings, and the worker thread's, which renders each job from a copy of them. So the window never stops responding.
- **Two C runtimes:** vcpkg's wxWidgets uses the DLL runtime and the engine the static one. Only C crosses between them, through `gama_api.dll`.
- **Standard controls only,** and numbers are `wxSpinCtrlDouble`. Every control, and the edit inside each spin control, is named explicitly through a `wxAccessible` override, since the inner edit would otherwise have no name.
- **The validator is removed from those inner edits.** It swallows keys silently: [docs/10](../docs/10-model5-api-gui-addon.md), section 8.
- **All the categories are built at start-up, and shown one at a time,** so nothing is destroyed under the focus, and hidden fields are out of the Tab order.

How to use it: [docs/11](../docs/11-using-it.md). The outside check: `tests/gui/gui_check.py`. It is adapted from the Gnuspeech GUI: [NOTICE.md](../NOTICE.md).
