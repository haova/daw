#pragma once

#include <juce_audio_basics/juce_audio_basics.h>

namespace daw
{

class SampleSynth final : public juce::Synthesiser
{
public:
    SampleSynth (juce::AudioBuffer<float> sampleData, double sourceSampleRate, int rootNote, int numVoices = 16);

private:
    juce::AudioBuffer<float> sample;
};

} // namespace daw
