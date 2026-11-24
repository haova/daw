#pragma once

#include "Instrument.h"
#include "PianoSynth.h"

namespace daw
{

class PianoSynthInstrument final : public Instrument
{
public:
    void setCurrentPlaybackSampleRate (double sampleRate) override;
    void renderNextBlock (juce::AudioBuffer<float>& buffer, const juce::MidiBuffer& midi,
                           int startSample, int numSamples) override;

private:
    PianoSynth synth;
};

} // namespace daw
