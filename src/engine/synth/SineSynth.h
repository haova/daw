#pragma once

#include <juce_audio_basics/juce_audio_basics.h>

namespace daw
{

class SineSynth final : public juce::Synthesiser
{
public:
    explicit SineSynth (int numVoices = 16);
};

} // namespace daw
