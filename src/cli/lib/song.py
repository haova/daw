from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class Note:
    pitch: int
    velocity: int
    start: float
    end: float

@dataclass
class Track:
    channel: int
    program: int
    notes: list[Note] = field(default_factory=list)
    volume: int = 100  # CC7 channel volume (gain của kênh), 100 là mặc định GM

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
