# SPDX-FileCopyrightText: 2021 Kattni Rembor for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
NeoPixel example for Pico. Turns the Neoeye_stalk_outer
 red.

REQUIRED HARDWARE:
* RGB NeoPixel LEDs connected to pin GP0.
"""
import board
import neopixel
import os
import time
import ipaddress
import wifi 
import socketpool 
import microcontroller
from digitalio import DigitalInOut, Direction
from adafruit_httpserver import Server, Request, Response, POST, FileResponse
import asyncio
import gc
import sdcardio
import storage
import busio
import supervisor
from adafruit_led_animation.animation.blink import Blink
from adafruit_led_animation.animation.solid import Solid
from adafruit_led_animation.animation.rainbowcomet import RainbowComet
from adafruit_led_animation.animation.comet import Comet
from adafruit_led_animation.animation.rainbowchase import RainbowChase
from adafruit_led_animation.animation.sparkle import Sparkle

from adafruit_led_animation.color import RED, GREEN, PURPLE, BLUE, PINK
from adafruit_led_animation.helper import PixelMap

print("Starting")
print("SD Card Setup.")
spi = busio.SPI(board.GP10, MOSI=board.GP11, MISO=board.GP12)
cs = board.GP13
sd = sdcardio.SDCard(spi, cs)
vfs = storage.VfsFat(sd)
storage.mount(vfs, '/sd')
print(os.listdir('/sd')) 

print("Configuring Alek")
gun = False
talking = False
rainbow_mode = False

brightness = 0.01

colorcode = "000000"

def getColorCode():
    global colorcode
    try:
        f = open('/sd/colorcode.txt', "r")
        code = f.read()
        colorcode = code 
        f.close() 
    except:
        return colorcode
    return colorcode

getColorCode()

def setColorCode(cc):
    global colorcode
    try:
        colorcode = cc
        f = open('/sd/colorcode.txt', "w+")
        f.write(cc)
        f.close()
    except:
        print("can't write to flash?")
        colorcode = cc



innerEyeStalk_colorcode = "000000"
def innerEyeStalk_getColorCode():
    global innerEyeStalk_colorcode
    try:
        f = open('/sd/innerEyeStalk_colorcode.txt', "r")
        code = f.read()
        innerEyeStalk_colorcode = code
        f.close()
    except:
        return innerEyeStalk_colorcode
    
    return innerEyeStalk_colorcode

innerEyeStalk_getColorCode()

def innerEyeStalk_setColorCode(cc):
    global innerEyeStalk_colorcode
    innerEyeStalk_colorcode = cc
    try:
        f = open('/sd/innerEyeStalk_colorcode.txt', "w+")
        f.write(cc)
        f.close()
    except:
        print("can't write to flash?")

ears_colorcode = "000000"
def ears_getColorCode():
    global ears_colorcode 
    try:
        f = open('/sd/ears_colorcode.txt', "r")
        code = f.read()
        ears_colorcode = code
        f.close() 
    except:
        return ears_colorcode
    
    return ears_colorcode


ears_getColorCode()

def ears_setColorCode(cc):
    global ears_colorcode
    ears_colorcode = cc
    try:
        f = open('/sd/ears_colorcode.txt', "w+")
        f.write(cc)
        f.close()
    except:
        print("can't write to flash?")

  
def hex2RGBColorCode(colorcode):
    r = int(colorcode[0:2],16)
    g = int(colorcode[2:4],16)
    b = int(colorcode[4:6],16)
    return (r,g,b)

def hex2RGBWColorCode(colorcode):
    r = int(colorcode[0:2], 16)
    g = int(colorcode[2:4], 16) 
    b = int(colorcode[4:6], 16)
    try:
        w = int(colorcode[6:8], 16)
    except:
        w = 0
    return (r,g,b,w)

print("Configuring onboard LED")

#  onboard LED setup
led = DigitalInOut(board.LED)
led.direction = Direction.OUTPUT
led.value = True


#  set static IP address
ipv4 =  ipaddress.IPv4Address("192.168.1.220")
netmask =  ipaddress.IPv4Address("255.255.255.0")
gateway =  ipaddress.IPv4Address("192.168.1.254")
wifi.radio.set_ipv4_address(ipv4=ipv4,netmask=netmask,gateway=gateway)
#  connect to your SSID
wifi.radio.connect(os.getenv('CIRCUITPY_WIFI_SSID'), os.getenv('CIRCUITPY_WIFI_PASSWORD'))

print("Connected to WiFi")
pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, "/static", debug=False)

#  variables for HTML
#  comment/uncomment desired temp unit

#  temp_test = str(ds18.temperature)
#  unit = "C"
unit = "F"
#  font for HTML
font_family = "monospace"

#  the HTML script
#  setup as an f string
#  this way, can insert string variables from code.py directly
#  of note, use {{ and }} if something from html *actually* needs to be in brackets
#  i.e. CSS style formatting
def fstr(template):
    print(eval(f"""f'{template}'"""))
    return eval(f"f'{template}'").replace("@@","{").replace("!!","}") 

def webpage():
    f = open('/static/DalekControl.html', "r")
    html = f.read()
    f.close()
    html = html.replace("ears_getColorCode()", ears_getColorCode())
    html = html.replace("innerEyeStalk_getColorCode()", innerEyeStalk_getColorCode())
    html = html.replace("getColorCode()", getColorCode())
    return html



#  route default static IP
@server.route("/")
def base(request: Request):  # pylint: disable=unused-argument
    #  serve the HTML f string
    #  with content type text/html
    return Response(request, webpage(), content_type='text/html')

@server.route("/eye-stalk-outer", POST)
def eyeStalkOuter(request: Request):  # pylint: disable=unused-argument
    raw_text = request.raw_request.decode("utf8")
    colorcode = raw_text[-6:]
    setColorCode(colorcode)
    return Response(request, "", content_type='text/html')

@server.route("/eye-stalk-inner", POST)
def eyeStalkInner(request: Request):  # pylint: disable=unused-argument
    raw_text = request.raw_request.decode("utf8")
    colorcode = raw_text[-6:]
    innerEyeStalk_setColorCode(colorcode)
    print(innerEyeStalk_getColorCode())
    return Response(request, "", content_type='text/html')

@server.route("/leftEar", POST)
@server.route("/rightEar", POST)
def leftEar(request: Request):  # pylint: disable=unused-argument
    raw_text = request.raw_request.decode("utf8")
    ears_colorcode = raw_text[-6:]
    ears_setColorCode(ears_colorcode)
    return Response(request, "", content_type='text/html')


@server.route("/rainbow")
def rightEar(request: Request):  # pylint: disable=unused-argument
    global rainbow_mode
    rainbow_mode = not rainbow_mode
    return Response(request, "", content_type='text/html')

@server.route("/get-image/<name>")
def base(request: Request, name):  # pylint: disable=unused-argument
    #return Response(request, html, content_type='image/png')
    print(name)
    return FileResponse(request, filename="/image/"+name+".png" , content_type='image/png')

@server.route("/trigger/<name>")
def base(request: Request, name):  
    global gun
    global talking
    global rainbow_mode
    print(name)

    if(name == "gun"):
        gun = True
    if(name == "talking"):
        talking = True
    if(name== "reset"):
        supervisor.reload()
    if(name=="rainbow"):
        rainbow_mode = not rainbow_mode

    return Response(request, name, content_type='text/plain')

@server.route("/brightness/<name>")
def base(request: Request, name):
    global brightness  
    print(name)
    brightness = float(name)
    return Response(request, name, content_type='text/plain')


print("starting server..")
# startup the server
try:
    server.start(str(wifi.radio.ipv4_address))
#  if the server fails to begin, restart the pico w 
except OSError:
    time.sleep(5)
    print("restarting..")
    microcontroller.reset()



num_eye_stalk_outer = 24
num_eye_stalk_inner = 7
num_ear_total = 14

eye_stalk_outer = neopixel.NeoPixel(board.GP0, num_eye_stalk_outer, auto_write=False)
eye_stalk_inner = neopixel.NeoPixel(board.GP2, num_eye_stalk_inner, pixel_order=(1, 0, 2, 3), auto_write=False)
ears = neopixel.NeoPixel(board.GP3, num_ear_total, pixel_order=(1, 0, 2, 3), auto_write=False)
lEar = PixelMap(ears, range(0,7), individual_pixels=True)
rEar = PixelMap(ears, range(7,14), individual_pixels=True)

lEar_comet = Comet(lEar, speed=0.10, color=BLUE, tail_length=4, bounce=False)
rEar_comet = Comet(rEar, speed=0.03, color=BLUE, tail_length=4, bounce=True)
cometC = Comet(eye_stalk_outer, speed=0.03, color=BLUE, tail_length=1, bounce=False)
solid = Solid(eye_stalk_outer, color=BLUE)
rainbow = RainbowComet(eye_stalk_inner, speed=2)
rainbow_chase = RainbowChase(eye_stalk_outer, speed=1, size=24, spacing=0)
sparkle = Sparkle(eye_stalk_inner, speed=0.001, color=BLUE, num_sparkles=1)

animation = rainbow
async def WebServer():
    while True:
        try:
            server.poll()
            await asyncio.sleep(0.2)
        except Exception as e:
            print(e)
            continue

async def LightControl():
    global animation
    global eye_stalk_outer
    global eye_stalk_inner
    global ears
    global lEar_comet
    global rEar_comet
    global rainbow_chase
    global rainbow

    while True:

            try:

                #make the brightness adjustable
                eye_stalk_outer.brightness = brightness
                eye_stalk_inner.brightness = brightness
                ears.brightness = brightness

                #eye outer ring
                if(not rainbow_mode):
                    ring = (r,g,b) = hex2RGBColorCode(getColorCode())
                    solid.color = ring
                    animation = solid
                else:
                    #cometC.color = ring
                    animation = rainbow
                
                animation.animate()
                #eye inner ring
                innerEye_color = (r,g,b,w) = hex2RGBWColorCode(innerEyeStalk_getColorCode())
                sparkle.color = innerEye_color
                sparkle.animate()

                #left "ear"
                
                lEar_color = (r,g,b,w) = hex2RGBWColorCode(ears_getColorCode())
                lEar_comet.color = lEar_color
                lEar_comet.animate()

                #right "ear"
                rEar_color = lEar_color
                rEar_comet.color = rEar_color
                rEar_comet.animate()
               
                await asyncio.sleep(0.01)

            except Exception as e:
                print(e)
                continue

async def main():
    WebServerTask = asyncio.create_task(WebServer())
    LightControlTask = asyncio.create_task(LightControl())
    await asyncio.gather(LightControlTask, WebServerTask)
    

asyncio.run(main())

