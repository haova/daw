from collections import namedtuple

# mã phím (ASCII)
ESC = 27
TAB = 9
ENTER = 13
SPACE = 32
BACKSPACE = 127
KEY_C = 99
KEY_R = 114
KEY_LBRACKET = 91
KEY_RBRACKET = 93
KEY_SLASH = 47
KEY_B = 98
KEY_D = 100
KEY_I = 105
KEY_M = 109
KEY_O = 111
KEY_P = 112
KEY_S = 115
KEY_HOME = 262
KEY_END = 360
KEY_LEFT = 260
KEY_RIGHT = 261
KEY_UP = 259    # không có mã ASCII, dùng cùng số với curses
KEY_DOWN = 258

# code: mã ASCII (-1 = không có phím), event: 1=nhấn 2=giữ 3=nhả, text: ký tự gõ ra (nếu có)
class Key(namedtuple("Key", "code event shift alt ctrl text", defaults=("",))):
    __slots__ = ()

    @property
    def is_ctrl_c(self):
        return self.ctrl and self.code == KEY_C

NO_KEY = Key(-1, 1, False, False, False)
