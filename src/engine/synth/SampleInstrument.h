#pragma once

#include "Instrument.h"
#include "SampleSynth.h"

#include <memory>

namespace daw
{

class SampleInstrument final : public Instrument
{
public:
    SampleInstrument (const juce::String& wavPath, int rootNote);

    bool isValid() const override { return synth != nullptr; }
    juce::String getLoadError() const override { return loadError; }

    void setCurrentPlaybackSampleRate (double sampleRate) override;
    void renderNextBlock (juce::AudioBuffer<float>& buffer, const juce::MidiBuffer& midi,
                           int startSample, int numSamples) override;

private:
    std::unique_ptr<SampleSynth> synth;
    juce::String loadError;
};

} // namespace daw
