#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'Rimco'

import logging


class _DummyOutputs(object):
    def __init__(self):
        self.relay_output = False

    def __setattr__(self, key, value):
        super(_DummyOutputs, self).__setattr__(key, value)
        logging.debug("Set %s to %s", key, value)


class _IOOutputs(object):
    def __init__(self):
        self._mapping = {}
        self._initialized = False

    def __setattr__(self, key, value):
        super(_IOOutputs, self).__setattr__(key, value)
        if not self._initialized:
            self._initialized = True
            for pin in self._mapping.values():
                self._io.setup(pin, self._io.OUT)

        if key in self._mapping:
            self._io.output(self._mapping[key], self._io.HIGH if value else self._io.LOW)


class _RPiOutputs(_IOOutputs):
    def __init__(self):
        import RPi.GPIO as GPIO  # RPi hardware

        super(_RPiOutputs, self).__init__()
        self._io = GPIO
        self._io.setwarnings(False)
        self._io.setmode(self._io.BOARD)

        self._mapping = {
            'relay_output': 10
        }


class _BBBOutputs(_IOOutputs):
    def __init__(self):
        import Adafruit_BBIO.GPIO as GPIO  # Beagle Bone Black hardware

        super(_BBBOutputs, self).__init__()
        self._io = GPIO
        self._io.setwarnings(False)

        self._mapping = {
            'relay_output': "P9_16"
        }


try:
    outputs = _RPiOutputs()
except Exception:
    try:
        outputs = _BBBOutputs()
    except Exception:
        outputs = _DummyOutputs()