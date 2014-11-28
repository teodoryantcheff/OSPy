__author__ = 'teodoryantcheff'

import logging

from stations import _BaseStations

from radio.radio import SpiRadio, OSPyRadio


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

            (0x12345678, 4),
            (0x12345678, 5),
            (0x12345678, 6),
            (0x12345678, 7),
        ]

        super(RadioStations, self).__init__(*args)

    def _activate(self):
        for index, station in enumerate(self._stations):
            ep_address, valve_index = self.stations_mapping[index]
            if station.active:
                self.radio.start_valve(ep_address, valve_index)
            else:
                self.radio.stop_valve(ep_address, valve_index)

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
