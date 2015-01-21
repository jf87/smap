from smap import driver, actuate
from smap.util import periodicSequentialCall

class VirtualBrightness(driver.SmapDriver):
    def setup(self, opts):
        self.state = {'brightness': 0
                }
        self.readperiod = float(opts.get('ReadPeriod',.5))
        self.transition = float(opts.get('TransitionProb', 0.05))


        brightness = self.add_timeseries('/brightness', 'Brightness Consumption (watt)',
                data_type='long')

        self.set_metadata('/', {'Metadata/Device': 'Brightness',
                                'Metadata/Model': 'Virtual Brightness',
                                'Metadata/Driver': __name__})

        brightness.add_actuator(SetpointActuator(device=self, path='brightness',
            _range=(0,1000)))

        metadata_type = [
                ('/brightness', 'Reading'),
                ('/brightness_act', 'Command')
                ]
        for ts, tstype in metadata_type:
            self.set_metadata(ts,{'Metadata/Type':tstype})

    def start(self):
        periodicSequentialCall(self.read).start(self.readperiod)

    def read(self):
        for k,v in self.state.iteritems():
            self.add('/'+k, v)

class VirtualBrightnessActuator(actuate.SmapActuator):
    def __init__(self, **opts):
        self.device = opts.get('device')
        self.path = opts.get('path')

    def get_state(self, request):
        return self.device.state[self.path]

class OnOffActuator(VirtualBrightnessActuator, actuate.BinaryActuator):
    def __init__(self, **opts):
        actuate.BinaryActuator.__init__(self)
        VirtualBrightnessActuator.__init__(self, **opts)

    def set_state(self, request, state):
        self.device.state[self.path] = int(state)
        return self.device.state[self.path]

class SetpointActuator(VirtualBrightnessActuator, actuate.ContinuousIntegerActuator):
    def __init__(self, **opts):
        actuate.ContinuousIntegerActuator.__init__(self, opts['_range'])
        VirtualBrightnessActuator.__init__(self, **opts)

    def set_state(self, request, state):
        self.device.state[self.path] = int(state)
        return self.device.state[self.path]


