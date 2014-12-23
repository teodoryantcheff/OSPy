# !/usr/bin/env python
# this plugins send and check SMS data for modem to control your OSPy

from threading import Thread, Event
import json
import time
from datetime import datetime
import sys
import traceback

import web
import helpers 
import version
from inputs import inputs
from options import options
from log import log
from plugins import PluginOptions, plugin_url
import plugins
from webpages import ProtectedPage
from helpers import reboot, poweroff


NAME = 'SMS Modem'
LINK = 'settings_page'

sms_options = PluginOptions(
    NAME,
    {
        'tel1': '+xxxyyyyyyyyy',
        'tel2': '+xxxyyyyyyyyy',
        'use_sms': False,
        'txt1': 'info',
        'txt2': 'stop',
        'txt3': 'start',
        'txt4': 'reboot',
        'txt5': 'poweroff',
        'txt6': 'update',
        'txt7': 'foto',
        'txt8': 'help',
        'txt9': 'run'
    }
)

email_options = PluginOptions(
    'Email Notifications',
    {
        'emlsubject': ''
    }
)

# Plugin system will catch the following error and disable the plugin automatically:
import gammu  # for SMS modem import gammu
# if no install modem and gammu visit: http://www.pihrt.com/elektronika/259-moje-rapsberry-pi-sms-ovladani-rpi
# USB modem HUAWEI E303 + SIM card with telephone provider

################################################################################
# Main function loop:                                                          #
################################################################################


class SMSSender(Thread):
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
        once_text = True
        two_text = True

        while True:
            try:
                if sms_options["use_sms"]:  # if use_sms is enable (on)
                    if two_text:
                       log.clear(NAME)
                       log.info(NAME, 'SMS plug-in is enabled')
                       once_text = True
                       two_text = False
                    sms_check(self)  # Check SMS command from modem

                else:
                    if once_text: 
                       log.clear(NAME)
                       log.info(NAME, 'SMS plug-in is disabled')
                       once_text = False
                       two_text = True

                self._sleep(20)

            except Exception:
                err_string = ''.join(traceback.format_exc())
                log.error(NAME, 'SMS control plug-in:\n' + err_string)
                self._sleep(60)


sms_sender = None

################################################################################
# Helper functions:                                                            #
################################################################################
def start():
    global sms_sender
    if sms_sender is None:
        sms_sender = SMSSender()

def stop():
    global sms_sender
    if sms_sender is not None:
        sms_sender.stop()
        sms_sender.join()
        sms_sender = None

def sms_check(self):
    """Control and processing SMS"""
    tel1 = sms_options['tel1']
    tel2 = sms_options['tel2']
    comm1 = sms_options['txt1']
    comm2 = sms_options['txt2']
    comm3 = sms_options['txt3']
    comm4 = sms_options['txt4']
    comm5 = sms_options['txt5']
    comm6 = sms_options['txt6']
    comm7 = sms_options['txt7']
    comm8 = sms_options['txt8']
    comm9 = sms_options['txt9']

    sm = gammu.StateMachine()
    sm.ReadConfig()
    try:
        sm.Init()
        #log.info(NAME, "Checking SMS...")
    except:
        log.debug(NAME, "Error: SMS modem fault")

    status = sm.GetSMSStatus()
    remain = status['SIMUsed'] + status['PhoneUsed'] + status['TemplatesUsed']
    sms = []
    start = True
    while remain > 0:
        if start:
            cursms = sm.GetNextSMS(Start=True, Folder=0)
            start = False
        else:
            cursms = sm.GetNextSMS(Location=cursms[0]['Location'], Folder=0)
        remain = remain - len(cursms)
        sms.append(cursms)
    data = gammu.LinkSMS(sms)
    for x in data:
        v = gammu.DecodeSMS(x)
        m = x[0]
        print '%-15s: %s' % ('Sender', m['Number'])
        print '%-15s: %s' % ('Date', str(m['DateTime']))
        print '%-15s: %s' % ('State', m['State'])
        print '%-15s: %s' % ('SMS command', m['Text'])
        if (m['Number'] == tel1) or (m['Number'] == tel2):  # If telephone is admin 1 or admin 2
            log.info(NAME, time.strftime("%d.%m.%Y at %H:%M:%S", time.localtime(time.time())) + ' SMS from admin')
            if m['State'] == "UnRead":          # If SMS is unread
                log.clear(NAME)
                if m['Text'] == comm1:           # If command = comm1 (info - send SMS to admin phone1 and phone2)
                    log.info(NAME, 'Command ' + comm1 + ' is processed')
                    # send 1/2 SMS with text 1
                    up = helpers.uptime()
                    temp = helpers.get_cpu_temp(options.temp_unit) + ' ' + options.temp_unit
                    ip = str(helpers.get_ip())
                    ver = version.ver_date
                    dat = datetime.now().strftime('Date: %d.%m.%Y')
                    tim = datetime.now().strftime('Time: %H:%M:%S')
                    datastr = ('SMS 1/2. ' + dat + ' '+ tim +  ', TEMP: ' + temp + ', IP: ' + ip + ', SW: ' + ver + ', UP: ' + up  )
                    message = {
                        'Text': datastr,
                        'SMSC': {'Location': 1},
                        'Number': m['Number'],
                    }
                    sm.SendSMS(message) # send sms 1/2
                    log.info(NAME, datastr)
                    # send 2/2 SMS with text 2
                    if inputs.rain_sensed():
                       rain = "Active"
                    else:
                       rain = "Inactive"
                    try:
                       pressure_reader = plugins.get('pressure_monitor')
                       state_press = pressure_reader.get_check_pressure()
                       if state_press:
                          press = "High"
                       else:
                          press = "Low"
                    except Exception:
                       press = "None"
                    finished = [run for run in log.finished_runs() if not run['blocked']]
                    if finished:
                       last_prog = finished[-1]['start'].strftime('%H:%M: ') + finished[-1]['program_name']
                    else:
                       last_prog = 'None'   
                    datastr = ('SMS 2/2. ' + 'RAIN: ' + rain + ', PRESS: ' + press + ', LAST: ' + last_prog)
                    message = {
                        'Text': datastr,
                        'SMSC': {'Location': 1},
                        'Number': m['Number'],
                    }
                    sm.SendSMS(message) # send sms 2/2
                    log.info(NAME, datastr)
                    
                    log.info(NAME, 
                        'Command: ' + comm1 + ' was processed and confirmation was sent as SMS to: ' + m['Number'])
                    log.info(NAME, 'SMS text: ' + datastr)

                    sm.DeleteSMS(m['Folder'], m['Location'])  # SMS deleted
                    log.info(NAME, 'Received SMS was deleted')

                elif m['Text'] == comm2:        # If command = comm2 (stop - scheduler)
                    log.info(NAME, 'Command ' + comm2 + ' is processed')
                    options.scheduler_enabled = False
                    message = {
                        'Text': 'Command: ' + comm2 + ' was processed',
                        'SMSC': {'Location': 1},
                        'Number': m['Number'],
                    }
                    sm.SendSMS(message)
                    log.info(NAME,
                        'Command: ' + comm2 + ' was processed and confirmation was sent as SMS to: ' + m['Number'])
                    sm.DeleteSMS(m['Folder'], m['Location'])
                    log.info(NAME, 'Received SMS was deleted')

                elif m['Text'] == comm3:         # If command = comm3 (start - scheduler)
                    log.info(NAME, 'Command ' + comm3 + ' is processed')
                    options.scheduler_enabled = True
                    message = {
                        'Text': 'Command: ' + comm3 + ' was processed',
                        'SMSC': {'Location': 1},
                        'Number': m['Number'],
                    }
                    sm.SendSMS(message)
                    log.info(NAME,
                        'Command: ' + comm3 + ' was processed and confirmation was sent as SMS to: ' + m['Number'])
                    sm.DeleteSMS(m['Folder'], m['Location'])
                    log.info(NAME, 'Received SMS was deleted')

                elif m['Text'] == comm4:        # If command = comm4 (reboot system)
                    log.info(NAME, 'Command ' + comm4 + ' is processed')
                    message = {
                        'Text': 'Command: ' + comm4 + ' was processed',
                        'SMSC': {'Location': 1},
                        'Number': m['Number'],
                    }
                    sm.SendSMS(message)
                    log.info(NAME,
                        'Command: ' + comm4 + ' was processed and confirmation was sent as SMS to: ' + m['Number'])
                    sm.DeleteSMS(m['Folder'], m['Location'])
                    log.info(NAME, 'Received SMS was deleted and system is now reboot')
                    reboot()                    # restart linux system

                elif m['Text'] == comm5:        # If command = comm5 (poweroff system)
                    log.info(NAME, 'Command ' + comm5 + ' is processed')
                    message = {
                        'Text': 'Command: ' + comm5 + ' was processed',
                        'SMSC': {'Location': 1},
                        'Number': m['Number'],
                    }
                    sm.SendSMS(message)
                    log.info(NAME,
                        'Command: ' + comm5 + ' was processed and confirmation was sent as SMS to: ' + m['Number'])
                    sm.DeleteSMS(m['Folder'], m['Location'])
                    log.info(NAME, 'Received SMS was deleted and system is now poweroff')
                    poweroff()                  # poweroff linux system

                elif m['Text'] == comm6:        # If command = comm6 (update ospi system)
                    log.info(NAME, 'Command ' + comm6 + ' is processed')
                    message = {
                        'Text': 'Command: ' + comm6 + ' was processed',
                        'SMSC': {'Location': 1},
                        'Number': m['Number'],
                    }
                    sm.SendSMS(message)
                    log.info(NAME,
                        'Command: ' + comm6 + ' was processed and confirmation was sent as SMS to: ' + m['Number'])
                    try:
                        from plugins.system_update import perform_update

                        perform_update()
                        log.info(NAME, 'Received SMS was deleted, update was performed and program will restart')
                    except ImportError:
                        log.info(NAME, 'Received SMS was deleted, but could not perform update')

                    sm.DeleteSMS(m['Folder'], m['Location'])

                elif m['Text'] == comm7:        # If command = comm7 (send email with foto from webcam)
                    log.info(NAME, 'Command ' + comm7 + ' is processed')
                    message = {
                        'Text': 'Command: ' + comm7 + ' was processed',
                        'SMSC': {'Location': 1},
                        'Number': m['Number'],
                    }
                    sm.SendSMS(message)
                    log.info(NAME,
                        'Command: ' + comm7 + ' was processed and confirmation was sent as SMS to: ' + m['Number'])
                    try:
                        from webcam import get_run_cam
                        get_run_cam() # process save foto to ./data/image.jpg
                        data_image = './data/image.jpg'
                        msg = ('SMS plug-in send image file from webcam.')

                        subject = email_options['emlsubject']
                        send_email(self, msg, subject, data_image)
                       
                    except ImportError:
                        log.info(NAME, 'Received SMS was deleted, but could not send email with foto from webcam')
                        message = {
                        'Text': 'Error: not send foto from webcam',
                        'SMSC': {'Location': 1},
                        'Number': m['Number'],
                         }
                        sm.SendSMS(message) 
                    sm.DeleteSMS(m['Folder'], m['Location'])
                        
                elif m['Text'] == comm8:        # If command = comm8 (send SMS with available commands)
                    log.info(NAME, 'Command ' + comm8 + ' is processed')
                    message = {
                        'Text': 'Available commands: ' + comm1 + ',' + comm2 + ',' + comm3 + ',' + comm4 + ',' + comm5 + ',' + comm6 + ',' + comm7 + ',' + comm8 + ',' + comm9 + 'xx',
                        'SMSC': {'Location': 1},
                        'Number': m['Number'],
                    }
                    sm.SendSMS(message)
                    log.info(NAME,
                        'Command: ' + comm8 + ' was processed and confirmation was sent as SMS to: ' + m['Number'])
                    sm.DeleteSMS(m['Folder'], m['Location'])
                    log.info(NAME, 'Received SMS was deleted')

                    
                elif m['Text'][0:len(comm9)] == comm9:        # If command = lenght char comm9 (run now program xx)
                    num = m['Text'][len(comm9):]              # number from sms text example: run36 -> num=36
                    log.info(NAME, 'Command ' + comm9 + ' is processed')
                    try:
                        import programs
                        from programs import run_now
                        run_now(self, num) 
                        
                        message = {
                        'Text': 'Program ' + num + ' now run',
                        'SMSC': {'Location': 1},
                        'Number': m['Number'],
                        }
                        
                    except:
                        message = {
                        'Text': 'Program ' + num + ' no exists',
                        'SMSC': {'Location': 1},
                        'Number': m['Number'],
                        }

                    sm.SendSMS(message)
                    log.info(NAME,
                        'Command: ' + comm9 + ' was processed and confirmation was sent as SMS to: ' + m['Number'])
                    sm.DeleteSMS(m['Folder'], m['Location'])
                    log.info(NAME, 'Received SMS was deleted')

                else:                            # If SMS command is not defined
                    sm.DeleteSMS(m['Folder'], m['Location'])
                    log.info(NAME, 'Received command ' + m['Text'] + ' is not defined!')

            else:                                # If SMS was read
                sm.DeleteSMS(m['Folder'], m['Location'])
                log.info(NAME, 'Received SMS was deleted - SMS was read')
        else:                          # If telephone number is not admin 1 or admin 2 phone number
            sm.DeleteSMS(m['Folder'], m['Location'])
            log.info(NAME, 'Received SMS was deleted - SMS was not from admin')

def send_email(self, msg, subject, attachments):
    """Send email"""
    mesage = ('On ' + time.strftime("%d.%m.%Y at %H:%M:%S", time.localtime(
          time.time())) + ' ' + str(msg))
    try:
       from plugins.email_notifications import email
       email(subject, mesage, attachments)    
       log.info(NAME, 'Email was sent: ' + mesage)
    except Exception as err:
       log.info(NAME, 'Email was not sent! ' + str(err))

################################################################################
# Web pages:                                                                   #
################################################################################
class settings_page(ProtectedPage):
    """Load an html page for entering lcd adjustments."""

    def GET(self):
        return self.template_render.plugins.sms_adj(sms_options, log.events(NAME))

    def POST(self):
        sms_options.web_update(web.input())

        sms_sender.update()
        raise web.seeother(plugin_url(settings_page))


class settings_json(ProtectedPage):
    """Returns plugin settings in JSON format."""

    def GET(self):
        web.header('Access-Control-Allow-Origin', '*')
        web.header('Content-Type', 'application/json')
        return json.dumps(sms_options)
        
