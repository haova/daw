import mido

from lib.song import CHORUS, EXPRESSION, MODULATION, PAN, REVERB, SWITCHES, VOLUME, Kind, Note, Song, Track

LEVELS = {MODULATION, VOLUME, PAN, EXPRESSION, REVERB, CHORUS}  # CC mức giá trị được đọc, các CC khác bỏ qua

def load(path):
    song = Song()
    programs = {}
    open_notes = {}
    open_effects = {}  # (channel, số CC) hoặc (channel, None) cho pitch bend -> (bắt đầu, giá trị, chương trình)
    tracks = {}
    now = 0.0
    bpm_found = False
    signature_found = False

    def close(channel, pitch):
        start, velocity, program = open_notes.pop((channel, pitch))
        track = tracks.setdefault((channel, program), Track(channel, program))
        track.notes.append(Note(pitch, velocity, start, now))

    def close_effect(key, end):
        start, value, program = open_effects.pop(key)
        channel, controller = key
        if end - start < 1e-6:
            return  # bị giá trị khác đè ngay cùng lúc, bỏ
        track = tracks.setdefault((channel, program), Track(channel, program))
        if controller is None:
            track.notes.append(Note(0, value, start, end, Kind.BEND))
        else:
            track.notes.append(Note(controller, value, start, end, Kind.CONTROL))

    def set_effect(key, value, on):
        # công tắc: on mở, off đóng; mức giá trị: mỗi giá trị mới đóng giá trị trước
        if key in open_effects and on is not False:
            close_effect(key, now)
        if on is False:
            if key in open_effects:
                close_effect(key, now)
        else:
            open_effects[key] = (now, value, programs.get(key[0], 0))

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
        elif msg.type == "note_on" and msg.velocity > 0:
            if (msg.channel, msg.note) in open_notes:
                close(msg.channel, msg.note)
            open_notes[(msg.channel, msg.note)] = (now, msg.velocity, programs.get(msg.channel, 0))
        elif msg.type in ("note_on", "note_off") and (msg.channel, msg.note) in open_notes:
            close(msg.channel, msg.note)
        elif msg.type == "control_change" and msg.control in SWITCHES:
            if msg.value >= 64:
                if (msg.channel, msg.control) not in open_effects:
                    set_effect((msg.channel, msg.control), 127, True)
            else:
                set_effect((msg.channel, msg.control), 0, False)
        elif msg.type == "control_change" and msg.control in LEVELS:
            set_effect((msg.channel, msg.control), msg.value, True)
        elif msg.type == "pitchwheel":
            set_effect((msg.channel, None), (msg.pitch + 8192) >> 7, True)

    for channel, pitch in list(open_notes):
        close(channel, pitch)
    for key in list(open_effects):
        close_effect(key, now)

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
        # thứ tự trong cùng một tick: đổi nhạc cụ, nhả pedal, hiệu ứng khác, nhả nốt, nhấn nốt
        events = [(to_tick(min(n.start for n in t.notes)), 0, mido.Message("program_change", channel=t.channel, program=t.program))]
        for n in t.notes:
            start, end = to_tick(n.start), to_tick(n.end)
            if n.kind is Kind.NOTE:
                events.append((start, 4, mido.Message("note_on", channel=t.channel, note=n.pitch, velocity=n.velocity)))
                events.append((max(end, start + 1), 3, mido.Message("note_off", channel=t.channel, note=n.pitch)))
            elif n.kind is Kind.BEND:
                bend = min(max((n.velocity - 64) * 128, -8192), 8191)
                events.append((start, 2, mido.Message("pitchwheel", channel=t.channel, pitch=bend)))
            elif n.kind is Kind.CONTROL and n.pitch in SWITCHES:
                events.append((start, 2, mido.Message("control_change", channel=t.channel, control=n.pitch, value=127)))
                events.append((end, 1, mido.Message("control_change", channel=t.channel, control=n.pitch, value=0)))
            elif n.kind is Kind.CONTROL:
                events.append((start, 2, mido.Message("control_change", channel=t.channel, control=n.pitch, value=n.velocity)))
        events.sort(key=lambda e: e[:2])

        track = mido.MidiTrack()
        last = 0
        for tick, _, msg in events:
            track.append(msg.copy(time=tick - last))
            last = tick
        track.append(mido.MetaMessage("end_of_track"))
        mid.tracks.append(track)

    mid.save(path)
