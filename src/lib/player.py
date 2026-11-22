import threading
import time

from lib.song import SWITCHES, Kind

TICK = 0.002

class Player:
    def __init__(self, synth, song, on_end=None):
        self.on_end = on_end
        self.synth = synth
        self.song = song
        self.position = 0.0  # giây
        self.playing = False
        self._thread = None
        self._length = 0.0

    def play(self, start=0.0, track=None):
        # track: chỉ phát track đó, None là phát cả bài
        if self.playing:
            return
        self.position = start

        tracks = [track] if track else self.song.tracks
        self._length = max((n.end for t in tracks for n in t.notes), default=0.0)
        events = []  # (giây, thứ tự, loại, channel, a, b); cùng thời điểm thì nhả pedal, hiệu ứng, nhả nốt, rồi mới nhấn nốt
        for track in tracks:
            self.synth.program(track.program, track.channel)
            for n in track.notes:
                if n.kind is Kind.NOTE:
                    events.append((n.start, 4, "on", track.channel, n.pitch, n.velocity))
                    events.append((n.end, 3, "off", track.channel, n.pitch, 0))
                elif n.kind is Kind.BEND:
                    events.append((n.start, 2, "bend", track.channel, n.velocity, 0))
                elif n.kind is Kind.CONTROL and n.pitch in SWITCHES:
                    events.append((n.start, 2, "cc", track.channel, n.pitch, 127))
                    events.append((n.end, 1, "cc", track.channel, n.pitch, 0))
                elif n.kind is Kind.CONTROL:
                    events.append((n.start, 2, "cc", track.channel, n.pitch, n.velocity))
        events.sort()

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

    def _send(self, event):
        _, _, kind, channel, a, b = event
        if kind == "on":
            self.synth.note_on(a, b, channel)
        elif kind == "off":
            self.synth.note_off(a, channel)
        elif kind == "cc":
            self.synth.control(a, b, channel)
        else:
            self.synth.bend(a, channel)

    def _run(self, events):
        length = self._length
        i = 0
        state = {}  # phát giữa bài: lệnh hiệu ứng gần nhất trước vị trí bắt đầu vẫn phải có hiệu lực
        while i < len(events) and events[i][0] < self.position:
            if events[i][2] in ("cc", "bend"):
                state[(events[i][2], events[i][3], events[i][4] if events[i][2] == "cc" else 0)] = events[i]
            i += 1
        for event in state.values():
            self._send(event)
        origin = time.monotonic() - self.position
        while self.playing:
            now = time.monotonic() - origin
            while i < len(events) and events[i][0] <= now:
                self._send(events[i])
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
