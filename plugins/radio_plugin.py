# coding=utf-8

__author__ = 'teodoryantcheff'

try:
    import simplejson as json
except:
    import json

import web
from webpages import ProtectedPage
from radio import OSPyRadio, Endpoint

NAME = 'Radio'
LINK = 'status_page'

radio = None


################################################################################
# Helper functions:                                                            #
################################################################################
def start():
    global radio
    print ('INIT RADIO from plugin')
    radio = OSPyRadio.get_instance()


def stop():
    pass


################################################################################
# Web pages:                                                                   #
################################################################################
class status_page(ProtectedPage):
    def GET(self):
        endpoints = list(radio.get_endpoints())
        return self.template_render.plugins.radio_plugin(endpoints)


class status_json(ProtectedPage):
    def GET(self):
        endpoints = list(radio.get_endpoints())

        web.header('Access-Control-Allow-Origin', '*')
        web.header('Content-Type', 'application/json')
        return json.dumps(endpoints, default=Endpoint.as_dict)