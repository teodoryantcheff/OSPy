#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'Rimco'

# System imports
from datetime import datetime
from threading import Timer
import logging
import shelve

import helpers
import traceback

OPTIONS_FILE = './ospy/data/options.db'


class _Options(object):
    # Using an array to preserve order
    OPTIONS = [
        #######################################################################
        # System ##############################################################
        {
            "key": "name",
            "name": "System name",
            "default": "OpenSprinkler Pi",
            "help": "Unique name of this OpenSprinkler system.",
            "category": "System"
        },
        {
            "key": "theme",
            "name": "System theme",
            "default": "basic",
            "options": helpers.themes,
            "help": "Determines the look of the GUI.",
            "category": "System"
        },
        {
            "key": "location",
            "name": "Location",
            "default": "",
            "help": "City name or zip code. Use comma or + in place of space.",
            "category": "System"
        },
        {
            "key": "time_format",
            "name": "24-hour clock",
            "default": True,
            "help": "Display times in 24 hour format (as opposed to AM/PM style.)",
            "category": "System"
        },
        {
            "key": "web_port",
            "name": "HTTP port",
            "default": 8080,
            "help": "HTTP port (effective after reboot.)",
            "category": "System",
            "min": 1,
            "max": 65535
        },
        {
            "key": "enabled_plugins",
            "name": "Enabled plug-ins",
            "default": []
        },
        {
            "key": "plugin_status",
            "name": "Plug-in status",
            "default": {}
        },
        {
            "key": "auto_plugin_update",
            "name": "Automatic plug-in updates",
            "default": True
        },

        #######################################################################
        # Security ############################################################
        {
            "key": "no_password",
            "name": "Disable security",
            "default": False,
            "help": "Allow anonymous users to access the system without a password.",
            "category": "Security"
        },

        #######################################################################
        # Station Handling ####################################################
        {
            "key": "max_usage",
            "name": "Maximum usage",
            "default": 1.0,
            "help": "Determines how schedules of different stations are combined. "
                    "0 is no limit. 1 is sequential in case all stations have a usage of 1.",
            "category": "Station Handling"
        },
        {
            "key": "output_count",
            "name": "Number of outputs",
            "default": 8,
            "help": "The number of outputs available (8 + 8*extensions)",
            "category": "Station Handling",
            "min": 8,
            "max": 1000
        },
        {
            "key": "station_delay",
            "name": "Station delay",
            "default": 0,
            "help": "Station delay time (in seconds), between 0 and 3600.",
            "category": "Station Handling",
            "min": 0,
            "max": 3600
        },

        #######################################################################
        # Configure Master ####################################################
        {
            "key": "master_relay",
            "name": "Activate relay",
            "default": False,
            "help": "Also activate the relay as master output.",
            "category": "Configure Master"
        },
        {
            "key": "master_on_delay",
            "name": "Master on delay",
            "default": 0,
            "help": "Master on delay (in seconds), between -1800 and +1800.",
            "category": "Configure Master",
            "min": -1800,
            "max": +1800
        },
        {
            "key": "master_off_delay",
            "name": "Master off delay",
            "default": 0,
            "help": "Master off delay (in seconds), between -1800 and +1800.",
            "category": "Configure Master",
            "min": -1800,
            "max": +1800
        },

        #######################################################################
        # Rain Sensor #########################################################
        {
            "key": "rain_sensor_enabled",
            "name": "Use rain sensor",
            "default": False,
            "help": "Use rain sensor.",
            "category": "Rain Sensor"
        },
        {
            "key": "rain_sensor_no",
            "name": "Normally open",
            "default": True,
            "help": "Rain sensor default.",
            "category": "Rain Sensor"
        },

        #######################################################################
        # Logging #############################################################
        {
            "key": "run_log",
            "name": "Enable run log",
            "default": False,
            "help": "Log all runs - note that repetitive writing to an SD card can shorten its lifespan.",
            "category": "Logging"
        },
        {
            "key": "run_entries",
            "name": "Max run entries",
            "default": 100,
            "help": "Number of run entries to save to disk, 0=no limit.",
            "category": "Logging",
            "min": 0,
            "max": 1000
        },
        {
            "key": "debug_log",
            "name": "Enable debug log",
            "default": False,
            "help": "Log all internal events (for debugging purposes).",
            "category": "Logging"
        },


        #######################################################################
        # Not in Options page as-is ###########################################
        {
            "key": "scheduler_enabled",
            "name": "Enable scheduler",
            "default": True,
        },
        {
            "key": "manual_mode",
            "name": "Manual operation",
            "default": False,
        },
        {
            "key": "level_adjustment",
            "name": "Level adjustment set by the user (fraction)",
            "default": 1.0,
        },
        {
            "key": "rain_block",
            "name": "Rain block (rain delay) set by the user (datetime)",
            "default": datetime(1970, 1, 1),
        },
        {
            "key": "temp_unit",
            "name": "C/F",
            "default": 'C',
        },

        {
            "key": "password_hash",
            "name": "Current password hash",
            "default": "opendoor",
        },
        {
            "key": "password_salt",
            "name": "Current password salt",
            "default": "",
        },
        {
            "key": "password_time",
            "name": "Current password decryption time",
            "default": 0,
        },
        {
            "key": "logged_runs",
            "name": "The runs that have been logged",
            "default": []
        }
    ]

    def __init__(self):
        self._values = {}
        self._write_timer = None
        self._callbacks = {}
        self._block = []

        for info in self.OPTIONS:
            self._values[info["key"]] = info["default"]

        try:
            db = shelve.open(OPTIONS_FILE)
            self._values.update(db)
            db.close()
        except Exception:
            pass

        if not self.password_salt:  # Password is not hashed yet
            from ospy.helpers import password_salt
            from ospy.helpers import password_hash

            self.password_salt = password_salt()
            self.password_hash = password_hash(self.password_hash, self.password_salt)

    def add_callback(self, key, function):
        if key not in self._callbacks:
            self._callbacks[key] = {
                'last_value': getattr(self, key),
                'functions': []
            }

        if function not in self._callbacks[key]['functions']:
            self._callbacks[key]['functions'].append(function)

    def remove_callback(self, key, function):
        if key in self._callbacks:
            if function in self._callbacks[key]['functions']:
                self._callbacks[key]['functions'].remove(function)

    def __str__(self):
        import pprint

        pp = pprint.PrettyPrinter(indent=2)
        return pp.pformat(self._values)

    def __getattr__(self, item):
        if item.startswith('_'):
            result = super(_Options, self).__getattribute__(item)
        else:
            result = self._values[item]
        return result

    def __setattr__(self, key, value):
        if key.startswith('_'):
            super(_Options, self).__setattr__(key, value)
        else:
            self._values[key] = value

            if key in self._callbacks:
                if value != self._callbacks[key]['last_value']:
                    for cb in self._callbacks[key]['functions']:
                        try:
                            cb(key, self._callbacks[key]['last_value'], value)
                        except Exception:
                            logging.error('Callback failed:\n' + traceback.format_exc())
                    self._callbacks[key]['last_value'] = value

            # Only write after 1 second without any more changes
            if self._write_timer is not None:
                self._write_timer.cancel()
            self._write_timer = Timer(1.0, self._write)
            self._write_timer.start()

    def __delattr__(self, item):
        if item.startswith('_'):
            super(_Options, self).__delattr__(item)
        else:
            del self._values[item]

            # Only write after 1 second without any more changes
            if self._write_timer is not None:
                self._write_timer.cancel()
            self._write_timer = Timer(1.0, self._write)
            self._write_timer.start()

    # Makes it possible to use this class like options[<item>]
    __getitem__ = __getattr__

    # Makes it possible to use this class like options[<item>] = <value>
    __setitem__ = __setattr__

    # Makes it possible to use this class like del options[<item>]
    __delitem__ = __delattr__

    def __contains__(self, item):
        return item in self._values

    def _write(self):
        """This function saves the current data to disk. Use a timer to limit the call rate."""
        db = shelve.open(OPTIONS_FILE)
        db.clear()
        db.update(self._values)
        db.close()

    def get_categories(self):
        result = []
        for info in self.OPTIONS:
            if "category" in info and info["category"] not in result:
                result.append(info["category"])
        return result

    def get_options(self, category=None):
        if category is None:
            result = [opt["key"] for opt in self.OPTIONS]
        else:
            result = []
            for info in self.OPTIONS:
                if "category" in info and info["category"] == category:
                    result.append(info["key"])
        return result

    def get_info(self, option):
        return self.OPTIONS[option]

    @staticmethod
    def cls_name(obj, key=""):
        tpy = (obj if isinstance(obj, type) else type(obj))
        return 'Cls_' + tpy.__module__ + '_' + tpy.__name__ + '_' + str(key).replace(' ', '_')

    def load(self, obj, key=""):
        cls = self.cls_name(obj, key)
        self._block.append(cls)
        try:
            values = getattr(self, cls)
            for name, value in values.iteritems():
                setattr(obj, name, value)
        except KeyError:
            pass
        self._block.remove(cls)

    def save(self, obj, key=""):
        cls = self.cls_name(obj, key)
        if cls not in self._block:
            values = {}
            exclude = obj.SAVE_EXCLUDE if hasattr(obj, 'SAVE_EXCLUDE') else []
            for attr in [att for att in dir(obj) if not att.startswith('_') and att not in exclude]:
                if not hasattr(getattr(obj, attr), '__call__'):
                    values[attr] = getattr(obj, attr)

            setattr(self, cls, values)

    def erase(self, obj, key=""):
        cls = self.cls_name(obj, key)
        if hasattr(self, cls):
            delattr(self, cls)

    def available(self, obj, key=""):
        cls = self.cls_name(obj, key)
        return hasattr(self, cls)

options = _Options()


class _LevelAdjustments(dict):
    def __init__(self):
        super(_LevelAdjustments, self).__init__()

    def total_adjustment(self):
        return max(0.0, min(5.0, reduce(lambda x, y: x * y, self.values(), options.level_adjustment)))

level_adjustments = _LevelAdjustments()


class _RainBlocks(dict):
    def __init__(self):
        super(_RainBlocks, self).__init__()

    def block_end(self):
        return max(self.values() + [options.rain_block])

    def seconds_left(self):
        return max(0, (self.block_end() - datetime.now()).total_seconds())

rain_blocks = _RainBlocks()
