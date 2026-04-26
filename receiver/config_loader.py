import json


CONFIG_FILE = "config.json"

# Defaults are kept in code so a missing or partial config.json can still boot
# the receiver with sensible hardware mappings.
DEFAULT_CONFIG = {
    "wifi_channel": 1,
    "sound": {
        "uart_id": 2,
        "baudrate": 9600,
        "tx": 17,
        "rx": 16,
        "reset_pin": 25,
        "reset_on_boot": True,
        "startup_volume": None,
    },
    "tracks": {
        "exterminate": 0,
        "beep": 1,
    },
    "amp": {
        "enabled": True,
        "shutdown_pin": 33,
        "enable_value": 1,
        "auto_unmute": True,
        "unmute_delay_ms": 1500,
        "i2c_enabled": True,
        "sda": 21,
        "scl": 22,
        "address": 0x58,
        "default_gain": 0,
        "min_gain": -28,
        "max_gain": 12,
    },
    "inputs": {
        "audio_act": {
            "enabled": True,
            "pin": 32,
            "active": 0,
            "pull": "up",
            "targets": ["left_ear", "right_ear"],
            "animation": "pulse",
            "color": None,
            "speed_ms": 45,
            "pulse_speed_ms": 45,
            "min_brightness": 0.15,
            "max_brightness": 1.0,
        },
    },
    "lights": {
        "brightness": 0.35,
        "default_color": "#0080ff",
        "default_target": "skirt",
        "play_triggers_lights": False,
        "startup_animation": "solid",
        "animation_speed_ms": 35,
        "strips": [
            {"name": "left_skirt", "group": "skirt", "pin": 18, "pixels": 60, "bpp": 4, "enabled": True},
            {"name": "right_skirt", "group": "skirt", "pin": 19, "pixels": 60, "bpp": 4, "enabled": True},
            {"name": "outer_eye", "group": "outer_eye", "pin": 23, "pixels": 24, "bpp": 3, "enabled": True},
            {"name": "inner_eye", "group": "inner_eye", "pin": 14, "pixels": 7, "bpp": 4, "enabled": True},
            {"name": "left_ear", "group": "left_ear", "pin": 27, "pixels": 7, "bpp": 4, "enabled": True},
            {"name": "right_ear", "group": "right_ear", "pin": 26, "pixels": 7, "bpp": 4, "enabled": True},
        ],
        "target_options": {
            "skirt": {"comet_tail": 18, "scanner_tail": 5, "sparkle_count": 8, "twinkle_count": 24},
            "outer_eye": {"comet_tail": 6, "scanner_tail": 3, "sparkle_count": 4, "twinkle_count": 8},
            "inner_eye": {"comet_tail": 2, "scanner_tail": 1, "sparkle_count": 1, "twinkle_count": 2},
            "left_ear": {"comet_tail": 2, "scanner_tail": 1, "sparkle_count": 1, "twinkle_count": 2},
            "right_ear": {"comet_tail": 2, "scanner_tail": 1, "sparkle_count": 1, "twinkle_count": 2},
        },
        "triggers": {
            "play_0": {"target": "skirt", "cmd": "animation", "name": "rainbow", "speed_ms": 20},
            "play_1": {"target": "skirt", "cmd": "animation", "name": "pulse", "color": "#ff0000"},
            "play_2": {"target": "skirt", "cmd": "animation", "name": "theater_chase", "color": "#ffffff"},
            "play_3": {"target": "skirt", "cmd": "animation", "name": "comet", "color": "#00ffff"},
            "play_4": {"target": "skirt", "cmd": "animation", "name": "scanner", "color": "#ff8000"},
            "play_5": {"target": "skirt", "cmd": "animation", "name": "sparkle", "color": "#8040ff"},
            "play_6": {"target": "skirt", "cmd": "animation", "name": "twinkle", "color": "#ffffff"},
            "play_7": {"target": "skirt", "cmd": "animation", "name": "color_wipe", "color": "#00ff00"},
            "play_8": {"target": "skirt", "cmd": "solid", "color": "#0080ff"},
            "play_9": {"target": "skirt", "cmd": "off"},
        },
    },
}


def deep_update(base, updates):
    """Merge nested dicts so config.json can override only the keys it needs."""
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base


def load_config():
    """Load config.json, creating it from defaults when it is absent."""
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        with open(CONFIG_FILE, "r") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            deep_update(config, loaded)
    except OSError:
        save_config(config)
    except ValueError as exc:
        print("config parse failed, using defaults:", exc)
    return config


def save_config(config):
    """Persist the current config in compact JSON for MicroPython."""
    with open(CONFIG_FILE, "w") as handle:
        json.dump(config, handle)
