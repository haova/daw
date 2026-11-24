#pragma once

#include <juce_core/juce_core.h>

#include <fluidsynth.h>

namespace daw
{

// Lazily dlopen's libfluidsynth so it's not a hard runtime dependency.
class FluidSynthLibrary
{
public:
    static FluidSynthLibrary& get();

    bool isLoaded() const { return loaded; }
    const juce::String& getLoadError() const { return loadError; }

    fluid_settings_t* (*new_fluid_settings) (void) = nullptr;
    void (*delete_fluid_settings) (fluid_settings_t*) = nullptr;
    int (*fluid_settings_setnum) (fluid_settings_t*, const char*, double) = nullptr;
    int (*fluid_settings_setint) (fluid_settings_t*, const char*, int) = nullptr;

    fluid_synth_t* (*new_fluid_synth) (fluid_settings_t*) = nullptr;
    void (*delete_fluid_synth) (fluid_synth_t*) = nullptr;
    int (*fluid_synth_sfload) (fluid_synth_t*, const char*, int) = nullptr;
    int (*fluid_synth_noteon) (fluid_synth_t*, int, int, int) = nullptr;
    int (*fluid_synth_noteoff) (fluid_synth_t*, int, int) = nullptr;
    int (*fluid_synth_cc) (fluid_synth_t*, int, int, int) = nullptr;
    int (*fluid_synth_program_change) (fluid_synth_t*, int, int) = nullptr;
    int (*fluid_synth_pitch_bend) (fluid_synth_t*, int, int) = nullptr;
    int (*fluid_synth_channel_pressure) (fluid_synth_t*, int, int) = nullptr;
    int (*fluid_synth_key_pressure) (fluid_synth_t*, int, int, int) = nullptr;
    int (*fluid_synth_write_float) (fluid_synth_t*, int, void*, int, int, void*, int, int) = nullptr;

private:
    FluidSynthLibrary();

    void* handle = nullptr;
    bool loaded = false;
    juce::String loadError;
};

} // namespace daw
