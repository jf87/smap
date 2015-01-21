from smap import driver, actuate
from smap.util import periodicSequentialCall

class VirtualLight(driver.SmapDriver):
    def setup(self, opts):
        self.state = {'enabled': 0,
                'brightness': 70,
                'power': 0,
                'heat': 0
                }
        self.readperiod = float(opts.get('ReadPeriod',.5))
        self.transition = float(opts.get('TransitionProb', 0.05))


        enabled = self.add_timeseries('/enabled', 'On/Off', data_type='long')
        brightness = self.add_timeseries('/brightness', 'Brightness',
                data_type = 'long')
        power = self.add_timeseries('/power', 'Power Consumption (watt)',
                data_type='long')
        heat = self.add_timeseries('/heat', 'Heat Output (watt)',
                data_type='long')


        self.set_metadata('/', {'Metadata/Device': 'Light',
                                'Metadata/Model': 'Virtual Light',
                                'Metadata/Driver': __name__})

        enabled.add_actuator(OnOffActuator(device=self, path='enabled'))
        brightness.add_actuator(SetpointActuator(device=self, path='brightness',
            _range=(0,100)))
        #power.add_actuator(SetpointActuator(device=self, path='power',
        #    _range=(0,1000)))

        metadata_type = [
                ('/enabled', 'Reading'),
                ('/enabled_act', 'Command'),
                ('/brightness', 'Reading'),
                ('/brightness_act', 'Command'),
                ('/power', 'Reading'),
                ('/heat', 'Reading')
                ]
        for ts, tstype in metadata_type:
            self.set_metadata(ts,{'Metadata/Type':tstype})

    def start(self):
        periodicSequentialCall(self.read).start(self.readperiod)

    def read(self):
        for k,v in self.state.iteritems():
            self.add('/'+k, v)

class VirtualLightActuator(actuate.SmapActuator):
    def __init__(self, **opts):
        self.device = opts.get('device')
        self.path = opts.get('path')

    def get_state(self, request):
        return self.device.state[self.path]

    def evaluate_states(self):
        power = self.device.state['enabled']*self.device.state['brightness']*1.0
        self.device.state['power'] = int(power)
        heat = self.device.state['enabled']*self.device.state['brightness']*0.96
        self.device.state['heat'] = int(heat)

class OnOffActuator(VirtualLightActuator, actuate.BinaryActuator):
    def __init__(self, **opts):
        actuate.BinaryActuator.__init__(self)
        VirtualLightActuator.__init__(self, **opts)

    def set_state(self, request, state):
        self.device.state[self.path] = int(state)
        VirtualLightActuator.evaluate_states(self)
        return self.device.state[self.path]

class SetpointActuator(VirtualLightActuator, actuate.ContinuousIntegerActuator):
    def __init__(self, **opts):
        actuate.ContinuousIntegerActuator.__init__(self, opts['_range'])
        VirtualLightActuator.__init__(self, **opts)

    def set_state(self, request, state):
        self.device.state[self.path] = int(state)
        VirtualLightActuator.evaluate_states(self)
        return self.device.state[self.path]
