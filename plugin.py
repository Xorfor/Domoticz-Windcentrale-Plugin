#  Windcentrale Python Plugin
#
# Author: Xorfor
#
# Using:
#   https://zep-api.windcentrale.nl/production/<id>/live
#
"""
<plugin key="xfr_windcentrale" name="Windcentrale" author="Xorfor" version="2.0.0" wikilink="https://github.com/Xorfor/Domoticz-Windcentrale-Plugin" externallink="https://www.windcentrale.nl/">
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

class BasePlugin:
    __HEARTBEATS2MIN_LIVE = 6 * 1  # 1 minute
    __HEARTBEATS2MIN_CONFIG = 6 * 60  # 1 hour

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
        # At the end of 2018, more windmills will be added
    }

    # Url to get data from the windmills
    API_ENDPOINT = "zep-api.windcentrale.nl"
    API_LIVE = "/production/{}/live"
    API_CONFIG = "/app/config"
    # Connections
    CONN_LIVE = "Live"
    CONN_CONFIG = "Config"
    # Devices
    UNIT_POWERWND = 1
    UNIT_POWERTOT = 2
    UNIT_WINDSPEED = 3
    # __UNIT_WINDDIRECTION = 4
    UNIT_POWERREL = 5
    UNIT_RPM = 6
    UNIT_OPERATIONAL = 7
    UNIT_KWHTOT = 8
    UNIT_KWHWND = 9
    UNIT_HOURSYEAR = 10
    UNIT_NEWS = 11
    # Switchtypes
    SWITCHTYPE_NONE = -1
    SWITCHTYPE_USAGE = 0
    SWITCHTYPE_RETURN = 4

    DEVICES = [
        # id, name, type, subtype, options, switchtype
        [UNIT_POWERWND, "Power ({})", 243, 29, {}, SWITCHTYPE_RETURN],
        [UNIT_POWERTOT, "Power (total)", 243, 29, {}, SWITCHTYPE_RETURN],
        [UNIT_POWERREL, "Relative", 243, 6, {}, SWITCHTYPE_NONE],
        [UNIT_WINDSPEED, "Windspeed", 243, 31, {
            "Custom": "0.0;bft"}, SWITCHTYPE_NONE],
        [UNIT_RPM, "RPM", 243, 7, {}, SWITCHTYPE_NONE],
        [UNIT_OPERATIONAL, "Operational time", 243, 6, {}, SWITCHTYPE_NONE],
        [UNIT_HOURSYEAR, "Hours this year", 243, 31, {}, SWITCHTYPE_NONE],
        [UNIT_NEWS, "News", 243, 19, {}, SWITCHTYPE_NONE],
    ]

    def __init__(self):
        self.__runAgainLive = 0
        self.__runAgainConfig = 0
        self.__id = None
        self.__parkid = None
        self.__max_winddelen = None
        self.__number_winddelen = None
        # self.__headers = {}
        # self.__url = ""
        self.__httplive = None
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
        Domoticz.Debug("Image created. ID: " + str(image))
        # Validation of parameters
        # Check the selected Windmill
        Domoticz.Debug("Adress: " + Parameters["Address"])
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
        Domoticz.Debug("Mode1: " + Parameters["Mode1"])
        try:
            self.__number_winddelen = int(Parameters["Mode1"])
            if self.__number_winddelen < 0 or self.__number_winddelen > self.__max_winddelen:
                self.__number_winddelen = None
        except:
            Domoticz.Error("Invalid number of winddelen entered")
            self.__number_winddelen = None

        Domoticz.Debug("id: " + str(self.__id))
        Domoticz.Debug("parkid: " + str(self.__parkid))
        Domoticz.Debug("max winddelen: " + str(self.__max_winddelen))
        Domoticz.Debug("number winddelen: " + str(self.__number_winddelen))
        # Create devices
        if len(Devices) == 0:
            Domoticz.Device(Unit=self.UNIT_POWERWND, Name="Power (" + str(self.__number_winddelen) + ")",
                            TypeName="Custom", Options={"Custom": "1;Watt"}, Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.UNIT_POWERTOT, Name="Power (total)", TypeName="Custom",
                            Options={"Custom": "1;kW"}, Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.UNIT_POWERREL, Name="Relative", TypeName="Custom", Options={"Custom": "1;%"},
                            Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.UNIT_WINDSPEED, Name="Wind speed", TypeName="Custom",
                            Options={"Custom": "0.0;bft"}, Image=image, Used=1).Create()
            # Domoticz.Device( Unit=self.__UNIT_WINDDIRECTION, Name="Wind direction", TypeName="Wind", Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.UNIT_RPM, Name="RPM", TypeName="Custom", Options={"Custom": "1;rpm"},
                            Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.UNIT_OPERATIONAL, Name="Operational time", TypeName="Custom",
                            Options={"Custom": "1;%"}, Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.UNIT_KWHWND, Name="Energy (" + str(self.__number_winddelen) + ")",
                            TypeName="Custom", Options={"Custom": "1;kWh"}, Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.UNIT_KWHTOT, Name="Energy (total)", TypeName="Custom",
                            Options={"Custom": "1;MWh"}, Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.UNIT_HOURSYEAR, Name="Hours", TypeName="Custom", Image=image, Used=1).Create()

            Domoticz.Device(Unit=self.UNIT_NEWS, Name="News", Type=243, Subtype=19, Image=image, Used=1).Create()

        DumpConfigToLog()
        Domoticz.Debug("self.__API_ADDRESS: " + self.API_ENDPOINT)
        self.__httplive = Domoticz.Connection(Name=self.CONN_LIVE, Transport="TCP/IP", Protocol="HTTPS",
                                             Address=self.API_ENDPOINT, Port="443")
        self.__httplive.Connect()
        self.__httpconfig = Domoticz.Connection(Name=self.CONN_CONFIG, Transport="TCP/IP", Protocol="HTTPS",
                                             Address=self.API_ENDPOINT, Port="443")
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
                    Domoticz.Debug("url: " + url)
                    sendData = {"Verb": "GET",
                                "URL": url,
                                "Headers": {"Host": self.API_ENDPOINT,
                                            "User-Agent": "Domoticz/1.0"}
                                }
                    Connection.Send(sendData)
            else:
                Domoticz.Error("Failed to connect (" + str(Status) + ") to: " + self.API_ENDPOINT + " with error: " + Description)
        # Config
        if Connection.Name == self.CONN_CONFIG:
            if Status == 0:
                if self.__id is not None:
                    url = self.API_CONFIG
                    Domoticz.Debug("url: " + url)
                    sendData = {"Verb": "GET",
                                "URL": url,
                                "Headers": {"Host": self.API_ENDPOINT,
                                            "User-Agent": "Domoticz/1.0"}
                                }
                    Connection.Send(sendData)
            else:
                Domoticz.Error("Failed to connect (" + str(Status) + ") to: " +
                               self.API_ENDPOINT + " with error: " + Description)

    def onMessage(self, Connection, Data):
        Domoticz.Debug("onMessage: {}, {}".format(Connection, Data))
        DumpHTTPResponseToLog(Data)
        # Live
        if Connection.Name == self.CONN_LIVE:
            data = json.loads(Data["Data"].decode("utf-8", "ignore"))
            # Power produced for the amount of wind shares
            ival = max(0, data.get("powerAbsWd", 0) * self.__number_winddelen)
            UpdateDevice(self.UNIT_POWERWND, int(ival), str(ival), AlwaysUpdate=True)
            # Total power produced by the windmill
            fval = round(max(0, float(data.get("powerAbsTot", 0))), 1)
            UpdateDevice(self.UNIT_POWERTOT, int(fval), str(fval), AlwaysUpdate=True)
            # Percentage of maximum power of the windmill
            ival = data.get("powerRel", 0)
            UpdateDevice(self.UNIT_POWERREL, int(ival), str(ival), AlwaysUpdate=True)
            # Windspeed in bft
            ival = data.get("windSpeed", 0)
            UpdateDevice(self.UNIT_WINDSPEED, int(ival), str(ival), AlwaysUpdate=True)
            #
            # tag = "windDirection"
            # if tag in jsonData:
            #     Domoticz.Debug(tag+": " + str(jsonData[tag]))
            #     UpdateDevice(self.UNIT_WINDDIRECTION, 0, "0;"+str(jsonData[tag])+"0;0;0", AlwaysUpdate=True)
            # RPM. Rotation speed windmill
            fval = round(float(data.get("rpm", 0)), 1)
            UpdateDevice(self.UNIT_RPM, int(fval), str(fval), AlwaysUpdate=True)
            # Percentage time in production (since start of windmill)
            fval = round(float(data.get("runPercentage", 0)), 1)
            UpdateDevice(self.UNIT_OPERATIONAL, int(fval), str(fval), AlwaysUpdate=True)
            # Total kwh of the windmill
            kwh = float(data.get("kwh", 0)) * 1000

            # Total production this year and for the winddelen
            fval = round(float(data.get("kwh", 0)) / 1000, 1)
            UpdateDevice(self.UNIT_KWHTOT, int(fval), str(fval), AlwaysUpdate=True)
            fval = round(float(data.get("kwh", 0)) / self.__max_winddelen * self.__number_winddelen, 1)
            UpdateDevice(self.UNIT_KWHWND, int(fval), str(fval), AlwaysUpdate=True)
            # Hours in production
            fval = round(float(data.get("hoursRunThisYear")), 1)
            UpdateDevice(self.UNIT_HOURSYEAR, int(fval), str(fval), AlwaysUpdate=True)
        # Config
        if Connection.Name == self.CONN_CONFIG:
            txt = ""
            lines = 2
            data = ET.fromstring(Data["Data"])
            news = data.findall("news/i")
            for child in news:
                if (child.attrib["p"] == self.__parkid and child.attrib["m"] == "0") \
                or (child.attrib["p"] == "0" and child.attrib["m"] == self.__id) \
                or (child.attrib["p"] == "0" and child.attrib["m"] == "0"):
                    Domoticz.Debug("child.findtext: {}".format(child.findtext("t")))
                    date = child.attrib["t"].split(" ", 1)[1]
                    txt += "{}: {}\r".format(date, child.findtext("t"))
                    lines -= 1
                if lines <= 0:
                    break
            UpdateDevice(self.UNIT_NEWS, 0, txt, AlwaysUpdate=True)


    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug("onCommand: {}, {}, {}, {}".format(Unit, Command, Level, Hue))

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Debug("onNotification: {}, {}, {}, {}, {}, {}, {}".format(Name, Subject, Text, Status, Priority,Sound, ImageFile))

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
        Domoticz.Debug("onHeartbeat (Config): {} heartbeats".format(self.__runAgainConfig))


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
            Domoticz.Debug("'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    for x in Settings:
        Domoticz.Debug("Setting:           " + str(x) + " - " + str(Settings[x]))


def UpdateDevice(Unit, nValue, sValue, TimedOut=0, AlwaysUpdate=False):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    if Unit in Devices:
        if Devices[Unit].nValue != nValue or Devices[Unit].sValue != sValue or Devices[
            Unit].TimedOut != TimedOut or AlwaysUpdate:
            Devices[Unit].Update(nValue=nValue, sValue=str(sValue), TimedOut=TimedOut)
            Domoticz.Debug(
                "Update " + Devices[Unit].Name + ": " + str(nValue) + " - "" + str(sValue) + "" - " + str(TimedOut))


def DumpHTTPResponseToLog(httpDict):
    if isinstance(httpDict, dict):
        Domoticz.Debug("HTTP Details (" + str(len(httpDict)) + "):")
        for x in httpDict:
            if isinstance(httpDict[x], dict):
                Domoticz.Debug("--->'" + x + " (" + str(len(httpDict[x])) + "):")
                for y in httpDict[x]:
                    Domoticz.Debug("------->"" + y + "":"" + str(httpDict[x][y]) + """)
            else:
                Domoticz.Debug("--->'" + x + "':'" + str(httpDict[x]) + "'")
