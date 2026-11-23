import mido

from lib.song import Note, Song, Track

def load(path):
    song = Song()
    programs = {}
    volumes = {}  # CC7 theo channel
    open_notes = {}
    tracks = {}
    now = 0.0
    bpm_found = False
    signature_found = False

    def close(channel, pitch):
        start, velocity, program = open_notes.pop((channel, pitch))
        track = tracks.setdefault((channel, program), Track(channel, program, volume=volumes.get(channel, 100)))
        track.notes.append(Note(pitch, velocity, start, now))

    for msg in mido.MidiFile(path):
        now += msg.time
        if msg.type == "set_tempo" and not bpm_found:
            song.bpm = mido.tempo2bpm(msg.tempo)
            bpm_found = True
        elif msg.type == "time_signature" and not signature_found:
            song.time_signature = (msg.numerator, msg.denominator)
            signature_found = True
        elif msg.type == "program_change":
            programs[msg.channel] = msg.program
        elif msg.type == "control_change" and msg.control == 7:
            volumes[msg.channel] = msg.value
        elif msg.type == "note_on" and msg.velocity > 0:
            if (msg.channel, msg.note) in open_notes:
                close(msg.channel, msg.note)
            open_notes[(msg.channel, msg.note)] = (now, msg.velocity, programs.get(msg.channel, 0))
        elif msg.type in ("note_on", "note_off") and (msg.channel, msg.note) in open_notes:
            close(msg.channel, msg.note)

    for channel, pitch in list(open_notes):
        close(channel, pitch)

    for track in tracks.values():
        track.notes.sort(key=lambda n: (n.start, n.pitch))
    song.tracks = sorted(tracks.values(), key=lambda t: (t.channel, t.program))
    return song

def write(song, path, ppq=480):
    mid = mido.MidiFile(ticks_per_beat=ppq)

    tempo = mido.MidiTrack()
    tempo.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(song.bpm)))
    numerator, denominator = song.time_signature
    tempo.append(mido.MetaMessage("time_signature", numerator=numerator, denominator=denominator))
    tempo.append(mido.MetaMessage("end_of_track"))
    mid.tracks.append(tempo)

    to_tick = lambda sec: round(sec * song.bpm / 60 * ppq)

    for t in song.tracks:
        if not t.notes:
            continue
        first = to_tick(t.notes[0].start)
        events = [(first, 0, mido.Message("program_change", channel=t.channel, program=t.program)),
                  (first, 0, mido.Message("control_change", channel=t.channel, control=7, value=t.volume))]
        for n in t.notes:
            start, end = to_tick(n.start), to_tick(n.end)
            events.append((start, 2, mido.Message("note_on", channel=t.channel, note=n.pitch, velocity=n.velocity)))
            events.append((max(end, start + 1), 1, mido.Message("note_off", channel=t.channel, note=n.pitch)))
        events.sort(key=lambda e: e[:2])

        track = mido.MidiTrack()
        last = 0
        for tick, _, msg in events:
            track.append(msg.copy(time=tick - last))
            last = tick
        track.append(mido.MetaMessage("end_of_track"))
        mid.tracks.append(track)

    mid.save(path)
