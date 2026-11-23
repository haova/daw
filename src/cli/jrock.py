"""Bài J-Rock đầy đủ (không lời, ghi ta hát giai điệu), Mi thứ, 180 BPM.

Intro 16 - Verse 1 16 - Pre 8 - Chorus 16 - Interlude 8 - Verse 2 8 - Pre 8 - Chorus 16
- Solo 16 - Bridge 8 - Last chorus (lên nửa cung) 20 - Outro 9

Chạy: python src/cli/jrock.py [đường_dẫn_ra]   (mặc định input/jrock.mid, ghi đè)
"""
import sys

from lib.song import Note, Song, Track
from lib import midi

OUT = sys.argv[1] if len(sys.argv) > 1 else "input/jrock.mid"
BPM = 180
BEAT = 60 / BPM

rhythm = Track(0, 30)  # Distortion Guitar - đệm
lead = Track(1, 29)    # Overdriven Guitar - giai điệu / lead 1
lead2 = Track(2, 29)   # Overdriven Guitar - lead 2 (bè quãng 3)
bass = Track(3, 34)    # Electric Bass (pick)
clean = Track(4, 27)   # Electric Guitar (clean) - bridge
drums = Track(9, 0)    # Trống GM kênh 10

KICK, SNARE, HAT, CRASH, RIDE = 36, 38, 42, 49, 51
TOM_HI, TOM_MID, TOM_LO, TOM_FLOOR = 50, 47, 45, 41

SHIFT = 0  # chuyển giọng (nửa cung), áp cho mọi track trừ trống

# ---------------------------------------------------------------- tiện ích
PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SCALE = {4, 6, 7, 9, 11, 0, 2}  # Mi thứ tự nhiên


def note(name):
    pc = PC[name[0]] + (1 if "#" in name else 0)
    return 12 * (int(name[-1]) + 1) + pc


def mel(text):
    """'E5:1 -:.5 G5:.5' -> [(76, 1.0), (None, .5), (79, .5)]"""
    out = []
    for tok in text.split():
        name, length = tok.split(":")
        out.append((None if name == "-" else note(name), float(length)))
    assert abs(sum(l for _, l in out) - 4) < 1e-9, f"ô nhịp không đủ 4 phách: {text}"
    return out


# Cân velocity từng loại trống (đo với FluidR3: snare quá gắt, kick yếu, hi-hat chìm)
DRUM_BAL = {SNARE: 0.85, KICK: 1.06, HAT: 1.15}


def add(track, pitch, bar, beat, length, vel):
    if track is drums:
        vel = round(vel * DRUM_BAL.get(pitch, 1.0))
    else:
        pitch += SHIFT
    start = (bar * 4 + beat) * BEAT
    track.notes.append(Note(pitch, min(127, vel), start, start + length * BEAT - 0.01))


def line(track, bar, notes, vel=100):
    beat = 0.0
    for pitch, length in notes:
        if pitch is not None:
            add(track, pitch, bar, beat, length, vel)
        beat += length


def third_below(pitch):
    p, steps = pitch, 0
    while steps < 2:
        p -= 1
        if p % 12 in SCALE:
            steps += 1
    return p


def twin(bar, notes, vel=108):
    line(lead, bar, notes, vel)
    line(lead2, bar, [(third_below(p) if p else None, l) for p, l in notes], vel - 10)


def melody(start, bars, vel=100, harmony=False):
    for i, text in enumerate(bars):
        (twin if harmony else lambda b, n, v: line(lead, b, n, v))(start + i, mel(text), vel)


# Power chord theo tên hợp âm (chỉ lấy nốt gốc)
ROOT = {"E": 40, "F": 41, "F#": 42, "G": 43, "A": 45, "B": 47, "C": 48, "D": 50}


def root(chord):
    return ROOT[chord.rstrip("m")]


def power(bar, beat, length, chord, vel):
    r = root(chord)
    for p in (r, r + 7, r + 12):
        add(rhythm, p, bar, beat, length, vel)


def bass_note(bar, beat, length, chord, vel, octave=0):
    add(bass, root(chord) - 12 + octave, bar, beat, length, vel)


def hits(pitch, bar, beats, vel, length=0.25):
    for b in beats:
        add(drums, pitch, bar, b, length, vel)


def fill(bar, start, pitches, vel=110):
    for i, p in enumerate(pitches):
        add(drums, p, bar, start + i * 0.25, 0.25, vel + i)


ROLL = [SNARE, SNARE, TOM_HI, TOM_HI, TOM_MID, TOM_MID, TOM_LO, TOM_FLOOR]

# ------------------------------------------------------------ kiểu đệm
SYNC = [(0, .75), (.75, .75), (1.5, 1), (2.5, .5), (3, .5), (3.5, .5)]


def band(start, chords, style):
    for i, chord in enumerate(chords):
        bar = start + i
        if style == "mute":        # verse: palm-mute nhẹ
            for k in range(8):
                power(bar, k * .5, .25, chord, 92 if k in (0, 3, 6) else 74)
                bass_note(bar, k * .5, .45, chord, 92)
            hits(KICK, bar, [0, 1.5, 2], 105)
            hits(SNARE, bar, [1, 3], 105)
            hits(HAT, bar, [k * .5 for k in range(8)], 70)
        elif style == "drive":     # intro / pre: palm-mute có nhấn, bass nảy quãng 8
            for k in range(8):
                power(bar, k * .5, .25, chord, 104 if k in (0, 3, 6) else 86)
                bass_note(bar, k * .5, .45, chord, 100, 12 if k == 7 else 0)
            hits(KICK, bar, [0, 1.5, 2], 115)
            hits(SNARE, bar, [1, 3], 118)
            hits(HAT, bar, [k * .5 for k in range(8)], 85)
        elif style == "chorus":    # điệp khúc: quạt mở móc đơn, ride + crash
            for k in range(8):
                power(bar, k * .5, .5, chord, 112 if k % 2 == 0 else 98)
                bass_note(bar, k * .5, .45, chord, 108)
            hits(KICK, bar, [0, 1.5, 2, 3.5], 118)
            hits(SNARE, bar, [1, 3], 120)
            hits(RIDE, bar, [k * .5 for k in range(8)], 90)
            if i % 2 == 0:
                hits(CRASH, bar, [0], 118, 1)
        elif style == "sync":      # đảo phách móc kép
            for beat, length in SYNC:
                power(bar, beat, length, chord, 112)
                bass_note(bar, beat, length, chord, 105)
            hits(KICK, bar, [0, .75, 1.5, 2.5], 118)
            hits(SNARE, bar, [1, 3], 120)
            hits(RIDE, bar, [k * .5 for k in range(8)], 90)
            if i % 2 == 0:
                hits(CRASH, bar, [0], 118, 1)


def kime(bar, chord, pattern, top=None, low=None, vel=125):
    for beat, length in pattern:
        power(bar, beat, length, chord, vel)
        bass_note(bar, beat, length, chord, vel - 10)
        if top:
            add(lead, top, bar, beat, length, vel - 10)
            add(lead2, low, bar, beat, length, vel - 20)
        hits(KICK, bar, [beat], 115)
        hits(CRASH, bar, [beat], 108, length)


# ------------------------------------------------------------- chất liệu
HOOK = [
    "E5:.5 E5:.25 G5:.25 A5:.5 G5:.25 E5:.25 B5:1 A5:.5 G5:.5",
    "G5:.5 E5:.5 C6:.75 B5:.75 G5:.5 E5:1",
    "D5:.5 D5:.25 G5:.25 A5:.5 G5:.25 D5:.25 B5:1 A5:.5 B5:.5",
    "A5:.5 F#5:.5 D6:.75 B5:.75 A5:.5 F#5:1",
]
INTRO_CH = ["E", "C", "G", "D"]

TWIN_LINE = [
    "B5:1.5 A5:.5 G5:1 F#5:.5 G5:.5",
    "E5:1.5 G5:.5 C6:1 B5:1",
    "D6:1.5 C6:.5 B5:1 A5:.5 B5:.5",
    "A5:2 F#5:1 A5:1",
    "B5:.5 E6:1 D6:.5 B5:.5 A5:.5 G5:1",
    "A5:.5 G5:.5 E5:.5 G5:.5 C6:1 B5:1",
]

VERSE_CH = ["Em", "D", "C", "D"] * 4
VERSE = [
    "-:1 B4:.5 E5:.5 E5:.5 F#5:.5 G5:1",
    "F#5:.5 E5:.5 D5:1 -:1 A4:.5 D5:.5",
    "E5:1.5 D5:.5 C5:.5 B4:.5 C5:1",
    "D5:3 -:1",
    "-:1 B4:.5 E5:.5 G5:.5 A5:.5 B5:1",
    "A5:.5 G5:.5 F#5:1 -:.5 D5:.5 F#5:.5 A5:.5",
    "G5:1.5 E5:.5 C5:1 E5:1",
    "F#5:2 -:2",
    "-:1 B4:.5 E5:.5 E5:.5 F#5:.5 G5:1",
    "F#5:.5 E5:.5 D5:1 -:1 A4:.5 D5:.5",
    "E5:1.5 D5:.5 C5:.5 B4:.5 C5:1",
    "D5:2 -:1 B4:.5 D5:.5",
    "E5:1 G5:.5 B5:1 A5:.5 G5:1",
    "F#5:.5 E5:.5 D5:1 F#5:1 A5:1",
    "G5:1 E5:1 C5:1 E5:1",
    "F#5:3 -:1",
]

PRE_CH = ["C", "D", "Bm", "Em", "Am", "C", "D", "D"]
PRE = [
    "-:.5 E5:.5 E5:.5 G5:.5 G5:1 E5:1",
    "F#5:.5 A5:.5 A5:1 F#5:1 D5:1",
    "D5:.5 F#5:.5 B5:1.5 A5:.5 F#5:1",
    "G5:2 -:1 E5:.5 G5:.5",
    "A5:1 A5:.5 B5:.5 C6:1 B5:1",
    "G5:1 E5:.5 G5:.5 C6:1 D6:1",
    "D6:2 C6:1 B5:1",
    "A5:2 -:2",
]

CHORUS_CH = ["C", "D", "Bm", "Em"] * 4  # vòng 王道進行 IV-V-iii-vi
CHORUS = [
    "E6:1 D6:.5 E6:1 D6:.5 B5:1",
    "A5:.5 B5:.5 D6:1.5 A5:.5 F#5:1",
    "F#5:.5 A5:.5 B5:1 D6:1 E6:1",
    "E6:2.5 -:.5 B5:.5 D6:.5",
    "E6:1 D6:.5 E6:1 D6:.5 E6:1",
    "F#6:1.5 E6:.5 D6:1 A5:1",
    "B5:1 D6:1 E6:1 F#6:1",
    "G6:2 F#6:1 E6:1",
    "E6:1 D6:.5 E6:1 D6:.5 B5:1",
    "A5:.5 B5:.5 D6:1.5 A5:.5 F#5:1",
    "F#5:.5 A5:.5 B5:1 D6:1 E6:1",
    "E6:2.5 -:.5 B5:.5 D6:.5",
    "E6:1 D6:.5 E6:1 G6:.5 E6:1",
    "F#6:1 E6:.5 D6:.5 A5:1 D6:1",
    "D6:1 E6:1 F#6:1 D6:.5 B5:.5",
    "E6:3 -:1",
]

SOLO = [
    "B5:1.5 A5:.25 B5:.25 D6:.5 B5:.5 A5:.5 G5:.5",
    "E5:.25 G5:.25 A5:.25 B5:.25 C6:.25 B5:.25 A5:.25 G5:.25 E6:2",
    "D6:.5 B5:.5 G5:.5 B5:.5 D6:.5 G6:1 F#6:.5",
    "E6:.25 D6:.25 B5:.25 A5:.25 F#5:.25 A5:.25 B5:.25 D6:.25 F#6:2",
    "E6:.25 D6:.25 B5:.25 D6:.25 E6:.25 D6:.25 B5:.25 D6:.25 E6:.25 D6:.25 B5:.25 A5:.25 G5:.25 A5:.25 B5:.25 D6:.25",
    "E6:.25 G6:.25 E6:.25 C6:.25 E6:.25 G6:.25 E6:.25 C6:.25 G5:1 C6:1",
    "B5:.25 D6:.25 G6:.25 D6:.25 B5:.25 D6:.25 G6:.25 D6:.25 B5:.25 D6:.25 G6:.25 A6:.25 B6:1",
    "A6:1.5 F#6:.5 D6:.5 E6:.25 F#6:.25 A6:1",
]

BRIDGE_CH = ["Am", "Em", "C", "D"] * 2
BRIDGE = [
    "C5:1.5 B4:.5 A4:2",
    "B4:1.5 G4:.5 E4:2",
    "C5:1 D5:1 E5:1 G5:1",
    "F#5:3 -:1",
    "A5:1.5 G5:.5 E5:2",
    "G5:1.5 F#5:.5 E5:2",
    "E5:1 G5:1 C6:1 D6:1",
    "D6:2 -:2",
]
TRIAD = {"Am": [57, 60, 64], "Em": [55, 59, 64], "C": [55, 60, 64], "D": [57, 62, 66]}

# ------------------------------------------------------------- dựng bài
bar = 0
sections = []


def mark(name, length):
    global bar
    sections.append((name, bar, length))
    start = bar
    bar += length
    return start


def intro(start, twin_hook_end=True):
    # 1-4: hook một mình
    for i in range(4):
        line(lead, start + i, mel(HOOK[i]), 100)
    fill(start + 3, 2, [SNARE] * 4 + [TOM_HI, TOM_HI, TOM_MID, TOM_FLOOR])
    # 5-8: cả band
    for i in range(4):
        line(lead, start + 4 + i, mel(HOOK[i]), 110)
    band(start + 4, INTRO_CH, "drive")
    hits(CRASH, start + 4, [0], 120, 1)
    fill(start + 7, 2, ROLL)
    # 9-14: twin lead, đảo phách
    for i in range(6):
        twin(start + 8 + i, mel(TWIN_LINE[i]))
    band(start + 8, (INTRO_CH * 2)[:6], "sync")
    fill(start + 13, 3, [SNARE] * 4)
    # 15-16: kime rồi lặng
    kime(start + 14, "G", [(0, .5), (.75, .5), (1.5, .5), (3, 1)], note("D6"), note("B5"))
    kime(start + 15, "D", [(0, .5), (.75, .5), (1.5, .5)], note("D6"), note("A5"))
    fill(start + 14, 2, [SNARE, SNARE, TOM_HI, TOM_MID])
    fill(start + 15, 2, [SNARE] * 4)


def verse(start, n):
    melody(start, VERSE[:n], 95)
    band(start, VERSE_CH[:n], "mute")
    fill(start + n - 1, 3, [SNARE, SNARE, TOM_HI, TOM_MID])


def pre(start):
    melody(start, PRE, 102)
    band(start, PRE_CH[:7], "drive")
    hits(CRASH, start, [0], 115, 1)
    kime(start + 7, "D", [(0, .5), (.75, .5), (1.5, .5)])
    fill(start + 7, 2, ROLL)


def chorus(start, n=16, harmony_from=8):
    bars = CHORUS + CHORUS[12:16] if n == 20 else CHORUS
    chords = CHORUS_CH + CHORUS_CH[12:16] if n == 20 else CHORUS_CH
    for i in range(n):
        if i >= harmony_from:
            twin(start + i, mel(bars[i]), 112)
        else:
            line(lead, start + i, mel(bars[i]), 110)
    band(start, chords, "chorus")
    fill(start + n - 1, 2, ROLL)


def interlude(start):
    for i in range(8):
        twin(start + i, mel(HOOK[i % 4]), 110)
    band(start, INTRO_CH * 2, "drive")
    hits(CRASH, start, [0], 120, 1)
    fill(start + 7, 2, ROLL)


def solo(start):
    for i in range(8):
        line(lead, start + i, mel(SOLO[i]), 115)
    for i in range(8):
        twin(start + 8 + i, mel(HOOK[i % 4]), 112)
    band(start, INTRO_CH * 2, "chorus")
    band(start + 8, INTRO_CH * 2, "sync")
    fill(start + 7, 2, ROLL)
    fill(start + 15, 2, ROLL)


def bridge(start):
    melody(start, BRIDGE, 85)
    for i, chord in enumerate(BRIDGE_CH):
        b = start + i
        triad = TRIAD[chord]
        for k, idx in enumerate([0, 1, 2, 1, 0, 1, 2, 1]):
            add(clean, triad[idx], b, k * .5, .9, 70 + i * 3)
        add(bass, root(chord) - 12, b, 0, 2, 80)
        add(bass, root(chord) - 12, b, 2, 2, 80)
        if i >= 4:  # build: hat rồi snare dồn
            hits(KICK, b, [0, 2], 95 + i * 3)
            hits(HAT, b, [k * .5 for k in range(8)], 70 + i * 3)
    hits(SNARE, start + 6, [k * .5 for k in range(8)], 90)
    hits(SNARE, start + 7, [k * .25 for k in range(16)], 100)
    for k in range(8):
        power(start + 7, k * .5, .25, "D", 90 + k * 4)


def outro(start):
    for i in range(4):
        line(lead, start + i, mel(HOOK[i]), 112)
    for i in range(4):
        twin(start + 4 + i, mel(HOOK[i]), 115)
    band(start, INTRO_CH, "drive")
    band(start + 4, INTRO_CH, "sync")
    hits(CRASH, start, [0], 120, 1)
    fill(start + 7, 2, ROLL)
    # Cú kết: Em ngân cả ô
    kime(start + 8, "E", [(0, 4)], note("E6"), note("B5"), 127)


intro(mark("Intro", 16))
verse(mark("Verse 1", 16), 16)
pre(mark("Pre-chorus 1", 8))
chorus(mark("Chorus 1", 16))
interlude(mark("Interlude", 8))
verse(mark("Verse 2", 8), 8)
pre(mark("Pre-chorus 2", 8))
chorus(mark("Chorus 2", 16))
solo(mark("Guitar solo", 16))
bridge(mark("Bridge", 8))
SHIFT = 1  # lên nửa cung cho điệp khúc cuối
chorus(mark("Last chorus (+1)", 20), n=20, harmony_from=0)
outro(mark("Outro (+1)", 9))

tracks = [rhythm, lead, lead2, bass, clean, drums]
# Gain kênh (CC7), cân theo đo LUFS từng kênh: giai điệu & trống nổi, đệm lùi, bè 2 dưới giai điệu
for t, volume in zip(tracks, [50, 64, 58, 80, 76, 89]):
    t.volume = volume
for t in tracks:
    t.notes.sort(key=lambda n: (n.start, n.pitch))

midi.write(Song(bpm=BPM, tracks=tracks, time_signature=(4, 4)), OUT)

check = midi.load(OUT)
mins, secs = divmod(check.length, 60)
print(OUT, round(check.bpm), f"{int(mins)}:{secs:04.1f}", [(t.channel, t.program, len(t.notes)) for t in check.tracks])
for name, start, length in sections:
    print(f"  ô {start + 1:>3}-{start + length:<3} {name}")
