#!/usr/bin/python
# coding=utf-8


import time
import struct
import sys
import logging
import threading
from functools import wraps
from collections import namedtuple
from array import array


logging.basicConfig(format='%(levelname)s:%(message)s',
                    stream=sys.stderr,
                    level=logging.DEBUG)

from spidev import SpiDev


def debounce(wait_millis):
    """ Decorator that will postpone a functions
        execution until after wait_millis millisecs
        have elapsed since the last time it was invoked. """
    def wrapper(func):
        def debounced(*args, **kwargs):
            def call_func():
                func(*args, **kwargs)

            try:
                debounced.timer.cancel()
            except AttributeError:
                pass
            debounced.timer = threading.Timer(wait_millis / 1000.0, call_func)
            debounced.timer.start()

        return debounced
    return wrapper


def rlocked(func):
    """ Decorator that guards func's reentrancy with a threading.RLock """
    rlock = threading.RLock()

    @wraps(func)
    def wrapper(*args, **kwargs):
        rlock.acquire()
        r = func(*args, **kwargs)
        rlock.release()
        return r

    return wrapper


class Endpoint(namedtuple('Endpoint',
                          'link_id, address, link_ok, valves, acdc_type, rainsensor, short, open, batt, rssi1, rssi2')):
    """Radio endpoint deivce. Encoded as a usable object"""

    struct_format = '<BI7B2b'  # Used in struct.unpack_from
    binary_size = 16           # Size in bytes of the packed structure

    radio_instance = None

    @classmethod
    def make(cls, buf, offset=0, radio_instance=None):
        ep = Endpoint._make(struct.unpack_from(Endpoint.struct_format, buf, offset))
        ep.radio_instance = radio_instance
        return ep

    def __repr__(self):
        return '{0.__class__.__name__}('            \
               'address={0.address:#010x}, '        \
               'link_id={0.link_id:}, '             \
               'link_ok={0.link_ok:#04x}, '         \
               'valves={0.valves}, '                \
               'acdc_type={0.acdc_type:02d}, '      \
               'rainsensor={0.rainsensor:#010b}, '  \
               'short={0.short:#010b}, '            \
               'open={0.open:#04x}, '               \
               'batt={0.batt:#04x}, '               \
               'rssi1={0.rssi1:}, '                 \
               'rssi2={0.rssi2:}'                   \
               ')'.format(self)


class SpiRadio(SpiDev):
    """Mega radio connected over spi

        Source : https://docs.google.com/document/d/1FiQ4Q2LxqjEiFXdZioh2Kb4eAb2XIkMK5a_XP6EbG3w/edit

        1.	55 02		- Write Device RESET. Може да потрябва!

        2.	55 04		- Write network configuration.	Следва запис на  xxx байта

        3.	55 06 xx yy	- Write -Command ON/OFF,	yy - битовете за  ON/OFF на крайното у-о
                                         bit = 1 -> ON
                                         bit = 0 -> OFF
                                    xx - LinkID  на крайното у-о

        4.	55 08 xx yy	- Write -Rain sensor type,	yy - 0000 0000 - no sensor connected
                                       - 0000 0001 - Normal Open type
                                       - 0000 0010 - Normal Closed type
                                    xx - LinkID  на крайното у-о

        5.	55 0A		- Read network configuration. Следва четене на  xxx байта

        6.	55 0C		- Read status. Следва четене на xxx байта - Status_TBL

        7.	55 0E		- Write status. Следва запис на xxx байта - Status_TBL

        8.	55 10		- Read status length xxx. Връща два байта за дължина. 1-LSB, 2-MSB

        9.	55 12		- Read network configuration length xxx.
          Връща два байта за дължина. 1-LSB, 2-MSB


        Status_TBL  48 x 8 bytes = 384,    Pointer is LinkID-1
            byte 0  - LinkID	LinkID
            byte 1  - Dst. Addr MSB , 7x
            byte 2  - Dst. Addr...  , 56
            byte 3  - Dst. Addr...  , 34
            byte 4  - Dst. Addr LSB , 12

            byte 5  - LinkOK	LinkOK	xxxx xxx1 = OK, xxxx xxx0 = No Link
                        става 1 веднага след Link с ED
                        нулира се ако 15 секунди няма запитване за съобщение от този LinkID.
            byte 6  - V_num	брой изходи за управление на вентили
            byte 7  - V_ACDC	тип: 9 - 9VDC, 24 - 24VAC

            byte 8  - RAIN	статус на сензора. 0000 0000 - no rain, 0000 0001 - rain detected.
            byte 9  - SHORT	късо по кой изход 0-7  (1-8), 0- no short, 1- short circuit.
            byte 10 - OPEN	прекъсване по кой изход 0-7  (1-8), 0- no open, 1- open circuit.
            byte 11 - BATT	състояние на батерията ако е тип 9VDC

            byte 12 - Rssi_from_AP	измерен от ED
            byte 13 - Rssi_from_ED	измерен от AP
            byte 14 - 0
            byte 15 - 0
        """

    _BUS_SPEED = 100000  # Clock data at this rate

    # _STATUS_ENTRY_SIZE = 16  # size in bytes of a single status table entry

    def __init__(self, *args, **kwargs):
        super(SpiRadio, self).__init__()

        logging.debug('SpiRadio __init__: speed:{} mode:{}'.format(self.max_speed_hz, self.mode))
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
        #logging.debug('get_netconfig_size')
        self.writebytes([0x55, 0x12])  # Command Get network config table size
        lsb, msb = self.readbytes(2)  # Read lsb, msb of size response
        self._netconfig_table_size = msb * 256 + lsb
        return self._netconfig_table_size

    def get_status_size(self):
        #logging.debug('get_status_size')
        self.writebytes([0x55, 0x10])  # Command Get status table size
        lsb, msb = self.readbytes(2)  # Read lsb, msb of size response
        self._status_table_size = msb * 256 + lsb
        return self._status_table_size

    def get_netconfig(self):
        logging.debug('get_netconfig')
        if not self._netconfig_table_size:
            self.get_netconfig_size()  # How many bytes to read back

        self.writebytes([0x55, 0x0A])  # Command Get network configuration
        return self.readbytes(self._netconfig_table_size)
        # return array.array('B', self.readbytes(to_read))

    def set_netconfig(self, config):
        # logging.debug('set_netconfig')
        self.writebytes([0x55, 0x04])
        self.writebytes(list(bytearray(config)))
        return

    def get_status(self):
        logging.debug('get_status')
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
        logging.debug('set_outputs: lid: {} output: {:#04x}'.format(link_id, output_state))
        self.writebytes([0x55, 0x06, link_id, output_state])  # Command Set output
        return

    def set_rainsensor(self, link_id, rainsensor_type):
        """55 08 xx yy	- Write -Rain sensor type,	yy - 0000 0000 - no sensor connected
                                  - 0000 0001 - Normal Open type
                                  - 0000 0010 - Normal Closed type
                               xx - LinkID  на крайното у-о
        """
        logging.debug('set_rainsensor: lid: {} type: {:#04x}'.format(link_id, rainsensor_type))
        self.writebytes([0x55, 0x08, link_id, rainsensor_type])  # Command Set output
        return self.readbytes(1)


class OSPyRadio(object):
    @rlocked
    def __init__(self, bus=0, device=0):
        self._radio = SpiRadio(bus=bus, device=device)
        self._endpoints_cache = []

    @rlocked
    def reset_radio(self):
        self._radio.reset_device()

    @rlocked
    def get_endpoints(self):
        status = array('B', self._radio.get_status())

        endpoints = []
        for i in xrange(self._radio.get_status_size() / Endpoint.binary_size):  # Read all Status Entries
            endpoint = Endpoint.make(status, i * Endpoint.binary_size, self)
            endpoints.append(endpoint)

        return endpoints

    @rlocked
    def get_netconfig_context(self):
        # Load neconfig from device and print link info
        import structs

        context = structs.persistentContext_t()
        context.unpack(array('B', self._radio.get_netconfig()))
        return context

    @rlocked
    @debounce(500)
    def set_endpoint_outputs(self, ep_address, output_state):
        ep_lid = None  # link_id of the endpoint having ep_address

        for ep in self.get_endpoints():
            if ep.address == ep_address:
                ep_lid = ep.link_id
                break
        if ep_lid:
            print 'setting out state {:#04x} to link_id:{:#04x}'.format(output_state, ep_lid)
            self._radio.set_outputs(ep_lid, output_state)
        else:
            logging.error('{:#10x} not connected !'.format(ep_address))


def binfmt(data):
    return ' '.join(['0b{:08b}'.format(x) for x in data])


def hexfmt(data):
    return ' '.join(['0x{:02X}'.format(x) for x in data])


def test_lowlevel():

    radio = SpiRadio(bus=0, device=0)

    print 'DEVICE RESET'
    radio.reset_device()
    logging.debug('Sleep 2')
    time.sleep(2)

    # print 'nc size:', radio.get_netconfig_size()
    # nc = radio.get_netconfig()
    # with open('./data/netconf.bin', 'w') as nconf:
    #     nconf.write(bytearray(nc))
    # print 'Written to file'

    # logging.debug('waiting 5 to restore net config...')
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
    logging.debug('Init')
    ospy_radio = OSPyRadio()
    logging.debug('Reset')
    ospy_radio.reset_radio()
    logging.debug('Endpoints:')
    for e in ospy_radio.get_endpoints():
        if e.link_id:
            print e

    logging.debug('Set outs')
    ospy_radio.set_endpoint_outputs(0x12345677, 0xAA)
    time.sleep(1)
    ospy_radio.set_endpoint_outputs(0x12345677, 0x55)
    time.sleep(1)
    ospy_radio.set_endpoint_outputs(0x12345677, 0x00)


if __name__ == '__main__':
    sys.exit(test_higherlevel())
    # sys.exit(test_lowlevel())
