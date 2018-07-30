#  Windcentrale Python Plugin
#
# Author: Xorfor
#
# Using:
#   https://zep-api.windcentrale.nl/production/<id>/live
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


class BasePlugin:
    __HEARTBEATS2MIN = 6  # 5 minutes
    __WINDMILLS = {
        # Name: [ ID, winddelen ]
        "De Grote Geert": [1, 9910],
        "De Jonge Held": [2, 10154],
        "Het Rode Hert": [31, 6648],
        "De Ranke Zwaan": [41, 6164],
        "De Witte Juffer": [51, 5721],
        "De Bonte Hen": [111, 5579],
        "De Trouwe Wachter": [121, 5602],
        "De Blauwe Reiger": [131, 5534],
        "De Vier Winden": [141, 5512],
        "De Boerenzwaluw": [191, 3000],
        # At the end of 2018, more windmills will be added
    }

    # Url to get data from the windmills
    __API_ADDRESS = "zep-api.windcentrale.nl"
    __API_URL = "/production/{}/live"

    __UNIT_POWERWND = 1
    __UNIT_POWERTOT = 2
    __UNIT_WINDSPEED = 3
    # __UNIT_WINDDIRECTION = 4
    __UNIT_POWERREL = 5
    __UNIT_RPM = 6
    __UNIT_OPERATIONAL = 7
    __UNIT_KWHTOT = 8
    __UNIT_KWHWND = 9
    __UNIT_HOURSYEAR = 10

    def __init__(self):
        self.__runAgain = 0
        self.__id = -1
        self.__max_winddelen = -1
        self.__number_winddelen = -1
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
            self.__max_winddelen = windmill[1]
        except:
            Domoticz.Debug("Invalid windmill selected")  # Should not be possible!
            self.__id = -1
            self.__max_winddelen = -1
        # Check the number of winddelen
        Domoticz.Debug("Mode1: " + Parameters["Mode1"])
        try:
            self.__number_winddelen = int(Parameters["Mode1"])
            if self.__number_winddelen < 0 or self.__number_winddelen > self.__max_winddelen:
                self.__number_winddelen = -1
        except:
            Domoticz.Debug("Invalid number of winddelen entered")
            self.__number_winddelen = -1

        Domoticz.Debug("id: " + str(self.__id))
        Domoticz.Debug("max winddelen: " + str(self.__max_winddelen))
        Domoticz.Debug("number winddelen: " + str(self.__number_winddelen))
        # Create devices
        if len(Devices) == 0:
            Domoticz.Device(Unit=self.__UNIT_POWERWND, Name="Power (" + str(self.__number_winddelen) + ")",
                            TypeName="Custom", Options={"Custom": "1;Watt"}, Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.__UNIT_POWERTOT, Name="Power (total)", TypeName="Custom",
                            Options={"Custom": "1;kW"}, Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.__UNIT_POWERREL, Name="Relative", TypeName="Custom", Options={"Custom": "1;%"},
                            Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.__UNIT_WINDSPEED, Name="Wind speed", TypeName="Custom",
                            Options={"Custom": "0.0;bft"}, Image=image, Used=1).Create()
            # Domoticz.Device( Unit=self.__UNIT_WINDDIRECTION, Name="Wind direction", TypeName="Wind", Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.__UNIT_RPM, Name="RPM", TypeName="Custom", Options={"Custom": "1;rpm"},
                            Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.__UNIT_OPERATIONAL, Name="Operational time", TypeName="Custom",
                            Options={"Custom": "1;%"}, Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.__UNIT_KWHWND, Name="Energy (" + str(self.__number_winddelen) + ")",
                            TypeName="Custom", Options={"Custom": "1;kWh"}, Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.__UNIT_KWHTOT, Name="Energy (total)", TypeName="Custom",
                            Options={"Custom": "1;MWh"}, Image=image, Used=1).Create()
            Domoticz.Device(Unit=self.__UNIT_HOURSYEAR, Name="Hours", TypeName="Custom", Image=image, Used=1).Create()

        DumpConfigToLog()
        Domoticz.Debug("self.__API_ADDRESS: " + self.__API_ADDRESS)
        self.__httpcon = Domoticz.Connection(Name="Windcentrale", Transport="TCP/IP", Protocol="HTTPS",
                                             Address=self.__API_ADDRESS, Port="443")
        self.__httpcon.Connect()

    def onStop(self):
        Domoticz.Debug("onStop called")

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("onConnect called (" + str(Status) + "): " + Description)
        if Status == 0:
            if self.__id > 0:
                url = self.__API_URL.format(self.__id)
                # url = "/production/"+str(self.__id)+"/live"
                Domoticz.Debug("url: " + url)
                sendData = {'Verb': 'GET',
                            'URL': url,
                            'Headers': {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                                        'Accept-Language': 'en-GB,en;q=0.5',
                                        'Connection': 'keep-alive',
                                        'Host': self.__API_ADDRESS,
                                        'User-Agent': 'Domoticz/1.0'}
                            }
                Connection.Send(sendData)
        else:
            Domoticz.Error(
                "Failed to connect (" + str(Status) + ") to: " + self.__API_ADDRESS + " with error: " + Description)

    def onMessage(self, Connection, Data):
        Domoticz.Debug("onMessage called")
        DumpHTTPResponseToLog(Data)
        jsonData = json.loads(Data["Data"].decode("utf-8", "ignore"))
        # Power produced for the amount of wind shares
        ival = max(0, jsonData.get("powerAbsWd", 0) * self.__number_winddelen)
        UpdateDevice(self.__UNIT_POWERWND, int(ival), str(ival), AlwaysUpdate=True)
        # Total power produced by the windmill
        fval = round(max(0, float(jsonData.get("powerAbsTot", 0))), 1)
        UpdateDevice(self.__UNIT_POWERTOT, int(fval), str(fval), AlwaysUpdate=True)
        # Percentage of maximum power of the windmill
        ival = jsonData.get("powerRel", 0)
        UpdateDevice(self.__UNIT_POWERREL, int(ival), str(ival), AlwaysUpdate=True)
        # Windspeed in bft
        ival = jsonData.get("windSpeed", 0)
        UpdateDevice(self.__UNIT_WINDSPEED, int(ival), str(ival), AlwaysUpdate=True)
        #
        # tag = "windDirection"
        # if tag in jsonData:
        #     Domoticz.Debug(tag+": " + str(jsonData[tag]))
        #     UpdateDevice(self.__UNIT_WINDDIRECTION, 0, "0;"+str(jsonData[tag])+"0;0;0", AlwaysUpdate=True)
        # RPM. Rotation speed windmill
        fval = round(float(jsonData.get("rpm", 0)), 1)
        UpdateDevice(self.__UNIT_RPM, int(fval), str(fval), AlwaysUpdate=True)
        # Percentage time in production (since start of windmill)
        fval = round(float(jsonData.get("runPercentage", 0)), 1)
        UpdateDevice(self.__UNIT_OPERATIONAL, int(fval), str(fval), AlwaysUpdate=True)
        # Total production this year and for the winddelen
        fval = round(float(jsonData.get("kwh", 0)) / 1000, 1)
        UpdateDevice(self.__UNIT_KWHTOT, int(fval), str(fval), AlwaysUpdate=True)
        fval = round(float(jsonData.get("kwh", 0)) / self.__max_winddelen * self.__number_winddelen, 1)
        UpdateDevice(self.__UNIT_KWHWND, int(fval), str(fval), AlwaysUpdate=True)
        # Hours in production
        fval = round(float(jsonData.get("hoursRunThisYear")), 1)
        UpdateDevice(self.__UNIT_HOURSYEAR, int(fval), str(fval), AlwaysUpdate=True)

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug(
            "onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Debug("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(
            Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        Domoticz.Debug("onDisconnect called")

    def onHeartbeat(self):
        Domoticz.Debug("onHeartbeat called")
        self.__runAgain -= 1
        if self.__runAgain <= 0:
            if self.__httpcon.Connecting() or self.__httpcon.Connected():
                Domoticz.Debug("onHeartbeat called, Connection is alive.")
            else:
                self.__httpcon.Connect()
            self.__runAgain = 1 * self.__HEARTBEATS2MIN  # 1 minute
        else:
            Domoticz.Debug("onHeartbeat called, run again in " + str(self.__runAgain) + " heartbeats.")


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
                "Update " + Devices[Unit].Name + ": " + str(nValue) + " - '" + str(sValue) + "' - " + str(TimedOut))


def DumpHTTPResponseToLog(httpDict):
    if isinstance(httpDict, dict):
        Domoticz.Debug("HTTP Details (" + str(len(httpDict)) + "):")
        for x in httpDict:
            if isinstance(httpDict[x], dict):
                Domoticz.Debug("--->'" + x + " (" + str(len(httpDict[x])) + "):")
                for y in httpDict[x]:
                    Domoticz.Debug("------->'" + y + "':'" + str(httpDict[x][y]) + "'")
            else:
                Domoticz.Debug("--->'" + x + "':'" + str(httpDict[x]) + "'")
