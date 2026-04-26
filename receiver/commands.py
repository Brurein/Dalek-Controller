import json

from lights import (
    ANIMATIONS,
    compact_target_phrase,
    configured_targets,
    normalize_target,
    randomize_controller,
    run_pixel_test,
    selected_controllers,
)


def send_reply(esp, host, payload):
    """Send a best-effort ESP-NOW response to the sender that issued a command."""
    if not host:
        return
    try:
        try:
            esp.add_peer(host)
        except OSError:
            pass
        esp.send(host, json.dumps(payload).encode())
    except Exception as exc:
        print("reply failed:", exc)


def is_number(text):
    try:
        float(text)
        return True
    except Exception:
        return False


def add_plain_args(command, args):
    """Interpret compact text commands as color, speed, and optional tail."""
    if not args:
        return
    first = args[0]
    if is_number(first):
        command["speed_ms"] = int(float(first))
    else:
        command["color"] = first
    if len(args) > 1 and is_number(args[1]):
        command["speed_ms"] = int(float(args[1]))
    if len(args) > 2 and is_number(args[2]):
        command["tail"] = int(float(args[2]))


def animation_params(command):
    """Keep animation-specific tuning keys separate from generic command data."""
    params = {}
    for key in ("tail", "comet_tail", "scanner_tail", "sparkle_count", "twinkle_count"):
        if key in command:
            params[key] = command[key]
    return params


def decode_command(message, light_config):
    """Decode ESP-NOW bytes into a light command plus the original text."""
    try:
        text = compact_target_phrase(message.decode().strip())
    except Exception:
        print("bad message:", message)
        return None, ""

    command = None
    triggers = light_config.get("triggers", {})
    # play_N always goes to sound. It only becomes a light command when enabled
    # globally or when the trigger is explicitly listed in the config.
    if text.startswith("play_") and not light_config.get("play_triggers_lights", False):
        command = None
    elif text in triggers:
        command = triggers[text]
    elif text.startswith("{"):
        try:
            command = json.loads(text)
        except ValueError as exc:
            print("bad json:", exc)
            return None, text
    else:
        parts = text.split()
        if not parts:
            return None, text
        targets = configured_targets(light_config)
        first = normalize_target(parts[0])
        if len(parts) > 1 and first in targets:
            command = {"target": first, "cmd": parts[1].lower()}
            add_plain_args(command, parts[2:])
        else:
            command = {"cmd": parts[0].lower()}
            add_plain_args(command, parts[1:])
    return command, text


def handle_light_command(command, host, esp, controllers, light_config, full_config, save_config):
    """Apply one decoded light command to the selected controller group."""
    cmd = command.get("cmd", "animation").lower()
    if cmd == "colour":
        cmd = "color"
    selected = selected_controllers(command, controllers, light_config)
    if not selected:
        return False
    print("light target(s):", ", ".join(selected.keys()), "cmd:", cmd)

    if cmd in ("animation", "animate", "run"):
        for target in selected:
            selected[target].start(
                command.get("name", command.get("animation", "solid")),
                color=command.get("color"),
                brightness=command.get("brightness"),
                speed_ms=command.get("speed_ms"),
                duration_ms=command.get("duration_ms", 0),
                **animation_params(command)
            )
        return True

    if cmd in ANIMATIONS:
        for target in selected:
            selected[target].start(
                cmd,
                color=command.get("color"),
                brightness=command.get("brightness"),
                speed_ms=command.get("speed_ms"),
                duration_ms=command.get("duration_ms", 0),
                **animation_params(command)
            )
        return True

    if cmd == "color":
        for target in selected:
            color = command.get("color", command.get("colour", command.get("value")))
            selected[target].set_color(color)
        return True

    if cmd == "brightness":
        for target in selected:
            selected[target].start(selected[target].name, brightness=command.get("value", command.get("brightness")))
        return True

    if cmd in ("speed", "delay"):
        speed_ms = command.get("value", command.get("speed_ms"))
        if speed_ms is None:
            print("missing speed value")
        else:
            for target in selected:
                selected[target].speed_ms = max(5, int(speed_ms))
                selected[target].needs_first_frame = True
                print("speed_ms:", target, selected[target].speed_ms)
        return True

    if cmd == "randomize":
        for target in selected:
            randomize_controller(selected[target])
        return True

    if cmd == "test":
        for target in selected:
            run_pixel_test(selected[target].strips, command.get("brightness", selected[target].brightness))
            selected[target].needs_first_frame = True
        return True

    if cmd == "status":
        status = {}
        for target in controllers:
            status[target] = {
                "animation": controllers[target].name,
                "brightness": controllers[target].brightness,
                "color": controllers[target].color,
            }
        send_reply(esp, host, {"targets": status, "animations": ANIMATIONS})
        return True

    if cmd in ("config", "set_config"):
        # Only a small safe subset of light config is writable over ESP-NOW.
        for key in ("brightness", "default_color", "startup_animation", "animation_speed_ms"):
            if key in command:
                light_config[key] = command[key]
        if "strips" in command and isinstance(command["strips"], list):
            light_config["strips"] = command["strips"]
        if command.get("save", True):
            save_config(full_config)
        for target in selected:
            selected[target].start(
                command.get("startup_animation", light_config.get("startup_animation", "solid")),
                color=command.get("default_color", light_config.get("default_color")),
                brightness=command.get("brightness", light_config.get("brightness")),
                speed_ms=command.get("animation_speed_ms", light_config.get("animation_speed_ms")),
            )
        send_reply(esp, host, {"ok": True, "config_saved": bool(command.get("save", True))})
        return True

    return False
