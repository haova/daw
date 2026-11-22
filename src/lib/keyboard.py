import queue
import re
from collections import namedtuple

import mido

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

VELOCITY_MIN = 90
VELOCITY_MAX = 110

def scale_velocity(v):
    return VELOCITY_MIN + round((v - 1) * (VELOCITY_MAX - VELOCITY_MIN) / 126)

def note_name(n):
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"

def parse_note(text):
    # "C4", "c#3", "Bb2" -> số nốt MIDI, không phải tên nốt thì None
    m = re.fullmatch(r"([A-Ga-g])([#b]?)(-?\d+)", text)
    if not m:
        return None
    letter, accidental, octave = m.groups()
    pitch = NOTE_NAMES.index(letter.upper()) + {"#": 1, "b": -1, "": 0}[accidental] + (int(octave) + 1) * 12
    return pitch if 0 <= pitch <= 127 else None

# note: số nốt MIDI (0-127), velocity: lực bấm, on: True nhấn / False nhả
class NoteEvent(namedtuple("NoteEvent", "note velocity on")):
    __slots__ = ()

    @property
    def name(self):
        return note_name(self.note)

class Keyboard:
    def __init__(self, name=None, on_note=()):
        self.name = name  # None: lấy port thật đầu tiên
        self.on_note = on_note  # list callback gọi mỗi khi có nốt, CHẠY Ở LUỒNG CỦA MIDO: không được đụng curses
        self._port = None
        self._queue = queue.Queue()
        self._held = set()  # số nốt đang giữ

    def open(self):
        name = self.name or self._default_port()
        self._port = mido.open_input(name, callback=self._on_message)

    @property
    def held_text(self):
        return " ".join(note_name(n) for n in sorted(self._held))

    def close(self):
        if self._port:
            self._port.close()
            self._port = None

    def poll(self):
        notes = []
        while True:
            try:
                notes.append(self._queue.get_nowait())
            except queue.Empty:
                return notes

    def _default_port(self):
        for name in mido.get_input_names():
            if "Through" not in name:
                return name
        raise RuntimeError("không thấy thiết bị MIDI nào")

    # chạy ở luồng của mido
    def _on_message(self, msg):
        if msg.type == "note_on":
            # note_on với velocity 0 nghĩa là nhả phím
            note = NoteEvent(msg.note, scale_velocity(msg.velocity) if msg.velocity > 0 else 0, msg.velocity > 0)
        elif msg.type == "note_off":
            note = NoteEvent(msg.note, msg.velocity, False)
        else:
            return

        if note.on:
            self._held.add(note.note)
        else:
            self._held.discard(note.note)

        self._queue.put(note)
        for f in self.on_note:
            f(note)
