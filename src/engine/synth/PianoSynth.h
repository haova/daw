#pragma once

#include <juce_audio_basics/juce_audio_basics.h>

namespace daw
{

class PianoSynth final : public juce::Synthesiser
{
public:
    explicit PianoSynth (int numVoices = 16);
};

} // namespace daw
