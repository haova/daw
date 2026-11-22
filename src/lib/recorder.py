import time

from lib.song import Note, Song, Track

DURATIONS = (0.25, 0.5, 1.0, 2.0, 4.0)  # phách: móc kép, móc đơn, đen, trắng, tròn
FINE_STEP = 0.25                        # 1 nốt móc kép
EPSILON = 1e-6
CHORD_WINDOW = 0.05  # giây: các nốt bấm cách nhau không quá mức này mới là một hợp âm
INSERT = "insert"        # chèn: đẩy các nốt phía sau
OVERWRITE = "overwrite"  # ghi đè: thay các nốt tại chỗ
MIN_BPM = 20
MAX_BPM = 300

class Recorder:
    def __init__(self, channel=0, program=0, bpm=120.0, beats=1.0):
        self.track = Track(channel, program)
        self.song = Song(bpm, [self.track])
        self.beats = beats
        self.cursor = 0.0
        self.recording = False
        self.mode = INSERT
        self._held = set()
        self._pending = False
        self._chord_start = 0.0

    @property
    def step(self):
        return self.beats * 60 / self.song.bpm

    @property
    def head(self):
        return self.cursor + self.step if self._pending else self.cursor

    def set_bpm(self, bpm):
        # nốt lưu bằng giây, đổi tempo thì co giãn để vẫn đúng phách cũ
        bpm = min(max(bpm, MIN_BPM), MAX_BPM)
        if self._pending or bpm == self.song.bpm:
            return
        ratio = self.song.bpm / bpm
        self.track.notes[:] = [Note(n.pitch, n.velocity, n.start * ratio, n.end * ratio) for n in self.track.notes]
        self.cursor *= ratio
        self.song.bpm = bpm

    def longer(self, fine=False):
        if self._pending:
            return
        if fine:
            self.beats = min(self.beats + FINE_STEP, DURATIONS[-1])
            return
        bigger = [d for d in DURATIONS if d > self.beats]
        if bigger:
            self.beats = bigger[0]

    def shorter(self, fine=False):
        if self._pending:
            return
        if fine:
            self.beats = max(self.beats - FINE_STEP, DURATIONS[0])
            return
        smaller = [d for d in DURATIONS if d < self.beats]
        if smaller:
            self.beats = smaller[-1]

    def delete(self):
        # lùi con trỏ một bước rồi xóa các nốt bắt đầu tại đó
        if not self.recording or self._pending:
            return
        old = self.cursor
        self.cursor = max(0.0, old - self.step)
        if self.cursor == old:
            return
        self.track.notes[:] = [n for n in self.track.notes if abs(n.start - self.cursor) > EPSILON]
        if self.mode == INSERT:
            self._shift(old, self.cursor - old)

    def rest(self):
        if not self.recording or self._pending:
            return
        self._make_room()
        self.cursor += self.step

    def _shift(self, start, delta):
        # dời các nốt bắt đầu từ `start` trở đi
        notes = self.track.notes
        notes[:] = [Note(n.pitch, n.velocity, n.start + delta, n.end + delta) if n.start >= start - EPSILON else n
                    for n in notes]

    def _make_room(self):
        # chèn: đẩy nốt phía sau con trỏ ra một bước; ghi đè: xóa nốt đang nằm trong bước đó
        if self.mode == INSERT:
            self._shift(self.cursor, self.step)
        else:
            end = self.cursor + self.step
            self.track.notes[:] = [n for n in self.track.notes
                                   if not self.cursor - EPSILON <= n.start < end - EPSILON]

    def move(self, direction, fine=False):
        if not self.recording or self._pending:
            return
        delta = FINE_STEP * 60 / self.song.bpm if fine else self.step
        self.cursor = max(0.0, self.cursor + direction * delta)

    def start(self):
        self.track.notes.clear()
        self.cursor = 0.0
        self._held.clear()
        self._pending = False
        self.recording = True

    def resume(self):
        self.recording = True

    def stop(self):
        self.recording = False

    def toggle(self):
        if self.recording:
            self.stop()
        else:
            self.start()

    def on_note(self, event):
        if not self.recording:
            return
        if event.on:
            now = time.monotonic()
            if self._pending and now - self._chord_start > CHORD_WINDOW:
                self._advance()  # bấm nhanh nối tiếp, không phải hợp âm
            if not self._pending:
                self._make_room()
                self._chord_start = now
            end = self.cursor + self.step
            self.track.notes.append(Note(event.note, event.velocity, self.cursor, end))
            self._held.add(event.note)
            self._pending = True
        else:
            self._held.discard(event.note)
            if self._pending and not self._held:
                self._advance()

    def _advance(self):
        self.cursor += self.step
        self._pending = False
        self._held.clear()
