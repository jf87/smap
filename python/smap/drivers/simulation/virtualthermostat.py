from smap import driver, actuate
from smap.util import periodicSequentialCall
import traceback

INACTIVE = 0
HEAT = 1
COOL = 2
AUTO = 3
OFF = 0

class VirtualThermostat(driver.SmapDriver):
    def setup(self, opts):
        self.state = {'temp': 72,
                      'humidity': 50,
                      'hvac_state': 0,
                      'temp_heat': 70,
                      'temp_cool': 75,
                      'hold': 0,
                      'override': 0,
                      'hvac_mode': 1,
                      'fan_mode': 1,
                      'power': 0,
                      'heat': 0
                      }

        self.readperiod = float(opts.get('ReadPeriod',.5))
        self.hysteresis = 1.0
        #self.add_timeseries('/temp', 'F', data_type='long') 
        self.add_timeseries('/humidity', '%RH', data_type='long') 
        self.add_timeseries('/hvac_state', 'Mode', data_type='long') 
        temp = self.add_timeseries('/temp', 'F', data_type='long')
        temp_heat = self.add_timeseries('/temp_heat', 'F', data_type='long') 
        temp_cool = self.add_timeseries('/temp_cool', 'F', data_type='long') 
        hold = self.add_timeseries('/hold', 'On/Off', data_type='long') 
        override = self.add_timeseries('/override', 'On/Off', data_type='long') 
        hvac_mode = self.add_timeseries('/hvac_mode', 'Mode', data_type='long') 
        fan_mode = self.add_timeseries('/fan_mode', 'Mode', data_type='long')
        power = self.add_timeseries('/power', 'Power Consumption',
                data_type='long')
        heat = self.add_timeseries('/heat', 'Heat Output',
                data_type='long')



        self.set_metadata('/', {'Metadata/Device': 'Thermostat',
                                'Metadata/Model': 'Virtual Thermostat',
                                'Metadata/Driver': __name__})
        temp.add_actuator(SetpointActuator(tstat=self, path='temp',
            _range=(45,95), archiver=opts.get('archiver'),
            subscribe=opts.get('temp')))
        temp_heat.add_actuator(SetpointActuator(tstat=self, path='temp_heat',
            _range=(45, 95), archiver=opts.get('archiver'),
            subscribe=opts.get('temp_heat')))
        temp_cool.add_actuator(SetpointActuator(tstat=self, path='temp_cool',
            _range=(45, 95), archiver=opts.get('archiver'),
            subscribe=opts.get('temp_cool')))
        hold.add_actuator(OnOffActuator(tstat=self, path='hold'))
        override.add_actuator(OnOffActuator(tstat=self, path='override'))
        hvac_mode.add_actuator(ModeActuator(tstat=self, path='hvac_mode',
            states=[0,1,2,3]))
        fan_mode.add_actuator(OnOffActuator(tstat=self, path='fan_mode'))

        metadata_type = [
                ('/temp','Sensor'),
                ('/temp_act', 'SP'),
                ('/humidity','Sensor'),
                ('/temp_heat','Reading'),
                ('/temp_heat_act','SP'),
                ('/temp_cool','Reading'),
                ('/temp_cool_act','SP'),
                ('/hold','Reading'),
                ('/hold_act','Command'),
                ('/override','Reading'),
                ('/override_act','Command'),
                ('/hvac_mode','Reading'),
                ('/hvac_mode_act','Command'),
                ('/fan_mode', 'Reading'),
                ('/fan_mode_act', 'Command'),
                ('/power', 'Reading'),
                ('/heat', 'Reading'),
                ('/hvac_state','Reading')
            ]
        for ts, tstype in metadata_type:
            self.set_metadata(ts,{'Metadata/Type':tstype})

    def start(self):
        periodicSequentialCall(self.read).start(self.readperiod)

    def read(self):
        for k,v in self.state.iteritems():
            self.add('/'+k, v)

class VirtualThermostatActuator(actuate.SmapActuator):
    def __init__(self, **opts):
        self.tstat = opts.get('tstat')
        self.path = opts.get('path')
        # we do this to get our the latest known value back from archiver
        self.subscribe(opts.get('archiver'),opts.get('subscribe'))

    def get_state(self, request):
        return self.tstat.state[self.path]

    def evaluate_states(self):
        hvac_state = self.tstat.state['hvac_state']
        hvac_mode = self.tstat.state['hvac_mode']
        temp = self.tstat.state['temp']
        temp_heat = self.tstat.state['temp_heat']
        temp_cool = self.tstat.state['temp_cool']
        hysteresis = self.tstat.hysteresis
        if hvac_mode == INACTIVE:
            hvac_state = OFF
        elif hvac_mode == HEAT:
            if hvac_state == HEAT:
                if temp >= (temp_heat + hysteresis):
                    hvac_state = OFF
            elif hvac_state == COOL:
                if temp <= (temp_heat - hysteresis):
                    hvac_state = HEAT
                else:
                    hvac_state = OFF
            elif hvac_state == OFF:
                if temp <= (temp_heat - hysteresis):
                    hvac_state = HEAT
        elif hvac_mode == COOL:
            if hvac_state == HEAT:
                if temp >= (temp_cool + hysteresis):
                    hvac_state = COOL
                else:
                    hvac_state = OFF
            elif hvac_state == COOL:
                if temp <= (temp_cool - hysteresis):
                    hvac_state = OFF
            elif hvac_state == OFF:
                if temp >= (temp_cool + hysteresis):
                    hvac_state = COOL
        elif hvac_mode == AUTO:
            if hvac_state == HEAT:
                if temp >= (temp_heat + hysteresis):
                    hvac_state = OFF
                if temp >= (temp_cool + hysteresis):
                    hvac_state = COOL
            elif hvac_state == COOL:
                if temp <= (temp_cool - hysteresis):
                    hvac_state = OFF
                if temp <= (temp_heat - hysteresis):
                    hvac_state = HEAT
            elif hvac_state == OFF:
                if temp <= (temp_heat - hysteresis):
                    hvac_state = HEAT
                if temp >= (temp_cool + hysteresis):
                    hvac_state = COOL
        if self.tstat.state['hvac_state'] != hvac_state:
            print "change state and calc power-heat"
            self.tstat.state['hvac_state'] = hvac_state
            self.tstat.state['power'] = self.calcPower()
            self.tstat.state['heat'] = self.calcHeat()

    def calcPower(self):
        hvac_state = self.tstat.state['hvac_state']
        if hvac_state == HEAT:
            power = 1000
        elif hvac_state == COOL:
            power = 1000
        else:
            power = 0
        return power

    def calcHeat(self):
        hvac_state = self.tstat.state['hvac_state']
        if hvac_state == HEAT:
            heat = 800
        elif hvac_state == COOL:
            heat = -800
        else:
            heat = 0
        return heat


class SetpointActuator(VirtualThermostatActuator, actuate.ContinuousIntegerActuator):
    def __init__(self, **opts):
        actuate.ContinuousIntegerActuator.__init__(self, opts['_range'])
        VirtualThermostatActuator.__init__(self, **opts)

    def set_state(self, request, state):
        self.tstat.state[self.path] = int(state)
        if (self.path == 'hvac_mode' or self.path == 'temp'
                or self.path == 'temp_cool' or self.path == 'temp_heat'):
            self.evaluate_states()
        return self.tstat.state[self.path]

class ModeActuator(VirtualThermostatActuator, actuate.NStateActuator):
    def __init__(self, **opts):
        actuate.NStateActuator.__init__(self, opts['states'])
        VirtualThermostatActuator.__init__(self, **opts)

    def set_state(self, request, state):
        self.tstat.state[self.path] = int(state)
        if (self.path == 'hvac_mode' or self.path == 'temp'
                or self.path == 'temp_cool' or self.path == 'temp_heat'):
            self.evaluate_states()
        return self.tstat.state[self.path]

class OnOffActuator(VirtualThermostatActuator, actuate.BinaryActuator):
    def __init__(self, **opts):
        actuate.BinaryActuator.__init__(self)
        VirtualThermostatActuator.__init__(self, **opts)

    def set_state(self, request, state):
        self.tstat.state[self.path] = int(state)
        return self.tstat.state[self.path] 
