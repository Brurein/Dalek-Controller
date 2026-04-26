import math
import random
import time

import neopixel
from machine import Pin


# Canonical target names are shared with the sender so text and JSON commands
# can address the same physical light groups.
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

ANIMATIONS = (
    "solid",
    "max",
    "off",
    "rainbow",
    "theater_chase",
    "color_wipe",
    "comet",
    "scanner",
    "pulse",
    "sparkle",
    "twinkle",
)

RANDOM_ANIMATIONS = (
    "solid",
    "rainbow",
    "theater_chase",
    "color_wipe",
    "comet",
    "scanner",
    "pulse",
    "sparkle",
    "twinkle",
)

RANDOM_COLORS = (
    "red",
    "green",
    "blue",
    "white",
    "warm_white",
    "yellow",
    "orange",
    "purple",
    "pink",
    "cyan",
    "#0080ff",
    "#ff4000",
)


def clamp(value, low, high):
    return max(low, min(high, value))


def normalize_target(value):
    if value is None:
        return None
    key = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return TARGET_ALIASES.get(key, key)


def compact_target_phrase(text):
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


def parse_color(value, fallback=(0, 128, 255, 0)):
    """Accept named colors, #RGB/#RRGGBB/0xRRGGBB, ints, or RGB/RGBW tuples."""
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (
            clamp(int(value[0]), 0, 255),
            clamp(int(value[1]), 0, 255),
            clamp(int(value[2]), 0, 255),
            clamp(int(value[3]), 0, 255) if len(value) >= 4 else 0,
        )

    if isinstance(value, int):
        return ((value >> 16) & 255, (value >> 8) & 255, value & 255, 0)

    if not isinstance(value, str):
        return fallback

    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    elif text.startswith("0x"):
        text = text[2:]

    if len(text) == 3:
        text = "".join(ch + ch for ch in text)

    try:
        raw = int(text, 16)
        return ((raw >> 16) & 255, (raw >> 8) & 255, raw & 255, 0)
    except ValueError:
        named = {
            "red": (255, 0, 0, 0),
            "green": (0, 255, 0, 0),
            "blue": (0, 0, 255, 0),
            "white": (0, 0, 0, 255),
            "rgb_white": (255, 255, 255, 0),
            "warm_white": (0, 0, 0, 180),
            "yellow": (255, 180, 0, 0),
            "orange": (255, 80, 0, 0),
            "purple": (140, 0, 255, 0),
            "pink": (255, 30, 120, 0),
            "cyan": (0, 180, 255, 0),
            "black": (0, 0, 0, 0),
            "off": (0, 0, 0, 0),
        }
        return named.get(value.lower(), fallback)


def scale_color(color, brightness):
    brightness = clamp(float(brightness), 0.0, 1.0)
    return (
        int(color[0] * brightness),
        int(color[1] * brightness),
        int(color[2] * brightness),
        int(color[3] * brightness) if len(color) >= 4 else 0,
    )


def fit_color(color, bpp):
    """Convert internal RGBW colors to the strip's configured byte depth."""
    if bpp == 4:
        return (color[0], color[1], color[2], color[3] if len(color) >= 4 else 0)
    if len(color) >= 4 and color[0] == 0 and color[1] == 0 and color[2] == 0 and color[3] > 0:
        return (color[3], color[3], color[3])
    return (color[0], color[1], color[2])


def wheel(pos):
    pos = 255 - (pos % 256)
    if pos < 85:
        return (255 - pos * 3, 0, pos * 3, 0)
    if pos < 170:
        pos -= 85
        return (0, pos * 3, 255 - pos * 3, 0)
    pos -= 170
    return (pos * 3, 255 - pos * 3, 0, 0)


class StripPair:
    """Treat one logical light target as one or more physical NeoPixel strips."""

    def __init__(self, strip_configs):
        self.strips = []
        self.max_pixels = 0
        for strip_config in strip_configs:
            if not strip_config.get("enabled", True):
                continue
            pin_no = int(strip_config["pin"])
            pixels = int(strip_config.get("pixels", 60))
            bpp = int(strip_config.get("bpp", 4))
            strip = neopixel.NeoPixel(Pin(pin_no, Pin.OUT), pixels, bpp=bpp)
            print("strip:", strip_config.get("name", "strip"), "pin:", pin_no, "pixels:", pixels, "bpp:", bpp)
            self.strips.append({"name": strip_config.get("name", "strip"), "pixels": pixels, "bpp": bpp, "strip": strip})
            self.max_pixels = max(self.max_pixels, pixels)

    def set_pixel(self, index, color):
        for item in self.strips:
            if 0 <= index < item["pixels"]:
                item["strip"][index] = fit_color(color, item["bpp"])

    def fill(self, color):
        for item in self.strips:
            fitted = fit_color(color, item["bpp"])
            for index in range(item["pixels"]):
                item["strip"][index] = fitted

    def clear(self):
        self.fill((0, 0, 0, 0))

    def write(self):
        for item in self.strips:
            item["strip"].write()


def configured_targets(light_config):
    """Return the target names available from the current strip config."""
    targets = {"all", "ears"}
    for strip_config in light_config.get("strips", []):
        if strip_config.get("enabled", True):
            targets.add(normalize_target(strip_config.get("group", "skirt")))
    return targets


def grouped_strip_configs(light_config):
    groups = {}
    for strip_config in light_config.get("strips", []):
        if not strip_config.get("enabled", True):
            continue
        group = normalize_target(strip_config.get("group", "skirt"))
        if group not in groups:
            groups[group] = []
        groups[group].append(strip_config)
    return groups


def selected_controllers(command, controllers, light_config):
    """Resolve all/ears/single-target commands into controller instances."""
    target = normalize_target(command.get("target", light_config.get("default_target", "skirt")))
    if target == "all":
        return dict(controllers)
    if target == "ears":
        selected = {}
        for ear_target in ("left_ear", "right_ear"):
            if ear_target in controllers:
                selected[ear_target] = controllers[ear_target]
        return selected
    if target in controllers:
        return {target: controllers[target]}
    print("unknown light target:", target)
    return {}


def tick_controllers(controllers):
    for target in controllers:
        controllers[target].tick()


def run_pixel_test(strips, brightness=0.2):
    """Exercise RGB and white channels to help catch wiring or bpp mistakes."""
    print("pixel test: red green blue white-channel rgb-white off")
    for color in ((255, 0, 0, 0), (0, 255, 0, 0), (0, 0, 255, 0), (0, 0, 0, 255), (255, 255, 255, 0), (0, 0, 0, 0)):
        strips.fill(scale_color(color, brightness))
        strips.write()
        time.sleep_ms(700)


class AnimationController:
    """Own the animation state for one logical light target."""

    def __init__(self, strips, config, target="lights", options=None):
        self.target = target
        self.strips = strips
        self.config = config
        self.options = options or {}
        self.name = "solid"
        self.color = parse_color(config.get("default_color"))
        self.brightness = float(config.get("brightness", 0.35))
        self.speed_ms = int(config.get("animation_speed_ms", 35))
        self.comet_tail = int(self.options.get("comet_tail", 18))
        self.scanner_tail = int(self.options.get("scanner_tail", 5))
        self.sparkle_count = int(self.options.get("sparkle_count", 8))
        self.twinkle_count = int(self.options.get("twinkle_count", 24))
        self.frame = 0
        self.started_ms = time.ticks_ms()
        self.last_frame_ms = 0
        self.duration_ms = 0
        self.needs_first_frame = True

    def start(self, name, color=None, brightness=None, speed_ms=None, duration_ms=0, **params):
        """Switch animation and update any supplied runtime parameters."""
        if name not in ANIMATIONS:
            print("unknown animation:", name)
            return False
        self.name = name
        if color is not None:
            self.color = parse_color(color, self.color)
        if name == "max":
            brightness = 1.0
        if brightness is not None:
            self.brightness = clamp(float(brightness), 0.0, 1.0)
        if speed_ms is not None:
            self.speed_ms = max(5, int(speed_ms))
        if params.get("comet_tail") is not None:
            self.comet_tail = max(1, int(params.get("comet_tail")))
        if params.get("tail") is not None:
            self.comet_tail = max(1, int(params.get("tail")))
        if params.get("scanner_tail") is not None:
            self.scanner_tail = max(0, int(params.get("scanner_tail")))
        if params.get("sparkle_count") is not None:
            self.sparkle_count = max(1, int(params.get("sparkle_count")))
        if params.get("twinkle_count") is not None:
            self.twinkle_count = max(1, int(params.get("twinkle_count")))
        self.duration_ms = max(0, int(duration_ms or 0))
        self.started_ms = time.ticks_ms()
        self.last_frame_ms = 0
        self.frame = 0
        self.needs_first_frame = True
        print("animation:", self.target, self.name, "color:", self.color, "brightness:", self.brightness, "speed_ms:", self.speed_ms, "tail:", self.comet_tail)
        return True

    def set_color(self, color):
        if color is not None:
            self.color = parse_color(color, self.color)
            self.needs_first_frame = True
            print("color:", self.target, self.color, "animation:", self.name)

    def tick(self):
        """Draw one frame when enough time has elapsed."""
        now = time.ticks_ms()
        if self.duration_ms and time.ticks_diff(now, self.started_ms) >= self.duration_ms:
            self.start("solid")
            return
        if not self.needs_first_frame and time.ticks_diff(now, self.last_frame_ms) < self.speed_ms:
            return
        self.last_frame_ms = now
        self.needs_first_frame = False
        getattr(self, "draw_" + self.name)()
        self.strips.write()
        self.frame += 1

    def draw_solid(self):
        self.strips.fill(scale_color(self.color, self.brightness))

    def draw_max(self):
        self.strips.fill((255, 255, 255, 255))

    def draw_off(self):
        self.strips.clear()

    def draw_rainbow(self):
        total = max(1, self.strips.max_pixels)
        for index in range(total):
            color = wheel(index * 256 // total + self.frame)
            self.strips.set_pixel(index, scale_color(color, self.brightness))

    def draw_theater_chase(self):
        base = scale_color(self.color, self.brightness)
        self.strips.clear()
        for index in range(self.frame % 3, self.strips.max_pixels, 3):
            self.strips.set_pixel(index, base)

    def draw_color_wipe(self):
        base = scale_color(self.color, self.brightness)
        pos = self.frame % max(1, self.strips.max_pixels + 1)
        self.strips.clear()
        for index in range(pos):
            self.strips.set_pixel(index, base)

    def draw_comet(self):
        head = self.frame % max(1, self.strips.max_pixels)
        tail = min(max(1, self.comet_tail), max(1, self.strips.max_pixels))
        self.strips.clear()
        for offset in range(tail):
            index = head - offset
            if index < 0:
                index += self.strips.max_pixels
            fade = (tail - offset) / tail
            self.strips.set_pixel(index, scale_color(self.color, self.brightness * fade))

    def draw_scanner(self):
        length = max(1, self.strips.max_pixels)
        cycle = max(1, (length - 1) * 2)
        pos = self.frame % cycle
        if pos >= length:
            pos = cycle - pos
        self.strips.clear()
        tail = min(max(0, self.scanner_tail), max(0, length - 1))
        for offset in range(-tail, tail + 1):
            index = pos + offset
            fade = 1.0 if tail == 0 else 1.0 - abs(offset) / (tail + 1)
            self.strips.set_pixel(index, scale_color(self.color, self.brightness * fade))

    def draw_pulse(self):
        level = (math.sin(self.frame / 8) + 1) / 2
        level = 0.08 + level * 0.92
        self.strips.fill(scale_color(self.color, self.brightness * level))

    def draw_sparkle(self):
        base = scale_color(self.color, self.brightness * 0.12)
        sparkle = scale_color((255, 255, 255, 0), self.brightness)
        self.strips.fill(base)
        for offset in range(min(self.sparkle_count, max(1, self.strips.max_pixels))):
            index = (self.frame * 17 + offset * 37) % max(1, self.strips.max_pixels)
            self.strips.set_pixel(index, sparkle)

    def draw_twinkle(self):
        self.strips.clear()
        total = max(1, self.strips.max_pixels)
        for offset in range(min(self.twinkle_count, max(1, self.strips.max_pixels))):
            index = (offset * 19 + self.frame * 3) % total
            phase = (self.frame + offset * 11) % 32
            level = phase / 16 if phase < 16 else (32 - phase) / 16
            self.strips.set_pixel(index, scale_color(self.color, self.brightness * level))


def make_light_controllers(light_config, default_light_config):
    """Build one AnimationController per configured light group."""
    controllers = {}
    groups = grouped_strip_configs(light_config)
    options = light_config.get("target_options", {})
    for target in groups:
        controllers[target] = AnimationController(StripPair(groups[target]), light_config, target=target, options=options.get(target, {}))
        controllers[target].start(
            light_config.get("startup_animation", "solid"),
            color=light_config.get("default_color", default_light_config["default_color"]),
            brightness=light_config.get("brightness", default_light_config["brightness"]),
            speed_ms=light_config.get("animation_speed_ms", default_light_config["animation_speed_ms"]),
        )
    return controllers


def random_choice(items):
    return items[random.getrandbits(16) % len(items)]


def random_between(low, high):
    if high <= low:
        return low
    return low + (random.getrandbits(16) % (high - low + 1))


def randomize_controller(controller):
    """Choose a random animation with target-sized effect parameters."""
    animation = random_choice(RANDOM_ANIMATIONS)
    color = random_choice(RANDOM_COLORS)
    speed_ms = random_between(15, 180)
    max_pixels = max(1, controller.strips.max_pixels)
    tail = min(max_pixels, random_between(1, max(1, max_pixels // 3)))
    scanner_tail = min(max_pixels - 1, random_between(0, min(5, max_pixels - 1)))
    sparkle_count = random_between(1, min(8, max_pixels))
    twinkle_count = random_between(1, min(12, max_pixels))
    controller.start(animation, color=color, speed_ms=speed_ms, tail=tail, scanner_tail=scanner_tail, sparkle_count=sparkle_count, twinkle_count=twinkle_count)
