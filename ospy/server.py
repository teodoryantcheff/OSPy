#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'Rimco'

import shelve
import web
import os

# Local imports
from ospy.options import options
from ospy.scheduler import scheduler

import plugins

server = None
session = None


class DebugLogMiddleware:
    """WSGI middleware for logging the status."""
    def __init__(self, app):
        self.app = app
        self.format = '%s "%s %s %s" - %s'

    def __call__(self, environ, start_response):
        def xstart_response(status, response_headers, *args):
            out = start_response(status, response_headers, *args)
            self.log(status, environ)
            return out

        return self.app(environ, xstart_response)

    def log(self, status, environ):
        import logging

        req = environ.get('PATH_INFO', '_')
        protocol = environ.get('ACTUAL_SERVER_PROTOCOL', '-')
        method = environ.get('REQUEST_METHOD', '-')
        host = "%s:%s" % (environ.get('REMOTE_ADDR', '-'),
                          environ.get('REMOTE_PORT', '-'))

        msg = self.format % (host, protocol, method, req, status)
        logging.debug(web.utils.safestr(msg))


class PluginStaticMiddleware(web.httpserver.StaticMiddleware):
    """WSGI middleware for serving static plugin files.
    This ensures all URLs starting with /plugins/static/plugin_name are mapped correctly."""

    def __call__(self, environ, start_response):
        upath = environ.get('PATH_INFO', '')
        upath = self.normpath(upath)
        words = upath.split('/')

        if len(words) >= 4 and words[1] == 'plugins' and words[3] == 'static':
            return web.httpserver.StaticApp(environ, start_response)
        else:
            return self.app(environ, start_response)


def start():
    global server
    global session
    from ospy.urls import urls

    ##############################
    #### web.py setup         ####
    ##############################
    web.config.debug = False  # Improves page load speed', ]

    app = web.application(urls, globals())
    app.notfound = lambda: web.seeother('/')

    wsgifunc = app.wsgifunc()
    wsgifunc = web.httpserver.StaticMiddleware(wsgifunc)
    wsgifunc = PluginStaticMiddleware(wsgifunc)
    wsgifunc = DebugLogMiddleware(wsgifunc)
    server = web.httpserver.WSGIServer(("0.0.0.0", options.web_port), wsgifunc)

    sessions = shelve.open(os.path.join('ospy', 'data', 'sessions.db'))
    session = web.session.Session(app, web.session.ShelfStore(sessions),
                                  initializer={'validated': False,
                                               'last_page': '/'})

    scheduler.start()
    plugins.start_enabled_plugins()

    try:
        server.start()
    except (KeyboardInterrupt, SystemExit):
        server.stop()
        sessions.close()
        session = None
        server = None

def stop():
    global server
    if server is not None:
        server.stop()
        server = None