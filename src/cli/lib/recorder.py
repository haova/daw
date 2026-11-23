import time
from dataclasses import replace

from lib.song import Note, Song, Track

DURATIONS = (0.25, 0.5, 1.0, 2.0, 4.0)  # phách: móc kép, móc đơn, đen, trắng, tròn
FINE_STEP = 0.25                        # 1 nốt móc kép
EPSILON = 1e-6
CHORD_WINDOW = 0.05  # giây: các nốt bấm cách nhau không quá mức này mới là một hợp âm
INSERT = "insert"        # chèn: đẩy các nốt phía sau
OVERWRITE = "overwrite"  # ghi đè: ghi chồng thêm lên, không xóa nốt đã có
PLAY = "play"            # chỉ đánh đàn: không ghi nốt từ midi keyboard, các thao tác khác vẫn như thường
MIN_BPM = 20
MAX_BPM = 300

class Recorder:
    def __init__(self, song=None, beats=1.0):
        self.song = song or Song()
        if not self.song.tracks:
            self.song.tracks.append(Track(0, 0))
        self.track = self.song.tracks[0]  # ghi vào track đầu tiên
        self.beats = beats
        self.cursor = self.track_length
        self.recording = False
        self.mode = PLAY
        self._held = set()
        self._pending = False
        self._chord_start = 0.0
        self._play_to = None  # chế độ PLAY: vị trí con trỏ sau khi nhả hợp âm đang giữ
        self.set_bpm(self.song.bpm)  # file nạp vào có thể có BPM lẻ

    @property
    def track_length(self):
        # hết nốt của track đang sửa (giây); các track khác không tính
        return max((n.end for n in self.track.notes), default=0.0)

    @property
    def step(self):
        return self.beats * 60 / self.song.bpm

    @property
    def head(self):
        if not self._pending:
            return self.cursor
        return self._play_to if self._play_to is not None else self.cursor + self.step

    def set_bpm(self, bpm):
        # nốt lưu bằng giây, đổi tempo thì co giãn để vẫn đúng phách cũ
        bpm = min(max(round(bpm), MIN_BPM), MAX_BPM)
        if self._pending or bpm == self.song.bpm:
            return
        ratio = self.song.bpm / bpm
        for t in self.song.tracks:
            t.notes[:] = [replace(n, start=n.start * ratio, end=n.end * ratio) for n in t.notes]
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

    def transpose(self, semitones, pitches=None, bars=None):
        # dời cao độ các nốt có cao độ trong pitches (thấp, cao) và đầu nốt nằm trong bars (ô nhịp đầu, cuối, từ 1); None là không giới hạn
        if self._pending:
            raise ValueError("đang giữ phím")
        bar = self.song.beats_per_bar * 60 / self.song.bpm
        low, high = (0.0, float("inf")) if bars is None else ((bars[0] - 1) * bar, bars[1] * bar)
        lowest, highest = pitches or (0, 127)
        chosen = [(self.track, i) for i, n in enumerate(self.track.notes)
                  if low - EPSILON <= n.start < high - EPSILON and lowest <= n.pitch <= highest]
        if any(not 0 <= t.notes[i].pitch + semitones <= 127 for t, i in chosen):
            raise ValueError("có nốt vượt quá dải 0-127")
        moved = []
        for t, i in chosen:
            n = t.notes[i]
            t.notes[i] = replace(n, pitch=n.pitch + semitones)
            moved.append(t.notes[i])
        return moved

    def select_track(self, track):
        # đổi track đang sửa, con trỏ về cuối track đó
        if self._pending:
            return False
        self.track = track
        self.cursor = self.track_length
        self._held.clear()
        return True

    def home(self):
        if self.recording and not self._pending:
            self.cursor = 0.0

    def end(self):
        if self.recording and not self._pending:
            self.cursor = self.track_length

    def rest(self):
        if not self.recording or self._pending:
            return
        self._make_room()
        self.cursor += self.step

    def _shift(self, start, delta):
        # dời các nốt bắt đầu từ `start` trở đi
        notes = self.track.notes
        notes[:] = [replace(n, start=n.start + delta, end=n.end + delta) if n.start >= start - EPSILON else n
                    for n in notes]

    def _make_room(self):
        # chèn: đẩy nốt phía sau con trỏ ra một bước; ghi đè: giữ nguyên các nốt, ghi chồng thêm lên
        if self.mode == INSERT:
            self._shift(self.cursor, self.step)

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

    def set_mode(self, mode):
        self.mode = mode
        if mode == PLAY:  # bỏ hợp âm đang chờ ghi dở
            self._pending = False
            self._play_to = None
            self._held.clear()

    def stop(self):
        self.recording = False

    def toggle(self):
        if self.mode == PLAY:
            return  # start() xóa bài mà chế độ này không ghi được gì
        if self.recording:
            self.stop()
        else:
            self.start()

    def on_note(self, event):
        if not self.recording:
            return
        play = self.mode == PLAY  # chỉ đánh đàn: con trỏ vẫn dịch như khi ghi nhưng không đụng tới nốt nào
        if event.on:
            now = time.monotonic()
            if self._pending and now - self._chord_start > CHORD_WINDOW:
                self._advance()  # bấm nhanh nối tiếp, không phải hợp âm
            if play and not self._pending:
                if self.cursor >= self.track_length - EPSILON:
                    return  # chỉ đánh đàn mà con trỏ ở cuối bài thì không dịch nữa
                self._play_to = self._next_cursor()
            if not self._pending:
                if not play:
                    self._make_room()
                self._chord_start = now
            if not play:
                end = self.cursor + self.step
                # chồng lên chính nốt đó (cùng cao độ, cùng chỗ) thì thay, không để hai nốt trùng nhau
                self.track.notes[:] = [n for n in self.track.notes
                                       if not (n.pitch == event.note and abs(n.start - self.cursor) < EPSILON)]
                self.track.notes.append(Note(event.note, event.velocity, self.cursor, end))
            self._held.add(event.note)
            self._pending = True
        else:
            self._held.discard(event.note)
            if self._pending and not self._held:
                self._advance()

    def _next_cursor(self):
        # chỉ đánh đàn: con trỏ đi hết nốt có sẵn kế tiếp (bỏ qua khoảng nghỉ phía trước), không vượt quá đầu nốt sau nó
        ahead = [n for n in self.track.notes if n.start >= self.cursor - EPSILON]
        if not ahead:
            return self.track_length
        first = min(n.start for n in ahead)
        duration = min(n.end - n.start for n in ahead if n.start - first < EPSILON)
        later = [n.start for n in ahead if n.start - first >= EPSILON]
        to = first + duration
        if later:
            to = min(to, min(later))
        return to if to > self.cursor + EPSILON else self.cursor + self.step

    def _advance(self):
        self.cursor = self._play_to if self._play_to is not None else self.cursor + self.step
        self._play_to = None
        self._pending = False
        self._held.clear()
