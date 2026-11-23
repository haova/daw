#pragma once

#include <juce_audio_devices/juce_audio_devices.h>

#include <functional>
#include <memory>
#include <vector>

namespace daw
{

// onMessage is called on the MIDI thread.
class MidiInputMonitor final : private juce::MidiInputCallback
{
public:
    using Handler = std::function<void (const juce::MidiInput&, const juce::MidiMessage&)>;

    explicit MidiInputMonitor (Handler onMessage);

private:
    void openAll();
    void handleIncomingMidiMessage (juce::MidiInput*, const juce::MidiMessage&) override;

    Handler onMessage;
    std::vector<std::unique_ptr<juce::MidiInput>> inputs;
    juce::MidiDeviceListConnection deviceListConnection;
};

} // namespace daw
