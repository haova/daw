#pragma once

#include <juce_audio_devices/juce_audio_devices.h>

namespace daw
{

enum class MidiEventType
{
    noteOn,
    noteOff,
    polyAftertouch,
    controlChange,
    programChange,
    channelPressure,
    pitchBend,
    sysex,
    other
};

juce::String toString (MidiEventType type);

// Flat, JSON-friendly decode of a juce::MidiMessage. t is seconds on the
// caller's own clock (not the device's), so ordering stays consistent
// across input backends.
struct MidiEvent
{
    double t = 0.0;
    juce::String device;
    int channel = 0; // 0 for non-channel messages (sysex, system common/realtime)
    MidiEventType type = MidiEventType::other;

    int note = 0;         // noteOn, noteOff, polyAftertouch
    int velocity = 0;     // noteOn, noteOff
    int pressure = 0;     // polyAftertouch, channelPressure
    int controller = 0;   // controlChange
    int value = 0;        // controlChange, pitchBend
    int program = 0;      // programChange
    juce::String raw;     // sysex, other (hex)
};

MidiEvent decodeMidiEvent (const juce::MidiMessage& message, double t, const juce::String& device);
juce::var toJson (const MidiEvent& event);

} // namespace daw
