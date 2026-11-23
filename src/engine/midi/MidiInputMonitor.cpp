#include "MidiInputMonitor.h"

#include <iostream>

namespace daw
{

MidiInputMonitor::MidiInputMonitor (Handler handler)
    : onMessage (std::move (handler)),
      deviceListConnection (juce::MidiDeviceListConnection::make ([this] { openAll(); }))
{
    openAll();
}

void MidiInputMonitor::openAll()
{
    inputs.clear();

    for (const auto& info : juce::MidiInput::getAvailableDevices())
    {
        if (auto input = juce::MidiInput::openDevice (info.identifier, this))
        {
            std::cerr << "midi: open " << info.name << std::endl;
            input->start();
            inputs.push_back (std::move (input));
        }
    }
}

void MidiInputMonitor::handleIncomingMidiMessage (juce::MidiInput* source, const juce::MidiMessage& message)
{
    onMessage (*source, message);
}

} // namespace daw
