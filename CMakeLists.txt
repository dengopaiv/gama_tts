# The whole of this fork's additions: the engine as upstream builds it, a C API over
# it, its tests, the desktop GUI. Upstream's own builds, from gama_tts/ and so on, are
# not changed by this file. docs/10 has the record.
#
#   cmake -S . -B build-x64 -G "Visual Studio 18 2026" -A x64
#   cmake --build build-x64 --config Release
#   ctest --test-dir build-x64 -C Release --output-on-failure
#
# 64-bit only. No 32-bit build of anything is made here.
cmake_minimum_required(VERSION 3.15)
project(gama_tts_nvda C CXX)

if(CMAKE_SIZEOF_VOID_P EQUAL 4)
    message(FATAL_ERROR "32-bit builds are not made here.")
endif()

# The engine's own CMakeLists asks for an older CMake, which would switch this policy
# off inside it, and then its objects would use the dynamic runtime.
set(CMAKE_POLICY_DEFAULT_CMP0091 NEW)
# Static C runtime on MSVC, so the add-on's DLL needs nothing from NVDA's folder.
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
# The engine sets these only under UNIX; MSVC would compile it as C++14 without them.
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(MSVC)
    add_compile_definitions(_USE_MATH_DEFINES _CRT_SECURE_NO_DEPRECATE)
    add_compile_options(/EHsc /utf-8)
endif()

add_subdirectory(gama_tts)

add_library(gama_api SHARED api/gama_api.cpp api/gama_spell.cpp api/gama_api.h)
target_include_directories(gama_api
    PUBLIC api
    PRIVATE gama_tts/src gama_tts/src/text_parser gama_tts/src/vtm gama_tts/src/vtm_control_model
)
target_link_libraries(gama_api PRIVATE gamatts)
set_target_properties(gama_api PROPERTIES
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN ON
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}
)
if(MINGW)
    # Self-contained like the MSVC build: no libstdc++ or libgcc DLLs to ship.
    target_link_options(gama_api PRIVATE -static -static-libgcc -static-libstdc++)
endif()

enable_testing()

# Ranges, errors, shared limits, chunked reading, independence of engines, in C17.
add_executable(gama_api_test tests/api/api_test.c)
set_target_properties(gama_api_test PROPERTIES
    C_STANDARD 17 C_STANDARD_REQUIRED ON
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}
)
if(NOT WIN32)
    target_link_libraries(gama_api_test PRIVATE m)
endif()
target_link_libraries(gama_api_test PRIVATE gama_api)
add_test(NAME api COMMAND gama_api_test ${CMAKE_SOURCE_DIR}/data)

find_package(Python3 COMPONENTS Interpreter)
if(Python3_FOUND)
    # The API against the golden traces of the unchanged engine.
    add_test(NAME golden
        COMMAND Python3::Interpreter -I ${CMAKE_SOURCE_DIR}/tests/api/check_golden.py
                $<TARGET_FILE:gama_api> ${CMAKE_SOURCE_DIR}/data ${CMAKE_SOURCE_DIR}/tests/golden/msvc-x64.tsv)
    # Hostile text, long tokens, high tempos, each parameter at its limits.
    add_test(NAME robustness
        COMMAND Python3::Interpreter -I ${CMAKE_SOURCE_DIR}/tests/api/check_robustness.py
                $<TARGET_FILE:gama_api> ${CMAKE_SOURCE_DIR}/data)
    # The levelled modes against the measure they aim at (numpy, scipy).
    add_test(NAME leveling
        COMMAND Python3::Interpreter -I ${CMAKE_SOURCE_DIR}/tests/api/check_leveling.py
                $<TARGET_FILE:gama_api> ${CMAKE_SOURCE_DIR}/data ${CMAKE_SOURCE_DIR}/tests/golden/corpus.txt)
    if(WIN32)
        # The NVDA driver, with stand-ins for NVDA's modules.
        add_test(NAME driver
            COMMAND Python3::Interpreter -I ${CMAKE_SOURCE_DIR}/tests/nvda/test_driver.py
                    $<TARGET_FILE:gama_api> ${CMAKE_SOURCE_DIR}/data ${CMAKE_SOURCE_DIR}/tests/golden/msvc-x64.tsv)
    endif()
endif()

# The desktop GUI, built when wxWidgets is found.
option(GAMA_BUILD_GUI "Build the wxWidgets GUI in gui/ if wxWidgets is found" ON)
if(GAMA_BUILD_GUI)
    add_subdirectory(gui)
endif()
