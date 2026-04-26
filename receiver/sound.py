import time

from machine import Pin, UART


class SoundBoard:
    def __init__(self, config, tick=None):
        self.tick = tick
        self.uart = UART(
            int(config.get("uart_id", 2)),
            baudrate=int(config.get("baudrate", 9600)),
            tx=int(config.get("tx", 17)),
            rx=int(config.get("rx", 16)),
        )
        self.reset_pin = Pin(int(config.get("reset_pin", 25)), Pin.OUT, value=1)
        self.current_volume = None
        if config.get("reset_on_boot", True):
            print("resetting sound board into UART mode...")
            self.reset()
        if config.get("startup_volume") is not None:
            self.set_volume(config.get("startup_volume"))

    def reset(self):
        self.reset_pin.value(0)
        time.sleep_ms(50)
        self.reset_pin.value(1)
        self.wait_ms(1000)

    def wait_ms(self, delay_ms):
        end = time.ticks_add(time.ticks_ms(), delay_ms)
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            if self.tick:
                self.tick()
            time.sleep_ms(10)

    def read_all(self, timeout_ms=1500):
        end = time.ticks_add(time.ticks_ms(), timeout_ms)
        data = b""
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            if self.uart.any():
                chunk = self.uart.read()
                if chunk:
                    data += chunk
            if self.tick:
                self.tick()
            time.sleep_ms(20)
        return data

    def send(self, cmd, timeout_ms=1500):
        print(">>", repr(cmd))
        self.uart.write((cmd + "\n").encode())
        data = self.read_all(timeout_ms)
        print("<<", data)
        return data

    def play_track(self, track_no):
        self.send("#{}".format(track_no), 1500)

    def volume_up(self, steps=1):
        return self.adjust_volume("+", steps)

    def volume_down(self, steps=1):
        return self.adjust_volume("-", steps)

    def adjust_volume(self, direction, steps=1):
        steps = max(1, int(steps))
        response = b""
        for _ in range(steps):
            response = self.send(direction, 250)
            parsed = parse_volume_response(response)
            if parsed is not None:
                self.current_volume = parsed
        if self.current_volume is not None:
            print("volume:", self.current_volume)
        return response

    def set_volume(self, volume):
        volume = max(0, min(204, int(volume)))
        if volume % 2:
            volume -= 1
        print("setting volume:", volume)

        # The Audio FX UART API exposes relative +/- commands, so absolute
        # volume is made deterministic by walking down to 0 first.
        self.adjust_volume("-", 102)
        if volume:
            self.adjust_volume("+", volume // 2)
        self.current_volume = volume
        print("volume:", self.current_volume)


def parse_volume_response(data):
    try:
        text = data.decode().strip()
    except Exception:
        return None
    digits = ""
    for char in text:
        if "0" <= char <= "9":
            digits += char
    if not digits:
        return None
    try:
        return int(digits[-3:])
    except Exception:
        return None


def handle_sound_command(text, sound, tracks):
    parts = text.split()
    if len(parts) >= 2 and parts[0].lower() == "sfx" and parts[1].lower() in ("volume", "vol"):
        if len(parts) < 3:
            print("volume:", sound.current_volume)
            return True
        action = parts[2].lower()
        steps = 1
        if len(parts) >= 4:
            try:
                steps = int(parts[3])
            except ValueError:
                steps = 1
        if action in ("up", "+"):
            sound.volume_up(steps)
        elif action in ("down", "-"):
            sound.volume_down(steps)
        else:
            try:
                sound.set_volume(int(action))
            except ValueError:
                print("usage: sfx volume up [steps], sfx volume down [steps], sfx volume <0-204>")
        return True

    if text == "list":
        sound.send("L", 2500)
        return True

    if text.startswith("play_"):
        try:
            sound.play_track(int(text[5:]))
        except ValueError:
            print("invalid play message:", text)
        return True

    if text == "exterminate":
        if "exterminate" in tracks:
            sound.play_track(tracks["exterminate"])
        else:
            sound.send("PT01.OGG", 1500)
        return True

    if text == "test0":
        sound.play_track(0)
        return True

    if text == "test1":
        sound.play_track(1)
        return True

    return False
