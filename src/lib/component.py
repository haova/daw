class Component:
    def __init__(self):
        self.win = None

    def rect(self, h, w):
        # (y, x, cao, rộng) theo kích thước terminal
        raise NotImplementedError

    def resize(self, win):
        self.win = win

    def handle_key(self, key):
        # trả True nếu đã xử lý phím
        return False

    def draw(self):
        self.win.noutrefresh()
