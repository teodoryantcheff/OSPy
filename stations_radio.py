__author__ = 'teodoryantcheff'

import logging

from stations import _Station
from stations import _BaseStations

from radio.radio import SpiRadio, OSPyRadio
from radio.radio import Endpoint


class _RadioStation(_Station):
    def __init__(self, *args):
        super(_RadioStation, self).__init__(*args)
        self.endpoint_address = None
        self.endpoint_index = None


class RadioStations(_BaseStations):
    radio = None

    def __init__(self, *args):

        self.radio = OSPyRadio(bus=0, device=0)

        logging.debug('RADIO device reset')
        self.radio.reset_radio()

        super(RadioStations, self).__init__(*args)

    def _activate(self):
        endpoints = self.radio.get_endpoints()
        ep = endpoints[0]
        out_byte = 0
        for station in self._stations:
            if station.active:
                out_byte |= (1 << station.index)
            else:
                out_byte &= ~(1 << station.index)
            self.radio.set_endpoint_outputs(ep.address, out_byte)
            # if station.index < 4:
        print 'activate {} {:#04x}'.format(self._state, out_byte)

    def resize(self, count):
        super(RadioStations, self).resize(count)
        self._activate()

    def activate(self, index):
        super(RadioStations, self).activate(index)
        self._activate()

    def deactivate(self, index):
        super(RadioStations, self).deactivate(index)
        self._activate()

    def clear(self):
        super(RadioStations, self).clear()
        self._activate()
