#  Windcentrale Python Plugin
#
# Author: Xorfor
#
# Using:
#   https://zep-api.windcentrale.nl/production/<id>/live
#   https://zep-api.windcentrale.nl/app/config
#
"""
<plugin key="xfr_windcentrale" name="Windcentrale" author="Xorfor" version="1.0.0" wikilink="https://github.com/Xorfor/Domoticz-Windcentrale-Plugin" externallink="https://www.windcentrale.nl/">
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
import subprocess
import xml.etree.ElementTree as ET


class BasePlugin:

    __HEARTBEATS2MIN = 6  # 5 minutes

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

    UNIT_POWERWND = 1
    UNIT_POWERTOT = 2
    UNIT_WINDSPEED = 3
    # UNIT_WINDDIRECTION = 4
    UNIT_POWERREL = 5
    UNIT_RPM = 6
    UNIT_OPERATIONAL = 7
    UNIT_HOURSYEAR = 8
    UNIT_NEWS = 9

    SWITCHTYPE_NONE = -1
    SWITCHTYPE_USAGE = 0
    SWITCHTYPE_RETURN = 4

    UNITS = [
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
        self.__runAgain = 0
        self.__id = None
        self.__max_winddelen = None
        self.__number_winddelen = None
        self.__headers = {}
        self.__url = ""
        self.__httpcon = None

    def onStart(self):
        Domoticz.Debug("onStart called")
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(1)
        else:
            Domoticz.Debugging(0)
        # Images
        # Check if images are in database
        # if "xfr_windcentrale" not in Images:
        #     Domoticz.Image("xfr_windcentrale.zip").Create()
        # image = Images["xfr_windcentrale"].ID
        # Domoticz.Debug("Image created. ID: " + str(image))

        # Validation of parameters
        # Check the selected Windmill
        Domoticz.Debug("Adress: " + Parameters["Address"])
        try:
            windmill = self.__WINDMILLS[Parameters["Address"]]
            self.__id = windmill[0]
            self.__parkid = windmill[1]
            self.__max_winddelen = windmill[2]
        except:
            # Should not be possible!
            Domoticz.Error("Invalid windmill selected")
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
        Domoticz.Debug("max winddelen: " + str(self.__max_winddelen))
        Domoticz.Debug("number winddelen: " + str(self.__number_winddelen))
        # Create devices
        if len(Devices) == 0:
            for unit in self.UNITS:
                Domoticz.Device(
                    Unit=unit[0],
                    Name=unit[1].format(self.__number_winddelen),
                    Type=unit[2],
                    Subtype=unit[3],
                    Options=unit[4],
                    Switchtype=unit[5],
                    Used=1).Create()

        DumpConfigToLog()
        Domoticz.Debug("self.API_ENDPOINT: " + self.API_ENDPOINT)
        self.__jsoncon = Domoticz.Connection(Name="Windcentrale", Transport="TCP/IP", Protocol="HTTPS",
                                             Address=self.API_ENDPOINT, Port="443")
        self.__jsoncon.Connect()

    def onStop(self):
        Domoticz.Debug("onStop")

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("onConnect: {}, {}, {}".format(
            Connection, Status, Description))

    def onMessage(self, Connection, Data):
        Domoticz.Debug("onMessage: {}, {}".format(Connection, Data))

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug("onCommand: {}, {}, {}, {}"
                       .format(Unit,
                               Command,
                               Level,
                               Hue)
                       )

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Debug("onNotification: {}, {}, {}, {}, {}, {}, {}"
                       .format(Name,
                               Subject,
                               Text,
                               Status,
                               Priority,
                               Sound,
                               ImageFile)
                       )

    def onDisconnect(self, Connection):
        Domoticz.Debug("onDisconnect: {}".format(Connection))

    def onHeartbeat(self):
        Domoticz.Debug("onHeartbeat")
        self.__runAgain -= 1
        if self.__runAgain <= 0:
            if self.__id is not None:
                url = "https://" + self.API_ENDPOINT + \
                    self.API_LIVE.format(self.__id)
                data = getData(url)
                jsonData = json.loads(data.decode("utf-8", "ignore"))

                # Total power of the windmill
                kw = float(jsonData.get("powerAbsTot", 0)) * 1000
                # Total kwh of the windmill
                kwh = float(jsonData.get("kwh", 0)) * 1000

                # Current power per windmill share
                fval = float(jsonData.get("powerAbsWd", 0))
                UpdateDevice(self.UNIT_POWERWND,
                             0,
                             "{};{}".format(
                                 fval * self.__number_winddelen,
                                 kwh * self.__number_winddelen / self.__max_winddelen),
                             AlwaysUpdate=True)

                # Total windmill power
                fval = round(max(0, kw), 1)
                UpdateDevice(self.UNIT_POWERTOT,
                             int(fval),
                             "{};{}".format(fval, kwh),
                             AlwaysUpdate=True)

                # Relative power
                fval = jsonData.get("powerRel", 0)
                UpdateDevice(self.UNIT_POWERREL,
                             int(fval),
                             str(fval),
                             AlwaysUpdate=True)

                # Windspeed in bft
                fval = jsonData.get("windSpeed", 0)
                UpdateDevice(self.UNIT_WINDSPEED,
                             int(fval),
                             str(fval),
                             AlwaysUpdate=True)

                # # Winddirection
                # winddirection = jsonData.get("windDirection")
                # UpdateDevice(self.__UNIT_WINDDIRECTION,
                #     0,
                #     "0;{};0;0;0".format(winddirection),
                #     AlwaysUpdate=True)

                # RPM. Rotation speed windmill
                fval = round(float(jsonData.get("rpm", 0)), 1)
                Domoticz.Debug("rpm: {}".format(fval))
                UpdateDevice(self.UNIT_RPM,
                             int(fval),
                             str(fval),
                             AlwaysUpdate=True)

                # Percentage time in production (since start of windmill)
                fval = round(float(jsonData.get("runPercentage", 0)), 1)
                Domoticz.Debug("runPercentage: {}".format(fval))
                UpdateDevice(self.UNIT_OPERATIONAL,
                             int(fval),
                             str(fval),
                             AlwaysUpdate=True)

                # Hours in production
                fval = round(float(jsonData.get("hoursRunThisYear")), 1)
                UpdateDevice(self.UNIT_HOURSYEAR,
                             int(fval),
                             str(fval),
                             AlwaysUpdate=True)

                txt = ""
                lines = 2
                url = "https://" + self.API_ENDPOINT + self.API_CONFIG
                # data = getData(url)
                # tree = ET.fromstring(data)
                # news = tree.findall("news/i")
                # for child in news:
                #     if (child.attrib["p"] == self.__parkid and child.attrib["m"] == "0") \
                #     or (child.attrib['p'] == "0" and child.attrib['m'] == self.__id) \
                #     or (child.attrib['p'] == "0" and child.attrib['m'] == "0"):
                #         Domoticz.Debug(
                #             "child.find: {}".format(child.find("t")))
                #         txt += child.find("t")
                #         lines -= 1
                #     if lines <= 0:
                #         break
                UpdateDevice(self.UNIT_NEWS,
                             0,
                             txt,
                             AlwaysUpdate=True)

            self.__runAgain = 1 * self.__HEARTBEATS2MIN  # 1 minute
        else:
            Domoticz.Debug("onHeartbeat called, run again in " +
                           str(self.__runAgain) + " heartbeats.")


def getData(url):
    Domoticz.Debug("getData: {}".format(url))
    command = "curl"
    options = "'" + url + "'"
    Domoticz.Debug("getData: {}".format(command + " " + options))
    p = subprocess.Popen(command + " " + options,
                         shell=True, stdout=subprocess.PIPE)
    p.wait()
    data, errors = p.communicate()
    if p.returncode != 0:
        Domoticz.Debug("Request failed")
    return data


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
    _plugin.onNotification(Name, Subject, Text, Status,
                           Priority, Sound, ImageFile)


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
        Domoticz.Debug("Setting:           " +
                       str(x) + " - " + str(Settings[x]))


def UpdateDevice(Unit, nValue, sValue, TimedOut=0, AlwaysUpdate=False):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    if Unit in Devices:
        if Devices[Unit].nValue != nValue or Devices[Unit].sValue != sValue or Devices[
                Unit].TimedOut != TimedOut or AlwaysUpdate:
            Devices[Unit].Update(
                nValue=nValue, sValue=str(sValue), TimedOut=TimedOut)
            Domoticz.Debug(
                "Update " + Devices[Unit].Name + ": " + str(nValue) + " - '" + str(sValue) + "' - " + str(TimedOut))


def DumpHTTPResponseToLog(httpDict):
    if isinstance(httpDict, dict):
        Domoticz.Debug("HTTP Details (" + str(len(httpDict)) + "):")
        for x in httpDict:
            if isinstance(httpDict[x], dict):
                Domoticz.Debug(
                    "--->'" + x + " (" + str(len(httpDict[x])) + "):")
                for y in httpDict[x]:
                    Domoticz.Debug("------->'" + y + "':'" +
                                   str(httpDict[x][y]) + "'")
            else:
                Domoticz.Debug("--->'" + x + "':'" + str(httpDict[x]) + "'")
