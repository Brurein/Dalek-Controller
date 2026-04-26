import os
import busio
import board
import storage
import sdcardio

spi = busio.SPI(clock=board.GP10, MOSI=board.GP11, MISO=board.GP12)

# For breakout boards, you can choose any GPIO pin that's convenient:
cs = board.GP13

sdcard = sdcardio.SDCard(spi, cs)

vfs = storage.VfsFat(sdcard)

storage.mount(vfs, "/sd")

print(os.listdir("/sd"))
print("print from file")