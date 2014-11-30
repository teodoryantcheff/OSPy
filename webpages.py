#!/usr/bin/env python
# -*- coding: utf-8 -*-

# System imports
import datetime
import json
import time
import web

# Local imports
from helpers import *
from inputs import inputs
from log import log
from options import level_adjustments
from options import options
from options import rain_blocks
from programs import programs
from programs import ProgramType
from runonce import run_once
from stations import stations
import scheduler
import version
import plugins


class WebPage(object):
    def __init__(self):
        import plugins
        template_globals = {
            'str': str,
            'bool': bool,
            'int': int,
            'eval': eval,
            'round': round,
            'datetime': datetime,
            'json': json,
            'isinstance': isinstance,
            'sorted': sorted,
            'hasattr': hasattr,

            'inputs': inputs,
            'log': log,
            'level_adjustments': level_adjustments,
            'options': options,
            'plugins': plugins,
            'rain_blocks': rain_blocks,
            'stations': stations,
            'programs': programs,
            'run_once': run_once,
            'ProgramType': ProgramType,
            'version': version,
            'long_day': long_day,

            'cpu_temp': get_cpu_temp(),
            'now': time.time() + (datetime.datetime.now() - datetime.datetime.utcnow()).total_seconds()
        }
        self.template_render = web.template.render('templates', globals=template_globals, base='base')


class ProtectedPage(WebPage):
    def __init__(self):
        check_login(True)
        WebPage.__init__(self)


class login_page(WebPage):
    """Login page"""

    def GET(self):
        return self.template_render.login(signin_form())

    def POST(self):
        my_signin = signin_form()

        if not my_signin.validates():
            return self.template_render.login(my_signin)
        else:
            web.config._session.user = 'admin'
            raise web.seeother('/')


class logout_page(WebPage):
    def GET(self):
        web.config._session.user = 'anonymous'
        raise web.seeother('/')


class home_page(ProtectedPage):
    """Open Home page."""

    def GET(self):
        qdict = web.input()
        if 'stop_all' in qdict and qdict['stop_all'] == '1':
            if not options.manual_mode:
                options.scheduler_enabled = False
            log.finish_run(None)
            stations.clear()
            raise web.seeother('/')

        return self.template_render.home()

    def POST(self):
        qdict = web.input()
        if 'scheduler_enabled' in qdict and qdict['scheduler_enabled'] != '':
            options.scheduler_enabled = True if qdict['scheduler_enabled'] == '1' else False
        if 'manual_mode' in qdict and qdict['manual_mode'] != '':
            options.manual_mode = True if qdict['manual_mode'] == '1' else False

        if 'rain_block' in qdict:
            if qdict['rain_block'] != '0' and qdict['rain_block'] != '':
                options.rain_block = datetime.datetime.now() + datetime.timedelta(hours=float(qdict['rain_block']))
            elif qdict['rain_block'] == '0':
                options.rain_block = datetime.datetime.now()

        if 'level_adjustment' in qdict and qdict['level_adjustment'] != '':
            options.level_adjustment = float(qdict['level_adjustment']) / 100

        raise web.seeother('/')  # Send browser back to home page


class programs_page(ProtectedPage):
    """Open programs page."""

    def GET(self):
        qdict = web.input()
        if 'delete' in qdict and qdict['delete'] == '1':
            while programs.count() > 0:
                programs.remove_program(programs.count()-1)
        return self.template_render.programs()


class program_page(ProtectedPage):
    """Open page to allow program modification."""

    def GET(self, index):
        qdict = web.input()
        try:
            index = int(index)
            if 'delete' in qdict and qdict['delete'] == '1':
                programs.remove_program(index)
                raise web.seeother('/programs')
            elif 'runnow' in qdict and qdict['runnow'] == '1':
                programs.run_now(index)
                raise web.seeother('/programs')
            elif 'enable' in qdict:
                programs[index].enabled = (qdict['enable'] == '1')
                raise web.seeother('/programs')
        except ValueError:
            pass

        if isinstance(index, int):
            program = programs.get(index)
        else:
            program = programs.create_program()
            program.set_days_simple(6*60, 30, 30, 0, [])

        return self.template_render.program(program)

    def POST(self, index):
        qdict = web.input()
        try:
            index = int(index)
            program = programs.get(index)
        except ValueError:
            program = programs.create_program()

        qdict['schedule_type'] = int(qdict['schedule_type'])

        program.name = qdict['name']
        program.stations = json.loads(qdict['stations'])
        program.enabled = True if 'enabled' in qdict and qdict['enabled'] == 'on' else False

        simple = [int(qdict['simple_hour']) * 60 + int(qdict['simple_minute']),
                  int(qdict['simple_duration']),
                  int(qdict['simple_pause']),
                  int(qdict['simple_rcount']) if 'simple_repeat' in qdict and qdict['simple_repeat'] == 'on' else 0]

        repeat_start_date = datetime.datetime.combine(datetime.date.today(), datetime.time.min) + \
                            datetime.timedelta(days=int(qdict['interval_delay']))

        if qdict['schedule_type'] == ProgramType.DAYS_SIMPLE:
            program.set_days_simple(*(simple + [
                                    json.loads(qdict['days'])]))

        elif qdict['schedule_type'] == ProgramType.DAYS_ADVANCED:
            program.set_days_advanced(json.loads(qdict['advanced_schedule_data']),
                                      json.loads(qdict['days']))

        elif qdict['schedule_type'] == ProgramType.REPEAT_SIMPLE:
            program.set_repeat_simple(*(simple + [
                                      int(qdict['interval']),
                                      repeat_start_date]))

        elif qdict['schedule_type'] == ProgramType.REPEAT_ADVANCED:
            program.set_repeat_advanced(json.loads(qdict['advanced_schedule_data']),
                                        int(qdict['interval']),
                                        repeat_start_date)

        elif qdict['schedule_type'] == ProgramType.WEEKLY_ADVANCED:
            program.set_weekly_advanced(json.loads(qdict['weekly_schedule_data']))

        elif qdict['schedule_type'] == ProgramType.CUSTOM:
            program.modulo = int(qdict['interval'])*1440
            program.manual = False
            program.start = repeat_start_date
            program.schedule = json.loads(qdict['custom_schedule_data'])

        if program.index < 0:
            programs.add_program(program)

        raise web.seeother('/programs')

class runonce_page(ProtectedPage):
    """Open a page to view and edit a run once program."""

    def GET(self):
        return self.template_render.runonce()

    def POST(self):
        qdict = web.input()
        station_seconds = {}
        for station in stations.enabled_stations():
            mm_str = "mm" + str(station.index)
            ss_str = "ss" + str(station.index)
            if mm_str in qdict and ss_str in qdict:
                seconds = int(qdict[mm_str] or 0) * 60 + int(qdict[ss_str] or 0)
                station_seconds[station.index] = seconds

        run_once.set(station_seconds)
        log.finish_run(None)
        stations.clear()
        raise web.seeother('/runonce')


class log_page(ProtectedPage):
    """View Log"""

    def GET(self):
        return self.template_render.log()

    def POST(self):
        qdict = web.input()
        if 'clear' in qdict:
            log.clear_runs()
        raise web.seeother('/log')


class options_page(ProtectedPage):
    """Open the options page for viewing and editing."""

    def GET(self):
        qdict = web.input()
        errorCode = qdict.get('errorCode', 'none')

        return self.template_render.options(errorCode)

    def POST(self):
        qdict = web.input()

        save_to_options(qdict)

        if 'master' in qdict:
            m = int(qdict['master'])
            if m < 0:
                stations.master = None
            elif m < stations.count():
                stations.master = m

        if 'old_password' in qdict and qdict['old_password'] != "":
            try:
                if test_password(qdict['old_password']):
                    if qdict['new_password'] == "":
                        raise web.seeother('/options?errorCode=pw_blank')
                    elif qdict['new_password'] == qdict['check_password']:
                        options.password_salt = password_salt()  # Make a new salt
                        options.password_hash = password_hash(qdict['new_password'], options.password_salt)
                    else:
                        raise web.seeother('/options?errorCode=pw_mismatch')
                else:
                    raise web.seeother('/options?errorCode=pw_wrong')
            except KeyError:
                pass

        plugins.start_enabled_plugins()

        raise web.seeother('/')


class stations_page(ProtectedPage):
    """Stations page"""

    def GET(self):
        return self.template_render.stations()

    def POST(self):
        qdict = web.input()

        for s in xrange(0, stations.count()):
            stations[s].name = qdict["%d_name" % s]
            stations[s].enabled = True if qdict.get("%d_enabled" % s, 'off') == 'on' else False
            stations[s].ignore_rain = True if qdict.get("%d_ignore_rain" % s, 'off') == 'on' else False
            if stations.master is not None:
                stations[s].activate_master = True if qdict.get("%d_activate_master" % s, 'off') == 'on' else False

        raise web.seeother('/')

################################################################################
# Helpers                                                                      #
################################################################################

class get_set_station_page(ProtectedPage):
    """Return a page containing a number representing the state of a station or all stations if 0 is entered as station number."""

    def GET(self):
        qdict = web.input()

        sid = get_input(qdict, 'sid', 0, int) - 1
        set_to = get_input(qdict, 'set_to', None, int)
        set_time = get_input(qdict, 'set_time', 0, int)

        if set_to is None:
            if sid < 0:
                status = '<!DOCTYPE html>\n'
                status += ''.join(('1' if s.active else '0') for s in stations)
                return status
            elif sid < stations.count():
                status = '<!DOCTYPE html>\n'
                status += '1' if stations.get(sid).active else '0'
                return status
            else:
                return 'Station ' + str(sid+1) + ' not found.'
        elif options.manual_mode:
            if set_to:  # if status is on
                start = datetime.datetime.now()
                new_schedule = {
                    'active': True,
                    'program': -1,
                    'station': sid,
                    'program_name': "Manual",
                    'manual': True,
                    'blocked': False,
                    'start': start,
                    'end': start + datetime.timedelta(days=3650),
                    'uid': '%s-%s-%d' % (str(start), "Manual", sid),
                    'usage': 1.0  # FIXME
                }
                if set_time > 0:  # if an optional duration time is given
                    new_schedule['end'] = datetime.datetime.now() + datetime.timedelta(seconds=set_time)

                log.start_run(new_schedule)
                stations.activate(new_schedule['station'])

            else:  # If status is off
                stations.deactivate(sid)
                active = log.active_runs()
                for interval in active:
                    if interval['station'] == sid:
                        log.finish_run(interval)

            raise web.seeother('/')
        else:
            return 'Manual mode not active.'


class show_revision_page(ProtectedPage):
    """Show revision info to the user. Use: [URL of Pi]/rev."""

    def GET(self):
        revpg = '<!DOCTYPE html>\n'
        revpg += 'Python Interval Program for OpenSprinkler Pi<br/><br/>\n'
        revpg += 'Compatable with OpenSprinkler firmware 1.8.3.<br/><br/>\n'
        revpg += 'Includes plugin architecture\n'
        revpg += 'ospy.py version: v' + version.ver_str + '<br/><br/>\n'
        revpg += 'Updated ' + version.ver_date + '\n'
        return revpg


class toggle_temp_page(ProtectedPage):
    """Change units of Raspi's CPU temperature display on home page."""

    def GET(self):
        qdict = web.input()
        options.temp_unit = "F" if qdict['tunit'] == "C" else "C"
        raise web.seeother(qdict.get('url', '/'))

################################################################################
# APIs                                                                         #
################################################################################

class api_status_json(ProtectedPage):
    """Simple Status API"""

    def GET(self):
        statuslist = []
        for station in stations.get():
            if station.enabled or station.is_master:
                status = {
                    'station': station.index,
                    'status': 'on' if station.active else 'off',
                    'reason': 'master' if station.is_master else '',
                    'master': 1 if station.is_master else 0,
                    'programName': '',
                    'remaining': 0}

                if not station.is_master:
                    if options.manual_mode:
                        status['programName'] = 'Manual Mode'
                    else:
                        if not options.scheduler_enabled:
                            status['reason'] = 'system_off'
                        elif not station.ignore_rain and inputs.rain_sensed():
                            status['reason'] = 'rain_sensed'
                        elif not station.ignore_rain and rain_blocks.seconds_left():
                            status['reason'] = 'rain_delay'
                        else:
                            active = log.active_runs()
                            for interval in active:
                                if not interval['blocked'] and interval['station'] == station.index:
                                    status['programName'] = interval['program_name']

                                    status['status'] = 'on'
                                    status['reason'] = 'program'
                                    status['remaining'] = max(0, (interval['end'] -
                                                                  datetime.datetime.now()).total_seconds())

                statuslist.append(status)

        web.header('Content-Type', 'application/json')
        return json.dumps(statuslist)


class api_log_json(ProtectedPage):
    """Simple Log API"""

    def GET(self):
        qdict = web.input()
        data = []
        if 'date' in qdict:
            # date parameter filters the log values returned; "yyyy-mm-dd" format
            date = datetime.datetime.strptime(qdict['date'], "%Y-%m-%d").date()
            check_start = datetime.datetime.combine(date, datetime.time.min)
            check_end = datetime.datetime.combine(date, datetime.time.max)
            log_start = check_start - datetime.timedelta(days=1)
            log_end = check_end + datetime.timedelta(days=1)

            events = scheduler.combined_schedule(log_start, log_end)
            for interval in events:
                # Return only records that are visible on this day:
                if check_start <= interval['start'] <= check_end or check_start <= interval['end'] <= check_end:
                    data.append(self._convert(interval))

        web.header('Content-Type', 'application/json')
        return json.dumps(data)

    def _convert(self, interval):
            duration = (interval['end'] - interval['start']).total_seconds()
            minutes, seconds = divmod(duration, 60)
            return {
                'program': interval['program'],
                'program_name': interval['program_name'],
                'active': interval['active'],
                'manual': interval.get('manual', False),
                'blocked': interval.get('blocked', False),
                'station': interval['station'],
                'date': interval['start'].strftime("%Y-%m-%d"),
                'start': interval['start'].strftime("%H:%M:%S"),
                'duration': "%02d:%02d" % (minutes, seconds)
            }

class water_log_page(ProtectedPage):
    """Simple Log API"""

    def GET(self):
        events = log.finished_runs() + log.active_runs()

        data = "Date, Start Time, Zone, Duration, Program\n"
        for interval in events:
            # return only records that are visible on this day:
            duration = (interval['end'] - interval['start']).total_seconds()
            minutes, seconds = divmod(duration, 60)

            data += ', '.join([
                interval['start'].strftime("%Y-%m-%d"),
                interval['start'].strftime("%H:%M:%S"),
                str(interval['station']),
                "%02d:%02d" % (minutes, seconds),
                interval['program_name']
            ]) + '\n'

        web.header('Content-Type', 'text/csv')
        return data