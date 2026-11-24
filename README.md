# Simple Console-based DAW

Run the engine:

```bash
engine live --sf2 /usr/share/soundfonts/FluidR3_GM.sf2 --velocity 80:110 --gain 3
```

## Layout

- `src/cli/` — Python (composition, terminal UI): `python src/cli/compose.py`
- `src/engine/` — C++/JUCE engine; extract JUCE 9.0.6 into `./JUCE` (not committed)

Build engine:

```bash
./build-engine.sh [Debug|Release] [--clean] [--run]
```
