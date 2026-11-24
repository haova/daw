#pragma once

#include <juce_audio_basics/juce_audio_basics.h>

namespace daw
{

class Instrument
{
public:
    virtual ~Instrument() = default;
    virtual bool isValid() const { return true; }
    virtual juce::String getLoadError() const { return {}; }
    virtual void setCurrentPlaybackSampleRate (double sampleRate) = 0;
    virtual void renderNextBlock (juce::AudioBuffer<float>& buffer, const juce::MidiBuffer& midi,
                                   int startSample, int numSamples) = 0;
};

} // namespace daw
