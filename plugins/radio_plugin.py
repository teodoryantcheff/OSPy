from radio.radio import OSPyRadio

__author__ = 'Jailbreaker'

from webpages import ProtectedPage


NAME = 'Radio'
LINK = 'status_page'


################################################################################
# Helper functions:                                                            #
################################################################################
def start():
    pass


def stop():
    pass


################################################################################
# Web pages:                                                                   #
################################################################################
class status_page(ProtectedPage):
    radio = OSPyRadio.get_instance()

    def GET(self):
        endpoints = list(self.radio.get_endpoints())
        return self.template_render.plugins.radio_plugin(endpoints)