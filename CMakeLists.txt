cmake_minimum_required(VERSION 3.22)
project(daw_engine VERSION 0.0.1 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# JUCE 9.0.6 lives in ./JUCE (not committed), override with -DJUCE_DIR
set(JUCE_DIR "${CMAKE_SOURCE_DIR}/JUCE" CACHE PATH "Path to the JUCE source tree")
add_subdirectory(${JUCE_DIR} JUCE EXCLUDE_FROM_ALL)

# libfluidsynth itself is dlopen'd at runtime, only headers are needed here
find_package(PkgConfig REQUIRED)
pkg_check_modules(FLUIDSYNTH REQUIRED fluidsynth)

juce_add_console_app(engine
    PRODUCT_NAME "engine"
    NEEDS_WEB_BROWSER FALSE
    NEEDS_CURL FALSE)

target_sources(engine PRIVATE
    src/engine/Main.cpp
    src/engine/audio/AudioEngine.cpp
    src/engine/cli/CliOptions.cpp
    src/engine/midi/MidiEvent.cpp
    src/engine/midi/MidiInputMonitor.cpp
    src/engine/synth/FluidSynthInstrument.cpp
    src/engine/synth/FluidSynthLibrary.cpp
    src/engine/synth/PianoSynth.cpp
    src/engine/synth/PianoSynthInstrument.cpp
    src/engine/synth/SampleInstrument.cpp
    src/engine/synth/SampleSynth.cpp)

target_include_directories(engine PRIVATE src/engine ${FLUIDSYNTH_INCLUDE_DIRS})

target_compile_definitions(engine PRIVATE
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0)

target_link_libraries(engine
    PRIVATE
        juce::juce_core
        juce::juce_audio_devices
        juce::juce_audio_formats
        ${CMAKE_DL_LIBS}
    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_warning_flags)
