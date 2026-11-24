#pragma once

#include <juce_core/juce_core.h>

#include <optional>

namespace daw
{

struct CliOptions
{
    juce::String mode;
    juce::String sf2Path;
    juce::String samplePath;
    int sampleRootNote = 60;
    int velocityLo = 0;
    int velocityHi = 127;
    float gain = 1.0f;
};

void printCliUsage();

std::optional<CliOptions> parseCliOptions (int argc, char* argv[]);

} // namespace daw
