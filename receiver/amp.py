import time

from machine import I2C, Pin


TPA2016_DEFAULT_ADDRESS = 0x58
TPA2016_REG_GAIN = 0x05


class AmpShutdown:
    def __init__(self, config):
        self.enabled = bool(config.get("enabled", False))
        self.enable_value = int(config.get("enable_value", 1))
        self.shutdown_value = 0 if self.enable_value else 1
        self.auto_unmute = bool(config.get("auto_unmute", True))
        self.unmute_delay_ms = max(0, int(config.get("unmute_delay_ms", 1500)))
        self.pin = None
        self.muted = True

        if self.enabled:
            pin_no = int(config.get("shutdown_pin", 33))
            self.pin = Pin(pin_no, Pin.OUT, value=self.shutdown_value)
            print("amp shutdown pin:", pin_no, "enable_value:", self.enable_value)

    def mute(self):
        if not self.enabled or self.pin is None:
            return
        self.pin.value(self.shutdown_value)
        self.muted = True
        print("amp muted")

    def unmute(self):
        if not self.enabled or self.pin is None:
            return
        self.pin.value(self.enable_value)
        self.muted = False
        print("amp enabled")

    def toggle(self):
        if self.muted:
            self.unmute()
        else:
            self.mute()

    def unmute_after_boot(self, tick=None):
        if not self.enabled or not self.auto_unmute:
            return
        end = time.ticks_add(time.ticks_ms(), self.unmute_delay_ms)
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            if tick:
                tick()
            time.sleep_ms(10)
        self.unmute()


def handle_amp_command(text, command, amp):
    action = None

    if text:
        parts = text.split()
        if len(parts) >= 2 and parts[0].lower() == "amp":
            action = parts[1].lower()

    if command and command.get("cmd", "").lower() == "amp":
        action = command.get("action", command.get("value", action))
        if action is not None:
            action = str(action).lower()

    if action is None:
        return False

    if action in ("mute", "off", "shutdown"):
        amp.mute()
        return True

    if action in ("unmute", "on", "enable"):
        amp.unmute()
        return True

    if action == "toggle":
        amp.toggle()
        return True

    if action == "status":
        print("amp muted:", amp.muted)
        return True

    print("unknown amp command:", action)
    return True


class TPA2016:
    def __init__(self, config):
        self.enabled = bool(config.get("i2c_enabled", False))
        self.address = int(config.get("address", TPA2016_DEFAULT_ADDRESS))
        self.sda = int(config.get("sda", 21))
        self.scl = int(config.get("scl", 22))
        self.freq = int(config.get("freq", 400000))
        self.min_gain = max(-28, int(config.get("min_gain", -28)))
        self.max_gain = min(30, int(config.get("max_gain", 12)))
        self.default_gain = int(config.get("default_gain", 0))
        self.gain = None
        self.i2c = None

        if not self.enabled:
            return

        self.i2c = I2C(0, sda=Pin(self.sda), scl=Pin(self.scl), freq=self.freq)
        print("tpa2016 i2c sda:", self.sda, "scl:", self.scl, "addr:", hex(self.address))
        self.set_gain(self.default_gain)

    def scan(self):
        if not self.enabled or self.i2c is None:
            print("tpa2016 i2c disabled")
            return []
        try:
            found = self.i2c.scan()
        except OSError as exc:
            print("tpa2016 i2c scan failed:", exc)
            return []
        print("i2c scan:", [hex(addr) for addr in found])
        return found

    def read_u8(self, register):
        data = self.i2c.readfrom_mem(self.address, register, 1)
        return data[0]

    def write_u8(self, register, value):
        self.i2c.writeto_mem(self.address, register, bytes([value & 0xFF]))

    def gain_to_register(self, gain):
        gain = max(self.min_gain, min(self.max_gain, int(gain)))
        if gain < 0:
            return (gain + 64) & 0x3F
        return gain & 0x3F

    def set_gain(self, gain):
        if not self.enabled or self.i2c is None:
            print("tpa2016 i2c disabled")
            return
        gain = max(self.min_gain, min(self.max_gain, int(gain)))
        try:
            current = self.read_u8(TPA2016_REG_GAIN)
            value = (current & 0xC0) | self.gain_to_register(gain)
            self.write_u8(TPA2016_REG_GAIN, value)
        except OSError as exc:
            print("tpa2016 i2c write failed:", exc)
            return
        self.gain = gain
        print("amp gain:", self.gain, "dB")

    def adjust_gain(self, delta):
        if self.gain is None:
            self.gain = self.default_gain
        self.set_gain(self.gain + int(delta))


def handle_tpa_command(text, command, tpa):
    action = None
    args = []

    if text:
        parts = text.split()
        if parts and parts[0].lower() in ("volume", "vol"):
            args = parts[1:]
            if not args:
                action = "status"
            elif args[0].lower() in ("up", "+", "down", "-"):
                action = args[0].lower()
                args = args[1:]
            else:
                action = "gain"
        elif len(parts) >= 2 and parts[0].lower() == "tpa":
            action = parts[1].lower()
            args = parts[2:]

    if command and command.get("cmd", "").lower() in ("volume", "vol", "tpa"):
        action = command.get("action", command.get("value", action))
        if action is not None:
            action = str(action).lower()
        if "gain" in command:
            args = [str(command["gain"])]

    if action is None:
        return False

    if action in ("scan", "i2c_scan"):
        tpa.scan()
        return True

    if action in ("up", "+"):
        try:
            step = int(args[0]) if args else 1
        except ValueError:
            print("usage: volume up [db]")
            return True
        tpa.adjust_gain(step)
        return True

    if action in ("down", "-"):
        try:
            step = int(args[0]) if args else 1
        except ValueError:
            print("usage: volume down [db]")
            return True
        tpa.adjust_gain(-step)
        return True

    if action in ("gain", "set"):
        if not args:
            print("amp gain:", tpa.gain)
            return True
        try:
            tpa.set_gain(int(args[0]))
        except ValueError:
            print("usage: volume <gain_db>, volume up [db], volume down [db]")
        return True

    if action == "status":
        print("amp gain:", tpa.gain)
        return True

    try:
        tpa.set_gain(int(action))
    except ValueError:
        print("unknown tpa command:", action)
    return True
