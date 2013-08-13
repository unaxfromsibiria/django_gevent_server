# -*- coding: utf-8 -*-
'''
@author: Michael Vorotyntsev
'''

import procname
import gevent
import os
import signal
import sys
import socket
import importlib
import logging
from types import ModuleType
from exceptions import BackgroundServerDoesNotExist
from gevent.pywsgi import WSGIServer, WSGIHandler
from django.core.handlers.wsgi import WSGIHandler as DjangoWSGIApp
from gevent.queue import JoinableQueue
from multiprocessing import Process


def import_by_path(path):
    parts = path.split('.')
    endpoint = None
    visited = []
    try:
        for part in parts:
            visited.append(part)
            if endpoint is None:
                endpoint = importlib.import_module(part)
            elif isinstance(endpoint, ModuleType):
                try:
                    endpoint = getattr(endpoint, part)
                except AttributeError:
                    endpoint = importlib.import_module(
                        '.'.join(visited))
            else:
                endpoint = getattr(endpoint, part)
    except (ImportError, AttributeError, AssertionError) as e:
        if isinstance(e, ImportError) and e.args[0] != (
            "No module named " + part):
            raise e
        raise ValueError('.'.join(visited))
    return endpoint


class LoggingWSGIHandler(WSGIHandler):
    def __init__(self, *args, **kwargs):
        WSGIHandler.__init__(self, *args, **kwargs)
        self.logger = logging.getLogger('wsgi')

    def log_request(self):
        if self.time_finish:
            delta = '%.6f' % (self.time_finish - self.time_start)
            length = self.response_length
        else:
            delta = '-'
            if not self.response_length:
                length = '-'
        self.logger.info('{0} "{1}" {2} {3} {4}'.format(
                self.client_address[0],
                self.requestline,
                (getattr(self, 'status', None) or '000').split()[0],
                length,
                delta))


def background_servers(modules_list):
    res = []
    for rpc_server in modules_list:
        copy_count = 1
        if isinstance(rpc_server, tuple):
            rpc_server, copy_count = rpc_server

        try:
            handler = import_by_path(rpc_server)
            assert callable(handler)
        except ValueError as e:
            raise BackgroundServerDoesNotExist(
                "No such path: {0}. Check variable "
                "GEVENT_SERVER['background_server'] in your settings".format(
                    e.args[0]))
        res += [handler] * copy_count
    return res


def run_server(**options):
    logger = logging.getLogger('gevent_server')
    from django.conf import settings
    conf = settings.GEVENT_SERVER
    conf['debug'] = settings.DEBUG

    if options.get('host'):
        conf['host'] = options.get('host')
    if options.get('port'):
        conf['port'] = options.get('port')
    if options.get('ports'):
        conf['ports'] = options.get('ports').split(',')

    if isinstance(options.get('name'), basestring):
        conf['name'] = options.get('name')
    procname.setprocname(str(conf['name']).lower().replace(' ', '_'))
    background_server_methods = []
    if conf.get('background'):
        background_server_methods += background_servers(
            conf.get('background_server'))

    application = DjangoWSGIApp()
    #server.init_socket()
    WORKERS = conf.get('workers')

    if 'ports' in conf:
        ports = list(conf['ports'])
    elif isinstance(WORKERS, int) and WORKERS > 1:
        ports = [conf['port'] + i for i in range(WORKERS)]
    else:
        ports = None

    children = []
    logger.debug('Master process PID {0}'.format(os.getpid()))
    if ports:
        logger.info('Creating {0} fork processes.'.format(len(ports)))
        for i, port in enumerate(ports[1:]):
            uuid = '{0}_{1}'.format(socket.gethostname(), i + 1)
            pid = gevent.fork()
            if not pid:
                break
            logger.debug('Child process PID {0}'.format(pid))
            children.append(pid)
        else:
            port = ports[0]
            uuid = '{0}_0'.format(socket.gethostname())
    else:
        port = conf.get('port')
        uuid = '{0}_0'.format(socket.gethostname())

    def at_exit(signum, frame):
        if signum != signal.SIGINT:
            for child in children:
                os.kill(child, signum)
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, at_exit)
    signal.signal(signal.SIGTERM, at_exit)
    signal.signal(signal.SIGQUIT, at_exit)

    greenlets = JoinableQueue()
    for run_method in background_server_methods:
        logger.debug('Spawning background method {0}'.format(run_method))
        greenlets.put(gevent.spawn(run_method, uuid))
    logger.info('Starting web server http://{0}:{1}'\
                .format(conf.get('host'), port))
    server = WSGIServer(
        (conf['host'], int(port)),
        application,
        handler_class=LoggingWSGIHandler)
    greenlets.put(gevent.spawn(server.serve_forever))
    greenlets.join()


def run_web_server(**options):
    logger = logging.getLogger('gevent_server')
    from django.conf import settings
    conf = settings.GEVENT_SERVER
    conf['debug'] = settings.DEBUG

    if options.get('host'):
        conf['host'] = options.get('host')
    if options.get('ports'):
        conf['ports'] = options.get('ports').split(',')

    if isinstance(options.get('name'), basestring):
        conf['name'] = options.get('name')
    procname.setprocname(str(conf['name']))
    background_server_methods = []
    if conf.get('background'):
        background_server_methods += background_servers(
            conf.get('background_server'))

    if 'ports' in conf:
        ports = list(conf['ports'])

    logger.debug('Master process PID {0}'.format(os.getpid()))
    application = DjangoWSGIApp()

    def create_server(tcp_listener):
        WSGIServer(tcp_listener,
            application, handler_class=LoggingWSGIHandler).serve_forever()

    for port in ports:
        listener = (conf['host'], int(port))
        logger.info('Creating processes at {0}'.format(listener))
        Process(target=create_server, args=(listener,)).start()


def stop_server(**options):
    import psutil
    import __main__ as main
    name = os.path.basename(main.__file__)
    this_pid = os.getpid()
    all_pid = [int(proc.pid)
        for proc in psutil.process_iter()
            if proc.name == name and this_pid != proc.pid]
    logger = logging.getLogger('gevent_server')
    if all_pid:
        logger.info('Kill processes: {0}'.format(
            ', '.join([str(p) for p in all_pid])))
        os.kill(min(all_pid), signal.SIGTERM)
    else:
        logger.warning('Processes "{0}" is exists?'.format(name))
