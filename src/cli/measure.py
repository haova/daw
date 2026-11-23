"""Đo độ to (LUFS) và đỉnh (dBFS) của từng kênh và của cả bài.

Render bằng fluidsynth với cùng soundfont và gain như app (Synth(gain=1.0)), đo bằng ffmpeg ebur128.
Chạy: python src/cli/measure.py [file.mid]   (mặc định input/jrock.mid; WAV từng kênh ghi vào output/stems/)
"""
import os
import re
import subprocess
import sys

from lib import midi
from lib.song import Song
from lib.synth import SOUNDFONT

GAIN = "1.0"
STEMS = os.path.join("output", "stems")


def lufs(mid, wav):
    subprocess.run(["fluidsynth", "-ni", "-g", GAIN, "-r", "44100", "-F", wav, SOUNDFONT, mid], check=True, capture_output=True)
    out = subprocess.run(["ffmpeg", "-nostats", "-i", wav, "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    integrated = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", out)[-1])
    peak = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", out)[-1])
    return integrated, peak


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "input/jrock.mid"
    os.makedirs(STEMS, exist_ok=True)
    song = midi.load(src)
    base = os.path.splitext(os.path.basename(src))[0]

    for t in song.tracks:
        name = f"ch{t.channel + 1}"
        mid = os.path.join(STEMS, f"{base}_{name}.mid")
        midi.write(Song(bpm=song.bpm, tracks=[t], time_signature=song.time_signature), mid)
        vel = sum(n.velocity for n in t.notes) / len(t.notes)
        i, p = lufs(mid, mid[:-4] + ".wav")
        print(f"{name:5} prog {t.program:3}  CC7 {t.volume:3}  vel TB {vel:5.1f}  max {max(n.velocity for n in t.notes):3}"
              f"  {i:6.1f} LUFS  peak {p:5.1f} dBFS")

    i, p = lufs(src, os.path.join(STEMS, f"{base}_mix.wav"))
    print(f"MIX   {i:6.1f} LUFS  peak {p:5.1f} dBFS" + ("  << thiếu headroom (đỉnh > -1 dBFS)" if p > -1 else ""))


if __name__ == "__main__":
    main()
