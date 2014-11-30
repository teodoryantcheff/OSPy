# !/usr/bin/env python


import datetime
from threading import Thread, Event
import traceback
import shutil
import json
import time
import re
import os
import urllib
import urllib2

import web
from log import log
from options import options
from options import level_adjustments
from helpers import mkdir_p
from webpages import ProtectedPage
from plugins import PluginOptions, plugin_url

NAME = 'Weather-based Water Level'
LINK = 'settings_page'


plugin_options = PluginOptions(
    NAME,
    {
        'enabled': False,
        'wl_min': 0,
        'wl_max': 200,
        'days_history': 3,
        'days_forecast': 3,
        'wapikey': ''
    })


################################################################################
# Main function loop:                                                          #
################################################################################
class WeatherLevelChecker(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self._stop = Event()

        self._sleep_time = 0
        self.start()

    def stop(self):
        self._stop.set()

    def update(self):
        self._sleep_time = 0

    def _sleep(self, secs):
        self._sleep_time = secs
        while self._sleep_time > 0 and not self._stop.is_set():
            time.sleep(1)
            self._sleep_time -= 1

    def run(self):
        while not self._stop.is_set():
            try:
                log.clear(NAME)
                if not plugin_options['enabled']:
                    if NAME in level_adjustments:
                        del level_adjustments[NAME]
                    self._sleep(5)
                else:
                    log.debug(NAME, "Checking weather status...")
                    remove_data(['history_', 'conditions_', 'forecast10day_'])

                    history = history_info()
                    forecast = forecast_info()
                    today = today_info()

                    info = {}

                    for day in range(-20, 20):
                        if day in history:
                            day_info = history[day]
                        elif day in forecast:
                            day_info = forecast[day]
                        else:
                            continue

                        info[day] = day_info

                    if 0 in info and 'rain_mm' in today:
                        day_time = datetime.datetime.now().time()
                        day_left = 1.0 - (day_time.hour * 60 + day_time.minute) / 24.0 / 60
                        info[0]['rain_mm'] = info[0]['rain_mm'] * day_left + today['rain_mm']

                    if not info:
                        log.info(NAME, str(history))
                        log.info(NAME, str(today))
                        log.info(NAME, str(forecast))
                        raise Exception('No information available!')

                    log.info(NAME, 'Using %d days of information.' % len(info))

                    total_info = {
                        'temp_c': sum([val['temp_c'] for val in info.values()])/len(info),
                        'rain_mm': sum([val['rain_mm'] for val in info.values()]),
                        'wind_ms': sum([val['wind_ms'] for val in info.values()])/len(info),
                        'humidity': sum([val['humidity'] for val in info.values()])/len(info)
                    }

                    # We assume that the default 100% provides 4mm water per day (normal need)
                    # We calculate what we will need to provide using the mean data of X days around today

                    water_needed = 4 * len(info)                                # 4mm per day
                    water_needed *= 1 + (total_info['temp_c'] - 20) / 15        # 5 => 0%, 35 => 200%
                    water_needed *= 1 + (total_info['wind_ms'] / 100)           # 0 => 100%, 20 => 120%
                    water_needed *= 1 - (total_info['humidity'] - 50) / 200     # 0 => 125%, 100 => 75%
                    water_needed = round(water_needed, 1)

                    water_left = water_needed - total_info['rain_mm']
                    water_left = round(max(0, min(100, water_left)), 1)

                    water_adjustment = round((water_left / (4 * len(info))) * 100, 1)

                    water_adjustment = float(max(plugin_options['wl_min'], min(plugin_options['wl_max'], water_adjustment)))

                    log.info(NAME, 'Water needed (%d days): %.1fmm' % (len(info), water_needed))
                    log.info(NAME, 'Total rainfall       : %.1fmm' % total_info['rain_mm'])
                    log.info(NAME, '_______________________________-')
                    log.info(NAME, 'Irrigation needed    : %.1fmm' % water_left)
                    log.info(NAME, 'Weather Adjustment   : %.1f%%' % water_adjustment)

                    level_adjustments[NAME] = water_adjustment/100

                    self._sleep(3600)

            except Exception:
                err_string = ''.join(traceback.format_exc())
                log.error(NAME, 'Weather-based water level plug-in:\n' + err_string)
                self._sleep(60)

checker = None


################################################################################
# Helper functions:                                                            #
################################################################################
# Resolve location to LID
def get_wunderground_lid():
    if re.search("pws:", options.location):
        lid = options.location
    else:
        data = urllib2.urlopen("http://autocomplete.wunderground.com/aq?h=0&query="+urllib.quote_plus(options.location))
        data = json.load(data)
        if data is None:
            return ""
        lid = "zmw:" + data['RESULTS'][0]['zmw']

    return lid


def get_data(suffix, name=None, force=False):
    if name is None:
        name = suffix
    path = os.path.join('.', 'data', 'weather_level_history', name)
    directory = os.path.dirname(path)
    mkdir_p(directory)
    try_nr = 1
    data = {}
    while try_nr <= 2:
        try:
            if not os.path.exists(path) or force:
                with open(path, 'wb') as fh:
                    req = urllib2.urlopen("http://api.wunderground.com/api/"+plugin_options['wapikey']+"/" + suffix)
                    while True:
                        chunk = req.read(20480)
                        if not chunk:
                            break
                        fh.write(chunk)

            try:
                with file(path, 'r') as fh:
                    data = json.load(fh)
            except ValueError:
                raise Exception('Failed to read ' + path + '.')

            if data is not None:
                if 'error' in data['response']:
                    raise Exception(path + ': ' + str(data['response']['error']))
            else:
                raise Exception('JSON decoding failed.')

        except Exception as err:
            if try_nr < 2:
                log.debug(str(err), 'Retrying.')
                os.remove(path)
            else:
                raise
        try_nr += 1

    return data


def remove_data(prefixes):
    # Delete old files
    for prefix in prefixes:
        check_date = datetime.date.today()
        start_delta = datetime.timedelta(days=14)
        day_delta = datetime.timedelta(days=1)
        check_date -= start_delta
        for index in range(60):
            datestring = check_date.strftime('%Y%m%d')
            path = os.path.join('.', 'data', 'weather_level_history', prefix + datestring)
            if os.path.isdir(path):
                shutil.rmtree(path)
            check_date -= day_delta


################################################################################
# Info queries:                                                                #
################################################################################
def history_info():
    if plugin_options['days_history'] == 0:
        return {}

    lid = get_wunderground_lid()
    if lid == "":
        raise Exception('No Location ID found!')

    check_date = datetime.date.today()
    day_delta = datetime.timedelta(days=1)

    info = {}
    for index in range(-1, -1 - plugin_options['days_history'], -1):
        check_date -= day_delta
        datestring = check_date.strftime('%Y%m%d')
        request = "history_"+datestring+"/q/"+lid+".json"

        data = get_data(request)

        if data and len(data['history']['dailysummary']) > 0:
            info[index] = data['history']['dailysummary'][0]

    result = {}
    for index, day_info in info.iteritems():
        result[index] = {
            'temp_c': float(day_info['maxtempm']),
            'rain_mm': float(day_info['precipm']),
            'wind_ms': float(day_info['meanwindspdm']) / 3.6,
            'humidity': float(day_info['humidity'])
        }

    return result


def today_info():
    lid = get_wunderground_lid()
    if lid == "":
        raise Exception('No Location ID found!')

    datestring = datetime.date.today().strftime('%Y%m%d')

    request = "conditions/q/"+lid+".json"
    name = "conditions_"+datestring+"/q/"+lid+".json"
    data = get_data(request, name, True)

    day_info = data['current_observation']

    result = {
        'temp_c': float(day_info['temp_c']),
        'rain_mm': float(day_info['precip_today_metric']),
        'wind_ms': float(day_info['wind_kph']) / 3.6,
        'humidity': float(day_info['relative_humidity'].replace('%', ''))
    }

    return result


def forecast_info():
    lid = get_wunderground_lid()
    if lid == "":
        raise Exception('No Location ID found!')

    datestring = datetime.date.today().strftime('%Y%m%d')

    request = "forecast10day/q/"+lid+".json"
    name = "forecast10day_"+datestring+"/q/"+lid+".json"
    data = get_data(request, name)

    info = {}
    for day_index, entry in enumerate(data['forecast']['simpleforecast']['forecastday']):
        info[day_index] = entry

    result = {}
    for index, day_info in info.iteritems():
        if index <= plugin_options['days_forecast']:
            if day_info['qpf_allday']['mm'] is None:
                day_info['qpf_allday']['mm'] = 0
            result[index] = {
                'temp_c': float(day_info['high']['celsius']),
                'rain_mm': float(day_info['qpf_allday']['mm']),
                'wind_ms': float(day_info['avewind']['kph']) / 3.6,
                'humidity': float(day_info['avehumidity'])
            }

    return result


def start():
    global checker
    if checker is None:
        checker = WeatherLevelChecker()


def stop():
    global checker
    if checker is not None:
        checker.stop()
        checker.join()
        checker = None
    if NAME in level_adjustments:
        del level_adjustments[NAME]


################################################################################
# Web pages:                                                                   #
################################################################################
class settings_page(ProtectedPage):
    """Load an html page for entering weather-based irrigation adjustments"""

    def GET(self):
        return self.template_render.plugins.weather_based_water_level(plugin_options, log.events(NAME))

    def POST(self):
        plugin_options.web_update(web.input())
        if checker is not None:
            checker.update()
        raise web.seeother(plugin_url(settings_page))


class settings_json(ProtectedPage):
    """Returns plugin settings in JSON format"""

    def GET(self):
        web.header('Access-Control-Allow-Origin', '*')
        web.header('Content-Type', 'application/json')
        return json.dumps(plugin_options)
