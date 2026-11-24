#include "MidiEvent.h"

namespace daw
{

juce::String toString (MidiEventType type)
{
    switch (type)
    {
        case MidiEventType::noteOn:          return "noteOn";
        case MidiEventType::noteOff:         return "noteOff";
        case MidiEventType::polyAftertouch:  return "polyAftertouch";
        case MidiEventType::controlChange:   return "controlChange";
        case MidiEventType::programChange:   return "programChange";
        case MidiEventType::channelPressure: return "channelPressure";
        case MidiEventType::pitchBend:       return "pitchBend";
        case MidiEventType::sysex:           return "sysex";
        case MidiEventType::other:           return "other";
    }

    return "other";
}

MidiEvent decodeMidiEvent (const juce::MidiMessage& m, double t, const juce::String& device)
{
    MidiEvent e;
    e.t = t;
    e.device = device;
    e.channel = m.getChannel();

    if (m.isNoteOn())
    {
        e.type = MidiEventType::noteOn;
        e.note = m.getNoteNumber();
        e.velocity = m.getVelocity();
    }
    else if (m.isNoteOff())
    {
        e.type = MidiEventType::noteOff;
        e.note = m.getNoteNumber();
        e.velocity = m.getVelocity();
    }
    else if (m.isAftertouch())
    {
        e.type = MidiEventType::polyAftertouch;
        e.note = m.getNoteNumber();
        e.pressure = m.getAfterTouchValue();
    }
    else if (m.isChannelPressure())
    {
        e.type = MidiEventType::channelPressure;
        e.pressure = m.getChannelPressureValue();
    }
    else if (m.isController())
    {
        e.type = MidiEventType::controlChange;
        e.controller = m.getControllerNumber();
        e.value = m.getControllerValue();
    }
    else if (m.isProgramChange())
    {
        e.type = MidiEventType::programChange;
        e.program = m.getProgramChangeNumber();
    }
    else if (m.isPitchWheel())
    {
        e.type = MidiEventType::pitchBend;
        e.value = m.getPitchWheelValue();
    }
    else if (m.isSysEx())
    {
        e.type = MidiEventType::sysex;
        e.raw = juce::String::toHexString (m.getRawData(), m.getRawDataSize());
    }
    else
    {
        e.type = MidiEventType::other;
        e.raw = juce::String::toHexString (m.getRawData(), m.getRawDataSize());
    }

    return e;
}

juce::var toJson (const MidiEvent& e)
{
    juce::DynamicObject::Ptr obj = new juce::DynamicObject();
    obj->setProperty ("t", e.t);
    obj->setProperty ("device", e.device);
    obj->setProperty ("channel", e.channel);
    obj->setProperty ("type", toString (e.type));
    obj->setProperty ("note", e.note);
    obj->setProperty ("velocity", e.velocity);
    obj->setProperty ("pressure", e.pressure);
    obj->setProperty ("controller", e.controller);
    obj->setProperty ("value", e.value);
    obj->setProperty ("program", e.program);
    obj->setProperty ("raw", e.raw);

    return juce::var (obj.get());
}

} // namespace daw
