import subprocess
import time

import mido

DRUM_CHANNEL = 9
SOUNDFONT = "/usr/share/soundfonts/FluidR3_GM.sf2"

class Synth:
    def __init__(self, name=None, soundfont=SOUNDFONT, gain=1.0):
        self.name = name
        self.soundfont = soundfont
        self.gain = gain
        self._port = None
        self._proc = None

    def open(self):
        name = self.name or self._find_port() or self._start()
        self._port = mido.open_output(name)

    def close(self):
        if self._port:
            self.all_off()
            self._port.close()
            self._port = None
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None

    def note_on(self, note, velocity=100, channel=0):
        self._send("note_on", channel=channel, note=note, velocity=velocity)

    def note_off(self, note, channel=0):
        self._send("note_off", channel=channel, note=note)

    def play(self, note, channel=0):
        if note.on:
            self.note_on(note.note, note.velocity, channel)
        else:
            self.note_off(note.note, channel)

    def program(self, program, channel=0, bank=0):
        if bank:
            self._send("control_change", channel=channel, control=0, value=bank >> 7)
            self._send("control_change", channel=channel, control=32, value=bank & 0x7F)
        self._send("program_change", channel=channel, program=program)

    def control(self, control, value, channel=0):
        self._send("control_change", channel=channel, control=control, value=value)

    def all_off(self):
        for ch in range(16):
            self._send("control_change", channel=ch, control=123, value=0)

    def send(self, msg):
        if self._port:
            self._port.send(msg)

    def _send(self, type, **kw):
        self.send(mido.Message(type, **kw))

    def _find_port(self):
        for name in mido.get_output_names():
            if "fluid" in name.lower():
                return name
        return None

    def _start(self):
        self._proc = subprocess.Popen(
            ["fluidsynth", "-a", "pulseaudio", "-m", "alsa_seq", "-g", str(self.gain), "-is", self.soundfont],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(50):
            if self._proc.poll() is not None:
                break
            name = self._find_port()
            if name:
                return name
            time.sleep(0.1)
        code = self._proc.poll()
        self.close()
        raise RuntimeError(f"không khởi động được FluidSynth (soundfont: {self.soundfont}, mã thoát: {code})")
