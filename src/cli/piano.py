import argparse
from collections import namedtuple
import curses
import os

from lib.app import App
from lib.component import Component
from lib.key import (BACKSPACE, ENTER, ESC, SPACE, KEY_B, KEY_C, KEY_D, KEY_DOWN, KEY_END, KEY_HOME, KEY_I, KEY_LBRACKET, KEY_LEFT, KEY_M, KEY_N, KEY_O, KEY_P, KEY_Q, KEY_R, KEY_S,
                     KEY_RBRACKET, KEY_RIGHT, KEY_SLASH, KEY_UP)
from lib import midi as midi_file
from lib.gm import GM
from lib.keyboard import Keyboard, note_name, parse_note
from lib.player import Player
from lib.recorder import INSERT, OVERWRITE, PLAY, Recorder
from lib.synth import Synth

BLACK_KEYS = {1, 3, 6, 8, 10}  # C# D# F# G# A#
LOW_NOTE = 48                  # C3 nằm ở dưới cùng lúc đầu
MIN_NOTE = 24                  # C1
MAX_NOTE = 120                 # C9
CELLS_PER_BEAT = 4             # 1 nốt đen rộng 4 ô
SIXTEENTHS_PER_BEAT = 4        # 1 nốt đen = 4 nốt móc kép
FIELD_KEYS = {KEY_B: "B", KEY_M: "M", KEY_D: "D", KEY_N: "N"}
MODE_KEYS = {KEY_I: INSERT, KEY_O: OVERWRITE}
CLAMP_RANGE = (90, 110)        # velocity khi bật Clamp
METERS = [(2, 4), (3, 4), (4, 4), (5, 4), (6, 8), (7, 8), (9, 8), (12, 8)]

class TopBar(Component):
    def __init__(self, recorder, player, output=None, fields="BMDIOCNSP", on_quit=None, solo=True, synth=None):
        super().__init__()
        self.synth = synth  # đổi nhạc cụ thì báo synth
        self.clamp = False  # bật thì velocity bàn phím bị kẹp trong CLAMP_RANGE
        self.solo = solo  # Play chỉ phát track đang sửa, False là phát cả bài
        self.on_quit = on_quit  # gọi khi bấm Q (mục Quit)
        self.fields = fields  # các mục (theo phím tắt) được hiện và dùng, màn hình khác nhau dùng khác nhau
        self.recorder = recorder
        self.output = output
        self.player = player
        self.text = ""
        self.selected = None  # phím tắt của mục đang chỉnh: B, M, D hoặc N
        self.label = ""       # tên track đang sửa, hiện sau các mục

    def rect(self, h, w):
        return (0, 0, 1, w)

    def resize(self, win):
        super().resize(win)
        curses.init_pair(8, curses.COLOR_RED, -1)

    def set_text(self, text):
        self.text = text

    def handle_key(self, key):
        if key.event == 3:
            return False
        if key.code == ESC and self.player.playing:
            self._stop_playing()
            return True
        if key.code == KEY_S:
            self._save()
            return True
        if key.code == KEY_Q and "Q" in self.fields and self.on_quit:
            self.on_quit()
            return True
        if key.code == KEY_P:
            if self.player.playing:
                self._stop_playing()
            else:
                self.recorder.stop()
                cursor = self.recorder.cursor
                track = self.recorder.track if self.solo else None
                length = self.recorder.track_length if self.solo else self.recorder.song.length
                at_end = cursor >= length
                self.player.play(0.0 if key.shift or at_end else cursor, track)
            return True
        if key.code == KEY_C and not key.ctrl and "C" in self.fields:
            self.clamp = not self.clamp
            return True
        if key.code in MODE_KEYS and chr(key.code).upper() in self.fields:
            mode = MODE_KEYS[key.code]
            self.recorder.set_mode(PLAY if self.recorder.mode == mode else mode)  # bấm lại thì về chỉ đánh đàn
            return True
        if key.code in FIELD_KEYS and FIELD_KEYS[key.code] in self.fields:
            self.selected = FIELD_KEYS[key.code]
            return True
        if self.selected is None:
            return False
        if key.code in (ESC, ENTER):
            self.selected = None
            return True
        if key.code in (KEY_UP, KEY_DOWN):
            self._adjust(1 if key.code == KEY_UP else -1, key.shift)
            return True
        return False

    def _save(self):
        if not self.output:
            self.text = "chưa có file, chạy với -o FILE"
            return
        try:
            midi_file.write(self.recorder.song, self.output)
            self.text = f"đã lưu {self.output}"
        except OSError as e:
            self.text = f"không lưu được: {e}"

    def _stop_playing(self):
        # dừng phát, con trỏ ghi âm ở đúng chỗ đang phát
        position = self.player.position
        self.player.stop()
        self.recorder.cursor = position
        self.recorder.resume()

    def _adjust(self, direction, fine):
        recorder = self.recorder
        song = recorder.song
        if self.selected == "B":
            recorder.set_bpm(song.bpm + direction * (1 if fine else 10))
        elif self.selected == "N":
            track = recorder.track
            track.program = (track.program + direction * (8 if fine else 1)) % 128  # Shift nhảy cả nhóm 8, hết thì vòng lại
            if self.synth:
                self.synth.program(track.program, track.channel)
        elif self.selected == "M":
            i = METERS.index(song.time_signature) if song.time_signature in METERS else 0
            song.time_signature = METERS[min(max(i + direction, 0), len(METERS) - 1)]
        elif direction > 0:
            recorder.longer(fine=fine)
        else:
            recorder.shorter(fine=fine)

    def draw(self):
        win = self.win
        h, w = win.getmaxyx()
        win.erase()

        song = self.recorder.song
        fields = (
            ("B", "BPM", f"{song.bpm:g}"),
            ("M", "Meter", f"{song.time_signature[0]}/{song.time_signature[1]}"),
            ("D", "Duration", f"{self.recorder.beats * SIXTEENTHS_PER_BEAT:g}"),
            ("I", "Insert", ""),
            ("O", "Overwrite", ""),
            ("C", "Clamp", ""),
            ("N", "Instrument", GM[self.recorder.track.program]),
            ("S", "Save", ""),
            ("P", "Pause" if self.player.playing else "Play", ""),
            ("Q", "Quit", ""),
        )
        x = 1
        for key, label, value in fields:
            if key not in self.fields:
                continue
            text = f"{label} {value}" if value else label
            if x + len(text) > w:
                break
            attr = curses.A_REVERSE if self.selected == key else 0
            if (key, self.recorder.mode) in (("I", INSERT), ("O", OVERWRITE)) or (key == "C" and self.clamp):
                attr |= curses.A_REVERSE
            win.addstr(0, x, text, attr)
            i = max(label.lower().find(key.lower()), 0)  # chữ phím tắt trong tên mục, tô đỏ
            win.addstr(0, x + i, label[i], attr | curses.color_pair(8))
            x += len(text) + 2

        if self.label and x + len(self.label) < w - len(self.text) - 2:
            win.addstr(0, x, self.label, curses.A_DIM)

        held = self.text[:max(0, w - x - 1)]
        if held:
            win.addstr(0, w - 1 - len(held), held)

        super().draw()

class DisplayKeyboard(Component):
    def __init__(self):
        super().__init__()
        self.pressed = set()  # số nốt đang bấm
        self.low = LOW_NOTE   # nốt thấp nhất đang hiện ở dưới cùng
        self.focus = ()       # nốt cần hiện thêm một lần (vd. vừa dời), dịch bàn phím nếu đang ngoài màn hình

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
        notes = tuple(n for n in {*self.pressed, *self.focus} if MIN_NOTE <= n <= MAX_NOTE)
        self.focus = ()
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
        return (1, 0, h - 2, 5)

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
        win.hline(h - 1, 0, curses.ACS_HLINE, w)
        self._fit(h - 2)

        # mỗi hàng là 1 nửa cung, nốt thấp ở dưới, cao ở trên; hàng đầu và cuối là border
        for row in range(1, h - 1):
            note = self.low + (h - 2 - row)
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
    def __init__(self, keyboard, recorder, player):
        super().__init__()
        self.player = player
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
        if key.code in (KEY_HOME, KEY_END) and key.event != 3:
            if key.code == KEY_HOME:
                self.recorder.home()
            else:
                self.recorder.end()
            return True
        if key.code in (KEY_LEFT, KEY_RIGHT) and key.event != 3:
            self.recorder.move(1 if key.code == KEY_RIGHT else -1, fine=key.shift)
            return True
        if key.code == SPACE and key.event != 3:
            self.recorder.rest()
            return True
        if key.code == BACKSPACE and key.event != 3:
            self.recorder.delete()
            return True
        if key.code == KEY_LBRACKET and key.event != 3:
            self.recorder.shorter(fine=key.shift)
            return True
        if key.code == KEY_RBRACKET and key.event != 3:
            self.recorder.longer(fine=key.shift)
            return True
        return False

    def rect(self, h, w):
        return (1, 5, h - 2, w - 5)

    def resize(self, win):
        super().resize(win)
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(6, curses.COLOR_CYAN, -1)
        curses.init_pair(7, 8 if curses.COLORS >= 16 else curses.COLOR_WHITE, -1)  # xám

    def _vline(self, x, attr=0):
        win = self.win
        h, w = win.getmaxyx()
        for row in range(1, h - 1):
            try:
                win.addstr(row, x, "│", attr)
            except curses.error:  # ô góc dưới phải vẫn được ghi, chỉ báo lỗi dời con trỏ
                pass

    def draw(self):
        win = self.win
        h, w = win.getmaxyx()
        win.erase()
        win.hline(0, 0, curses.ACS_HLINE, w)
        win.hline(h - 1, 0, curses.ACS_HLINE, w)

        # con trỏ đi từ trái sang phải, tới mép phải thì nốt mới trôi dần sang trái
        # đang phát thì con trỏ là vị trí phát, không thì là đầu ghi
        head = self.player.position if self.player.playing else self.recorder.head
        # mọi vị trí tính theo ô nguyên (1 ký tự): con trỏ nhích từng ô, view dời cả ô nên độ dài nốt không nhảy
        scale = self.scale
        head_cell = round(head * scale)  # cùng cách làm tròn với vị trí nốt, để con trỏ trùng đầu nốt
        origin = max(0, head_cell - (w - 1))
        self.time = origin / scale
        cursor_x = head_cell - origin

        # vạch ô nhịp màu xám chạy suốt view, số ô nhịp ở hàng border dưới cùng
        song = self.recorder.song
        bar_seconds = song.beats_per_bar * 60 / song.bpm
        bar = int(self.time // bar_seconds)
        while True:
            x = round(bar * bar_seconds * scale) - origin
            if x >= w:
                break
            if x >= 0:
                self._vline(x, curses.color_pair(7))
                number = str(bar + 1)
                if x + len(number) <= w:
                    try:
                        win.addstr(h - 1, x, number)
                    except curses.error:
                        pass
            bar += 1

        if cursor_x is not None:
            self._vline(cursor_x)

        # chỉ vẽ nốt của track đang sửa
        for n in self.recorder.track.notes:
            row = h - 2 - (n.pitch - self.keyboard.low)
            left = round(n.start * scale) - origin
            right = max(round(n.end * scale) - origin, left + 1)
            if not 1 <= row < h - 1 or right <= 0 or left >= w:
                continue

            # ô đầu là nửa ô ▐ để tách nốt liền nhau, thân nốt tô nền (xóa vạch bên dưới)
            body = (max(left + 1, 0), min(right, w))
            if body[0] < body[1]:
                try:
                    win.addstr(row, body[0], " " * (body[1] - body[0]))
                except curses.error:
                    pass
                win.chgat(row, body[0], body[1] - body[0], curses.color_pair(5))
            if 0 <= left < w:
                try:
                    win.addstr(row, left, "▐", curses.color_pair(6))
                except curses.error:
                    pass

        if cursor_x is not None:
            win.addstr(0, cursor_x, "▼")

        super().draw()

class CommandLine(Component):
    PROMPT = "/"

    def __init__(self, on_command=None):
        super().__init__()
        self.on_command = on_command
        self.active = False
        self.text = ""

    def rect(self, h, w):
        return (h - 1, 0, 1, w)

    def resize(self, win):
        super().resize(win)
        curses.init_pair(8, curses.COLOR_RED, -1)

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
                self.text = self.on_command(command) or ""  # kết quả hiện trên dòng lệnh tới lần nhập sau
        elif key.code == BACKSPACE:
            self.text = self.text[:-1]
        elif key.text.isprintable():
            self.text += key.text
        return True

    def draw(self):
        win = self.win
        h, w = win.getmaxyx()
        win.erase()

        # dấu nhắc đỏ luôn hiện, sau đó là lệnh đang gõ hoặc kết quả lệnh trước
        win.addstr(0, 0, self.PROMPT, curses.color_pair(8))
        text = self.text[:max(0, w - len(self.PROMPT) - 2)]
        win.addstr(0, len(self.PROMPT) + 1, text)
        if self.active:
            win.addstr(0, len(self.PROMPT) + 1 + len(text), " ", curses.A_REVERSE)

        super().draw()

def parse_selection(text):
    # "C4:3" nốt C4 ở ô nhịp 3, "C3:E4" dải nốt, "2:5" dải ô nhịp, "C4" một nốt, "3" một ô nhịp, rỗng là cả bài
    items = []
    for part in text.split(":") if text else []:
        pitch = parse_note(part)
        if pitch is not None:
            items.append(("note", pitch))
        elif part.isdigit() and int(part) >= 1:
            items.append(("bar", int(part)))
        else:
            raise ValueError(f"không hiểu '{part}'")
    if len(items) > 2:
        raise ValueError("chọn tối đa 2 phần, cách nhau bởi :")
    pitches = sorted(v for kind, v in items if kind == "note")
    bars = sorted(v for kind, v in items if kind == "bar")
    return (pitches[0], pitches[-1]) if pitches else None, (bars[0], bars[-1]) if bars else None

def run_command(command, recorder, keyboard):
    words = command.split()
    if not words:
        return ""
    if words[0] not in ("t", "transpose"):
        return f"không có lệnh {words[0]}"
    usage = "dùng: t [CHỌN] SỐ_NỬA_CUNG, CHỌN: C4:3 | C3:E4 | 2:5 | C4 | 3, bỏ trống là cả bài"
    args = words[1:]
    if not 1 <= len(args) <= 2:
        return usage
    try:
        semitones = int(args[-1])
        pitches, bars = parse_selection(args[0] if len(args) == 2 else "")
        moved = recorder.transpose(semitones, pitches, bars)
        keyboard.focus = [n.pitch for n in moved]
        return f"đã dời {len(moved)} nốt"
    except ValueError as e:
        return usage if "int()" in str(e) else str(e)

Editor = namedtuple("Editor", "commandline topbar keyboard view")

def build_editor(recorder, player, output=None, label="", fields="BMDIOCNSP", on_quit=None, synth=None):
    # các component của màn hình piano, sửa track recorder.track
    topbar = TopBar(recorder, player, output, fields, on_quit, synth=synth)
    topbar.label = label
    keyboard = DisplayKeyboard()
    commandline = CommandLine(lambda command: run_command(command, recorder, keyboard))
    view = View(keyboard, recorder, player)
    if recorder.track.notes:
        pitches = sorted(n.pitch for n in recorder.track.notes)
        keyboard.low = pitches[len(pitches) // 2] - 12  # đưa bàn phím tới vùng nốt của bài
    return Editor(commandline, topbar, keyboard, view)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", metavar="FILE", help="file .mid để mở (nếu có) và lưu vào bằng phím S")
    args = parser.parse_args()

    song = None
    if args.output and os.path.exists(args.output):
        try:
            song = midi_file.load(args.output)
        except (OSError, ValueError) as e:
            parser.error(f"không mở được {args.output}: {e}")

    recorder = Recorder(song)
    recorder.resume()
    synth = Synth(gain=1.0)
    player = Player(synth, recorder.song, on_end=recorder.resume)
    editor = build_editor(recorder, player, args.output, synth=synth)
    def clamped(f):
        # kẹp velocity nốt nhấn khi Clamp bật; chạy ở luồng mido nên chỉ đọc cờ
        def wrapper(note):
            if editor.topbar.clamp and note.on:
                note = note._replace(velocity=min(max(note.velocity, CLAMP_RANGE[0]), CLAMP_RANGE[1]))
            f(note)
        return wrapper

    midi = Keyboard(on_note=[
        clamped(lambda note: synth.play(note, recorder.track.channel)),
        clamped(recorder.on_note),
        lambda note: editor.topbar.set_text(midi.held_text),
        editor.keyboard.on_note,
    ])
    try:
        synth.open()
        synth.program(recorder.track.program, recorder.track.channel)
        midi.open()
        curses.wrapper(App(list(editor), midi).run)
    except KeyboardInterrupt:
        pass
    finally:
        player.stop()
        midi.close()
        synth.close()

if __name__ == "__main__":
    main()
