#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
import urllib.request

url = "https://zep-api.windcentrale.nl/app/config"
f = urllib.request.urlopen(url).read().decode('utf-8')

root = ET.fromstring(f)

molens = root.find("molens")
for molen in molens.findall("molen"):
    name = molen.find("name").text
    id = molen.find("id").text
    parkid = molen.find("parkid").text
    winddelen = int(molen.find("winddelen").text)

    print("{} - {} ({}): {}".format(name, id, parkid, winddelen))

print("\r")

# Get info from De Trouwe Wachter
id = 121
parkid = 21

j = 0
news = root.find("news")
for new in news.findall("i"):
    if (int(new.get("m")) == id or int(new.get("p")) == parkid) or (new.get("m") == "0" and new.get("p") == "0"):
        print("{}: {}".format(new.get("t"), new.find("t").text))
        j += 1
    if j == 2:
        break
