#include <juce_core/juce_core.h>

int main (int argc, char* argv[])
{
    juce::ignoreUnused (argc, argv);
    std::cout << "Hello from " << juce::SystemStats::getJUCEVersion() << std::endl;
    return 0;
}
