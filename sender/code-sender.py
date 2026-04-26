import network
import espnow
from machine import Pin
import json
import select
import sys
import time

# ESP-NOW peer MAC for the receiver. Keep this paired with the receiver board
# and on the same Wi-Fi channel or messages will silently disappear.
peer = b'\x78\x21\x84\x9d\x41\xe4'
WIFI_CHANNEL = 1

# Friendly console aliases. The receiver uses the same normalized target names,
# so commands like "outer eye rainbow" and "outer_eye rainbow" land identically.
TARGET_ALIASES = {
    "outer": "outer_eye",
    "outer_eye": "outer_eye",
    "outereye": "outer_eye",
    "inner": "inner_eye",
    "inner_eye": "inner_eye",
    "innereye": "inner_eye",
    "left_ear": "left_ear",
    "leftear": "left_ear",
    "right_ear": "right_ear",
    "rightear": "right_ear",
    "ears": "ears",
    "skirt": "skirt",
    "all": "all",
}

trigger_pins = [
    27, #  0 .
    26, #  1 .
    25, #  2 .
    33, #  3 .
    32, #  4 .
    15, #  5 .
    5,  #  6 
    13, #  7 .
    4,  #  8 .
    14  #  9 .
    ]

DEBOUNCE_MS = 50
PIN_LOW = 0
PIN_HIGH = 1

print("EXTERMINATE")

# ESP-NOW on ESP32/ESP8266 is tied to the station interface even when the board
# is not connected to an access point.
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
try:
    wlan.config(channel=WIFI_CHANNEL)
except Exception as exc:
    print("wifi channel config skipped:", exc)

e = espnow.ESPNow()
e.active(True)
e.add_peer(peer)

serial = select.poll()
serial.register(sys.stdin, select.POLLIN)
trigger_enabled = True
console_buffer = ""
prompt_pending = True

# Each trigger pin is active-low with a pull-up. The index in trigger_pins maps
# directly to the play_N message sent to the receiver.
trigger_pin_objs = {}

for track_no, pin_no in enumerate(trigger_pins):
    pin_obj = Pin(pin_no, Pin.IN, Pin.PULL_UP)
    trigger_pin_objs[pin_no] = {
        "pin": pin_no,
        "pin_obj": pin_obj,
        "last_state": pin_obj.value(),
        "track_no": track_no,
        "last_trigger_ms": 0,
    }


def is_triggered():
    """Return the first button edge that survives debounce, if any."""
    now = time.ticks_ms()

    for pin_no in trigger_pin_objs:
        t_pin = trigger_pin_objs[pin_no]
        current_state = t_pin["pin_obj"].value()
        last_state = t_pin["last_state"]

        t_pin["last_state"] = current_state

        if last_state == PIN_HIGH and current_state == PIN_LOW:
            elapsed = time.ticks_diff(now, t_pin["last_trigger_ms"])

            if elapsed >= DEBOUNCE_MS:
                t_pin["last_trigger_ms"] = now
                return t_pin

    return None


def send_payload(payload):
    """Send raw text or bytes to the configured ESP-NOW peer."""
    if isinstance(payload, str):
        payload = payload.encode()
    e.send(peer, payload)
    console_print("sent:", payload)


def send_json(payload):
    """Send structured commands for light control."""
    send_payload(json.dumps(payload))


def print_prompt():
    sys.stdout.write("sender> ")
    try:
        sys.stdout.flush()
    except Exception:
        pass


def console_print(*args):
    # Keep asynchronous replies readable without losing the half-typed command.
    print("")
    print(*args)
    if not prompt_pending:
        sys.stdout.write("sender> " + console_buffer)
        try:
            sys.stdout.flush()
        except Exception:
            pass


def print_help():
    print("")
    print("ESP-NOW sender commands")
    print("  help                         show this help")
    print("  trigger                      enable trigger-pin mode")
    print("  console                      disable trigger-pin mode")
    print("  play <0-9>                   send play_N trigger")
    print("  color <name|#rrggbb>         set solid color")
    print("  colour <name|#rrggbb>        same as color")
    print("  brightness <0.0-1.0>         set brightness")
    print("  max                          full current LED test")
    print("  speed <ms>                   set current animation frame delay")
    print("  amp <mute|unmute|toggle>     control receiver amp shutdown")
    print("  volume <up|down|gain_db>     control TPA2016 amp gain")
    print("  tpa <scan|status>            TPA2016 diagnostics")
    print("  sfx volume <up|down|0-204>   power-user Audio FX volume")
    print("  off                          turn lights off")
    print("  test                         run skirt pixel test")
    print("  randomize                    random color and animation")
    print("  status                       request skirt status")
    print("  <target> <command> ...       target skirt, outer_eye, inner_eye, ears, left_ear, right_ear, all")
    print("  solid [color]                solid animation")
    print("  max                          full current LED test")
    print("  rainbow [speed_ms]           rainbow animation")
    print("  theater [color] [speed_ms]   theater chase")
    print("  wipe [color] [speed_ms]      color wipe")
    print("  comet [color] [speed_ms]     comet animation")
    print("  scanner [color] [speed_ms]   scanner animation")
    print("  pulse [color] [speed_ms]     pulse animation")
    print("  sparkle [color] [speed_ms]   sparkle animation")
    print("  twinkle [color] [speed_ms]   twinkle animation")
    print("  raw <payload>                send exact text payload")
    print("  json <json>                  send exact JSON payload")
    print("")


def maybe_int(value):
    try:
        return int(value)
    except Exception:
        return None


def maybe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def normalize_target(value):
    """Convert user-facing target names into receiver target keys."""
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    return TARGET_ALIASES.get(key, key)


def compact_target_phrase(text):
    """Allow natural two-word target names before normal command splitting."""
    lower = text.lower()
    phrases = (
        ("outer eye", "outer_eye"),
        ("inner eye", "inner_eye"),
        ("left ear", "left_ear"),
        ("right ear", "right_ear"),
    )
    for phrase, target in phrases:
        if lower == phrase:
            return target
        if lower.startswith(phrase + " "):
            return target + text[len(phrase):]
    return text


def add_target(payload, target):
    if target:
        payload["target"] = target
    return payload


def animation_command(name, args, target=None):
    """Build the common animation JSON payload from console arguments."""
    payload = {"cmd": "animation", "name": name}
    add_target(payload, target)

    if args:
        if args[0].startswith("#") or args[0].isalpha() or args[0].startswith("0x"):
            payload["color"] = args[0]
            args = args[1:]

    if args:
        speed_ms = maybe_int(args[0])
        if speed_ms is not None:
            payload["speed_ms"] = speed_ms
            args = args[1:]

    if args:
        tail = maybe_int(args[0])
        if tail is not None:
            payload["tail"] = tail

    send_json(payload)


def handle_target_command(target, args):
    """Handle commands that explicitly start with a light target."""
    if not args:
        print("usage: <target> <command> ...")
        return True

    cmd = args[0].lower()
    rest = args[1:]

    if cmd in ("color", "colour") and rest:
        send_json({"target": target, "cmd": "color", "color": rest[0]})
    elif cmd in ("brightness", "bright", "b") and rest:
        value = maybe_float(rest[0])
        if value is None:
            print("usage: <target> brightness <0.0-1.0>")
        else:
            send_json({"target": target, "cmd": "brightness", "value": value})
    elif cmd in ("speed", "delay") and rest:
        speed_ms = maybe_int(rest[0])
        if speed_ms is None:
            print("usage: <target> speed <ms>")
        else:
            send_json({"target": target, "cmd": "speed", "value": speed_ms})
    elif cmd == "off":
        send_json({"target": target, "cmd": "off"})
    elif cmd == "test":
        send_json({"target": target, "cmd": "test"})
    elif cmd == "randomize":
        send_json({"target": target, "cmd": "randomize"})
    elif cmd == "status":
        send_json({"target": target, "cmd": "status"})
    elif cmd == "solid":
        payload = {"target": target, "cmd": "solid"}
        if rest:
            payload["color"] = rest[0]
        send_json(payload)
    elif cmd == "max":
        send_json({"target": target, "cmd": "max"})
    elif cmd == "rainbow":
        animation_command("rainbow", rest, target)
    elif cmd == "theater":
        animation_command("theater_chase", rest, target)
    elif cmd == "wipe":
        animation_command("color_wipe", rest, target)
    elif cmd in ("comet", "scanner", "pulse", "sparkle", "twinkle"):
        animation_command(cmd, rest, target)
    else:
        print("unknown target command:", cmd)
        print("type 'help' for commands")
    return True


def handle_console(line):
    """Parse one completed serial-console command."""
    global trigger_enabled

    line = compact_target_phrase(line.strip())
    if not line:
        return

    parts = line.split()
    cmd = parts[0].lower()
    args = parts[1:]
    target = normalize_target(cmd)

    if target in TARGET_ALIASES.values():
        handle_target_command(target, args)
        return

    if cmd in ("help", "?"):
        print_help()

    elif cmd == "trigger":
        trigger_enabled = True
        print("trigger-pin mode enabled")

    elif cmd in ("console", "serial"):
        trigger_enabled = False
        print("trigger-pin mode disabled")

    elif cmd == "play" and args:
        track_no = maybe_int(args[0])
        if track_no is None:
            print("usage: play <0-9>")
        else:
            send_payload("play_{}".format(track_no))

    elif cmd in ("color", "colour") and args:
        send_json({"cmd": "color", "color": args[0]})

    elif cmd in ("brightness", "bright", "b") and args:
        value = maybe_float(args[0])
        if value is None:
            print("usage: brightness <0.0-1.0>")
        else:
            send_json({"cmd": "brightness", "value": value})

    elif cmd in ("speed", "delay") and args:
        speed_ms = maybe_int(args[0])
        if speed_ms is None:
            print("usage: speed <ms>")
            print("try: speed 10, speed 75, speed 150, speed 300")
        else:
            send_json({"cmd": "speed", "value": speed_ms})

    elif cmd == "amp" and args:
        send_payload(line)

    elif cmd in ("volume", "vol") and args:
        send_payload(line)

    elif cmd == "tpa" and args:
        send_payload(line)

    elif cmd == "sfx" and args:
        send_payload(line)

    elif cmd == "off":
        send_json({"cmd": "off"})

    elif cmd == "test":
        send_json({"cmd": "test"})

    elif cmd == "randomize":
        send_json({"cmd": "randomize"})

    elif cmd == "status":
        send_json({"cmd": "status"})

    elif cmd == "solid":
        payload = {"cmd": "solid"}
        if args:
            payload["color"] = args[0]
        send_json(payload)

    elif cmd == "max":
        send_json({"target": "all", "cmd": "max"})

    elif cmd == "rainbow":
        if args:
            animation_command("rainbow", args)
        else:
            send_json({"cmd": "animation", "name": "rainbow"})

    elif cmd == "theater":
        animation_command("theater_chase", args)

    elif cmd == "wipe":
        animation_command("color_wipe", args)

    elif cmd in ("comet", "scanner", "pulse", "sparkle", "twinkle"):
        animation_command(cmd, args)

    elif cmd == "raw" and args:
        send_payload(line[4:])

    elif cmd == "json" and args:
        payload = line[5:]
        try:
            json.loads(payload)
        except ValueError as exc:
            print("invalid json:", exc)
            return
        send_payload(payload)

    else:
        print("unknown command:", cmd)
        print("type 'help' for commands")


def read_console():
    """Read stdin one character at a time so the main loop stays responsive."""
    global console_buffer, prompt_pending

    if prompt_pending:
        print_prompt()
        prompt_pending = False

    if serial.poll(0):
        char = sys.stdin.read(1)

        if char in ("\r", "\n"):
            sys.stdout.write("\n")
            line = console_buffer
            console_buffer = ""
            prompt_pending = True
            return line

        if char in ("\b", "\x7f"):
            if console_buffer:
                console_buffer = console_buffer[:-1]
                sys.stdout.write("\b \b")
                try:
                    sys.stdout.flush()
                except Exception:
                    pass
            return None

        if char >= " ":
            console_buffer += char
            sys.stdout.write(char)
            try:
                sys.stdout.flush()
            except Exception:
                pass

    return None


def read_replies():
    """Print optional receiver replies, such as status responses."""
    host, msg = e.recv(0)
    if msg:
        try:
            console_print("reply:", msg.decode())
        except Exception:
            console_print("reply:", msg)


print("ESP-NOW sender ready")
print("type 'help' for commands")

while True:
    # Keep all three activities cooperative: console input, button triggers, and
    # receiver replies. Long sleeps would make buttons and typing feel laggy.
    line = read_console()
    if line is not None:
        handle_console(line)

    if trigger_enabled:
        triggered = is_triggered()

        if triggered:
            payload = "play_{}".format(triggered["track_no"])
            send_payload(payload)

    read_replies()

    time.sleep_ms(10)
