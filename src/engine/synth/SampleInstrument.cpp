#include "SampleInstrument.h"

#include <juce_audio_formats/juce_audio_formats.h>

namespace daw
{

SampleInstrument::SampleInstrument (const juce::String& wavPath, int rootNote)
{
    juce::AudioFormatManager formatManager;
    formatManager.registerBasicFormats();

    const juce::File file (wavPath);
    std::unique_ptr<juce::AudioFormatReader> reader (formatManager.createReaderFor (file));

    if (reader == nullptr)
    {
        loadError = "could not read audio file: " + wavPath;
        return;
    }

    juce::AudioBuffer<float> sampleData ((int) reader->numChannels, (int) reader->lengthInSamples);
    reader->read (&sampleData, 0, (int) reader->lengthInSamples, 0, true, true);

    synth = std::make_unique<SampleSynth> (std::move (sampleData), reader->sampleRate, rootNote);
}

void SampleInstrument::setCurrentPlaybackSampleRate (double sampleRate)
{
    if (synth != nullptr)
        synth->setCurrentPlaybackSampleRate (sampleRate);
}

void SampleInstrument::renderNextBlock (juce::AudioBuffer<float>& buffer, const juce::MidiBuffer& midi,
                                         int startSample, int numSamples)
{
    if (synth != nullptr)
        synth->renderNextBlock (buffer, midi, startSample, numSamples);
}

} // namespace daw
