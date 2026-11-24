#include "SampleSynth.h"

namespace daw
{

namespace
{

struct SampleSound final : juce::SynthesiserSound
{
    bool appliesToNote (int) override { return true; }
    bool appliesToChannel (int) override { return true; }
};

// Pitch-shifts by reading the shared sample at a rate relative to rootNote.
class SampleVoice final : public juce::SynthesiserVoice
{
public:
    SampleVoice (const juce::AudioBuffer<float>& sample_, double sourceSampleRate_, int rootNote_)
        : sample (sample_), sourceSampleRate (sourceSampleRate_), rootNote (rootNote_)
    {
    }

    bool canPlaySound (juce::SynthesiserSound*) override { return true; }

    void startNote (int note, float velocity, juce::SynthesiserSound*, int) override
    {
        position = 0.0;
        level = velocity;

        const auto noteHz = juce::MidiMessage::getMidiNoteInHertz (note);
        const auto rootHz = juce::MidiMessage::getMidiNoteInHertz (rootNote);
        playbackRate = (noteHz / rootHz) * (sourceSampleRate / getSampleRate());
        playing = true;
    }

    void stopNote (float, bool) override
    {
        playing = false;
        clearCurrentNote();
    }

    void renderNextBlock (juce::AudioBuffer<float>& out, int start, int num) override
    {
        if (! playing)
            return;

        const auto numFrames = sample.getNumSamples();

        for (int i = start; i < start + num; ++i)
        {
            if (position >= (double) (numFrames - 1))
            {
                playing = false;
                clearCurrentNote();
                break;
            }

            const auto pos0 = (int) position;
            const auto frac = (float) (position - pos0);

            for (int ch = 0; ch < out.getNumChannels(); ++ch)
            {
                const auto srcCh = juce::jmin (ch, sample.getNumChannels() - 1);
                const auto s0 = sample.getSample (srcCh, pos0);
                const auto s1 = sample.getSample (srcCh, pos0 + 1);
                out.addSample (ch, i, (s0 + frac * (s1 - s0)) * level);
            }

            position += playbackRate;
        }
    }

    void pitchWheelMoved (int) override {}
    void controllerMoved (int, int) override {}

private:
    const juce::AudioBuffer<float>& sample;
    double sourceSampleRate;
    int rootNote;
    double position = 0.0, playbackRate = 1.0;
    float level = 0.0f;
    bool playing = false;
};

} // namespace

SampleSynth::SampleSynth (juce::AudioBuffer<float> sampleData, double sourceSampleRate, int rootNote, int numVoices)
    : sample (std::move (sampleData))
{
    for (int i = 0; i < numVoices; ++i)
        addVoice (new SampleVoice (sample, sourceSampleRate, rootNote));

    addSound (new SampleSound());
}

} // namespace daw
