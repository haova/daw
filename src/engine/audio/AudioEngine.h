#pragma once

#include "synth/Instrument.h"

#include <juce_audio_devices/juce_audio_devices.h>

#include <memory>

namespace daw
{

class AudioEngine final : private juce::AudioIODeviceCallback
{
public:
    // Picks FluidSynth (sf2Path), a single-sample instrument (samplePath), or PianoSynth, in that priority.
    explicit AudioEngine (const juce::String& sf2Path = {}, const juce::String& samplePath = {},
                          int sampleRootNote = 60, float gain = 1.0f);
    ~AudioEngine() override;

    bool isReady() const { return instrument->isValid(); }
    juce::String getLoadError() const { return instrument->getLoadError(); }

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
    std::unique_ptr<Instrument> instrument;
    float gain;
};

} // namespace daw
