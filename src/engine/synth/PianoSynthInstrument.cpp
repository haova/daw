#include "PianoSynthInstrument.h"

namespace daw
{

void PianoSynthInstrument::setCurrentPlaybackSampleRate (double sampleRate)
{
    synth.setCurrentPlaybackSampleRate (sampleRate);
}

void PianoSynthInstrument::renderNextBlock (juce::AudioBuffer<float>& buffer, const juce::MidiBuffer& midi,
                                             int startSample, int numSamples)
{
    synth.renderNextBlock (buffer, midi, startSample, numSamples);
}

} // namespace daw
