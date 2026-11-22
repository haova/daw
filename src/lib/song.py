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

@dataclass
class Song:
    bpm: float = 120.0
    tracks: list[Track] = field(default_factory=list)

    @property
    def length(self):
        return max((n.end for t in self.tracks for n in t.notes), default=0.0)
