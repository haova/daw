#include "FluidSynthInstrument.h"

namespace daw
{

FluidSynthInstrument::FluidSynthInstrument (const juce::String& sf2Path_) : sf2Path (sf2Path_)
{
}

FluidSynthInstrument::~FluidSynthInstrument()
{
    if (synth != nullptr)
        delete_fluid_synth (synth);
    if (settings != nullptr)
        delete_fluid_settings (settings);
}

void FluidSynthInstrument::setCurrentPlaybackSampleRate (double sampleRate)
{
    if (synth != nullptr)
    {
        delete_fluid_synth (synth);
        synth = nullptr;
    }
    if (settings != nullptr)
    {
        delete_fluid_settings (settings);
        settings = nullptr;
    }

    settings = new_fluid_settings();
    fluid_settings_setnum (settings, "synth.sample-rate", sampleRate);
    fluid_settings_setint (settings, "synth.audio-channels", 1);

    synth = new_fluid_synth (settings);
    fluid_synth_sfload (synth, sf2Path.toRawUTF8(), 1);
}

void FluidSynthInstrument::handleMidiEvent (const juce::MidiMessage& message)
{
    const auto channel = message.getChannel() - 1; // fluidsynth channels are 0-based

    if (message.isNoteOn())
        fluid_synth_noteon (synth, channel, message.getNoteNumber(), message.getVelocity());
    else if (message.isNoteOff())
        fluid_synth_noteoff (synth, channel, message.getNoteNumber());
    else if (message.isController())
        fluid_synth_cc (synth, channel, message.getControllerNumber(), message.getControllerValue());
    else if (message.isProgramChange())
        fluid_synth_program_change (synth, channel, message.getProgramChangeNumber());
    else if (message.isPitchWheel())
        fluid_synth_pitch_bend (synth, channel, message.getPitchWheelValue());
    else if (message.isChannelPressure())
        fluid_synth_channel_pressure (synth, channel, message.getChannelPressureValue());
    else if (message.isAftertouch())
        fluid_synth_key_pressure (synth, channel, message.getNoteNumber(), message.getAfterTouchValue());
}

void FluidSynthInstrument::renderNextBlock (juce::AudioBuffer<float>& buffer, const juce::MidiBuffer& midi,
                                             int startSample, int numSamples)
{
    auto* left = buffer.getWritePointer (0, startSample);
    auto* right = buffer.getNumChannels() > 1 ? buffer.getWritePointer (1, startSample) : left;

    int sampleOffset = 0;

    for (const auto metadata : midi)
    {
        const auto eventSample = metadata.samplePosition;
        if (eventSample > sampleOffset)
        {
            fluid_synth_write_float (synth, eventSample - sampleOffset,
                                      left + sampleOffset, 0, 1,
                                      right + sampleOffset, 0, 1);
            sampleOffset = eventSample;
        }

        handleMidiEvent (metadata.getMessage());
    }

    if (sampleOffset < numSamples)
        fluid_synth_write_float (synth, numSamples - sampleOffset,
                                  left + sampleOffset, 0, 1,
                                  right + sampleOffset, 0, 1);
}

} // namespace daw
