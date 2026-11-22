import curses

from lib.app import App
from lib.component import Component
from lib.key import BACKSPACE, ENTER, ESC, KEY_LBRACKET, KEY_R, KEY_RBRACKET, KEY_SLASH
from lib.keyboard import Keyboard, note_name
from lib.recorder import Recorder
from lib.synth import Synth

BLACK_KEYS = {1, 3, 6, 8, 10}  # C# D# F# G# A#
LOW_NOTE = 48                  # C3 nằm ở dưới cùng lúc đầu
MIN_NOTE = 24                  # C1
MAX_NOTE = 120                 # C9
CELLS_PER_BEAT = 4             # 1 nốt đen rộng 4 ô
SIXTEENTHS_PER_BEAT = 4        # 1 nốt đen = 4 nốt móc kép

class TopBar(Component):
    def __init__(self):
        super().__init__()
        self.text = ""

    def rect(self, h, w):
        return (0, 0, 1, w)

    def set_text(self, text):
        self.text = text

    def draw(self):
        win = self.win
        h, w = win.getmaxyx()
        win.erase()

        win.addstr(0, 1, self.text[:w - 2])

        super().draw()

class DisplayKeyboard(Component):
    def __init__(self):
        super().__init__()
        self.pressed = set()  # số nốt đang bấm
        self.low = LOW_NOTE   # nốt thấp nhất đang hiện ở dưới cùng

    def on_note(self, note):
        if note.on:
            self.pressed.add(note.note)
        else:
            self.pressed.discard(note.note)

    def _fit(self, h):
        # dịch bàn phím để hiện được nhiều nốt đang bấm nhất, không có nốt thì giữ nguyên
        max_low = max(MIN_NOTE, MAX_NOTE - h + 1)
        self.low = min(max(self.low, MIN_NOTE), max_low)

        # copy, vì luồng mido sửa tập này; nốt ngoài C1-C9 không hiện nên bỏ qua
        notes = tuple(n for n in self.pressed if MIN_NOTE <= n <= MAX_NOTE)
        if not notes:
            return

        covered = lambda low: [n for n in notes if low <= n < low + h]
        candidates = {min(max(c, MIN_NOTE), max_low) for n in notes for c in (n, n - h + 1)}
        best = max(len(covered(c)) for c in candidates)
        if len(covered(self.low)) == best:
            return

        # trong các vị trí hiện được nhiều nhất, chọn cái gần vị trí hiện tại nhất
        low = min((c for c in candidates if len(covered(c)) == best), key=lambda c: abs(c - self.low))

        # đặt các nốt đó vào giữa bàn phím
        got = covered(low)
        spare = h - 1 - (max(got) - min(got))
        self.low = min(max(min(got) - spare // 2, MIN_NOTE), max_low)

    def rect(self, h, w):
        return (1, 0, h - 3, 5)

    def resize(self, win):
        super().resize(win)
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_WHITE, -1)
        curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_RED)

    def draw(self):
        win = self.win
        h, w = win.getmaxyx()
        win.erase()
        win.hline(0, 0, curses.ACS_HLINE, w)
        self._fit(h - 1)

        # mỗi hàng là 1 nửa cung, nốt thấp ở dưới, cao ở trên; hàng 0 là border
        for row in range(1, h):
            note = self.low + (h - 1 - row)
            if not MIN_NOTE <= note <= MAX_NOTE:
                continue
            pc = note % 12

            pressed = note in self.pressed

            if pressed or pc == 0:
                win.addstr(row, 0, note_name(note))

            pair = 4 if pressed else 2 if pc in BLACK_KEYS else 1
            win.chgat(row, 0, w - 1, curses.color_pair(pair))

            # border bên phải, ▌ nửa trái của ô
            try:
                win.addstr(row, w - 1, "▌", curses.color_pair(3))
            except curses.error:  # ô góc dưới phải vẫn được ghi, chỉ báo lỗi dời con trỏ
                pass

        super().draw()

class View(Component):
    def __init__(self, keyboard, recorder):
        super().__init__()
        self.keyboard = keyboard  # lấy vị trí hàng theo bàn phím
        self.recorder = recorder
        self.song = recorder.song
        self.time = 0.0           # giây ở cột trái cùng

    @property
    def scale(self):
        return self.recorder.song.bpm / 60 * CELLS_PER_BEAT  # số cột mỗi giây

    def handle_key(self, key):
        if key.code == KEY_R and key.event == 1:
            self.recorder.toggle()
            return True
        if key.code == KEY_LBRACKET and key.event != 3:
            self.recorder.shorter(fine=key.shift)
            return True
        if key.code == KEY_RBRACKET and key.event != 3:
            self.recorder.longer(fine=key.shift)
            return True
        return False

    def rect(self, h, w):
        return (1, 5, h - 3, w - 5)

    def resize(self, win):
        super().resize(win)
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(6, curses.COLOR_CYAN, -1)
        curses.init_pair(7, 8 if curses.COLORS >= 16 else curses.COLOR_WHITE, -1)  # xám

    def _vline(self, x, attr=0):
        win = self.win
        h, w = win.getmaxyx()
        for row in range(1, h):
            try:
                win.addstr(row, x, "│", attr)
            except curses.error:  # ô góc dưới phải vẫn được ghi, chỉ báo lỗi dời con trỏ
                pass

    def draw(self):
        win = self.win
        h, w = win.getmaxyx()
        win.erase()
        win.hline(0, 0, curses.ACS_HLINE, w)

        # con trỏ đi từ trái sang phải, tới mép phải thì nốt mới trôi dần sang trái
        head = self.recorder.head
        self.time = max(0.0, head - (w - 1) / self.scale)

        cursor_x = None
        if self.recorder.recording:
            x = round((head - self.time) * self.scale)
            if 0 <= x < w:
                cursor_x = x
        label = f"{self.recorder.beats * SIXTEENTHS_PER_BEAT:g}"
        label_x = min(cursor_x, w - len(label)) if cursor_x is not None else None

        # vạch ô nhịp màu xám chạy suốt view, số ô nhịp ở trên hàng border (nhường chỗ cho số trường độ)
        song = self.recorder.song
        bar_seconds = song.beats_per_bar * 60 / song.bpm
        bar = int(self.time // bar_seconds)
        while True:
            x = round((bar * bar_seconds - self.time) * self.scale)
            if x >= w:
                break
            if x >= 0:
                self._vline(x, curses.color_pair(7))
                number = str(bar + 1)
                overlaps = label_x is not None and x < label_x + len(label) and label_x < x + len(number)
                if x + len(number) <= w and not overlaps:
                    win.addstr(0, x, number)
            bar += 1

        if cursor_x is not None:
            self._vline(cursor_x)

        if self.song:
            for track in self.song.tracks:
                for n in track.notes:
                    row = h - 1 - (n.pitch - self.keyboard.low)
                    left = round((n.start - self.time) * self.scale)
                    right = max(round((n.end - self.time) * self.scale), left + 1)
                    if not 1 <= row < h or right <= 0 or left >= w:
                        continue

                    # thân nốt tô nền (xóa vạch bên dưới), ô cuối là nửa ô ▌ để tách nốt liền nhau
                    body = (max(left, 0), min(right - 1, w))
                    if body[0] < body[1]:
                        try:
                            win.addstr(row, body[0], " " * (body[1] - body[0]))
                        except curses.error:
                            pass
                        win.chgat(row, body[0], body[1] - body[0], curses.color_pair(5))
                    if right - 1 < w:
                        try:
                            win.addstr(row, right - 1, "▌", curses.color_pair(6))
                        except curses.error:
                            pass

        if label_x is not None:
            win.addstr(0, label_x, label, curses.A_BOLD)

        super().draw()

class CommandLine(Component):
    PROMPT = "/"

    def __init__(self, on_command=None):
        super().__init__()
        self.on_command = on_command
        self.active = False
        self.text = ""

    def rect(self, h, w):
        return (h - 2, 0, 2, w)

    def handle_key(self, key):
        if not self.active:
            if key.code == KEY_SLASH and key.event != 3:
                self.active = True
                self.text = ""
                return True
            return False

        # đang nhập: nuốt mọi phím, kể cả nhả phím
        if key.event == 3:
            return True
        if key.code == ESC:
            self.active = False
            self.text = ""
        elif key.code == ENTER:
            command = self.text
            self.active = False
            self.text = ""
            if self.on_command:
                self.on_command(command)
        elif key.code == BACKSPACE:
            self.text = self.text[:-1]
        elif key.text.isprintable():
            self.text += key.text
        return True

    def draw(self):
        win = self.win
        h, w = win.getmaxyx()
        win.erase()
        win.hline(0, 0, curses.ACS_HLINE, w)

        line = (self.PROMPT + self.text) if self.active else self.text
        win.addstr(1, 0, line[:w - 2])
        if self.active:
            win.addstr(1, min(len(line), w - 2), " ", curses.A_REVERSE)

        super().draw()

def main():
    recorder = Recorder()
    recorder.start()
    topbar = TopBar()
    commandline = CommandLine()
    keyboard = DisplayKeyboard()
    view = View(keyboard, recorder)
    synth = Synth(gain=1.0)
    midi = Keyboard(on_note=[
        synth.play,
        recorder.on_note,
        lambda note: topbar.set_text(midi.held_text),
        keyboard.on_note,
    ])
    try:
        synth.open()
        midi.open()
        curses.wrapper(App([commandline, topbar, keyboard, view], midi).run)
    except KeyboardInterrupt:
        pass
    finally:
        midi.close()
        synth.close()

if __name__ == "__main__":
    main()
