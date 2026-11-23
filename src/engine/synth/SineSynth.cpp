#include "SineSynth.h"

namespace daw
{

namespace
{

struct SineSound final : juce::SynthesiserSound
{
    bool appliesToNote (int) override { return true; }
    bool appliesToChannel (int) override { return true; }
};

class SineVoice final : public juce::SynthesiserVoice
{
public:
    using SynthesiserVoice::renderNextBlock;

    bool canPlaySound (juce::SynthesiserSound*) override { return true; }

    void startNote (int note, float velocity, juce::SynthesiserSound*, int) override
    {
        phase = 0.0;
        delta = juce::MathConstants<double>::twoPi * juce::MidiMessage::getMidiNoteInHertz (note) / getSampleRate();
        level = velocity * 0.2f;
        adsr.setSampleRate (getSampleRate());
        adsr.setParameters ({ 0.005f, 0.1f, 0.8f, 0.2f });
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
            const auto sample = (float) std::sin (phase) * level * adsr.getNextSample();
            phase += delta;

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
    double phase = 0.0, delta = 0.0;
    float level = 0.0f;
    juce::ADSR adsr;
};

} // namespace

SineSynth::SineSynth (int numVoices)
{
    for (int i = 0; i < numVoices; ++i)
        addVoice (new SineVoice());

    addSound (new SineSound());
}

} // namespace daw
