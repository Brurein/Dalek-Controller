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

os.chdir("/")
colorcode = "000000"
def getColorCode():
    global colorcode
    try:
        f = open('colorcode.txt', "w+")
        code = f.read()
        colorcode = code 
        f.close()
    except:
        return colorcode
    return code

def setColorCode(cc):
    global colorcode
    try:
        colorcode = cc
        f = open('colorcode.txt', "w+")
        f.write(cc)
        f.close()
    except:
        print("can't write to flash?")
        colorcode = cc

rainbow_mode = False

innerEyeStalk_colorcode = "00000000"
def innerEyeStalk_getColorCode():
    global innerEyeStalk_colorcode
    try:
        f = open('innerEyeStalk_colorcode.txt', "w+")
        code = f.read()
        innerEyeStalk_colorcode = code
        f.close() 
    except:
        return innerEyeStalk_colorcode
    
    return innerEyeStalk_colorcode

def innerEyeStalk_setColorCode(cc):
    global innerEyeStalk_colorcode
    innerEyeStalk_colorcode = cc
    try:
        f = open('innerEyeStalk_colorcode.txt', "w+")
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
    w = int(colorcode[6:8], 16)
    return (r,g,b,w)

#  onboard LED setup
led = DigitalInOut(board.LED)
led.direction = Direction.OUTPUT
led.value = False


#  set static IP address
ipv4 =  ipaddress.IPv4Address("192.168.1.220")
netmask =  ipaddress.IPv4Address("255.255.255.0")
gateway =  ipaddress.IPv4Address("192.168.1.254")
wifi.radio.set_ipv4_address(ipv4=ipv4,netmask=netmask,gateway=gateway)
#  connect to your SSID
wifi.radio.connect(os.getenv('CIRCUITPY_WIFI_SSID'), os.getenv('CIRCUITPY_WIFI_PASSWORD'))

print("Connected to WiFi")
pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, "/static", debug=True)

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
    return html.replace("getColorCode()", getColorCode())



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
    innerEyeStalk_setColorCode(colorcode + "00")
    print(innerEyeStalk_getColorCode())
    return Response(request, "", content_type='text/html')

@server.route("/leftEar", POST)
def leftEar(request: Request):  # pylint: disable=unused-argument
    raw_text = request.raw_request.decode("utf8")
    colorcode = raw_text[-6:]
    setColorCode(colorcode)
    return Response(request, "", content_type='text/html')

@server.route("/rightEar", POST)
def rightEar(request: Request):  # pylint: disable=unused-argument
    raw_text = request.raw_request.decode("utf8")
    colorcode = raw_text[-6:]
    setColorCode(colorcode)
    return Response(request, "", content_type='text/html')

@server.route("/rainbow")
def rightEar(request: Request):  # pylint: disable=unused-argument
    global rainbow_mode
    rainbow_mode = not rainbow_mode
    return Response(request, "", content_type='text/html')

@server.route("/get-image")
def base(request: Request):  # pylint: disable=unused-argument
    #return Response(request, html, content_type='image/png')
    return FileResponse(request, filename="/image/Daleks.png", content_type='image/png')


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

eye_stalk_outer = neopixel.NeoPixel(board.GP0, num_eye_stalk_outer)
eye_stalk_inner = neopixel.NeoPixel(board.GP2, num_eye_stalk_inner, pixel_order=(1, 0, 2, 3))
ears = neopixel.NeoPixel(board.GP3, 14)

eye_stalk_outer.brightness = 0.2
eye_stalk_inner.brightness = 1
ears.brightness = 1




gun = DigitalInOut(board.GP4)
lights = DigitalInOut(board.GP5)

gun.direction = Direction.INPUT
lights.direction = Direction.INPUT

async def WebServer():
    while True:
        try:
            server.poll()
            await asyncio.sleep(0.2)
        except Exception as e:
            print(e)
            continue

async def LightControl():
    while True:
        try:
            
            #if(rainbow_mode):
        #    print(eye_stalk_inner)
        #else:
            (r,g,b) = hex2RGBColorCode(getColorCode())
            eye_stalk_outer.fill((r, g, b))

            
            (r,g,b,w) = hex2RGBWColorCode(innerEyeStalk_getColorCode())           
            eye_stalk_inner.fill((r, g, b, 0))


            if(lights.value == False or gun.value == False):
                ears.fill((r, g, b, 0)) 
            else:
                ears.fill((0, 0, 0, 0))

            
            await asyncio.sleep(0.01)

        except Exception as e:
            print(e)
            continue

async def main():
    WebServerTask = asyncio.create_task(WebServer())
    LightControlTask = asyncio.create_task(LightControl())
    await asyncio.gather(LightControlTask, WebServerTask)
    

asyncio.run(main())

