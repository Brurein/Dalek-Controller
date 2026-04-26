import socketpool
import wifi
from adafruit_httpserver import Server, Request, Response, POST, FileResponse
import time
import microcontroller
import Dalek
import asyncio

print("starting server..")
# startup the server
try:
    server = Server(socketpool.SocketPool(wifi.radio), "/static", debug=True)
    server.start(str(wifi.radio.ipv4_address))
#  if the server fails to begin, restart the pico w 
except OSError:
    time.sleep(5)
    print("restarting..")
    microcontroller.reset()


def webpage():
    f = open('/sd/static/DalekControl.html', "r")
    html = f.read()
    f.close()
    return html

#  route default static IP
@server.route("/")
def base( request: Request):  # pylint: disable=unused-argument
    return Response(request, webpage(), content_type='text/html')

@server.route("/rightEar", POST)
@server.route("/leftEar", POST)
@server.route("/eye-stalk-inner", POST)
@server.route("/eye-stalk-outer", POST)
def setColor( request: Request):  # pylint: disable=unused-argument
    print(request)
    #dir(request)
    raw_text = request.raw_request.decode("utf8")
    colorcode = raw_text[-6:]
    #setColorCode(colorcode)
    return Response(request, "", content_type='text/html')


@server.route("/rainbow")
def rightEar( request: Request):  # pylint: disable=unused-argument
    global rainbow_mode
    rainbow_mode = not rainbow_mode
    return Response(request, "", content_type='text/html')

@server.route("/get-image")
def base( request: Request):  # pylint: disable=unused-argument
    #return Response(request, html, content_type='image/png')
    return FileResponse(request, root_path='/sd', filename="/static/image/Daleks.png", content_type='image/png')


async def WebServerLoop():
    global server
    while True:
        try:
            server.poll()
            await asyncio.sleep(0.2)
        except Exception as e:
            print(e)
            continue
