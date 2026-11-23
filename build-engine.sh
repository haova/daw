#!/usr/bin/env bash
# Build the C++/JUCE engine (src/engine).
# Usage: ./build-engine.sh [Debug|Release] [--clean] [--run]
set -euo pipefail

cd "$(dirname "$0")"

config=Debug
clean=0
run=0
for arg in "$@"; do
    case "$arg" in
        Debug|Release|RelWithDebInfo) config=$arg ;;
        --clean) clean=1 ;;
        --run) run=1 ;;
        *) echo "Unknown argument: $arg" >&2; echo "Usage: $0 [Debug|Release] [--clean] [--run]" >&2; exit 1 ;;
    esac
done

if [[ ! -f JUCE/CMakeLists.txt ]]; then
    echo "JUCE/ not found in repo root (extract JUCE 9.0.6 into ./JUCE)" >&2
    exit 1
fi

dir="build/$config"
[[ $clean == 1 ]] && rm -rf "$dir"

cmake -S . -B "$dir" -G Ninja -DCMAKE_BUILD_TYPE="$config"
cmake --build "$dir" --target engine

bin="$dir/engine_artefacts/$config/engine"
echo "==> $bin"
[[ $run == 1 ]] && "$bin"
exit 0
