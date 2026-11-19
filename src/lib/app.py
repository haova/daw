import curses
import sys

from .key import Key, NO_KEY

FRAME_MS = 16 # 60 fps
KEYS_ON = "\x1b[>4;2m\x1b[>25u"  # xterm modifyOtherKeys=2, kitty keyboard protocol (flags 1+8+16)
KEYS_OFF = "\x1b[>4m\x1b[<u"

class App:
    def __init__(self, components, midi=None):
        self.components = components
        self.midi = midi
        self.running = True

    def run(self, stdscr):
        curses.curs_set(0)
        curses.use_default_colors()
        stdscr.timeout(FRAME_MS)
        sys.stdout.write(KEYS_ON)
        sys.stdout.flush()

        try:
            self._build_windows(stdscr)
            self._loop(stdscr)
        finally:
            sys.stdout.write(KEYS_OFF)
            sys.stdout.flush()

    def _build_windows(self, stdscr):
        h, w = stdscr.getmaxyx()
        for c in self.components:
            y, x, ch, cw = c.rect(h, w)
            c.resize(curses.newwin(ch, cw, y, x))

    def _read_key(self, stdscr):
        # phím thường
        key = stdscr.getch()
        if key == -1:
            return NO_KEY
        if key != 27:
            return Key(key, 1, False, False, False)

        # ESC đơn, không phải chuỗi "ESC ["
        if stdscr.getch() != ord("["):
            return Key(27, 1, False, False, False)

        # đọc tới ký tự kết thúc
        seq = ""
        while True:
            ch = stdscr.getch()
            if ch == -1:
                return Key(27, 1, False, False, False)
            seq += chr(ch)
            if 0x40 <= ch <= 0x7E:
                break

        # không phải kiểu "u" (mũi tên...) thì bỏ qua
        if not seq.endswith("u"):
            return NO_KEY

        # tách: mã ; modifier : sự kiện
        parts = seq[:-1].split(";")
        code = int(parts[0].split(":")[0])
        mods = 1
        event = 1
        if len(parts) > 1:
            fields = parts[1].split(":")
            mods = int(fields[0])
            if len(fields) > 1:
                event = int(fields[1])

        # modifier = 1 + bitmask: shift=1, alt=2, ctrl=4
        m = mods - 1
        return Key(code, event, bool(m & 1), bool(m & 2), bool(m & 4))

    def _loop(self, stdscr):
        while self.running:
            key = self._read_key(stdscr)

            if self.midi:
                notes = self.midi.poll()

            # terminal đổi kích thước
            if key.code == curses.KEY_RESIZE:
                self._build_windows(stdscr)
                continue

            # Ctrl+C thoát
            if key.is_ctrl_c and key.event == 1:
                self.running = False
                continue

            # chuyển phím cho component, ai xử lý rồi thì dừng
            if key.code != -1:
                for c in self.components:
                    if c.handle_key(key):
                        break

            # vẽ: mỗi component gọi win.noutrefresh(), App flush một lần
            for c in self.components:
                c.draw()
            curses.doupdate()
