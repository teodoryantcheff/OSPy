# coding=utf-8

import ctypes
import logging
import sys
import threading
import time
from array import array
from datetime import datetime

from endpoint import EndpointStatusTable, Endpoint
from utils import guarded

try:
    from spidev import SpiDev
except:
    SpiDev = object

logger = logging.getLogger('radio')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter('%(name)s:%(levelname)s:%(message)s'))
# handler.setFormatter(logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s'))
logger.addHandler(handler)


class SpiRadio(SpiDev):
    """Mega radio connected over SPI

        Source : https://docs.google.com/document/d/1FiQ4Q2LxqjEiFXdZioh2Kb4eAb2XIkMK5a_XP6EbG3w/edit

    """

    _BUS_SPEED = 100000  # Clock data at this rate

    # _BUS_SPEED = 200000  # Clock data at this rate

    def __init__(self, *args, **kwargs):
        super(SpiRadio, self).__init__()

        logger.debug('SpiRadio __init__: speed:{} mode:{}'.format(self.max_speed_hz, self.mode))
        self.open(*args, **kwargs)  # TODO: exception handling if open fails
        self.max_speed_hz = self._BUS_SPEED  # set bus speed
        self.mode = 3  # set Clock Polarity and Phase

        self._status_table_size = None
        self._netconfig_table_size = None
        return

    def reset_device(self):
        logging.debug('reset_device')
        self.writebytes([0x55, 0x02])
        return

    def get_netconfig_size(self):
        # logger.debug('get_netconfig_size')
        self.writebytes([0x55, 0x12])  # Command Get network config table size
        lsb, msb = self.readbytes(2)  # Read lsb, msb of size response
        self._netconfig_table_size = msb * 256 + lsb
        return self._netconfig_table_size

    def get_status_size(self):
        # logger.debug('get_status_size')
        self.writebytes([0x55, 0x10])  # Command Get status table size
        lsb, msb = self.readbytes(2)  # Read lsb, msb of size response
        self._status_table_size = msb * 256 + lsb
        return self._status_table_size

    def get_netconfig(self):
        logger.debug('get_netconfig')
        if not self._netconfig_table_size:
            self.get_netconfig_size()  # How many bytes to read back

        self.writebytes([0x55, 0x0A])  # Command Get network configuration
        return self.readbytes(self._netconfig_table_size)
        # return array.array('B', self.readbytes(to_read))

    def set_netconfig(self, config):
        # logger.debug('set_netconfig')
        self.writebytes([0x55, 0x04])
        self.writebytes(list(bytearray(config)))
        return

    def get_status(self):
        logger.debug('get_status')
        if not self._status_table_size:
            self.get_status_size()  # How many bytes to read back

        self.writebytes([0x55, 0x0C])  # Command Get status
        return self.readbytes(self._status_table_size)
        # return array.array('B', self.readbytes(to_read))

    def set_outputs(self, link_id, output_state):
        """55 06 xx yy	- Write -Command ON/OFF,	yy - битовете за  ON/OFF на крайното у-о
                                    bit = 1 -> ON
                                    bit = 0 -> OFF
                               xx - LinkID  на крайното у-о
        """
        logger.debug('set_outputs: lid: {} output: {:#04x}'.format(link_id, output_state))
        self.writebytes([0x55, 0x06, link_id, output_state])  # Command Set output
        return

    def set_rainsensor(self, link_id, rainsensor_type):
        """55 08 xx yy	- Write -Rain sensor type,	yy - 0000 0000 - no sensor connected
                                  - 0000 0001 - Normal Open type
                                  - 0000 0010 - Normal Closed type
                               xx - LinkID  на крайното у-о
        """
        logger.debug('set_rainsensor: lid: {} type: {:#04x}'.format(link_id, rainsensor_type))
        self.writebytes([0x55, 0x08, link_id, rainsensor_type])  # Command Set output
        return self.readbytes(1)


class OSPyRadio(object):
    ENDPOINT_CACHE_TIME = 1000  # milliseconds
    SETOUTPUT_DEBOUNCE_TIME = 500  # milliseconds

    __instance = None

    @classmethod
    def get_instance(cls):
        if not cls.__instance:
            cls.__instance = OSPyRadio()
        return cls.__instance

    @guarded
    def __init__(self, bus=0, device=0):
        self._radio = SpiRadio(bus=bus, device=device)

        self._endpoints_output_cache = {}
        self._output_timers = {}
        self._last_endpoints_refresh = datetime(1, 1, 1)
        self._endpoints_cache = []

    @guarded
    def reset_radio(self):
        self._radio.reset_device()

    @guarded
    def get_endpoints(self):
        now = datetime.now()
        if (now - self._last_endpoints_refresh).total_seconds() > self.ENDPOINT_CACHE_TIME / 1000.0:
            self._last_endpoints_refresh = now
            status = str(bytearray(self._radio.get_status()))
            est = EndpointStatusTable(self)
            est.deserialize(status)
            self._endpoints_cache = est.est

        return self._endpoints_cache

    @guarded
    def get_netconfig_context(self):
        # Load netconfig from device
        import netconfig

        context = netconfig.persistentContext_t()
        context.unpack(array('B', self._radio.get_netconfig()))
        return context

    @guarded
    def set_endpoint_outputs(self, ep_address, output_state):
        # logger.debug('Setting outputs of {:#010x} to {:#04x}'.format(ep_address, output_state))
        # Find link id for endpoint having ep_address
        link_id = None  # link_id of the endpoint having ep_address
        for ep in self.get_endpoints():
            if ep.address == ep_address:
                link_id = ep.link_id
                break

        if link_id:
            try:
                self._output_timers[link_id].cancel()
            except:
                pass

            self._output_timers[link_id] = threading.Timer(self.SETOUTPUT_DEBOUNCE_TIME / 1000.0,
                                                           self._radio.set_outputs, (link_id, output_state))
            self._output_timers[link_id].start()
        else:
            logger.error('{:#010x} not connected !'.format(ep_address))

    @guarded
    def start_output(self, ep_address, output_num):
        try:
            self._endpoints_output_cache[ep_address] |= (0x01 << output_num)
        except:
            self._endpoints_output_cache[ep_address] = (0x01 << output_num)

        self.set_endpoint_outputs(ep_address, self._endpoints_output_cache[ep_address])

    @guarded
    def stop_output(self, ep_address, output_num):
        try:
            self._endpoints_output_cache[ep_address] &= ~(0x01 << output_num)
        except:
            self._endpoints_output_cache[ep_address] = 0

        self.set_endpoint_outputs(ep_address, self._endpoints_output_cache[ep_address])


def binfmt(data):
    return ' '.join(['0b{:08b}'.format(x) for x in data])


def hexfmt(data):
    return ' '.join(['{:#04x}'.format(x) for x in data])


def test_lowlevel():
    radio = SpiRadio(bus=0, device=0)

    print 'DEVICE RESET'
    radio.reset_device()
    logger.debug('Sleep 2')
    time.sleep(2)

    # print 'nc size:', radio.get_netconfig_size()
    # nc = radio.get_netconfig()
    # with open('./data/netconf.bin', 'w') as nconf:
    #     nconf.write(bytearray(nc))
    # print 'Written to file'

    # logger.debug('waiting 5 to restore net config...')
    # time.sleep(5)
    #
    # with open('./data/netconf.bin', 'rb') as nconf:
    #     radio.set_netconfig(nconf.read())
    #     print 'Network configuration set'
    #     # sys.exit()

    endpoints = []

    try:
        # c = 1
        leds = 0x55
        while True:
            endpoints = radio.get_endpoints()

            print 'Link OK :'
            for e in endpoints:
                if e.link_id > 0:
                    print e

            # print '\n\n'
            #
            # print 'Link __NOT__ OK :'
            # for e in endpoints:
            #     print e if e.link_id <= 0 else ''

            # for e in endpoints:
            #     if e.link_id > 0:
            #         # print 'set_output({}, 0x{:02X})'.format(e.link_id, leds)
            #         radio.set_outputs(e.link_id, leds)
            #
            #         # print 'set_rainsensor_type({}, 0x{:02X})'.format(e.link_id, leds)
            #         radio.set_rainsensor(e.link_id, leds)

            leds = ~leds & 0xFF

            # context = radio.get_NC_context()
            # print 'From Network Config Table'
            # for conInfo in context.connStruct:
            #     if conInfo.peerAddr > 0:
            #         print 'linkID={ci.thisLinkID} address={ci.peerAddr:#010x} {ci.sigInfo}'.format(ci=conInfo)

            # with open('./data/netconf.json', 'wb') as json_file:
            #     json.dump(context.as_dict(), json_file, ensure_ascii=True, sort_keys=True)

            print '\n\n'
            time.sleep(5)  # sleep for 0.1 seconds

    except KeyboardInterrupt:  # Ctrl+C pressed, so.
        pass
    finally:
        for e in (e for e in endpoints if e.link_id > 0):
            radio.set_outputs(e.link_id, 0x00)
            radio.set_rainsensor(e.link_id, 0x00)
        radio.close()  # close the port before exit


def test_higherlevel():
    logger.debug('Init')
    ospy_radio = OSPyRadio.get_instance()
    logger.debug('Reset')
    ospy_radio.reset_radio()
    logger.debug('Endpoints:')
    for e in ospy_radio.get_endpoints():
        if e.link_id:
            print e.as_dict()

    logger.debug('Set outs')
    ospy_radio.set_endpoint_outputs(0x12345677, 0x11)
    ospy_radio.set_endpoint_outputs(0x12345677, 0x22)
    ospy_radio.set_endpoint_outputs(0x12345677, 0x33)
    ospy_radio.set_endpoint_outputs(0x12345677, 0xFF)

    ospy_radio.set_endpoint_outputs(0x12345678, 0x55)
    ospy_radio.set_endpoint_outputs(0x12345679, 0x56)
    ospy_radio.set_endpoint_outputs(0x12345678, 0x57)
    ospy_radio.set_endpoint_outputs(0x12345679, 0x58)
    ospy_radio.set_endpoint_outputs(0x12345678, 0x59)
    ospy_radio.set_endpoint_outputs(0x12345679, 0x5a)

    ospy_radio.set_endpoint_outputs(0x12345677, 0x00)
    # time.sleep(.1)


def ttt():
    # In[7]: %timeit array('B', l[32:48]).tostring()
    # 1000000 loops, best of 3: 1.92 µs per loop
    # In[8]: %timeit str(bytearray(l[32:48]))
    # 100000 loops, best of 3: 2.59 µs per loop

    print 'single:{} array:{}'.format(
        ctypes.sizeof(Endpoint),
        ctypes.sizeof(EndpointStatusTable)
    )

    radio = SpiRadio(bus=0, device=0)
    radio.reset_device()
    radio.set_outputs(1, 0x0a)
    est = EndpointStatusTable(radio)
    status = radio.get_status()
    # arr = array('B', status).tostring()
    arr = str(bytearray(status))
    est.deserialize(arr)
    for ep in est.est:
        if ep.link_id:
            print ep

    radio.close()


if __name__ == '__main__':
    # sys.exit(ttt())
    sys.exit(test_higherlevel())
    # sys.exit(test_lowlevel())
