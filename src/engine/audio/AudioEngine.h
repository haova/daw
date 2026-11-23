#pragma once

#include "synth/SineSynth.h"

#include <juce_audio_devices/juce_audio_devices.h>

namespace daw
{

class AudioEngine final : private juce::AudioIODeviceCallback
{
public:
    AudioEngine();
    ~AudioEngine() override;

    // Thread-safe: may be called from the MIDI thread.
    void addMidiMessage (const juce::MidiMessage& message) { midiCollector.addMessageToQueue (message); }

private:
    void audioDeviceIOCallbackWithContext (const float* const*, int, float* const* outputs, int numOutputs,
                                           int numSamples, const juce::AudioIODeviceCallbackContext&) override;
    void audioDeviceAboutToStart (juce::AudioIODevice* device) override;
    void audioDeviceStopped() override {}

    juce::AudioDeviceManager deviceManager;
    juce::MidiMessageCollector midiCollector;
    juce::MidiBuffer midiBlock;
    SineSynth synth;
};

} // namespace daw
