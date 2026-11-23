#include "AudioEngine.h"

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

} // namespace

AudioEngine::AudioEngine()
{
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
    synth.setCurrentPlaybackSampleRate (sampleRate);
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
    synth.renderNextBlock (buffer, midiBlock, 0, numSamples);
}

} // namespace daw
