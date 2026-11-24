#pragma once

#include "Instrument.h"

#include <fluidsynth.h>

namespace daw
{

class FluidSynthInstrument final : public Instrument
{
public:
    // No-op if libfluidsynth failed to load; check getLoadError().
    explicit FluidSynthInstrument (const juce::String& sf2Path);
    ~FluidSynthInstrument() override;

    bool isValid() const override { return valid; }
    juce::String getLoadError() const override;

    void setCurrentPlaybackSampleRate (double sampleRate) override;
    void handleMidiEvent (const juce::MidiMessage& message);
    void renderNextBlock (juce::AudioBuffer<float>& buffer, const juce::MidiBuffer& midi,
                           int startSample, int numSamples) override;

private:
    juce::String sf2Path;
    fluid_settings_t* settings = nullptr;
    fluid_synth_t* synth = nullptr;
    bool valid = false;
};

} // namespace daw
