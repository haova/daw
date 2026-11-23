# Simple Console-based DAW

Run `fluidsynth`:

```bash
fluidsynth -a pulseaudio -m alsa_seq -g 1.0 /usr/share/soundfonts/FluidR3_GM.sf2
```

Play with `fluidsynth`:

```bash
fluidsynth -a pulseaudio -g 1.0 -i /usr/share/soundfonts/FluidR3_GM.sf2 <mid_path>
```

## Layout

- `src/cli/` — Python (composition, terminal UI): `python src/cli/compose.py`
- `src/engine/` — C++/JUCE engine; extract JUCE 9.0.6 into `./JUCE` (not committed)

Build engine:

```bash
./build-engine.sh [Debug|Release] [--clean] [--run]
```
