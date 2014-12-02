__author__ = 'teodoryantcheff'

import logging

from stations import _BaseStations

from radio import OSPyRadio


class RadioStations(_BaseStations):
    radio = None

    def __init__(self, *args):

        self.radio = OSPyRadio.get_instance()

        logging.debug('RADIO device reset')
        self.radio.reset_radio()

        # TODO: station mapping config and saving
        self.stations_mapping = [
            # array index = station index
            (0x12345677, 0),
            (0x12345677, 1),
            (0x12345677, 2),
            (0x12345677, 3),

            (0x12345674, 0),
            (0x12345674, 1),
            (0x12345674, 2),
            (0x12345674, 3),
            (0x12345674, 4),
            (0x12345674, 5),
            (0x12345674, 6),
            (0x12345674, 7),
        ]

        # TODO Save mapping and endpoint names
        self.endpoint_names = {
            0x12345677: 'Radio edno da go eba',
            0x12345674: 'Radio dve.. da go eba'
        }

        super(RadioStations, self).__init__(*args)

    def get_endpoint_name(self, address):
        return self.endpoint_names.get(address, '<NO NAME>')

    def set_endpoint_name(self, address, name):
        self.endpoint_names[address] = name

    def get_endoint_mapping(self, index):
        try:
            m = self.stations_mapping[index]
        except:
            m = (0, 0)
        return m

    def set_endoint_mapping(self, index, ep_idx):
        self.stations_mapping[index] = ep_idx

    def _activate(self):
        for index, station in enumerate(self.enabled_stations()):
            ep_address, valve_index = self.get_endoint_mapping(index)
            if station.active:
                self.radio.start_output(ep_address, valve_index)
            else:
                self.radio.stop_output(ep_address, valve_index)

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
