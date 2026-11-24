#include "AudioEngine.h"
#include "synth/FluidSynthInstrument.h"
#include "synth/PianoSynthInstrument.h"
#include "synth/SampleInstrument.h"

#include <iostream>

namespace daw
{

namespace
{

juce::String findPipeWireOutput (juce::AudioDeviceManager& deviceManager)
{
    for (auto* type : deviceManager.getAvailableDeviceTypes())
    {
        type->scanForDevices();

        for (const auto& name : type->getDeviceNames (false))
            if (name.containsIgnoreCase ("PipeWire"))
                return name;
    }

    return {};
}

std::unique_ptr<Instrument> createInstrument (const juce::String& sf2Path, const juce::String& samplePath,
                                               int sampleRootNote)
{
    if (sf2Path.isNotEmpty())
        return std::make_unique<FluidSynthInstrument> (sf2Path);

    if (samplePath.isNotEmpty())
        return std::make_unique<SampleInstrument> (samplePath, sampleRootNote);

    return std::make_unique<PianoSynthInstrument>();
}

} // namespace

AudioEngine::AudioEngine (const juce::String& sf2Path, const juce::String& samplePath, int sampleRootNote,
                           float gain_)
    : instrument (createInstrument (sf2Path, samplePath, sampleRootNote)), gain (gain_)
{
    midiCollector.reset (44100.0); // avoid asserting if MIDI arrives before the audio device starts

    juce::AudioDeviceManager::AudioDeviceSetup setup;
    setup.outputDeviceName = findPipeWireOutput (deviceManager);

    const auto* preferred = setup.outputDeviceName.isNotEmpty() ? &setup : nullptr;

    if (const auto error = deviceManager.initialise (0, 2, nullptr, true, {}, preferred); error.isNotEmpty())
        std::cerr << "audio: " << error << std::endl;

    deviceManager.addAudioCallback (this);
}

AudioEngine::~AudioEngine()
{
    deviceManager.removeAudioCallback (this);
}

void AudioEngine::audioDeviceAboutToStart (juce::AudioIODevice* device)
{
    const auto sampleRate = device->getCurrentSampleRate();

    instrument->setCurrentPlaybackSampleRate (sampleRate);
    midiCollector.reset (sampleRate);
    midiBlock.ensureSize (4096);

    std::cerr << "audio: " << device->getName() << ", " << sampleRate << " Hz, "
              << device->getCurrentBufferSizeSamples() << " samples" << std::endl;
}

void AudioEngine::audioDeviceIOCallbackWithContext (const float* const*, int, float* const* outputs, int numOutputs,
                                                    int numSamples, const juce::AudioIODeviceCallbackContext&)
{
    juce::AudioBuffer<float> buffer (outputs, numOutputs, numSamples);
    buffer.clear();

    midiBlock.clear();
    midiCollector.removeNextBlockOfMessages (midiBlock, numSamples);

    instrument->renderNextBlock (buffer, midiBlock, 0, numSamples);

    buffer.applyGain (gain);
}

} // namespace daw
