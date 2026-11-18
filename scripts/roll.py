"""ASCII piano roll for a MIDI keyboard.

Reads notes from the keyboard, forwards them to FluidSynth (so you hear them),
and draws a two-row piano at the bottom of the terminal, one character per note.
Pressed keys turn green. Above the piano is the roll: time runs upwards, one row per
sixteenth note, and each note sits in the column of its key. While playing, the roll
falls onto the piano.

Capture always appends: what you play is written right after the end of the selected
notes (or at the write head if nothing is selected). A
single note or a chord (notes pressed together) is added there and selected. New notes
are as long as the longest selected note (the note value `, .` if nothing is selected). Velocities are not recorded (a fixed one is used).

Start FluidSynth first, then run this script.
Keys:
  (what you play is selected, so you can edit it right away)
  up / down      go to the next / previous row with notes and select ONE note there
                 (the nearest in pitch to the one you were on);
                 up past the last row adds a rest (silent note) there, as long as the selection;
                 down past the first row selects the start note, to write before everything.
                 Every song begins with that start note (a rest of length 0): it can be
                 selected but not moved, resized or deleted.
  left / right   select the next lower / higher note of the row (still just one)
  l              select the whole row (every note of the chord)
  { }            move the write head one row earlier / later (PgDn / PgUp: one beat)
  [  ]           shorten / lengthen the selected notes by a sixteenth
  d  u  /  H  L  move the selected notes down / up a semitone  /  an octave
  j  k  /  J  K  move the selected notes earlier / later by a sixteenth  /  a beat
  ,  .           shorter / longer note value for new notes (1/16 .. 1)
  Delete         remove the selected notes
  space          play back from the start / stop
  shift + space  play back from the cursor / stop (Enter too; shift+space needs a terminal that
                 reports modified keys: kitty, foot, WezTerm, xterm, ... otherwise it acts as space)
  r              reset: clear everything
  +  -           change the BPM
  p              toggle the sustain pedal (starts ON)
  q or Ctrl+C    quit
Usage: python scripts/roll.py [--save file] [--import file.mid] [--bpm n]
                              [--input port_name] [--output port_name]
  --save file     the song is saved there (JSON) after every change, and loaded from it at
                  start if it already holds notes. Without it nothing is saved.
  --import f.mid  start from a MIDI file: all tracks merged, times rounded to sixteenths,
                  drums skipped, silence before the first note dropped, BPM from its first
                  tempo. It replaces what the --save file holds.

Layout of this file: configuration, MIDI (Synth, Keyboard), model (Note, Song,
Player), view (Piano, Theme, View), controller (App), main.
"""
import argparse
import collections
import json
import curses
import locale
import math
import os
import sys
import tempfile
import time

import mido

# --------------------------------------------------------------------------- config

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
BLACK_KEYS = {1, 3, 6, 8, 10}  # pitch classes that are black keys

# MIDI
VEL_MIN, VEL_MAX = 80, 127  # keys you play are remapped onto this velocity range
DRUM_CHANNEL = 9  # channel 10, counting from 1: not imported
SUSTAIN_CC = 64  # sustain pedal controller number

# Time is counted in units: one unit is a sixteenth note, the shortest note there is.
UNITS_PER_BEAT = 4
NOTE_VALUES = (1, 2, 4, 8, 16)  # note lengths in units: 1/16, 1/8, 1/4, 1/2, whole
VALUE_NAMES = {1: "1/16", 2: "1/8", 4: "1/4", 8: "1/2", 16: "1"}
DEFAULT_LENGTH = 4
DEFAULT_VALUE = 2  # index into NOTE_VALUES: new notes are quarter notes
REST = -1  # the "pitch" of a rest: a silent note that only takes time
MAX_LENGTH = 64  # longest note, in units

# Capture
CHORD_WINDOW = 0.08  # seconds: notes pressed within this of the first one form one chord
PLAY_VEL = 100  # velocity of every captured note (what you played is not recorded)

# Playback
DEFAULT_BPM = 120  # beats per minute; a beat is a quarter note
BPM_MIN, BPM_MAX, BPM_STEP = 30, 300, 5
REST_UNITS = 0.25  # each note is released this long before its end, so repeats stay distinct

# Drawing: two rows, one character cell per note
#   white key:  █ on both rows
#   black key:  gap on the top row, thin line on the bottom row
#   E|F and B|C have no black key between them: a thin line on both rows separates them
FULL_LO, FULL_HI = 24, 127  # octaves 1..9: C1 up to G9
KEY_CH = "█"
LINE_CH = "│"
START_CH = "▁"  # the start note of the song
REST_CH = "░"  # a rest in the roll
ROLL_CH = "▅"  # top row of a note: shorter than a full block, so stacked notes stay distinct
HINTS = [  # shortcuts shown on the right of the top bar, most important first
    ("space", "play"),
    ("⇧space", "play here"),
    ("↑↓", "note"),
    ("←→", "note"),
    ("l", "row"),
    ("{ }", "row"),
    ("[ ]", "len"),
    ("dujk", "move"),
    (", .", "value"),
    ("Del", "delete"),
    ("r", "reset"),
    ("+ -", "bpm"),
    ("p", "sus"),
    ("q", "quit"),
]
SHIFT_SPACE = 0x110000  # pseudo key code: beyond any character
# Extended keyboard protocols: a plain terminal sends the same byte for space and shift+space,
# so ask for modified keys to be reported as escape sequences (unsupported terminals ignore this).
KEYS_ON = "\x1b[>4;2m\x1b[>25u"  # xterm modifyOtherKeys=2, kitty keyboard protocol (flags 1+8+16)
KEYS_OFF = "\x1b[>4m\x1b[<u"
MIN_H, MIN_W = 7, 20  # smaller terminals just show a message
FRAME_MS = 16  # ~60 fps; getch() doubles as the frame delay


def note_name(n):
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"


def remap_velocity(v):
    """Linearly map velocity 1..127 onto VEL_MIN..VEL_MAX."""
    return round(VEL_MIN + (v - 1) / 126 * (VEL_MAX - VEL_MIN))


# ------------------------------------------------------------------------------ MIDI


def pick_input():
    names = mido.get_input_names()
    # Prefer the keyboard's MIDI1 port, skip the virtual "Midi Through" port
    for name in names:
        if "Through" not in name and "MIDI1" in name:
            return name
    for name in names:
        if "Through" not in name:
            return name
    return None


def pick_output():
    for name in mido.get_output_names():
        if "FLUID" in name.upper():
            return name
    return None


def import_midi(path):
    """Read a MIDI file; returns (bpm, notes), the notes as Note objects on the sixteenth grid."""
    mid = mido.MidiFile(path)
    unit = mid.ticks_per_beat / UNITS_PER_BEAT  # ticks per sixteenth
    bpm = None
    held = collections.defaultdict(list)  # (channel, pitch) -> [(start ticks, velocity)]
    spans = []  # (start ticks, end ticks, pitch, velocity)
    now = 0
    for msg in mido.merge_tracks(mid.tracks):
        now += msg.time
        if msg.type == "set_tempo" and bpm is None:
            bpm = round(mido.tempo2bpm(msg.tempo))
        elif msg.type == "note_on" and msg.velocity > 0:
            if msg.channel != DRUM_CHANNEL:
                held[msg.channel, msg.note].append((now, msg.velocity))
        elif msg.type in ("note_off", "note_on") and held.get((msg.channel, msg.note)):
            start, vel = held[msg.channel, msg.note].pop(0)  # note_on with velocity 0 is a note_off
            spans.append((start, now, msg.note, vel))
    for (_, pitch), rest in held.items():  # never released: ends with the file
        spans.extend((start, now, pitch, vel) for start, vel in rest)
    first = min((s[0] for s in spans), default=0)
    notes = [
        Note(round((a - first) / unit), max(1, min(MAX_LENGTH, round((b - a) / unit))), pitch, vel)
        for a, b, pitch, vel in spans
    ]
    return max(BPM_MIN, min(BPM_MAX, bpm or DEFAULT_BPM)), notes


class Synth:
    """MIDI output to FluidSynth, plus the latched sustain pedal.

    With no port (None) every call is a no-op, so nothing else needs to check.
    While sustain is on, the physical pedal is ignored (see Keyboard).
    """

    def __init__(self, port_name):
        self.out = mido.open_output(port_name) if port_name else None
        self.sustain = True  # starts with the pedal held down
        self._send_sustain()

    def send(self, msg):
        if self.out is not None:
            self.out.send(msg)

    def note_on(self, pitch, vel):
        self.send(mido.Message("note_on", note=pitch, velocity=vel))

    def note_off(self, pitch):
        self.send(mido.Message("note_off", note=pitch, velocity=0))

    def toggle_sustain(self):
        self.sustain = not self.sustain
        self._send_sustain()

    def _send_sustain(self):
        value = 127 if self.sustain else 0
        for ch in range(16):
            self.send(mido.Message("control_change", channel=ch, control=SUSTAIN_CC, value=value))

    def close(self):
        if self.out is not None:
            self.out.reset()  # silence any hanging notes
            self.out.close()


class Keyboard:
    """MIDI input. mido calls _on_message on its own thread: it forwards to the synth
    first (low latency) and queues events for the UI thread to drain."""

    def __init__(self, name, synth):
        self.name = name
        self.synth = synth
        self.events = collections.deque()  # (time, 'on' | 'off', pitch)
        self._checked_at = float("-inf")
        self._connected = True
        self.port = mido.open_input(name, callback=self._on_message)

    def _on_message(self, msg):
        if msg.type == "control_change" and msg.control == SUSTAIN_CC and self.synth.sustain:
            return  # latched on: ignore the physical pedal
        t = time.monotonic()
        if msg.type == "note_on" and msg.velocity > 0:
            msg = msg.copy(velocity=remap_velocity(msg.velocity))
            self.events.append((t, "on", msg.note))
        elif msg.type in ("note_off", "note_on"):  # note_on with vel 0 == note_off
            self.events.append((t, "off", msg.note))
        self.synth.send(msg)  # forward everything: notes, pitch wheel...

    def connected(self, now):
        """Is the keyboard still listed? Re-checked at most once a second."""
        if now - self._checked_at > 1.0:
            self._connected = self.name in mido.get_input_names()
            self._checked_at = now
        return self._connected

    def close(self):
        self.port.close()


# ----------------------------------------------------------------------------- model


class Note:
    """One note on the grid. start and length are in units (sixteenth notes), so a
    note can be any number of rows long and runs across the rows after its start."""

    __slots__ = ("start", "length", "pitch", "velocity", "first")

    def __init__(self, start, length, pitch, velocity=PLAY_VEL, first=False):
        self.first = first  # the start note of the song (see Song)
        self.start = start  # row where it begins, 0 = the first row
        self.length = length  # 1..MAX_LENGTH
        self.pitch = pitch  # MIDI note number, C4 = 60
        self.velocity = velocity


class Song:
    """The notes, the write head and the selection.

    Every song begins with the start note: a rest of length 0 at row 0 that can be selected,
    to write from the very beginning, but not moved, resized or deleted.
    Notes are a flat list; a chord is simply notes with the same start. The write head
    is the row where the next capture goes. The selection is a set of notes: capturing
    selects what was just played; moving the head with the arrows selects ONE note of
    the new row (the cursor, nearest in pitch to the previous one); with shift it selects
    whole rows, from the anchor to the head. pick() moves the cursor within a row.
    Two notes of the same pitch never overlap: the earlier one is cut short, or
    dropped if both start on the same row.
    """

    def __init__(self):
        self.first = Note(0, 0, REST, first=True)
        self.notes = [self.first]
        self.head = 0  # write head row
        self.anchor = 0  # the other end of a multi-row selection
        self.selected = {self.first}
        self.cursor = None  # the note the arrows are on (one of the selected notes)
        self.cursor_pitch = 60  # remembered when the cursor is lost, to land near it
        self.value = DEFAULT_VALUE  # index into NOTE_VALUES
        self.group_start = None  # time of the first note of the newest chord
        self.group_row = 0  # row of the newest chord
        self.group = []  # notes of the newest chord
        self.group_length = DEFAULT_LENGTH  # their length

    @property
    def length(self):
        """Length in units given to new notes: that of the longest selected note, or the
        chosen note value if nothing is selected."""
        lengths = [n.length for n in self.selected if not n.first]
        return max(lengths) if lengths else NOTE_VALUES[self.value]

    # -- capture

    def capture(self, t, pitch):
        """Append a note. A new chord is written where the selected notes end (or at the
        write head if nothing is selected); notes pressed within CHORD_WINDOW of the first
        one join its row."""
        if self.group_start is None or t - self.group_start > CHORD_WINDOW:
            self.group_start = t
            self.group_length = self.length  # taken from the selection, before it changes
            if self.selected:  # append: write right after the selected notes end
                self.head = max(n.start + n.length for n in self.selected)
            self.group_row = self.head
            self.head += self.group_length
            self.anchor = self.head
            self.group = []
        note = Note(self.group_row, self.group_length, pitch)
        self.notes.append(note)
        self.group.append(note)
        self.selected = set(self.group)  # exactly what was played
        self._set_cursor(note)
        self._normalize()

    # -- selection

    def starting_at(self, row):
        return [n for n in self.notes if n.start == row]

    def _set_cursor(self, note):
        self.cursor = note
        if note is not None and note.pitch != REST:
            self.cursor_pitch = note.pitch

    def _land(self, extend):
        """The head has moved: with `extend` select the whole rows from the anchor to the
        head; otherwise select a single note of the head's row, nearest in pitch to the
        cursor (nothing if the row is empty)."""
        if extend:
            lo, hi = min(self.anchor, self.head), max(self.anchor, self.head)
            self.selected = {n for n in self.notes if lo <= n.start <= hi}
            row = self.starting_at(self.head)
            if row and self.cursor not in row:
                self._set_cursor(min(row, key=lambda n: abs(n.pitch - self.cursor_pitch)))
        else:
            self.anchor = self.head
            row = self.starting_at(self.head)
            target = min(row, key=lambda n: abs(n.pitch - self.cursor_pitch)) if row else None
            self.selected = {target} if target else set()
            self._set_cursor(target)

    def move_head(self, delta, extend=False):
        """Move the head later (delta > 0) or earlier and select what starts there."""
        self.head = max(0, self.head + delta)
        self._land(extend)

    def jump(self, direction, extend=False):
        """Move the head to the next (direction > 0) or previous row that has notes and
        select it. Past the last row it adds a rest after the last note (as long as the
        selected notes) and selects it; before the first one it goes to row 0."""
        starts = sorted({n.start for n in self.notes})
        if direction > 0:
            later = [r for r in starts if r > self.head]
            end = max((n.start + n.length for n in self.notes), default=0)
            if later:
                self.head = later[0]
            else:
                rest = Note(max(self.head, end), self.length, REST)
                self.notes.append(rest)
                self.head = rest.start
                self.selected = {rest}
                self._set_cursor(rest)
                self._normalize()
                return
        else:
            earlier = [r for r in starts if r < self.head]
            if not earlier and self.head == 0 and self.selected != {self.first}:
                self.selected = {self.first}  # below the first chord: the start note
                self._set_cursor(self.first)
                return
            self.head = earlier[-1] if earlier else 0
        self._land(extend)

    def select_row(self):
        """Select every note of the head's row."""
        self.selected = set(self.starting_at(self.head))

    def pick(self, delta, extend=False):
        """In the head's row, move to the next higher (delta > 0) or lower note and select
        just it; with `extend` add it to the selection instead."""
        row = sorted(self.starting_at(self.head), key=lambda n: n.pitch)
        if not row:
            return
        if self.cursor in row:
            i = row.index(self.cursor) + (1 if delta > 0 else -1)
            if not 0 <= i < len(row):
                return
            target = row[i]
        else:  # no cursor in this row: land on the note nearest to where it was
            target = min(row, key=lambda n: abs(n.pitch - self.cursor_pitch))
        if extend:
            self.selected.add(target)
        else:
            self.selected = {target}
        self._set_cursor(target)

    # -- editing

    def change_length(self, delta):
        for n in self.selected:
            if not n.first:
                n.length = max(1, min(MAX_LENGTH, n.length + delta))
        self._normalize()

    def move_selected(self, d_rows, d_pitch):
        """Move the selected notes in time and/or pitch; refused if any would leave the grid."""
        sel = [n for n in self.selected if not n.first]
        if not sel or any(n.start + d_rows < 0 or n.pitch != REST and not 0 <= n.pitch + d_pitch <= 127 for n in sel):
            return
        for n in sel:
            n.start += d_rows
            if n.pitch != REST:
                n.pitch += d_pitch
        self.head = max(0, self.head + d_rows)  # the head goes along with the notes
        self.anchor = max(0, self.anchor + d_rows)
        self._normalize()

    def delete(self):
        """Remove the selected notes and go to the chord before them (like pressing down)."""
        doomed = {n for n in self.selected if not n.first}
        if not doomed:
            return
        first = min(n.start for n in doomed)
        self.notes = [n for n in self.notes if n not in doomed]
        self.selected = set()
        self.cursor = None
        self.group_start = None  # the next note starts a new chord
        self.head = first
        self.jump(-1)

    def change_value(self, delta):
        """Pick a shorter / longer note value for new notes."""
        self.value = max(0, min(len(NOTE_VALUES) - 1, self.value + delta))

    def reset(self):
        self.notes = [self.first]
        self.head = self.anchor = 0
        self.selected = {self.first}
        self.cursor = None
        self.group_start = None

    def _normalize(self):
        """Keep same-pitch notes from overlapping, and the list sorted."""
        by_pitch = collections.defaultdict(list)
        for n in self.notes:  # list order is creation order, and sorting is stable
            if n.first:
                continue
            by_pitch[n.pitch].append(n)
        dead = set()
        for notes in by_pitch.values():
            notes.sort(key=lambda n: n.start)
            kept = []
            for n in notes:
                if kept and kept[-1].start == n.start:  # same pitch, same row: one must go
                    if kept[-1] in self.selected and n not in self.selected:
                        dead.add(n)
                        continue
                    dead.add(kept.pop())
                kept.append(n)
            for a, b in zip(kept, kept[1:]):
                if a.start + a.length > b.start:
                    a.length = b.start - a.start  # cut the earlier note short
        self.notes = sorted((n for n in self.notes if n not in dead), key=lambda n: (n.start, n.pitch))
        self.selected -= dead
        if self.cursor in dead:
            self.cursor = None


class Storage:
    """The song file (JSON): {"bpm": 120, "notes": [[start, length, pitch, velocity], ...]}.
    Saved only when something changed, through a temporary file so a crash can't corrupt it."""

    def __init__(self, path):
        self.path = path
        self.saved = None  # what the file holds, as of the last load / save

    @staticmethod
    def _state(song, player):
        return (player.bpm, [(n.start, n.length, n.pitch, n.velocity) for n in song.notes if not n.first])

    def load(self, song, player):
        """Fill song and player from the file; a missing or empty file leaves them as they are.
        The write head goes to the end, to keep writing."""
        try:
            with open(self.path) as f:
                text = f.read()
        except FileNotFoundError:
            text = ""
        if text.strip():
            try:
                data = json.loads(text)
                notes = [Note(int(a), int(b), int(c), int(d)) for a, b, c, d in data.get("notes", [])]
                player.bpm = max(BPM_MIN, min(BPM_MAX, int(data.get("bpm", player.bpm))))
            except (ValueError, TypeError, AttributeError) as e:
                sys.exit(f"{self.path}: not a song file ({e})")
            song.notes = [song.first] + notes
            song._normalize()
            song.head = song.anchor = max((n.start + n.length for n in song.notes), default=0)
        self.saved = self._state(song, player)

    def save_if_changed(self, song, player):
        state = self._state(song, player)
        if state == self.saved:
            return
        data = {"bpm": state[0], "notes": [list(n) for n in state[1]]}
        folder = os.path.dirname(os.path.abspath(self.path))
        with tempfile.NamedTemporaryFile("w", dir=folder, delete=False, suffix=".tmp") as f:
            json.dump(data, f)
        os.replace(f.name, self.path)
        self.saved = state


class Player:
    """Plays a snapshot of the song. The UI loop calls tick().

    Position is counted in units, so the tempo can change while playing. The notes
    are turned into a sorted list of (position, kind, pitch, velocity) events.
    """

    def __init__(self, synth, bpm=DEFAULT_BPM):
        self.synth = synth
        self.bpm = bpm
        self.active = False
        self.notes = []  # snapshot taken at start(): later edits don't affect this run
        self.events = []
        self.total = 0  # length of the whole song, in units
        self.idx = 0  # next event
        self.pos = 0.0  # playback position in units
        self.last = 0.0  # time of the previous tick
        self.sounding = set()  # pitches currently held

    def change_bpm(self, delta):
        self.bpm = max(BPM_MIN, min(BPM_MAX, self.bpm + delta))

    def start(self, notes, now, pos=0):
        """Play the notes from position `pos` (units); notes starting before it are skipped."""
        if not notes:
            return
        self.notes = [Note(n.start, n.length, n.pitch, n.velocity) for n in notes]
        events = []
        for n in self.notes:  # kind 0 (off) sorts before 1 (on) at the same position
            if n.pitch == REST:
                continue  # silent: only counts for the length of the song
            events.append((n.start, 1, n.pitch, n.velocity))
            events.append((n.start + n.length - REST_UNITS, 0, n.pitch, 0))
        self.events = sorted(events)
        self.total = max(n.start + n.length for n in self.notes)
        self.idx = next((i for i, e in enumerate(self.events) if e[0] >= pos), len(self.events))
        self.pos = float(pos)
        self.last = now
        self.active = True

    def stop(self):
        for pitch in self.sounding:
            self.synth.note_off(pitch)
        self.sounding = set()
        self.active = False

    def toggle(self, notes, now, pos=0):
        if self.active:
            self.stop()
        else:
            self.start(notes, now, pos)

    def tick(self, now):
        if not self.active:
            return
        self.pos += (now - self.last) * self.bpm / 60 * UNITS_PER_BEAT
        self.last = now
        while self.idx < len(self.events) and self.events[self.idx][0] <= self.pos:
            _, kind, pitch, vel = self.events[self.idx]
            self.idx += 1
            if kind:
                self.synth.note_on(pitch, vel)
                self.sounding.add(pitch)
            else:
                self.synth.note_off(pitch)
                self.sounding.discard(pitch)
        if self.idx >= len(self.events) and self.pos >= self.total:
            self.active = False


# ------------------------------------------------------------------------------ view


class Piano:
    """The piano rows for one frame, one character cell per note.

    top/bottom are the two rows, numbers the octave number under each C, and cols
    maps every visible pitch to its column. If the full range doesn't fit in
    `width` columns, a window around `focus` is shown.
    """

    def __init__(self, focus, width):
        cells = []  # a pitch, or None for a separator between two white keys
        for p in range(FULL_LO, FULL_HI + 1):
            if p % 12 in (0, 5) and p != FULL_LO:  # C and F follow B and E directly
                cells.append(None)
            cells.append(p)
        if len(cells) > width:
            fi = cells.index(max(FULL_LO, min(focus, FULL_HI)))
            start = max(0, min(fi - width // 2, len(cells) - width))
            cells = cells[start : start + width]

        top, bottom, numbers = [], [], []
        self.cols = {}
        for i, c in enumerate(cells):
            if c is None:  # separator between two adjacent white keys: a full-height line
                top.append(LINE_CH)
                bottom.append(LINE_CH)
            elif c % 12 in BLACK_KEYS:
                top.append(" ")
                bottom.append(LINE_CH)
            else:
                top.append(KEY_CH)
                bottom.append(KEY_CH)
            if c is not None:
                self.cols[c] = i
            numbers.append(str(c // 12 - 1) if c is not None and c % 12 == 0 else " ")
        self.top, self.bottom = "".join(top), "".join(bottom)
        self.numbers = "".join(numbers).rstrip()
        self.width = len(cells)


class Theme:
    """Text attributes, with a fallback for terminals without colours."""

    def __init__(self):
        if curses.has_colors():
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_WHITE, -1)
            curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
            curses.init_pair(3, curses.COLOR_GREEN, -1)
            curses.init_pair(4, curses.COLOR_CYAN, -1)
            self.key = curses.color_pair(1)  # white key block
            self.line = curses.color_pair(2)  # thin line, white background
            self.lit = curses.color_pair(3) | curses.A_BOLD  # pressed / selected: green
            self.note = curses.color_pair(4)  # note in the roll
            self.dim = curses.color_pair(1) | curses.A_DIM  # grey: off / disconnected / margin
        else:
            self.key, self.line, self.lit = 0, curses.A_REVERSE, curses.A_BOLD
            self.note = self.dim = curses.A_DIM


class View:
    """Draws one frame of the app: top bar, roll, piano."""

    def __init__(self, stdscr):
        self.scr = stdscr
        self.theme = Theme()

    def frame(self, app, now):
        scr = self.scr
        h, w = scr.getmaxyx()
        scr.erase()
        if h < MIN_H or w < MIN_W:
            scr.addstr(0, 0, "Terminal too small")
        else:
            self.topbar(app, now, w)
            piano = Piano(app.focus, w - 3)  # one spare column on each side: the roll's margin
            x = (w - 1 - piano.width) // 2  # centre horizontally
            ty = h - 3  # the piano sits at the bottom: top row, bottom row, numbers
            self.roll(app, piano, x, ty)
            self.piano(app, piano, x, ty)
        scr.refresh()

    def topbar(self, app, now, w):
        t = self.theme
        parts = [
            ("MIDI", t.lit if app.keyboard.connected(now) else t.dim),
            (" ", 0),
            ("SUS", t.lit if app.synth.sustain else t.dim),
            (f" BPM[{app.player.bpm}]", 0),
            (f" NOTE[{VALUE_NAMES.get(app.song.length, str(app.song.length) + 'u')}]", 0),
        ]
        if app.player.active:
            parts.append((f" PLAY[{int(app.player.pos) // UNITS_PER_BEAT + 1}]", 0))
        x = 0
        for text, attr in parts:
            text = text[: max(0, w - 1 - x)]
            if text:
                self.scr.addstr(0, x, text, attr)
            x += len(text)

        # Shortcuts, right-aligned: as many as fit after the status (the rest are dropped)
        hint = ""
        for key, what in HINTS:
            more = (hint + "  " if hint else "") + f"{key} {what}"
            if x + 2 + len(more) > w - 1:
                break
            hint = more
        if hint:
            self.scr.addstr(0, w - 1 - len(hint), hint, t.dim)

    def edit_view(self, song, rows):
        """The view while editing: the head (cursor) stays in the middle of the roll. Where
        there is nothing above it (the end of the song, e.g. while capturing: each new
        note appears at the top edge and pushes the older ones down) the cursor moves up
        to the top edge instead; at the start of the song it moves down to the bottom."""
        end = max([song.head] + [n.start + n.length for n in song.notes])
        return min(max(-1, song.head - (rows + 1) // 2), end - rows)

    def roll(self, app, piano, x, ty):
        """The roll above the piano: time runs upwards, one row per unit.

        A note n units long is n rows tall: full blocks, then a shorter block on its top
        row, so neighbouring notes stay distinct. A row at depth d is d rows above the
        piano; `view` is the position (in units) that sits on the piano itself.
        Editing: the write head (the cursor) moves freely up to the middle of the roll,
        then the roll scrolls instead; selected notes are green.
        Playing: the view is the playback position, so the notes fall onto the piano.
        """
        t = self.theme
        rows = ty - 1  # depths 1..rows
        if app.player.active:
            notes, view, selected = app.player.notes, app.player.pos, ()
        else:
            song = app.song
            view = self.edit_view(song, rows)
            notes, selected = song.notes, song.selected

        if notes is not app.player.notes:  # the start note: a thin line at the bottom of row 0
            d = math.ceil(-view)
            if 1 <= d <= rows:
                self.scr.addstr(ty - d, x, START_CH * piano.width, t.lit if app.song.first in selected else t.dim)

        for n in notes:
            rest = n.pitch == REST
            if n.start + n.length - 1 - view < 1 or n.start - view > rows or not rest and n.pitch not in piano.cols:
                continue  # off screen
            for b in range(n.length):
                d = math.ceil(n.start + b - view)
                if 1 <= d <= rows:
                    if rest:  # a rest: a faint band across the whole piano width
                        self.scr.addstr(ty - d, x, REST_CH * piano.width, t.lit if n in selected else t.dim)
                        continue
                    attr = t.lit if n in selected else t.note
                    ch = ROLL_CH if b == n.length - 1 else KEY_CH
                    self.scr.addstr(ty - d, x + piano.cols[n.pitch], ch, attr)

    def piano(self, app, piano, x, ty):
        scr, t = self.scr, self.theme
        by, ny = ty + 1, ty + 2
        scr.addstr(ty, x, piano.top, t.key)
        scr.addstr(by, x, piano.bottom, t.key)
        scr.addstr(ny, x, piano.numbers)
        for y, row in ((ty, piano.top), (by, piano.bottom)):  # thin lines get a white background
            for i, ch in enumerate(row):
                if ch == LINE_CH:
                    scr.addstr(y, x + i, ch, t.line)

        label_end = -2  # last column used by a note label under the piano
        for pitch in sorted(app.shown):  # highlight pressed keys; thin lines never change colour
            if pitch not in piano.cols:
                continue
            i = piano.cols[pitch]
            scr.addstr(ty, x + i, KEY_CH, t.lit)
            if piano.bottom[i] != LINE_CH:
                scr.addstr(by, x + i, piano.bottom[i], t.lit)
            # Note name under the key, drawn over the octave numbers (with a space on each
            # side to wipe a neighbouring digit). A label that would touch the previous
            # one is skipped.
            text = note_name(pitch)
            start = max(0, min(i, piano.width - len(text)))
            if start > label_end + 1:
                left = " " if start > 0 else ""
                right = " " if start + len(text) < piano.width else ""
                scr.addstr(ny, x + start - len(left), left + text + right, t.lit)
                label_end = start + len(text) - 1


# ------------------------------------------------------------------------ controller


class App:
    """Owns the state and runs the loop: drain MIDI events, advance playback, draw, handle a key."""

    def __init__(self, keyboard, synth, storage=None, imported=None, bpm=None):
        self.keyboard = keyboard
        self.storage = storage
        self.synth = synth
        self.song = Song()
        self.player = Player(synth)
        if storage and not imported:  # an import replaces whatever the file holds
            storage.load(self.song, self.player)
        if imported:  # (bpm, notes) read from a MIDI file
            self.player.bpm = imported[0]
            self.song.notes += imported[1]
            self.song._normalize()
            self.song.head = self.song.anchor = max(n.start + n.length for n in self.song.notes)
        if bpm is not None:  # beats the tempo of the file / import
            self.player.bpm = bpm
        self.pressed = set()  # pitches currently held
        self.focus = 60  # the piano window follows the last played note when it must crop
        self.running = False
        self.keymap = {}
        song, player = self.song, self.player
        self._bind("q", self.quit)
        self._bind("p", synth.toggle_sustain)
        self._bind(" ", lambda: player.toggle(song.notes, time.monotonic()))
        self._bind([SHIFT_SPACE, 10, 13, curses.KEY_ENTER], lambda: player.toggle(song.notes, time.monotonic(), song.head))
        self._bind("r", self.reset)
        self._bind("+=", lambda: player.change_bpm(BPM_STEP))
        self._bind("-_", lambda: player.change_bpm(-BPM_STEP))
        self._bind([curses.KEY_DC], song.delete)
        # Time runs upwards on the roll: up goes to the next chord, down to the previous one.
        self._bind([curses.KEY_UP], lambda: song.jump(1))
        self._bind([curses.KEY_DOWN], lambda: song.jump(-1))
        self._bind("{", lambda: song.move_head(-1), exact=True)  # one row at a time
        self._bind("}", lambda: song.move_head(1), exact=True)
        self._bind([curses.KEY_PPAGE], lambda: song.move_head(UNITS_PER_BEAT))
        self._bind([curses.KEY_NPAGE], lambda: song.move_head(-UNITS_PER_BEAT))
        self._bind([curses.KEY_LEFT], lambda: song.pick(-1))
        self._bind([curses.KEY_RIGHT], lambda: song.pick(1))
        self._bind("l", song.select_row, exact=True)
        self._bind("[", lambda: song.change_length(-1), exact=True)
        self._bind("]", lambda: song.change_length(1), exact=True)
        self._bind("d", lambda: song.move_selected(0, -1), exact=True)
        self._bind("u", lambda: song.move_selected(0, 1), exact=True)
        self._bind("H", lambda: song.move_selected(0, -12), exact=True)
        self._bind("L", lambda: song.move_selected(0, 12), exact=True)
        self._bind("j", lambda: song.move_selected(-1, 0), exact=True)
        self._bind("k", lambda: song.move_selected(1, 0), exact=True)
        self._bind("J", lambda: song.move_selected(-UNITS_PER_BEAT, 0), exact=True)
        self._bind("K", lambda: song.move_selected(UNITS_PER_BEAT, 0), exact=True)
        self._bind(",", lambda: song.change_value(-1), exact=True)
        self._bind(".", lambda: song.change_value(1), exact=True)

    def _bind(self, keys, action, exact=False):
        """keys: a list of curses key codes, or a string of characters. A string binds
        both cases of each letter unless `exact`."""
        if isinstance(keys, str):
            keys = [ord(c) for ch in keys for c in ({ch} if exact else {ch.lower(), ch.upper()})]
        for k in keys:
            self.keymap[k] = action

    def quit(self):
        self.running = False

    def reset(self):
        self.player.stop()
        self.song.reset()

    @property
    def shown(self):
        """Keys lit: held by you or played back."""
        return self.pressed | self.player.sounding

    def _drain_events(self):
        while self.keyboard.events:
            t, kind, pitch = self.keyboard.events.popleft()
            if kind == "on":
                self.pressed.add(pitch)
                self.focus = pitch
                self.song.capture(t, pitch)  # capturing is always on
            else:
                self.pressed.discard(pitch)

    def read_key(self, scr):
        """getch(), plus decoding of the escape sequences of the extended keyboard
        protocols (see KEYS_ON): kitty `CSI code;mods;text u` and xterm `CSI 27;mods;code ~`.
        Returns a key code; shift+space is SHIFT_SPACE, other decoded keys the plain character."""
        key = scr.getch()
        if key != 27:
            return key
        scr.nodelay(True)
        seq = ""
        while len(seq) < 24:
            c = scr.getch()
            if c < 0 or c > 255:
                break
            seq += chr(c)
            if len(seq) > 1 and 0x40 <= c <= 0x7E:
                break
        scr.timeout(FRAME_MS)
        if not seq:
            return 27
        # Arrows etc. as plain sequences. In the extended modes they may come as `CSI 1;1 A`,
        # which curses doesn't know, so decode them here.
        names = {"A": curses.KEY_UP, "B": curses.KEY_DOWN, "C": curses.KEY_RIGHT, "D": curses.KEY_LEFT,
                 "H": curses.KEY_HOME, "F": curses.KEY_END}
        if seq[0] == "O" and len(seq) == 2:
            return names.get(seq[1], -1)
        if not seq.startswith("["):
            return -1
        if seq[-1] in names or seq[-1] == "~" and not seq.startswith("[27;"):
            fields = seq[1:-1].split(";")
            try:
                mods = (int(fields[1]) - 1) & 7 if len(fields) > 1 and fields[1] else 0
            except ValueError:
                return -1
            if mods:
                return -1  # modified arrows are not used
            if seq[-1] != "~":
                return names[seq[-1]]
            return {"3": curses.KEY_DC, "5": curses.KEY_PPAGE, "6": curses.KEY_NPAGE}.get(fields[0], -1)
        if seq[-1] not in "u~":
            return -1
        fields = [f.split(":")[0] for f in seq[1:-1].split(";")]
        try:
            if seq[-1] == "~":  # xterm: 27 ; mods ; code
                if len(fields) != 3 or fields[0] != "27":
                    return -1
                code, mods, text = int(fields[2]), int(fields[1]), None
            else:  # kitty: code ; mods ; text
                code = int(fields[0])
                mods = int(fields[1]) if len(fields) > 1 and fields[1] else 1
                text = int(fields[2]) if len(fields) > 2 and fields[2] else None
        except ValueError:
            return -1
        mods = (mods - 1) & 7  # 1 shift, 2 alt, 4 ctrl
        if code == 32 and mods == 1:
            return SHIFT_SPACE
        if mods & 4 and code in (99, 67):
            raise KeyboardInterrupt  # ctrl+c is no longer a signal in these modes
        if mods & 6:
            return -1
        if text is not None:
            return text
        return ord(chr(code).upper()) if mods == 1 and chr(code).isalpha() else code

    def run(self, stdscr):
        curses.curs_set(0)
        stdscr.timeout(FRAME_MS)
        sys.stdout.write(KEYS_ON)
        sys.stdout.flush()
        try:
            self._loop(stdscr)
        finally:
            sys.stdout.write(KEYS_OFF)
            sys.stdout.flush()

    def _loop(self, stdscr):
        view = View(stdscr)
        self.running = True
        while self.running:
            self._drain_events()
            now = time.monotonic()
            self.player.tick(now)
            if self.player.sounding:
                self.focus = min(self.player.sounding)
            view.frame(self, now)
            action = self.keymap.get(self.read_key(stdscr))
            if action:
                action()
            if self.storage:
                self.storage.save_if_changed(self.song, self.player)


def main():
    ap = argparse.ArgumentParser(description="ASCII piano roll for a MIDI keyboard")
    ap.add_argument("--save", metavar="FILE", help="song file: loaded if it has notes, and saved after every change")
    ap.add_argument("--import", dest="import_", metavar="FILE.mid", help="start from a MIDI file")
    ap.add_argument("--bpm", type=int, help=f"tempo, {BPM_MIN}..{BPM_MAX} (default: the file's, else {DEFAULT_BPM})")
    ap.add_argument("--input", help="MIDI input port name (default: the keyboard)")
    ap.add_argument("--output", help="MIDI output port name (default: FluidSynth)")
    args = ap.parse_args()
    if args.bpm is not None and not BPM_MIN <= args.bpm <= BPM_MAX:
        ap.error(f"--bpm must be between {BPM_MIN} and {BPM_MAX}")
    imported = None
    if args.import_:
        try:
            imported = import_midi(args.import_)
        except (OSError, ValueError, EOFError) as e:
            ap.error(f"{args.import_}: {e}")
    in_name = args.input or pick_input()
    out_name = args.output or pick_output()
    if in_name is None:
        sys.exit("No keyboard found. Available ports: " + str(mido.get_input_names()))

    os.environ.setdefault("ESCDELAY", "25")  # ms to wait after ESC for the rest of a sequence
    locale.setlocale(locale.LC_ALL, "")  # needed to draw non-ASCII characters in curses
    synth = Synth(out_name)
    keyboard = Keyboard(in_name, synth)
    try:
        curses.wrapper(App(keyboard, synth, Storage(args.save) if args.save else None, imported, args.bpm).run)
    except KeyboardInterrupt:
        pass
    finally:
        keyboard.close()
        synth.close()


if __name__ == "__main__":
    main()
