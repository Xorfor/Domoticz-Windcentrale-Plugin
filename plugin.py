#  Windcentrale Python Plugin
#
# Author: Xorfor
#
# Using:
#   https://zep-api.windcentrale.nl/production/<id>/live
#   https://zep-api.windcentrale.nl/production/<id>
#   https://zep-api.windcentrale.nl/app/config
#
"""
<plugin key="xfr_windcentrale" name="Windcentrale" author="Xorfor" version="3.0" wikilink="https://github.com/Xorfor/Domoticz-Windcentrale-Plugin" externallink="https://www.windcentrale.nl/">
    <params>
        <param field="Address" label="Select a mill" width="200px" required="true">
            <options>
                <option label="De Blauwe Reiger" value="De Blauwe Reiger"/>
                <option label="De Boerenzwaluw" value="De Boerenzwaluw"/>
                <option label="De Bonte Hen" value="De Bonte Hen"/>
                <option label="De Grote Geert" value="De Grote Geert"/>
                <option label="De Jonge Held" value="De Jonge Held"/>
                <option label="De Ranke Zwaan" value="De Ranke Zwaan"/>
                <option label="Het Rode Hert" value="Het Rode Hert"/>
                <option label="De Trouwe Wachter" value="De Trouwe Wachter"/>
                <option label="De Vier Winden" value="De Vier Winden"/>
                <option label="De Witte Juffer" value="De Witte Juffer"/>
            </options>
        </param>
        <param field="Mode1" label="Number of winddelen" width="30px" required="true"/>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal" default="true"/>
            </options>
        </param>
    </params>
</plugin>
"""
import Domoticz
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from enum import IntEnum, auto, unique


@unique
class Unit(IntEnum):
    # Devices
    POWERWND = auto()
    POWERTOT = auto()
    WINDSPEED = auto()
    DKWHWND = auto()  # version >= 3.0
    POWERREL = auto()
    RPM = auto()
    OPERATIONAL = auto()
    KWHTOT = auto()
    KWHWND = auto()
    HOURSYEAR = auto()
    NEWS = auto()  # version >= 2.0


@unique
class Switchtype(IntEnum):
    NONE = -1
    USAGE = 0
    RETURN = 4


@unique
class Used(IntEnum):
    NOTUSED = 0
    USED = auto()


class BasePlugin:
    __HEARTBEATS2MIN = 6
    __HEARTBEATS2MIN_LIVE = __HEARTBEATS2MIN * 1  # 1 minute
    __HEARTBEATS2MIN_PROD = __HEARTBEATS2MIN * 1  # 1 minute
    __HEARTBEATS2MIN_CONFIG = __HEARTBEATS2MIN * 60  # 1 hour

    __WINDMILLS = {
        # Name: [ id, parkid, winddelen ]
        "De Grote Geert": ["1", "1", 9910],
        "De Jonge Held": ["2", "1", 10154],
        "Het Rode Hert": ["31", "11", 6648],
        "De Ranke Zwaan": ["41", "11", 6164],
        "De Witte Juffer": ["51", "11", 5721],
        "De Bonte Hen": ["111", "21", 5579],
        "De Trouwe Wachter": ["121", "21", 5602],
        "De Blauwe Reiger": ["131", "21", 5534],
        "De Vier Winden": ["141", "21", 5512],
        "De Boerenzwaluw": ["191", "31", 3000],
        # "Het Vliegend Hert": ["211", "", 9751],
    }

    # Url to get data from the windmills
    API_ENDPOINT = "zep-api.windcentrale.nl"
    API_LIVE = "/production/{}/live"
    API_PROD = "/production/{}"
    API_CONFIG = "/app/config"

    # Connections
    CONN_LIVE = "Live"
    CONN_PROD = "Production"
    CONN_CONFIG = "Config"

    __UNITS = [
        # id, name, typename, type, subtype, options, switchtype, used
        [
            Unit.POWERWND,
            "Power ({})",
            "Custom",
            243,
            29,
            {"Custom": "0;W"},
            Switchtype.NONE,
            Used.NOTUSED,
        ],
        [
            Unit.POWERTOT,
            "Power (total)",
            "Custom",
            243,
            29,
            {"Custom": "0;kW"},
            Switchtype.NONE,
            Used.NOTUSED,
        ],
        [
            Unit.POWERREL,
            "Relative",
            "Custom",
            243,
            6,
            {"Custom": "0;%"},
            Switchtype.NONE,
            Used.NOTUSED,
        ],
        [
            Unit.WINDSPEED,
            "Windspeed",
            "Custom",
            243,
            31,
            {"Custom": "0.0;Bft"},
            Switchtype.NONE,
            Used.NOTUSED,
        ],
        [
            Unit.RPM,
            "RPM",
            "Custom",
            243,
            7,
            {"Custom": "0;rpm"},
            Switchtype.NONE,
            Used.NOTUSED,
        ],
        [
            Unit.OPERATIONAL,
            "Operational time",
            "Custom",
            243,
            6,
            {"Custom": "0;%"},
            Switchtype.NONE,
            Used.NOTUSED,
        ],
        [
            Unit.KWHWND,
            "Energy ({})",
            "Custom",
            243,
            6,
            {"Custom": "0;kWh"},
            Switchtype.NONE,
            Used.NOTUSED,
        ],
        [
            Unit.KWHTOT,
            "Energy (total)",
            "Custom",
            243,
            6,
            {"Custom": "0;MWh"},
            Switchtype.NONE,
            Used.NOTUSED,
        ],
        [
            Unit.HOURSYEAR,
            "Hours this year",
            "Custom",
            243,
            31,
            {},
            Switchtype.NONE,
            Used.NOTUSED,
        ],
        [Unit.NEWS, "News", None, 243, 19, {}, Switchtype.NONE, Used.USED],
        [Unit.DKWHWND, "Power ({})", "kWh", 243, 6, {}, Switchtype.RETURN, Used.USED],
    ]

    def __init__(self):
        self.__runAgainLive = 0
        self.__runAgainProd = 0
        self.__runAgainConfig = 0
        self.__id = None
        self.__parkid = None
        self.__max_winddelen = None
        self.__number_winddelen = None
        self.__wnd_w = 0
        self.__wnd_kwh = 0
        self.__httplive = None
        self.__httpprod = None
        self.__httpconfig = None

    def onStart(self):
        Domoticz.Debug("onStart")
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(1)
        else:
            Domoticz.Debugging(0)
        # Images
        # Check if images are in database
        if "xfr_windcentrale" not in Images:
            Domoticz.Image("xfr_windcentrale.zip").Create()
        image = Images["xfr_windcentrale"].ID
        Domoticz.Debug("Image created. ID: {}".format(image))
        # Validation of parameters
        # Check the selected Windmill
        Domoticz.Debug("Adress: {}".format(Parameters["Address"]))
        try:
            windmill = self.__WINDMILLS[Parameters["Address"]]
            self.__id = windmill[0]
            self.__parkid = windmill[1]
            self.__max_winddelen = windmill[2]
        except:
            Domoticz.Error("Invalid windmill selected")  # Should not be possible!
            self.__id = None
            self.__parkid = None
            self.__max_winddelen = None
        # Check the number of winddelen
        Domoticz.Debug("Mode1: {}".format(Parameters["Mode1"]))
        try:
            self.__number_winddelen = int(Parameters["Mode1"])
            if (
                self.__number_winddelen < 0
                or self.__number_winddelen > self.__max_winddelen
            ):
                self.__number_winddelen = None
        except:
            Domoticz.Error("Invalid number of winddelen entered")
            self.__number_winddelen = None

        Domoticz.Debug("id: {}".format(self.__id))
        Domoticz.Debug("parkid: {}".format(self.__parkid))
        Domoticz.Debug("max winddelen: {}".format(self.__max_winddelen))
        Domoticz.Debug("number winddelen: {}".format(self.__number_winddelen))
        # Create devices
        for unit in self.__UNITS:
            if unit[0] not in Devices:
                if unit[2] is None:
                    Domoticz.Device(
                        Unit=unit[0],
                        Name=unit[1].format(self.__number_winddelen),
                        Type=unit[3],
                        Subtype=unit[4],
                        Options=unit[5],
                        Switchtype=unit[6],
                        Used=unit[7],
                        Image=image,
                    ).Create()
                else:
                    Domoticz.Device(
                        Unit=unit[0],
                        Name=unit[1].format(self.__number_winddelen),
                        TypeName=unit[2],
                        Options=unit[5],
                        Switchtype=unit[6],
                        Used=unit[7],
                        Image=image,
                    ).Create()

        DumpConfigToLog()
        Domoticz.Debug("self.API_ENDPOINT: {}".format(self.API_ENDPOINT))
        #
        self.__httplive = Domoticz.Connection(
            Name=self.CONN_LIVE,
            Transport="TCP/IP",
            Protocol="HTTPS",
            Address=self.API_ENDPOINT,
            Port="443",
        )
        self.__httplive.Connect()
        #
        self.__httpprod = Domoticz.Connection(
            Name=self.CONN_PROD,
            Transport="TCP/IP",
            Protocol="HTTPS",
            Address=self.API_ENDPOINT,
            Port="443",
        )
        self.__httpprod.Connect()
        #
        self.__httpconfig = Domoticz.Connection(
            Name=self.CONN_CONFIG,
            Transport="TCP/IP",
            Protocol="HTTPS",
            Address=self.API_ENDPOINT,
            Port="443",
        )
        self.__httpconfig.Connect()

    def onStop(self):
        Domoticz.Debug("onStop")

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("onConnect: {}, {}, {}".format(Connection, Status, Description))
        # Live
        if Connection.Name == self.CONN_LIVE:
            if Status == 0:
                if self.__id is not None:
                    url = self.API_LIVE.format(self.__id)
                    Domoticz.Debug("url: {}".format(url))
                    sendData = {
                        "Verb": "GET",
                        "URL": url,
                        "Headers": {
                            "Host": self.API_ENDPOINT,
                            "User-Agent": "Domoticz/1.0",
                        },
                    }
                    Connection.Send(sendData)
            else:
                Domoticz.Error(
                    "Failed to connect ({}) to: {} with error: {}".format(
                        Status, self.API_ENDPOINT, Description
                    )
                )
        # Production data
        if Connection.Name == self.CONN_PROD:
            if Status == 0:
                if self.__id is not None:
                    url = self.API_PROD.format(self.__id)
                    Domoticz.Debug("url: {}".format(url))
                    sendData = {
                        "Verb": "GET",
                        "URL": url,
                        "Headers": {
                            "Host": self.API_ENDPOINT,
                            "User-Agent": "Domoticz/1.0",
                        },
                    }
                    Connection.Send(sendData)
            else:
                Domoticz.Error(
                    "Failed to connect ({}) to: {} with error: {}".format(
                        Status, self.API_ENDPOINT, Description
                    )
                )
        # Config
        if Connection.Name == self.CONN_CONFIG:
            if Status == 0:
                if self.__id is not None:
                    url = self.API_CONFIG
                    Domoticz.Debug("url: {}".format(url))
                    sendData = {
                        "Verb": "GET",
                        "URL": url,
                        "Headers": {
                            "Host": self.API_ENDPOINT,
                            "User-Agent": "Domoticz/1.0",
                        },
                    }
                    Connection.Send(sendData)
            else:
                Domoticz.Error(
                    "Failed to connect ({}) to: {} with error: {}".format(
                        Status, self.API_ENDPOINT, Description
                    )
                )

    def onMessage(self, Connection, Data):
        Domoticz.Debug("onMessage: {}, {}".format(Connection, Data))
        DumpHTTPResponseToLog(Data)

        # Live: Get the actual data from the windmill
        if Connection.Name == self.CONN_LIVE:
            data = json.loads(Data["Data"].decode("utf-8", "ignore"))
            #
            # Power produced for the amount of wind shares
            self.__wnd_w = round(
                max(0, data.get("powerAbsWd", 0) * self.__number_winddelen), 1
            )
            UpdateDevice(
                Unit.POWERWND, int(self.__wnd_w), str(self.__wnd_w), AlwaysUpdate=True
            )
            UpdateDevice(
                Unit.DKWHWND,
                0,
                "{};{}".format(self.__wnd_w, 1000 * self.__wnd_kwh),
                AlwaysUpdate=True,
            )
            #
            # Total power produced by the windmill
            fval = round(max(0, float(data.get("powerAbsTot", 0))), 1)
            UpdateDevice(Unit.POWERTOT, int(fval), str(fval), AlwaysUpdate=True)
            #
            # Percentage of maximum power of the windmill
            ival = data.get("powerRel", 0)
            UpdateDevice(Unit.POWERREL, int(ival), str(ival), AlwaysUpdate=True)
            #
            # Windspeed in bft
            ival = data.get("windSpeed", 0)
            UpdateDevice(Unit.WINDSPEED, int(ival), str(ival), AlwaysUpdate=True)
            #
            # tag = "windDirection"
            # if tag in jsonData:
            #     Domoticz.Debug(tag+": " + str(jsonData[tag]))
            #     UpdateDevice(Unit.WINDDIRECTION, 0, "0;"+str(jsonData[tag])+"0;0;0", AlwaysUpdate=True)
            #
            # RPM. Rotation speed windmill
            fval = round(float(data.get("rpm", 0)), 1)
            UpdateDevice(Unit.RPM, int(fval), str(fval), AlwaysUpdate=True)
            #
            # Percentage time in production (since start of windmill)
            fval = round(float(data.get("runPercentage", 0)), 1)
            UpdateDevice(Unit.OPERATIONAL, int(fval), str(fval), AlwaysUpdate=True)
            #
            # Total production this year and for the winddelen
            fval = round(float(data.get("kwh", 0)) / 1000, 1)
            UpdateDevice(Unit.KWHTOT, int(fval), str(fval), AlwaysUpdate=True)
            wnd_kwh = round(
                (self.__number_winddelen * float(data.get("kwh", 0)))
                / self.__max_winddelen,
                1,
            )
            UpdateDevice(Unit.KWHWND, int(wnd_kwh), str(wnd_kwh), AlwaysUpdate=True)
            #
            # Hours in production
            fval = round(float(data.get("hoursRunThisYear")), 1)
            UpdateDevice(Unit.HOURSYEAR, int(fval), str(fval), AlwaysUpdate=True)

        # Production data: Get total production from today
        if Connection.Name == self.CONN_PROD:
            data = ET.fromstring(Data["Data"])
            sum = float(data.find("./productie/subset[@period='DAY']").get("sum"))
            Domoticz.Error("sum: {}".format(int(sum)))
            self.__wnd_kwh = (self.__number_winddelen * sum) / self.__max_winddelen
            Domoticz.Error("self.__wnd_kwh: {}".format(1000 * self.__wnd_kwh))
            UpdateDevice(
                Unit.DKWHWND,
                0,
                "{};{}".format(self.__wnd_w, 1000 * self.__wnd_kwh),
                AlwaysUpdate=True,
            )

        # Config: Get the global or the windmill specific news lines
        if Connection.Name == self.CONN_CONFIG:
            txt = ""
            lines = 2
            data = ET.fromstring(Data["Data"])
            news = data.findall("news/i")
            for child in news:
                if (
                    (child.attrib["p"] == self.__parkid and child.attrib["m"] == "0")
                    or (child.attrib["p"] == "0" and child.attrib["m"] == self.__id)
                    or (child.attrib["p"] == "0" and child.attrib["m"] == "0")
                ):
                    Domoticz.Debug("child.findtext: {}".format(child.findtext("t")))
                    date = child.attrib["t"].split(" ", 1)[1]
                    txt += "{}: {}\r".format(date, child.findtext("t"))
                    lines -= 1
                if lines <= 0:
                    break
            UpdateDevice(Unit.NEWS, 0, txt, AlwaysUpdate=True)

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug("onCommand: {}, {}, {}, {}".format(Unit, Command, Level, Hue))

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Debug(
            "onNotification: {}, {}, {}, {}, {}, {}, {}".format(
                Name, Subject, Text, Status, Priority, Sound, ImageFile
            )
        )

    def onDisconnect(self, Connection):
        Domoticz.Debug("onDisconnect: {}".format(Connection))

    def onHeartbeat(self):
        Domoticz.Debug("onHeartbeat")
        # Live
        self.__runAgainLive -= 1
        if self.__runAgainLive <= 0:
            if self.__httplive.Connecting() or self.__httplive.Connected():
                Domoticz.Debug("onHeartbeat: {} is alive".format(self.__httplive))
            else:
                self.__httplive.Connect()
            self.__runAgainLive = self.__HEARTBEATS2MIN_LIVE
        Domoticz.Debug("onHeartbeat (Live): {} heartbeats".format(self.__runAgainLive))
        # Production
        self.__runAgainProd -= 1
        if self.__runAgainProd <= 0:
            if self.__httpprod.Connecting() or self.__httpprod.Connected():
                Domoticz.Debug("onHeartbeat: {} is alive".format(self.__httpprod))
            else:
                self.__httpprod.Connect()
            self.__runAgainProd = self.__HEARTBEATS2MIN_PROD
        Domoticz.Debug("onHeartbeat (Prod): {} heartbeats".format(self.__runAgainProd))
        # Config
        self.__runAgainConfig -= 1
        if self.__runAgainConfig <= 0:
            if self.__httpconfig.Connecting() or self.__httpconfig.Connected():
                Domoticz.Debug("onHeartbeat: {} is alive".format(self.__httpconfig))
            else:
                self.__httpconfig.Connect()
            # Reset Heartbeat countdown
            self.__runAgainConfig = self.__HEARTBEATS2MIN_CONFIG
        #
        Domoticz.Debug(
            "onHeartbeat (Config): {} heartbeats".format(self.__runAgainConfig)
        )


global _plugin
_plugin = BasePlugin()


def onStart():
    global _plugin
    _plugin.onStart()


def onStop():
    global _plugin
    _plugin.onStop()


def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)


def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)


def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)


def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)


def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)


def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()


################################################################################
# Generic helper functions
################################################################################
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug("'{}: '{}'".format(x, Parameters[x]))
    Domoticz.Debug("Device count: {}".format(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           {} - {}".format(x, Devices[x]))
        Domoticz.Debug("Device ID:        {}".format(Devices[x].ID))
        Domoticz.Debug("Device Name:     '{}'".format(Devices[x].Name))
        Domoticz.Debug("Device nValue:    {}".format(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '{}'".format(Devices[x].sValue))
        Domoticz.Debug("Device LastLevel: {}".format(Devices[x].LastLevel))


def UpdateDevice(Unit, nValue, sValue, TimedOut=0, AlwaysUpdate=False):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    if Unit in Devices:
        if (
            Devices[Unit].nValue != nValue
            or Devices[Unit].sValue != sValue
            or Devices[Unit].TimedOut != TimedOut
            or AlwaysUpdate
        ):
            Devices[Unit].Update(nValue=nValue, sValue=str(sValue), TimedOut=TimedOut)
            Domoticz.Debug(
                "Update {}: {} - '{}' - {}".format(
                    Devices[Unit].Name, nValue, sValue, TimedOut
                )
            )


def DumpHTTPResponseToLog(httpDict):
    if isinstance(httpDict, dict):
        Domoticz.Debug("HTTP Details ({}):".format(len(httpDict)))
        for x in httpDict:
            if isinstance(httpDict[x], dict):
                Domoticz.Debug("..'{}' ({}):".format(x, len(httpDict[x])))
                for y in httpDict[x]:
                    Domoticz.Debug("....'{}': '{}'".format(y, httpDict[x][y]))
            else:
                Domoticz.Debug("..'{}': '{}'".format(x, httpDict[x]))
