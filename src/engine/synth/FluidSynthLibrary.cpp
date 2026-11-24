#include "FluidSynthLibrary.h"

#include <dlfcn.h>

namespace daw
{

namespace
{

// Versioned SONAME first, then the dev symlink.
constexpr const char* candidateNames[] = { "libfluidsynth.so.3", "libfluidsynth.so" };

template <typename Fn>
bool resolve (void* handle, const char* name, Fn& fn)
{
    fn = reinterpret_cast<Fn> (dlsym (handle, name));
    return fn != nullptr;
}

} // namespace

FluidSynthLibrary& FluidSynthLibrary::get()
{
    static FluidSynthLibrary instance;
    return instance;
}

FluidSynthLibrary::FluidSynthLibrary()
{
    for (const auto* name : candidateNames)
    {
        handle = dlopen (name, RTLD_NOW | RTLD_GLOBAL);
        if (handle != nullptr)
            break;
    }

    if (handle == nullptr)
    {
        loadError = "could not load libfluidsynth: " + juce::String (dlerror());
        return;
    }

    bool ok = true;
    ok &= resolve (handle, "new_fluid_settings", new_fluid_settings);
    ok &= resolve (handle, "delete_fluid_settings", delete_fluid_settings);
    ok &= resolve (handle, "fluid_settings_setnum", fluid_settings_setnum);
    ok &= resolve (handle, "fluid_settings_setint", fluid_settings_setint);
    ok &= resolve (handle, "new_fluid_synth", new_fluid_synth);
    ok &= resolve (handle, "delete_fluid_synth", delete_fluid_synth);
    ok &= resolve (handle, "fluid_synth_sfload", fluid_synth_sfload);
    ok &= resolve (handle, "fluid_synth_noteon", fluid_synth_noteon);
    ok &= resolve (handle, "fluid_synth_noteoff", fluid_synth_noteoff);
    ok &= resolve (handle, "fluid_synth_cc", fluid_synth_cc);
    ok &= resolve (handle, "fluid_synth_program_change", fluid_synth_program_change);
    ok &= resolve (handle, "fluid_synth_pitch_bend", fluid_synth_pitch_bend);
    ok &= resolve (handle, "fluid_synth_channel_pressure", fluid_synth_channel_pressure);
    ok &= resolve (handle, "fluid_synth_key_pressure", fluid_synth_key_pressure);
    ok &= resolve (handle, "fluid_synth_write_float", fluid_synth_write_float);

    if (! ok)
    {
        loadError = "libfluidsynth loaded but is missing expected symbols (version mismatch?)";
        return;
    }

    loaded = true;
}

} // namespace daw
