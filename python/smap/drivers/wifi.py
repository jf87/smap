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
import requests
from smap import driver
from smap.util import periodicSequentialCall
import json
import hashlib
import unicodedata

class WIFI(driver.SmapDriver):
    devices_ts = [
        {"key": "wifi0Channel", "name": "chan0", "unit": "Channel", "type": "long", "func": (lambda x: x)},
        {"key": "wifi0Power", "name": "power0", "unit": "dBm", "type": "long", "func": (lambda x: x[:-4])},
        {"key": "wifi1Channel", "name": "chan1", "unit": "Channel", "type": "long", "func": (lambda x: x)},
        {"key": "wifi1Power", "name": "power1", "unit": "dBm", "type": "long", "func": (lambda x: x[:-4])},
        {"key": "clients", "name": "no_clients_device", "unit": "Clients", "type": "long", "func": (lambda x: x)}
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
            floor = d['topologyName']
            floor = unicodedata.normalize('NFKD', floor).encode('ascii','ignore')
            if floor == 'ITU WIFI_Etage0':
                floor_no = '0'
            elif floor == 'ITU WIFI_Etage1':
                floor_no = '1'
            elif floor == 'ITU WIFI_Etage2':
                floor_no = '2'
            elif floor == 'ITU WIFI_Etage3':
                floor_no = '3'
            elif floor == 'ITU WIFI_Etage4':
                floor_no = '4'
            elif floor == 'ITU WIFI_Etage5':
                floor_no = '5'
            elif floor == 'ITU WIFI_Basement':
                floor_no = '-1'
            else:
                floor_no = '-'
            if self.get_collection("/"+floor_no) is None:
                self.add_collection("/"+floor_no)
            path = "/"+floor_no+'/'+hostName
            if self.get_collection(path) is None:
                self.add_collection(path)
            cl2 = self.get_collection(path)
            cl2['Metadata'] = {
                'Location' : {
                    'Building': 'IT University of Copenhagen',
                    'Street': 'Rued Langgaards Vej 7',
                    'City': 'Copenhagen',
                    'Floor': floor_no,
                    'Room' : location
                },
                'Instrument': {
                    "Model": "Access Point"
                }
            }
            for ts in self.devices_ts:
                try:
                    v = d[ts['key']]
                    if isinstance(v, unicode):
                        v = unicodedata.normalize('NFKD', v).encode('ascii','ignore')
                    v = ts["func"](v)
                    if ts["type"] == "long":
                        v = long(v)
                    elif ts["type"] == "float":
                        v = float(v)
                    if self.get_timeseries(path+"/"+ts["name"]) is None:
                        self.add_timeseries(path+"/"+ts["name"],
                            ts["unit"], data_type=ts["type"], timezone=self.tz)
                    self.add(path+"/"+ts["name"], v)
                except:
                    if v is None:
                        v = "None"
                    print 'could not add '+str(v)+" to "+ts['key']

            devices[hostName] = {"deviceName": d["hostName"], "location": location, "path": path}
        return devices

    clients_ts = [
        {"key": "channel", "name": "channel", "unit": "Channel", "type": "long", "func": (lambda x: x)},
        {"key": "rssi", "name": "rssi", "unit": "dBm", "type": "long", "func": (lambda x : x[:-4])},
        {"key": "health", "name": "health", "unit": "State", "type": "long", "func": (lambda x : x)},
        {"key": "signalToNoiseRatio", "name": "snr", "unit": "dB", "type": "long", "func": (lambda x : x[:-3])},
    ]

    def getClients(self):
        devices_count = {}
        for k, v in self.devices.iteritems():
            devices_count[k] = 0
        r = requests.get(self.url+"/hm/api/v1/clients?q=10", auth=(self.user, self.password))
        j = json.loads(r.text)
        for c in j:
            deviceName = c["deviceName"]
            deviceName = unicodedata.normalize('NFKD', deviceName).encode('ascii','ignore')
            if deviceName in devices_count:
                devices_count[deviceName] += 1
            else:
                devices_count[deviceName] = 1
            mac = c["macAddress"]
            mac_hashed = hashlib.sha512(mac.encode('latin-1')).hexdigest()
            mac_hashed = mac_hashed.replace("/", "")
            try:
                clientOS = c["clientOS"]
                clientOS = unicodedata.normalize('NFKD', clientOS).encode('ascii','ignore')
                if clientOS == "":
                    clientOS = "Unknown"
            except:
                clientOS = "Unknown"
            try:
                vendorName = c["vendorName"]
                vendorName = unicodedata.normalize('NFKD', vendorName).encode('ascii','ignore')
                if vendorName == "":
                    vendorName = "Unknown"
            except:
                vendorName = "Unknown"
            path = self.devices[deviceName]["path"]+"/"+ str(mac_hashed)
            for ts in self.clients_ts:
                try:
                    v = c[ts['key']]
                    if isinstance(v, unicode):
                        v = unicodedata.normalize('NFKD', v).encode('ascii','ignore')
                    v = ts["func"](v)
                    if ts["type"] == "long":
                        v = long(v)
                    elif ts["type"] == "float":
                        v = float(v)
                    if self.get_timeseries(path+"/"+ts["name"]) is None:
                        self.add_timeseries(path+"/"+ts["name"],
                            ts["unit"], data_type=ts["type"], timezone=self.tz)
                        self.set_metadata(path, {
                            'Extra/clientOS' : clientOS
                        })
                        self.set_metadata(path, {
                            'Extra/vendorName' : vendorName
                        })
                        self.set_metadata(path, {
                            'Extra/accessPoint' : deviceName
                        })
                        self.set_metadata(path, {
                            'Extra/id' : str(mac_hashed)
                        })
                    self.set_metadata(path, {
                        'Instrument/Model' : 'Client'
                    })
                    self.add(path+"/"+ts["name"], v)
                except:
                    if v is None:
                        v = "None"
                    print 'could not add '+str(v)+" to "+ts['key']
        for k, v in devices_count.iteritems():
            try:
                path = self.devices[k]["path"] +"/no_clients"
                if self.get_timeseries(path) is None:
                    self.add_timeseries(path,
                            "Clients", data_type="long", timezone=self.tz)
                self.add(path, v)
            except:
                print 'could not add client count'

    def setup(self, opts):
        self.tz = opts.get('Metadata/Timezone', None)
        self.url = opts.get('url', None)
        self.password = opts.get('password', None)
        self.user = opts.get('user', None)
        self.rate = float(opts.get('Rate', 300))
        # Get all accesspoints
        self.devices = self.getDevices()

    def start(self):
        # call self.read every self.rate seconds
        periodicSequentialCall(self.read).start(self.rate)
    def read(self):
        self.getDevices()
        self.getClients()

def remove_non_ascii(text):
    return ''.join(i for i in text if ord(i)<128)

def whatisthis(s):
    if isinstance(s, str):
        print "ordinary string"
    elif isinstance(s, unicode):
        print "unicode string"
    else:
        print "not a string"
