# coding=utf-8

__author__ = 'teodoryantcheff'


# TODO run under apache
# TODO https
# TODO endpoint names
# TODO fix logging
# TODO Docs and comments
# TODO Mapping config stations to endpoints
# TODO Callbacks on endpoint events
# TODO rainsensor status injection
# TODO multiple rainsensors
# TODO css redo

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