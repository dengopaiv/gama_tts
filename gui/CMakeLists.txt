# gama_gui: the desktop GUI (docs/10). wxWidgets, over gama_api and nothing else of
# the engine.
#
# On Windows, wxWidgets comes from vcpkg, as for Tawkative and Gnuspeech's GUI:
#   cmake -S . -B build-gui -G "Visual Studio 18 2026" -A x64
#         -DCMAKE_TOOLCHAIN_FILE=%VCPKG_ROOT%/scripts/buildsystems/vcpkg.cmake
#         -DVCPKG_TARGET_TRIPLET=x64-windows
# On Linux, a system wxWidgets (libwxgtk3.2-dev) is found by CMake's module.
# Without wxWidgets the rest of the project builds as before.

find_package(wxWidgets CONFIG QUIET COMPONENTS core base)
if(TARGET wx::core)
    set(GAMA_WX_LIBS wx::core wx::base)
else()
    find_package(wxWidgets QUIET COMPONENTS core base)
    if(NOT wxWidgets_FOUND)
        message(STATUS "gama_gui: wxWidgets not found, so the GUI is not built (docs/10)")
        return()
    endif()
    add_library(gama_wx INTERFACE)
    target_include_directories(gama_wx SYSTEM INTERFACE ${wxWidgets_INCLUDE_DIRS})
    target_compile_definitions(gama_wx INTERFACE ${wxWidgets_DEFINITIONS})
    target_compile_options(gama_wx INTERFACE ${wxWidgets_CXX_FLAGS})
    target_link_directories(gama_wx INTERFACE ${wxWidgets_LIBRARY_DIRS})
    target_link_libraries(gama_wx INTERFACE ${wxWidgets_LIBRARIES})
    set(GAMA_WX_LIBS gama_wx)
endif()

add_executable(gama_gui WIN32 gama_gui.cpp)
if(WIN32)
    target_sources(gama_gui PRIVATE gama_gui.rc)
endif()
set_target_properties(gama_gui PROPERTIES
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF
    # vcpkg's wxWidgets is built against the DLL C runtime. The engine's DLL keeps its
    # static one inside; only C crosses between them.
    MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL"
    # Beside gama_api.dll, which it loads.
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}
)
target_link_libraries(gama_gui PRIVATE gama_api ${GAMA_WX_LIBS})
if(MSVC)
    target_compile_options(gama_gui PRIVATE /W4)
endif()

# Opens the window (hidden), renders "Hello world." through the worker thread and exits
# 0 if it came back with samples.
if(WIN32 OR DEFINED ENV{DISPLAY} OR DEFINED ENV{WAYLAND_DISPLAY})
    add_test(NAME gui.smoke COMMAND gama_gui --smoke --data ${CMAKE_SOURCE_DIR}/data)
endif()
