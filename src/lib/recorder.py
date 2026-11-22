from lib.song import Note, Song, Track

DURATIONS = (0.25, 0.5, 1.0, 2.0, 4.0)  # phách: móc kép, móc đơn, đen, trắng, tròn
FINE_STEP = 0.25                        # 1 nốt móc kép

class Recorder:
    def __init__(self, channel=0, program=0, bpm=120.0, beats=1.0):
        self.track = Track(channel, program)
        self.song = Song(bpm, [self.track])
        self.beats = beats
        self.cursor = 0.0
        self.recording = False
        self._held = set()
        self._pending = False

    @property
    def step(self):
        return self.beats * 60 / self.song.bpm

    @property
    def head(self):
        return self.cursor + self.step if self._pending else self.cursor

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

    def start(self):
        self.track.notes.clear()
        self.cursor = 0.0
        self._held.clear()
        self._pending = False
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
            end = self.cursor + self.step
            self.track.notes.append(Note(event.note, event.velocity, self.cursor, end))
            self._held.add(event.note)
            self._pending = True
        else:
            self._held.discard(event.note)
            if self._pending and not self._held:
                self.cursor += self.step
                self._pending = False
