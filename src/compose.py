import argparse
import curses
import os

from lib import midi as midi_file
from lib.app import App
from lib.component import Component
from lib.gm import GM
from lib.key import BACKSPACE, ENTER, ESC, KEY_DOWN, KEY_END, KEY_HOME, KEY_LBRACKET, KEY_LEFT, KEY_N, KEY_RBRACKET, KEY_RIGHT, KEY_UP
from lib.keyboard import Keyboard
from lib.player import Player
from lib.recorder import PLAY, Recorder
from lib.song import Track
from lib.synth import DRUM_CHANNEL, Synth
from piano import CELLS_PER_BEAT, CommandLine, TopBar, build_editor, run_command

class TrackList(Component):
    def __init__(self, recorder, synth, say, on_open):
        super().__init__()
        self.recorder = recorder
        self.song = recorder.song
        self.synth = synth
        self.say = say  # hiện thông báo ở dòng lệnh
        self.on_open = on_open
        self.index = 0
        self._confirm_delete = False

    @property
    def track(self):
        return self.song.tracks[self.index]

    def select(self, index):
        self.index = min(max(index, 0), len(self.song.tracks) - 1)
        cursor = self.recorder.cursor
        self.recorder.select_track(self.track)  # select_track dời con trỏ về cuối track, ở danh sách thì giữ nguyên chỗ cũ
        self.recorder.cursor = cursor
        self.synth.program(self.track.program, self.track.channel)  # bàn phím MIDI kêu bằng nhạc cụ của track đang chọn

    def rect(self, h, w):
        return (1, 0, h - 2, names_width(w))

    def resize(self, win):
        super().resize(win)
        curses.init_pair(11, curses.COLOR_BLACK, curses.COLOR_WHITE)  # dải chọn
        curses.init_pair(12, curses.COLOR_RED, curses.COLOR_WHITE)    # mũi tên trong dải chọn

    def handle_key(self, key):
        if key.event == 3:
            return False
        confirm, self._confirm_delete = self._confirm_delete, False
        if key.code in (KEY_UP, KEY_DOWN):
            self.select(self.index + (1 if key.code == KEY_DOWN else -1))
        elif key.code in (KEY_LEFT, KEY_RIGHT):
            step = (1 if key.shift else 8) * (1 if key.code == KEY_RIGHT else -1)  # đổi nhóm (8 nhạc cụ), Shift đổi từng cái
            self.track.program = (self.track.program + step) % 128  # hết danh sách thì vòng lại
            self.synth.program(self.track.program, self.track.channel)
        elif key.code in (KEY_HOME, KEY_END, KEY_LBRACKET, KEY_RBRACKET):
            self._move_cursor(key.code)
        elif key.code == ENTER:
            self.on_open(self.track)
        elif key.code == KEY_N:
            self._new_track()
        elif key.code == BACKSPACE:
            self._delete(confirm)
        else:
            return False
        return True

    def _move_cursor(self, code):
        # Home/End: đầu/cuối bài; [ ]: lùi/tiến một ô nhịp. Phím P của thanh trên phát từ con trỏ này
        recorder, song = self.recorder, self.song
        bar = song.beats_per_bar * 60 / song.bpm
        cursor = {KEY_HOME: 0.0, KEY_END: song.length, KEY_LBRACKET: recorder.cursor - bar, KEY_RBRACKET: recorder.cursor + bar}[code]
        recorder.cursor = min(max(cursor, 0.0), song.length)

    def _new_track(self):
        used = {t.channel for t in self.song.tracks}
        free = [c for c in range(16) if c != DRUM_CHANNEL and c not in used]
        if not free:
            self.say("hết channel (tối đa 15 track, channel 10 dành cho trống)")
            return
        self.song.tracks.append(Track(free[0], 0))
        self.select(len(self.song.tracks) - 1)

    def _delete(self, confirmed):
        if len(self.song.tracks) == 1:
            self.say("phải còn ít nhất 1 track")
        elif not confirmed:
            self._confirm_delete = True
            self.say("bấm Backspace lần nữa để xóa track này")
        else:
            del self.song.tracks[self.index]
            self.select(self.index)

    def draw(self):
        win = self.win
        h, w = win.getmaxyx()
        win.erase()
        win.hline(0, 0, curses.ACS_HLINE, w)
        win.hline(h - 1, 0, curses.ACS_HLINE, w)

        height = track_height(h, len(self.song.tracks))
        for i, track in enumerate(self.song.tracks):
            for k in range(height):
                row = 1 + i * height + k
                if row >= h - 1:
                    break
                name = f" {GM[track.program]}" if k == 0 else ""  # tên ở hàng trên của track
                try:
                    if i == self.index:
                        # track đang chọn: dải nền sáng chạy hết hàng, hai mũi tên đỏ nằm trong dải ở hai đầu báo ←→ đổi được nhạc cụ
                        win.addstr(row, 0, (" " + name).ljust(w - 1)[:w - 1], curses.color_pair(11))
                        if k == 0:
                            win.addstr(row, 0, "◄", curses.color_pair(12))
                            win.addstr(row, w - 2, "►", curses.color_pair(12))
                    else:
                        win.addstr(row, 0, " " + name)
                except curses.error:
                    pass
        super().draw()

class Timeline(Component):
    # khuôn nhạc: mỗi track một hàng cùng hàng với tên nhạc cụ, khối màu từ nốt đầu tới nốt cuối của track
    def __init__(self, tracklist, player):
        super().__init__()
        self.tracklist = tracklist
        self.song = tracklist.song
        self.player = player

    def rect(self, h, w):
        left = names_width(w)
        return (1, left, h - 2, w - left)

    def resize(self, win):
        super().resize(win)
        curses.init_pair(6, curses.COLOR_CYAN, -1)
        curses.init_pair(7, 8 if curses.COLORS >= 16 else curses.COLOR_WHITE, -1)  # xám
        curses.init_pair(10, curses.COLOR_GREEN, -1)  # track đang chọn

    def _put(self, y, x, text, attr=0):
        try:
            self.win.addstr(y, x, text, attr)
        except curses.error:
            pass

    def _vline(self, x, attr=0):
        for row in range(1, self.win.getmaxyx()[0] - 1):
            self._put(row, x, "│", attr)

    def draw(self):
        win = self.win
        h, w = win.getmaxyx()
        win.erase()
        win.hline(0, 0, curses.ACS_HLINE, w)
        win.hline(h - 1, 0, curses.ACS_HLINE, w)

        # tỉ lệ cố định như view của piano: con trỏ chạy từ trái sang phải, tới mép phải thì khối trôi dần sang trái
        # đang phát thì con trỏ là vị trí phát, không thì là con trỏ của recorder
        song = self.song
        scale = song.bpm / 60 * CELLS_PER_BEAT  # số cột mỗi giây
        head = self.player.position if self.player.playing else self.tracklist.recorder.cursor
        head_cell = round(head * scale)
        origin = max(0, head_cell - (w - 1))
        cursor_x = head_cell - origin

        # vạch ô nhịp màu xám chạy suốt khuôn nhạc, số ô nhịp ở hàng border dưới cùng
        bar_seconds = song.beats_per_bar * 60 / song.bpm
        bar = int(origin / scale // bar_seconds)
        while True:
            x = round(bar * bar_seconds * scale) - origin
            if x >= w:
                break
            if x >= 0:
                self._vline(x, curses.color_pair(7))
                number = str(bar + 1)
                if x + len(number) <= w:
                    self._put(h - 1, x, number)
            bar += 1

        self._vline(cursor_x)
        self._put(0, cursor_x, "▼")

        # mỗi track 2 hàng: hàng trên là ▆ (3/4 ô phía dưới), hàng dưới là ▂ đảo màu (3/4 ô phía trên),
        # ghép lại thành một khối liền có khe hở trên dưới nên các track không dính nhau
        height = track_height(h, len(song.tracks))
        for i, track in enumerate(song.tracks):
            if not track.notes:
                continue
            left = round(min(n.start for n in track.notes) * scale) - origin
            right = max(round(max(n.end for n in track.notes) * scale) - origin, left + 1)
            if right <= 0 or left >= w:
                continue
            attr = curses.color_pair(10 if i == self.tracklist.index else 6)
            body = (max(left, 0), min(right, w))
            row = 1 + i * height
            if row < h - 1:
                self._put(row, body[0], "▆" * (body[1] - body[0]), attr)
            if height == 2 and row + 1 < h - 1:
                self._put(row + 1, body[0], "▂" * (body[1] - body[0]), attr | curses.A_REVERSE)
        super().draw()

def names_width(w):
    return min(28, w // 2)  # cột tên nhạc cụ (tên dài nhất 23 chữ)

def track_height(h, count):
    return 2 if count * 2 <= h - 2 else 1  # mỗi track 2 hàng, hết chỗ thì 1 hàng

class Back(Component):
    # ESC ở màn hình piano: quay lại danh sách track, khi không có gì khác cần ESC
    def __init__(self, editor, player, on_back):
        super().__init__()
        self.editor = editor
        self.player = player
        self.on_back = on_back

    def rect(self, h, w):
        return (h - 1, w - 1, 1, 1)  # cửa sổ 1 ô không dùng để vẽ, chỉ để nhận phím

    def handle_key(self, key):
        if (key.event == 1 and key.code == ESC and not self.player.playing
                and not self.editor.commandline.active and self.editor.topbar.selected is None):
            self.on_back()
            return True
        return False

class Screen:
    editor = None  # màn hình piano đang mở, None là đang ở danh sách

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
    recorder.cursor = 0.0  # ở danh sách, con trỏ bắt đầu từ đầu bài
    synth = Synth(gain=1.0)
    player = Player(synth, recorder.song, on_end=recorder.resume)
    screen = Screen()
    app = None

    def open_editor(track):
        if player.playing:
            player.stop()
        recorder.select_track(track)
        recorder.set_mode(PLAY)
        recorder.resume()
        synth.program(track.program, track.channel)
        screen.editor = build_editor(recorder, player, args.output, GM[track.program], "BMDIOSPQ", close_editor)
        app.set_components([Back(screen.editor, player, close_editor), *screen.editor])

    def close_editor():
        if player.playing:
            player.stop()
        screen.editor = None
        recorder.set_mode(PLAY)
        tracklist.select(recorder.song.tracks.index(recorder.track))
        app.set_components(list_screen)

    def run_list_command(command):
        class NoKeyboard:  # lệnh có thể đặt tiêu điểm bàn phím, màn hình danh sách không có
            focus = ()
        return run_command(command, recorder, NoKeyboard())

    commandline = CommandLine(run_list_command)
    topbar = TopBar(recorder, player, args.output, fields="BMSP", solo=False)  # danh sách phát cả bài
    tracklist = TrackList(recorder, synth, lambda text: setattr(commandline, "text", text), open_editor)
    list_screen = [commandline, topbar, tracklist, Timeline(tracklist, player)]

    def editing(f):
        return lambda note: f(note) if screen.editor else None

    midi = Keyboard(on_note=[
        lambda note: synth.play(note, recorder.track.channel),
        editing(recorder.on_note),
        editing(lambda note: screen.editor.topbar.set_text(midi.held_text)),
        editing(lambda note: screen.editor.keyboard.on_note(note)),
    ])
    app = App(list_screen, midi)
    try:
        synth.open()
        tracklist.select(0)
        midi.open()
        curses.wrapper(app.run)
    except KeyboardInterrupt:
        pass
    finally:
        player.stop()
        midi.close()
        synth.close()

if __name__ == "__main__":
    main()
