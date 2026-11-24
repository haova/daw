#include "PianoSynth.h"

namespace daw
{

namespace
{

struct PianoSound final : juce::SynthesiserSound
{
    bool appliesToNote (int) override { return true; }
    bool appliesToChannel (int) override { return true; }
};

// FM electric piano (Rhodes-style): modulation index decays over time.
class PianoVoice final : public juce::SynthesiserVoice
{
public:
    using SynthesiserVoice::renderNextBlock;

    static constexpr float modIndexInitial = 3.0f;
    static constexpr float modIndexDecay = 4.0f;

    bool canPlaySound (juce::SynthesiserSound*) override { return true; }

    void startNote (int note, float velocity, juce::SynthesiserSound*, int) override
    {
        time = 0.0;
        sampleDuration = 1.0 / getSampleRate();

        const auto f0 = juce::MidiMessage::getMidiNoteInHertz (note);
        delta = juce::MathConstants<double>::twoPi * f0 / getSampleRate();

        carrierPhase = 0.0;
        modulatorPhase = 0.0;
        level = velocity * 0.3f;

        adsr.setSampleRate (getSampleRate());
        adsr.setParameters ({ 0.003f, 1.2f, 0.2f, 0.5f });
        adsr.noteOn();
    }

    void stopNote (float, bool allowTailOff) override
    {
        if (allowTailOff)
        {
            adsr.noteOff();
            return;
        }

        adsr.reset();
        clearCurrentNote();
    }

    void renderNextBlock (juce::AudioBuffer<float>& out, int start, int num) override
    {
        if (! isVoiceActive())
            return;

        for (int i = start; i < start + num; ++i)
        {
            const auto modIndex = modIndexInitial * std::exp (-modIndexDecay * (float) time);
            const auto sample = (float) std::sin (carrierPhase + modIndex * std::sin (modulatorPhase))
                                 * level * adsr.getNextSample();

            carrierPhase += delta;
            modulatorPhase += delta;
            time += sampleDuration;

            for (int ch = 0; ch < out.getNumChannels(); ++ch)
                out.addSample (ch, i, sample);

            if (! adsr.isActive())
            {
                clearCurrentNote();
                break;
            }
        }
    }

    void pitchWheelMoved (int) override {}
    void controllerMoved (int, int) override {}

private:
    double carrierPhase = 0.0, modulatorPhase = 0.0, delta = 0.0;
    double time = 0.0, sampleDuration = 0.0;
    float level = 0.0f;
    juce::ADSR adsr;
};

} // namespace

PianoSynth::PianoSynth (int numVoices)
{
    for (int i = 0; i < numVoices; ++i)
        addVoice (new PianoVoice());

    addSound (new PianoSound());
}

} // namespace daw
