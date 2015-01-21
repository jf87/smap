from smap import driver, actuate
from smap.util import periodicSequentialCall

class VirtualPower(driver.SmapDriver):
    def setup(self, opts):
        self.state = {'power': 0
                }
        self.readperiod = float(opts.get('ReadPeriod',.5))
        self.transition = float(opts.get('TransitionProb', 0.05))


        power = self.add_timeseries('/power', 'Power Consumption (watt)',
                data_type='long')

        self.set_metadata('/', {'Metadata/Device': 'Power',
                                'Metadata/Model': 'Virtual Power',
                                'Metadata/Driver': __name__})

        power.add_actuator(SetpointActuator(device=self, path='power',
            _range=(0,1000)))

        metadata_type = [
                ('/power', 'Reading'),
                ('/power_act', 'Command')
                ]
        for ts, tstype in metadata_type:
            self.set_metadata(ts,{'Metadata/Type':tstype})

    def start(self):
        periodicSequentialCall(self.read).start(self.readperiod)

    def read(self):
        for k,v in self.state.iteritems():
            self.add('/'+k, v)

class VirtualPowerActuator(actuate.SmapActuator):
    def __init__(self, **opts):
        self.device = opts.get('device')
        self.path = opts.get('path')

    def get_state(self, request):
        return self.device.state[self.path]

class OnOffActuator(VirtualPowerActuator, actuate.BinaryActuator):
    def __init__(self, **opts):
        actuate.BinaryActuator.__init__(self)
        VirtualPowerActuator.__init__(self, **opts)

    def set_state(self, request, state):
        self.device.state[self.path] = int(state)
        return self.device.state[self.path]

class SetpointActuator(VirtualPowerActuator, actuate.ContinuousIntegerActuator):
    def __init__(self, **opts):
        actuate.ContinuousIntegerActuator.__init__(self, opts['_range'])
        VirtualPowerActuator.__init__(self, **opts)

    def set_state(self, request, state):
        self.device.state[self.path] = int(state)
        return self.device.state[self.path]

