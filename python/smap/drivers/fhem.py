
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

from twisted.internet import threads

class FHEM(driver.SmapDriver):
    api = [
        {"api": "desired-temp", "access": "rw", "data_type":"double", "unit": "C",
        "act_type": "continuous", "range": [5,30]},
        {"api": "measured-temp", "access": "r", "data_type":"double", "unit": "C"}
        ]

    def getThermostats(self, ip ):
        tstats = []
        r = requests.get("http://" + ip + "/fhem?cmd=jsonlist2&XHR=1")
        val = json.loads(r.text)
        for i in val["Results"]:
            if i["Name"] != None:
                if i["Name"].endswith("_Clima"):
                    print "new thermostat found"
                    tstats.append({"name":str(i["Name"]), "device":str(i["Internals"]["device"])})
        return tstats

    def setup(self, opts):
        self.tz = opts.get('Metadata/Timezone', None)
        self.rate = float(opts.get('Rate', 30))
        self.ip = opts.get('ip', None)
        self.tstats = []
        # Get a list of lights
        self.tstats = self.getThermostats(self.ip)
        print self.tstats
        for tstat in self.tstats:
            print tstat
            tstat_name = tstat["name"]
            tstat_device = tstat["device"]
            for option in self.api:
                if option["access"] == "rw":
                    ts = self.add_timeseries('/'+tstat_device+'/'+option["api"],
                            option["unit"], data_type=option["data_type"], timezone=self.tz)
                    setup={'model': option["act_type"], 'ip':self.ip,
                            'range': option.get("range"), 'id': tstat_name,
                            'api': option["api"]}
                    if  option["act_type"] == "binary":
                        setup['states'] = option.get("states")
                        act = BinaryActuator(**setup)
                    if  option["act_type"] == "continuousInteger":
                        act = ContinuousIntegerActuator(**setup)
                    if  option["act_type"] == "discrete":
                        act = DiscreteActuator(**setup)
                    if  option["act_type"] == "continuous":
                        act = ContinuousActuator(**setup)
                    # ts = self.add_timeseries('/'+ tstat_device + '/' + option["api"] + '_act', option["unit"], data_type=option["data_type"])
                    ts.add_actuator(act)
                else:
                    self.add_timeseries('/'+ tstat_device + '/' +option["api"],
                            option["unit"], data_type=option["data_type"], timezone=self.tz)
    def start(self):
        # call self.read every self.rate seconds
        periodicSequentialCall(self.read).start(self.rate)
    def read(self):
        for tstat in self.tstats:
            tstat_name = tstat["name"]
            tstat_device = tstat["device"]
            #192.168.0.105:8083/fhem?cmd=jsonlist2+CUL_HM_HM_CC_RT_DN_2EEF7B_Clima&XHR=1
            r = requests.get("http://" + self.ip + "/fhem?cmd=jsonlist2+" + tstat_name + "&XHR=1")
            val = json.loads(r.text)
            #print r.url
            #print val
            for option in self.api:
                #print val["Results"][0]["Readings"][option["api"]]
                self.add('/'+tstat_device +"/"+ option["api"],
                        float(val["Results"][0]["Readings"][option["api"]]["Value"]))

class Actuator(actuate.SmapActuator):

    def __init__(self, **opts):
        self.ip = opts['ip']
        self.id = opts['id']
        self.api = opts['api']
        actuate.SmapActuator.__init__(self, opts.get('archiver', 'http://130.226.142.195:8079'))

    def get_state(self, request):
        print "get state"
        r = requests.get("http://" + self.ip + "/fhem?cmd=jsonlist2+" + self.id + "&XHR=1")
        val = json.loads(r.text)
        reading = val["Results"][0]["Readings"][self.api]["Value"]
        print reading
        return self.parse_state(str(reading))

    def set_state(self, request, state):
        print "set state"
        if self.api == "on":
            state = bool(state)
        #192.168.0.105:8083/fhem?cmd=set%20CUL_HM_HM_CC_RT_DN_2EEF7B_Clima%20desired-temp%2020.23
        url = ("http://" + self.ip + "/fhem?cmd=set%20" + self.id + "%20" + self.api + "%20"+str(state))
        r = requests.get(url)
        print r.url
        print r.text
        return state


class ContinuousActuator(Actuator, actuate.ContinuousActuator):
    def __init__(self, **opts):
        actuate.ContinuousActuator.__init__(self, opts["range"])
        Actuator.__init__(self, **opts)

class BinaryActuator(Actuator, actuate.BinaryActuator):
        def __init__(self, **opts):
                actuate.BinaryActuator.__init__(self)
                Actuator.__init__(self, **opts)

class DiscreteActuator(Actuator, actuate.NStateActuator):
        def __init__(self, **opts):
                actuate.NStateActuator.__init__(self, opts["states"])
                Actuator.__init__(self, **opts)


class ContinuousIntegerActuator(Actuator, actuate.ContinuousIntegerActuator):
        def __init__(self, **opts):
                actuate.ContinuousIntegerActuator.__init__(self, opts["range"])
                Actuator.__init__(self, **opts)
