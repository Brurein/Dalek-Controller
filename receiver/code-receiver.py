import time

import espnow
import network

from amp import AmpShutdown, TPA2016, handle_amp_command, handle_tpa_command
from commands import decode_command, handle_light_command
from config_loader import DEFAULT_CONFIG, load_config, save_config
from inputs import ActiveLowPulseOverlay
from lights import ANIMATIONS, make_light_controllers, tick_controllers
from sound import SoundBoard, handle_sound_command


def setup_espnow(channel):
    """Start ESP-NOW on the configured channel without joining Wi-Fi."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    try:
        wlan.config(channel=int(channel))
    except Exception as exc:
        print("wifi channel config skipped:", exc)
    esp = espnow.ESPNow()
    esp.active(True)
    return esp


def main():
    print("EXTERMINATE")

    # config.json overrides DEFAULT_CONFIG, but missing keys keep their defaults.
    config = load_config()
    light_config = config.get("lights", DEFAULT_CONFIG["lights"])
    input_config = config.get("inputs", DEFAULT_CONFIG["inputs"])

    controllers = make_light_controllers(light_config, DEFAULT_CONFIG["lights"])
    amp_config = config.get("amp", DEFAULT_CONFIG["amp"])
    amp = AmpShutdown(amp_config)
    tpa = TPA2016(amp_config)
    audio_act = ActiveLowPulseOverlay(
        input_config.get("audio_act", DEFAULT_CONFIG["inputs"]["audio_act"]),
        controllers,
        name="audio_act",
    )

    def tick_outputs():
        # Called during long waits as well as the main loop so animations do not
        # freeze while the sound board or amp is settling.
        tick_controllers(controllers)
        audio_act.apply()

    sound = SoundBoard(config.get("sound", DEFAULT_CONFIG["sound"]), tick=tick_outputs)
    amp.unmute_after_boot(tick_outputs)
    esp = setup_espnow(config.get("wifi_channel", 1))

    print("combined receiver ready")
    print("animations:", ", ".join(ANIMATIONS))
    print("targets:", ", ".join(controllers.keys()))

    while True:
        host, message = esp.recv(0)
        if message:
            command, text = decode_command(message, light_config)
            print("rx:", text)
            # Amp commands are handled before lights, then sound handling runs
            # last so play_N can trigger both audio and configured light effects.
            if handle_amp_command(text, command, amp):
                pass
            elif handle_tpa_command(text, command, tpa):
                pass
            elif command:
                handle_light_command(command, host, esp, controllers, light_config, config, save_config)
            handle_sound_command(text, sound, config.get("tracks", {}))
        tick_outputs()
        time.sleep_ms(1)


main()
