from dataclasses import dataclass, field
from enum import Enum

class Kind(Enum):
    NOTE = "note"          # nốt thường
    CONTROL = "control"    # lệnh CC: pitch = số CC, velocity = giá trị
    BEND = "bend"          # pitch bend: velocity = 0-127, 64 là giữa
    PRESSURE = "pressure"  # aftertouch: pitch = nốt (0 là cả channel), velocity = lực

# số CC của các hiệu ứng hay dùng
MODULATION = 1
VOLUME = 7
PAN = 10
EXPRESSION = 11
SUSTAIN = 64
PORTAMENTO = 65
SOSTENUTO = 66
SOFT = 67
REVERB = 91
CHORUS = 93

SWITCHES = {SUSTAIN, PORTAMENTO, SOSTENUTO, SOFT}  # công tắc: hết nốt thì nhả

@dataclass(frozen=True, slots=True)
class Note:
    pitch: int
    velocity: int
    start: float
    end: float
    kind: Kind = Kind.NOTE

@dataclass
class Track:
    channel: int
    program: int
    notes: list[Note] = field(default_factory=list)

@dataclass
class Song:
    bpm: float = 120.0
    tracks: list[Track] = field(default_factory=list)
    time_signature: tuple[int, int] = (4, 4)

    @property
    def beats_per_bar(self):
        numerator, denominator = self.time_signature
        return numerator * 4 / denominator

    @property
    def length(self):
        return max((n.end for t in self.tracks for n in t.notes), default=0.0)
