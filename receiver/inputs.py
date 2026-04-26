import time

from machine import Pin

from lights import ANIMATIONS, clamp, normalize_target, scale_color


def pin_pull_mode(value):
    value = str(value or "").lower()
    if value == "up":
        return Pin.PULL_UP
    if value == "down":
        return Pin.PULL_DOWN
    return None


class ActiveLowPulseOverlay:
    def __init__(self, config, controllers, name="input"):
        self.enabled = bool(config.get("enabled", False))
        self.controllers = controllers
        self.name = name
        self.active = int(config.get("active", 0))
        self.targets = [normalize_target(target) for target in config.get("targets", [])]
        self.animation = str(config.get("animation", "pulse")).lower()
        self.color = config.get("color")
        self.speed_ms = max(5, int(config.get("speed_ms", config.get("pulse_speed_ms", 45))))
        self.pulse_speed_ms = max(10, int(config.get("pulse_speed_ms", 45)))
        self.min_brightness = clamp(float(config.get("min_brightness", 0.15)), 0.0, 1.0)
        self.max_brightness = clamp(float(config.get("max_brightness", 1.0)), 0.0, 1.0)
        self.was_active = False
        self.started_ms = time.ticks_ms()
        self.saved_states = {}
        self.pin = None

        if self.enabled:
            pin_no = int(config.get("pin"))
            pull = pin_pull_mode(config.get("pull", "up"))
            self.pin = Pin(pin_no, Pin.IN, pull) if pull is not None else Pin(pin_no, Pin.IN)
            print(self.name, "input pin:", pin_no, "active:", self.active)

    def is_active(self):
        return self.enabled and self.pin is not None and self.pin.value() == self.active

    def apply(self):
        active = self.is_active()
        if active and not self.was_active:
            self.started_ms = time.ticks_ms()
            print(self.name, "active")
            self.saved_states = {}
            for target in self.targets:
                if target not in self.controllers:
                    continue
                controller = self.controllers[target]
                self.saved_states[target] = {
                    "name": controller.name,
                    "color": controller.color,
                    "brightness": controller.brightness,
                    "speed_ms": controller.speed_ms,
                    "comet_tail": controller.comet_tail,
                    "scanner_tail": controller.scanner_tail,
                    "sparkle_count": controller.sparkle_count,
                    "twinkle_count": controller.twinkle_count,
                }
                if self.animation in ANIMATIONS:
                    controller.start(
                        self.animation,
                        color=self.color,
                        speed_ms=self.speed_ms,
                        tail=controller.comet_tail,
                        scanner_tail=controller.scanner_tail,
                        sparkle_count=controller.sparkle_count,
                        twinkle_count=controller.twinkle_count,
                    )
        elif not active and self.was_active:
            print(self.name, "inactive")
            for target in self.targets:
                if target in self.controllers:
                    state = self.saved_states.get(target)
                    if state:
                        controller = self.controllers[target]
                        controller.name = state["name"]
                        controller.color = state["color"]
                        controller.brightness = state["brightness"]
                        controller.speed_ms = state["speed_ms"]
                        controller.comet_tail = state["comet_tail"]
                        controller.scanner_tail = state["scanner_tail"]
                        controller.sparkle_count = state["sparkle_count"]
                        controller.twinkle_count = state["twinkle_count"]
                    self.controllers[target].needs_first_frame = True
            self.saved_states = {}

        self.was_active = active
        if not active or self.animation != "pulse":
            return

        elapsed = time.ticks_diff(time.ticks_ms(), self.started_ms)
        phase = (elapsed // self.pulse_speed_ms) % 2
        level = self.max_brightness if phase else self.min_brightness

        for target in self.targets:
            if target not in self.controllers:
                continue
            controller = self.controllers[target]
            color = scale_color(controller.color, controller.brightness * level)
            controller.strips.fill(color)
            controller.strips.write()
