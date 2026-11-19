from collections import namedtuple

# mã phím (ASCII)
ESC = 27
TAB = 9
ENTER = 13
SPACE = 32
BACKSPACE = 127
KEY_C = 99

# code: mã ASCII (-1 = không có phím), event: 1=nhấn 2=giữ 3=nhả
class Key(namedtuple("Key", "code event shift alt ctrl")):
    __slots__ = ()

    @property
    def is_ctrl_c(self):
        return self.ctrl and self.code == KEY_C

NO_KEY = Key(-1, 1, False, False, False)
