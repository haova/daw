#include "audio/AudioEngine.h"
#include "midi/MidiInputMonitor.h"

#include <juce_events/juce_events.h>

#include <atomic>
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

} // namespace

int main()
{
    std::signal (SIGINT, [] (int) { shouldQuit = true; });
    std::signal (SIGTERM, [] (int) { shouldQuit = true; });

    juce::ScopedJuceInitialiser_GUI juceInit;

    daw::AudioEngine engine;
    daw::MidiInputMonitor monitor ([&] (const juce::MidiInput&, const juce::MidiMessage& message)
    {
        engine.addMidiMessage (message);
    });

    QuitWatcher quitWatcher;
    std::cerr << "listening, Ctrl+C to quit" << std::endl;
    juce::MessageManager::getInstance()->runDispatchLoop();
    return 0;
}
