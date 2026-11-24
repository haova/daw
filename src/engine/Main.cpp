#include "audio/AudioEngine.h"
#include "cli/CliOptions.h"
#include "midi/MidiEvent.h"
#include "midi/MidiInputMonitor.h"

#include <juce_events/juce_events.h>

#include <atomic>
#include <cmath>
#include <csignal>
#include <iostream>

namespace
{

std::atomic<bool> shouldQuit { false };

struct QuitWatcher final : juce::Timer
{
    QuitWatcher() { startTimer (100); }

    void timerCallback() override
    {
        if (shouldQuit)
            juce::MessageManager::getInstance()->stopDispatchLoop();
    }
};

juce::MidiMessage remapVelocity (const juce::MidiMessage& message, int lo, int hi)
{
    if (! message.isNoteOn())
        return message;

    const auto input = (double) message.getVelocity();
    const auto remapped = lo + (hi - lo) * (input / 127.0);
    const auto output = juce::jlimit (1, 127, (int) std::round (remapped));

    auto result = juce::MidiMessage::noteOn (message.getChannel(), message.getNoteNumber(), (juce::uint8) output);
    result.setTimeStamp (message.getTimeStamp());
    return result;
}

} // namespace

int main (int argc, char* argv[])
{
    const auto options = daw::parseCliOptions (argc, argv);
    if (! options.has_value())
        return 1;

    std::signal (SIGINT, [] (int) { shouldQuit = true; });
    std::signal (SIGTERM, [] (int) { shouldQuit = true; });

    juce::ScopedJuceInitialiser_GUI juceInit;

    daw::AudioEngine engine (options->sf2Path, options->samplePath, options->sampleRootNote, options->gain);

    if (! engine.isReady())
        std::cerr << "warning: " << engine.getLoadError() << " -- continuing without sound" << std::endl;

    daw::MidiInputMonitor monitor ([&, lo = options->velocityLo, hi = options->velocityHi]
        (const juce::MidiInput& source, const juce::MidiMessage& message)
    {
        const auto processed = remapVelocity (message, lo, hi);

        const auto t = juce::Time::getMillisecondCounterHiRes() / 1000.0;
        std::cerr << juce::JSON::toString (daw::toJson (daw::decodeMidiEvent (processed, t, source.getName())), true)
                  << std::endl;

        engine.addMidiMessage (processed);
    });

    QuitWatcher quitWatcher;
    std::cerr << "listening, Ctrl+C to quit" << std::endl;
    juce::MessageManager::getInstance()->runDispatchLoop();
    return 0;
}
