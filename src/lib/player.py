import threading
import time

TICK = 0.002

class Player:
    def __init__(self, synth, song, on_end=None):
        self.on_end = on_end
        self.synth = synth
        self.song = song
        self.position = 0.0  # giây
        self.playing = False
        self._thread = None

    def play(self, start=0.0):
        if self.playing:
            return
        self.position = start

        events = []
        for track in self.song.tracks:
            self.synth.program(track.program, track.channel)
            for n in track.notes:
                events.append((n.start, 1, track.channel, n.pitch, n.velocity))
                events.append((n.end, 0, track.channel, n.pitch, 0))
        events.sort()  # cùng thời điểm thì nhả (0) trước nhấn (1)

        self.playing = True
        self._thread = threading.Thread(target=self._run, args=(events,), daemon=True)
        self._thread.start()

    def stop(self):
        self.playing = False
        if self._thread:
            self._thread.join()
            self._thread = None
        self.position = 0.0
        self.synth.all_off()

    def _run(self, events):
        length = self.song.length
        i = 0
        while i < len(events) and events[i][0] < self.position:
            i += 1
        origin = time.monotonic() - self.position
        while self.playing:
            now = time.monotonic() - origin
            while i < len(events) and events[i][0] <= now:
                _, on, channel, pitch, velocity = events[i]
                if on:
                    self.synth.note_on(pitch, velocity, channel)
                else:
                    self.synth.note_off(pitch, channel)
                i += 1
            self.position = now
            if now >= length:
                self.playing = False
                self.position = 0.0
                self.synth.all_off()
                if self.on_end:
                    self.on_end()
                return
            time.sleep(TICK)
