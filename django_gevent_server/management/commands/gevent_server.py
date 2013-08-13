# -*- coding: utf-8 -*-
'''
@author: Michael Vorotyntsev
'''

from django.core.management.base import BaseCommand, CommandError
from optparse import make_option


class Command(BaseCommand):
    args = '<start stop ...>'
    help = 'Run web-server on gevent'
    option_list = BaseCommand.option_list + (
        make_option('--port',
            dest='port',
            type='int',
            default=None,
            help='Server listen port'),
        make_option('--ports',
            dest='ports',
            type='str',
            default=None,
            help='Server listen ports, fork process to all'),
        make_option('--host',
            dest='host',
            type='str',
            default=None,
            help='Server listen host'),
        make_option('--name',
            dest='name',
            type='str',
            default=None,
            help='Server process name'),
        )

    def handle(self, *args, **options):
        if 'stop' in args:
            from ...handler import stop_server
            stop_server()
        elif 'start' in args:
            #import os
            #os.environ["GEVENT_RESOLVER"] = "block"
            from ...handler import run_server
            run_server(**options)
        elif 'help' in args:
            print self.help
            print self.args
        else:
            raise CommandError('Unknown command try argument "help"')
