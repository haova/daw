#include "CliOptions.h"

#include <iostream>

namespace daw
{

void printCliUsage()
{
    std::cerr << "usage: engine <mode> [--sf2 <path> | --sample <wav> [--root-note <n>]] [--velocity <lo>:<hi>] [--gain <x>]\n"
              << "modes: live\n"
              << "--sample <wav>: single-sample instrument, pitch-shifted across the keyboard.\n"
              << "--root-note <n>: MIDI note the sample was recorded at (default 60 = C4).\n"
              << "--velocity <lo>:<hi>: remaps note-on velocity from 0-127 to lo-hi (linear).\n"
              << "--gain <x>: output gain multiplier (1.0 = unchanged).\n";
}

std::optional<CliOptions> parseCliOptions (int argc, char* argv[])
{
    if (argc < 2)
    {
        printCliUsage();
        return std::nullopt;
    }

    CliOptions options;
    options.mode = argv[1];

    if (options.mode != "live")
    {
        std::cerr << "error: unknown mode '" << options.mode << "'\n";
        printCliUsage();
        return std::nullopt;
    }

    for (int i = 2; i < argc; ++i)
    {
        const juce::String arg = argv[i];

        if (arg == "--sf2")
        {
            if (++i >= argc)
            {
                std::cerr << "error: --sf2 requires a path\n";
                return std::nullopt;
            }
            options.sf2Path = argv[i];
        }
        else if (arg == "--velocity")
        {
            if (++i >= argc)
            {
                std::cerr << "error: --velocity requires <lo>:<hi>\n";
                return std::nullopt;
            }

            const juce::String spec = argv[i];
            const auto colon = spec.indexOfChar (':');

            if (colon < 0)
            {
                std::cerr << "error: --velocity must be in the form <lo>:<hi>, got '" << spec << "'\n";
                return std::nullopt;
            }

            options.velocityLo = spec.substring (0, colon).getIntValue();
            options.velocityHi = spec.substring (colon + 1).getIntValue();

            if (options.velocityLo < 0 || options.velocityHi > 127 || options.velocityLo > options.velocityHi)
            {
                std::cerr << "error: --velocity range must satisfy 0 <= lo <= hi <= 127, got '" << spec << "'\n";
                return std::nullopt;
            }
        }
        else if (arg == "--sample")
        {
            if (++i >= argc)
            {
                std::cerr << "error: --sample requires a path\n";
                return std::nullopt;
            }
            options.samplePath = argv[i];
        }
        else if (arg == "--root-note")
        {
            if (++i >= argc)
            {
                std::cerr << "error: --root-note requires a value\n";
                return std::nullopt;
            }

            const juce::String spec = argv[i];
            options.sampleRootNote = spec.getIntValue();

            if (options.sampleRootNote < 0 || options.sampleRootNote > 127)
            {
                std::cerr << "error: --root-note must be 0-127, got '" << spec << "'\n";
                return std::nullopt;
            }
        }
        else if (arg == "--gain")
        {
            if (++i >= argc)
            {
                std::cerr << "error: --gain requires a value\n";
                return std::nullopt;
            }

            const juce::String spec = argv[i];
            options.gain = spec.getFloatValue();

            if (options.gain < 0.0f)
            {
                std::cerr << "error: --gain must be >= 0, got '" << spec << "'\n";
                return std::nullopt;
            }
        }
        else
        {
            std::cerr << "error: unknown argument '" << arg << "'\n";
            printCliUsage();
            return std::nullopt;
        }
    }

    if (options.sf2Path.isNotEmpty() && options.samplePath.isNotEmpty())
    {
        std::cerr << "error: --sf2 and --sample are mutually exclusive\n";
        return std::nullopt;
    }

    return options;
}

} // namespace daw
