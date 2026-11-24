#include "MidiInputMonitor.h"
#include "MidiEvent.h"

#include <iostream>

namespace daw
{

namespace
{

void logSystemEvent (const juce::String& event, const juce::String& device, const juce::String& identifier)
{
    juce::DynamicObject::Ptr obj = new juce::DynamicObject();
    obj->setProperty ("ts", juce::Time::getCurrentTime().toISO8601 (true));
    obj->setProperty ("level", "info");
    obj->setProperty ("component", "midi");
    obj->setProperty ("event", event);
    obj->setProperty ("device", device);
    obj->setProperty ("identifier", identifier);

    std::cerr << juce::JSON::toString (juce::var (obj.get()), true) << std::endl;
}

} // namespace

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
            logSystemEvent ("device_open", info.name, info.identifier);
            input->start();
            inputs.push_back (std::move (input));
        }
    }
}

void MidiInputMonitor::handleIncomingMidiMessage (juce::MidiInput* source, const juce::MidiMessage& message)
{
    const auto t = juce::Time::getMillisecondCounterHiRes() / 1000.0;
    std::cerr << juce::JSON::toString (toJson (decodeMidiEvent (message, t, source->getName())), true) << std::endl;

    onMessage (*source, message);
}

} // namespace daw
