#!/usr/bin/env python3
'''
    Upstream server for socketio.

    Copyright 2018-2020 DeNova
    Last modified: 2020-11-04
'''

import argparse
import os
import os.path
import sys
from subprocess import CalledProcessError
from traceback import format_exc

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__)).replace('\\','/')
os.chdir(CURRENT_DIR)
from ve import activate, virtualenv_dir
activate(django_app='blockchain-backup')

from blockchain_backup.settings import LOCAL_HOST, PROJECT_PATH, SOCKETIO_PORT
from denova.os.command import run
from denova.os.fs import cd
from denova.os.user import whoami
from denova.python.log import get_log

log = get_log()

def main(args):
    if args.start:
        start()
    else:
        stop()

def start():
    hostname = LOCAL_HOST
    log(f'hostname: {hostname}')

    bin_dir = os.path.join(virtualenv_dir(), 'bin')

    start_uwsgi_server_for_socketio(bin_dir)

def start_uwsgi_server_for_socketio(bin_dir):
    ''' Start the uwsgi server for socketio connections.'''

    log('starting uwsgi for socketio connections')
    uwsgi_cmd = os.path.join(bin_dir, 'uwsgi')
    if not os.path.exists(uwsgi_cmd):
        uwsgi_cmd = 'uwsgi'
    ini_path = os.path.abspath(os.path.join(PROJECT_PATH, 'config/uwsgi_socketio.ini'))
    args = [uwsgi_cmd, ini_path]
    print(f'args: {args}')

    try:
        run(*args)
        log('uwsgi socketio server started')
    except CalledProcessError as scpe:
        log('uwsgi socketio server threw a CalledProcessError')
        log(scpe.stderr)
        raise
    except Exception as e:
        log('uwsgi socketio server threw an unexpected exception')
        log(e)
        raise
    except: # 'bare except' because it catches more than "except Exception"
        log('uwsgi socketio server threw an unexpected error')
        raise
    log('socketio server started')

def stop():

    log('stopping socketio server')
    try:
        run('fuser', '--kill', f'{SOCKETIO_PORT}/tcp')
    except CalledProcessError as cpe:
        log('socketio server threw a CalledProcessError')
        log(cpe)
        try:
            run('killmatch', 'blockchain-backup-socketio-server')
        except: # 'bare except' because it catches more than "except Exception"
            log(format_exc())
    except Exception as e:
        log('socketio server threw an unexpected exception')
        log(e)
    log('socketio server stopped')

def parse_args():
    ''' Parsed command line. '''

    global args

    parser = argparse.ArgumentParser(description='Manage upstream server for socketio.')

    parser.add_argument('--start',
                        help="Start the server",
                        action='store_true')
    parser.add_argument('--stop',
                        help="Stop the server",
                        action='store_true')

    args = parser.parse_args()

    return args

if __name__ == "__main__":
    args = parse_args()

    main(args)
    sys.exit(0)
