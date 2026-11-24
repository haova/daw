#pragma once

#include <juce_audio_basics/juce_audio_basics.h>

#include <fluidsynth.h>

namespace daw
{

class FluidSynthInstrument final
{
public:
    explicit FluidSynthInstrument (const juce::String& sf2Path);
    ~FluidSynthInstrument();

    void setCurrentPlaybackSampleRate (double sampleRate);
    void handleMidiEvent (const juce::MidiMessage& message);
    void renderNextBlock (juce::AudioBuffer<float>& buffer, const juce::MidiBuffer& midi, int startSample, int numSamples);

private:
    juce::String sf2Path;
    fluid_settings_t* settings = nullptr;
    fluid_synth_t* synth = nullptr;
};

} // namespace daw
