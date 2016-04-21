"""
Copyright (c) 2011, 2012, Regents of the University of California
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

  - Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
  - Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the
      distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL
THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
OF THE POSSIBILITY OF SUCH DAMAGE.
"""
"""
@author Jonathan Fuerst <jonf@itu.dk>
"""
import os, requests, __builtin__
from smap import actuate, driver
from smap.util import periodicSequentialCall
from smap.contrib import dtutil
from requests.auth import HTTPDigestAuth
import json
import time
import bcrypt
import hashlib
import unicodedata

from twisted.internet import threads

class WIFI(driver.SmapDriver):
    client_api = [
        {"api": "rssi", "access": "r", "data_type":"double", "unit": "dBm"},
        {"api": "signalToNoiseRatio", "access": "r", "data_type":"double", "unit": "dB"},
        {"api": "clientOS", "access": "r", "data_type":"string"},
        {"api": "deviceName", "access": "r", "data_type":"string"}
        ]

    def getDevices(self):
        devices = {}
        r = requests.get(self.url+"/hm/api/v1/devices", auth=(self.user, self.password))
        j = json.loads(r.text)
        for d in j:
            hostName = d["hostName"]
            hostName = unicodedata.normalize('NFKD', hostName).encode('ascii','ignore')
            location = d["location"]
            location = unicodedata.normalize('NFKD', location).encode('ascii','ignore')
            self.add_collection("/"+hostName)
            cl2 = self.get_collection("/"+hostName)
            cl2['Metadata'] = {
                'Location' : {
                      'Room' : location
                }
            }
            devices[hostName] = {"deviceName": d["hostName"], "location": location}
        return devices

    def getClients(self):
        clients = []
        r = requests.get(self.url+"/hm/api/v1/clients?q=10", auth=(self.user, self.password))
        j = json.loads(r.text)
        for c in j:
            mac = c["macAddress"]
            mac_hashed = hashlib.sha512(mac.encode('latin-1')).hexdigest()
            mac_hashed = mac_hashed.replace("/", "")
            # hashed = bcrypt.hashpw(mac.encode('latin-1'), bcrypt.gensalt())
            # hashed = hashed.replace("/", "")
            # print hashed
            # hashed = mac
            try:
                rssi_str = c["rssi"][:-4]
                rssi = float(rssi_str)
            except:
                rssi = 0.0
            try:
                snr_str = c["signalToNoiseRatio"][:-3]
                snr = float(snr_str)
            except:
                snr = 0.0
            try:
                health = c["health"]
                health = float(health)
            except:
                health = 0.0
            try:
                chan = c["channel"]
                chan = float(chan)
            except:
                chan = 0.0
            try:
                clientOS = c["clientOS"]
                clientOS = unicodedata.normalize('NFKD', clientOS).encode('ascii','ignore')
            except:
                clientOS = "Unknown"
            try:
                vendorName = c["vendorName"]
                vendorName = unicodedata.normalize('NFKD', vendorName).encode('ascii','ignore')
            except:
                vendorName = "Unknown"
            snr_str = c["signalToNoiseRatio"][:-3]
            deviceName = c["deviceName"]
            deviceName = unicodedata.normalize('NFKD', deviceName).encode('ascii','ignore')
            clients.append({"id": mac_hashed, "deviceName":deviceName,
                            "rssi":rssi, "signalToNoiseRatio":snr,
                            "health": health, "channel":chan,
                            "clientOS":clientOS, "vendorName": vendorName})
        return clients

    def setup(self, opts):
        self.tz = opts.get('Metadata/Timezone', None)
        self.url = opts.get('url', None)
        self.password = opts.get('password', None)
        self.user = opts.get('user', None)
        self.rate = float(opts.get('Rate', 300))
        # Get all accesspoints
        self.devices = self.getDevices()
        # for d in self.devices:
            # self.add_collection("/"+d["deviceName"])
        # Get all clients
        # for option in self.api:
            # self.add_timeseries('/'+ tstat_device + '/' +option["api"],
                    # option["unit"], data_type=option["data_type"], timezone=self.tz)
    def start(self):
        # call self.read every self.rate seconds
        periodicSequentialCall(self.read).start(self.rate)
    def read(self):
        self.clients = self.getClients()
        for c in self.clients:
            d_n = c["deviceName"]
            c_id = c["id"]
            c_rssi = c["rssi"]
            c_snr = c["signalToNoiseRatio"]
            c_health = c["health"]
            c_chan= c["channel"]
            path = "/"+d_n +"/"+ str(c_id)
            if self.get_timeseries(path+"/rssi") is None:
                self.add_timeseries(path+"/rssi",
                        "dBm", data_type="double", timezone=self.tz)
                self.add_timeseries(path+"/snr",
                        "dB", data_type="double", timezone=self.tz)
                self.add_timeseries(path+"/health",
                        "State", data_type="double", timezone=self.tz)
                self.add_timeseries(path+"/channel",
                        "Channel", data_type="double", timezone=self.tz)
                self.set_metadata(path, {
                                 'Extra/clientOS' : c["clientOS"]
                })
                self.set_metadata(path, {
                                 'Extra/vendorName' : c["vendorName"]
                })
            self.add(path+"/rssi", c_rssi)
            self.add(path+"/snr", c_snr)
            self.add(path+"/health", c_health)
            self.add(path+"/channel", c_chan)

def remove_non_ascii(text):
    return ''.join(i for i in text if ord(i)<128)


def whatisthis(s):
    if isinstance(s, str):
        print "ordinary string"
    elif isinstance(s, unicode):
        print "unicode string"
    else:
        print "not a string"
