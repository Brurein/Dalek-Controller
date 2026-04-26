
class DalekLight():
    EYE_INNER = 1
    EYE_OUTER = 2
    EAR_LEFT = 3
    EAR_RIGHT = 4

class Dalek:

    _storage = {}

    def __init__(self) -> None:
        pass
        self.writeState()
        self.loadState()
         

    def parseColorCode(self, colorcode) -> bytes:
        return ""
    
    def writeState(self):
        try:
            f = open('/sd/dalek.json', "w+")
            f.write(self.Temp().decode("utf-8"))
            f.close()
        except Exception as e:
            pass
        

    def loadState(self):
        try:
            f = open('/sd/dalek.json', "r+")
            out = f.read()
            f.close()
            print(out)
        except Exception as e:
            pass

    def getColor(dalekLight: DalekLight):
        pass

    def Temp() -> str:
        return """
            {
                "EYE_INNER": {"color":"0000FF00", "type":"RGBW"},
                "EYE_OUTER":{"color":"0000FF00", "type":"RGB"},
                "EAR_LEFT":{"color":"0000FF00", "type":"RGB"},
                "EAR_RIGHT":{"color":"0000FF00", "type":"RGB"}
            }
        """

    
    

