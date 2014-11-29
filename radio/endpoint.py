# coding=utf-8

__author__ = 'teodoryantcheff'

import ctypes
from collections import OrderedDict


class _EndpointBase(ctypes.LittleEndianStructure):
    def __init__(self, radio_instance=None, *args, **kwargs):
        self._radio = radio_instance
        super(_EndpointBase, self).__init__(*args, **kwargs)

    def serialize(self):
        return buffer(self)[:]

    def deserialize(self, data):
        fit = min(len(data), ctypes.sizeof(self))
        ctypes.memmove(ctypes.addressof(self), data, fit)


class Endpoint(_EndpointBase):
    _pack_ = 1
    _fields_ = [
        ('link_id', ctypes.c_ubyte),
        ('address', ctypes.c_uint32),
        ('_link_ok', ctypes.c_ubyte, 1),
        ('_rainsensor', ctypes.c_ubyte, 1),
        # ('__unusedstatusbits', ctypes.c_ubyte, 6),
        ('outputs', ctypes.c_ubyte),
        ('device_type', ctypes.c_ubyte, 4),
        ('valves', ctypes.c_ubyte, 4),
        ('_voltage', ctypes.c_ubyte),
        ('current', ctypes.c_uint16),
        ('temperature', ctypes.c_ubyte),
        ('rssi1', ctypes.c_byte),
        ('rssi2', ctypes.c_byte),
        ('__unused2', ctypes.c_uint16)
    ]

    @property
    def voltage(self):
        return (self._voltage * 128) / 1000.0

    @property
    def link_ok(self):
        return True if self._link_ok else False

    @property
    def rainsensor(self):
        return True if self._rainsensor else False

    def __repr__(self):
        return '{0.__class__.__name__}(' \
               'address={0.address:#010x}, ' \
               'link_id={0.link_id:}, ' \
               'link_ok={0.link_ok:}, ' \
               'rainsensor={0.rainsensor:}, ' \
               'outputs={0.outputs:#04x}, ' \
               'valves={0.valves}, ' \
               'voltage={0.voltage:}, ' \
               'current={0.current:}, ' \
               'temperature={0.temperature:}, ' \
               'rssi1={0.rssi1:}, ' \
               'rssi2={0.rssi2:}' \
               ')'.format(self)

    def as_dict(self):
        d = OrderedDict([(k, getattr(self, k))
                        for k in ['address', 'link_id', 'link_ok', 'rainsensor', 'outputs', 'valves',
                                  'voltage', 'current', 'temperature', 'rssi1', 'rssi2']])
        return d


class EndpointStatusTable(_EndpointBase):
    _pack_ = 1
    _fields_ = [
        ('est', Endpoint * 48)
    ]
