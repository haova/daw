import curses

from lib.app import App
from lib.component import Component
from lib.midi import MidiInput, note_name

BLACK_KEYS = {1, 3, 6, 8, 10}  # C# D# F# G# A#
LOW_NOTE = 48                  # C3 nằm ở dưới cùng lúc đầu
MIN_NOTE = 24                  # C1
MAX_NOTE = 120                 # C9

class TopBar(Component):
    def __init__(self):
        super().__init__()
        self.text = ""

    def rect(self, h, w):
        return (0, 0, 2, w)

    def set_text(self, text):
        self.text = text

    def draw(self):
        win = self.win
        h, w = win.getmaxyx()
        win.erase()

        win.addstr(0, 1, self.text[:w - 2])
        win.hline(1, 0, curses.ACS_HLINE, w)

        super().draw()

class Keyboard(Component):
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
        return (2, 0, h - 2, 5)

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
        self._fit(h)

        # mỗi hàng là 1 nửa cung, nốt thấp ở dưới, cao ở trên
        for row in range(h):
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

def main():
    topbar = TopBar()
    keyboard = Keyboard()
    midi = MidiInput(on_note=[
        lambda note: topbar.set_text(midi.held_text),
        keyboard.on_note,
    ])
    try:
        midi.open()
        curses.wrapper(App([topbar, keyboard], midi).run)
    except KeyboardInterrupt:
        pass
    finally:
        midi.close()

if __name__ == "__main__":
    main()
