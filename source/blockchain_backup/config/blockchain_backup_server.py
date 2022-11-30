#!/usr/bin/env python3
'''
    Upstream server for django.

    Copyright 2018-2022 DeNova
    Last modified: 2022-08-21
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

from blockchain_backup.bitcoin.nonce import NONCE_FILE
from blockchain_backup.settings import DJANGO_PORT, PROJECT_PATH, TOP_LEVEL_DOMAIN
from denova.os.command import run
from denova.python.log import Log

log = Log()

USE_GUNICORN = False

def main(args):
    if args.start:
        start()
    else:
        stop()

def start():
    try:
        if os.path.exists(NONCE_FILE):
            os.remove(NONCE_FILE)

        bin_dir = os.path.join(virtualenv_dir(), 'bin')

        if USE_GUNICORN:
            python_cmd = os.path.join(bin_dir, 'python3')
            start_gunicorn_server_for_django(bin_dir, python_cmd)
        else:
            start_uwsgi_server_for_django(bin_dir)
    except: # 'bare except' because it catches more than "except Exception"
        error = format_exc()
        log(error)
        sys.exit(error)

def start_gunicorn_server_for_django(bin_dir, python_cmd):
    ''' Start the gunicorn server for django connections.'''

    log('starting django webserver')

    try:
        GUNICORN_CONFIG_PATH = os.path.abspath(os.path.join(CURRENT_DIR, 'gunicorn.conf.py'))

        log('starting gunicorn for django connections')
        gunicorn_cmd = os.path.join(bin_dir, 'gunicorn')
        args = []
        args.append(python_cmd)
        args.append(gunicorn_cmd)
        args.append('--config')
        args.append(GUNICORN_CONFIG_PATH)
        args.append(f'{TOP_LEVEL_DOMAIN}.wsgi_django:application')
        try:
            run(*args)
            log(f'started gunicorn for {TOP_LEVEL_DOMAIN}')
        except CalledProcessError as scpe:
            log('gunicorn threw a CalledProcessError while starting')
            log(scpe.stderr)
            raise
        except Exception as e:
            log('gunicorn threw an unexpected exception while starting')
            log(e)
            raise

    except: # 'bare except' because it catches more than "except Exception"
        error = format_exc()
        log(error)
        sys.exit(error)

def start_uwsgi_server_for_django(bin_dir):
    ''' Start the uwsgi server for django connections.'''

    log('starting uwsgi for django connections')
    uwsgi_cmd = os.path.join(bin_dir, 'uwsgi')
    ini_path = os.path.abspath(os.path.join(PROJECT_PATH, 'config/uwsgi_django.ini'))
    log(f'ini path: {ini_path}')
    args = [uwsgi_cmd, ini_path]

    try:
        run(*args)
        log('uwsgi django server started')
    except CalledProcessError as scpe:
        log('uwsgi django server threw a CalledProcessError while starting')
        log(scpe.stdout)
        log(scpe.stderr)
        log(scpe)
        raise
    except Exception as e:
        log('uwsgi django server threw an unexpected exception while starting')
        log(e)
        raise

def stop():
    log('stopping django server')

    # make sure bitcoind is shutdown before we shut down this server
    stop_bitcoind()

    try:
        run(*['fuser', '--kill', f'{DJANGO_PORT}/tcp'])
    except CalledProcessError as scpe:
        log('django server threw a CalledProcessError while stopping')
        log(scpe)
        run(*['killmatch', 'blockchain-backup-server'])
    except FileNotFoundError:
        log('unable to kill job because "fuser" not installed')
    except Exception as e:
        log('django servers threw an unexpected exception while stopping')
        log(e)
    log('django server stopped')

def stop_bitcoind():
    ''' Stop bitcoind if it's running. '''

    log('stopping bitcoind')

    bin_dir = os.path.join(virtualenv_dir(), 'bin')

    try:
        SHUTDOWN_PATH = os.path.abspath(os.path.join(CURRENT_DIR, 'bitcoin_shutdown.py'))

        python_cmd = os.path.join(bin_dir, 'python')
        args = []
        args.append(python_cmd)
        args.append(SHUTDOWN_PATH)
        try:
            run(*args)
        except CalledProcessError as scpe:
            log(scpe.stderr)
        except Exception as e:
            log(e)

    except: # 'bare except' because it catches more than "except Exception"
        error = format_exc()
        log(error)

    log('bitcoind stopped')


def parse_args():
    ''' Parsed command line. '''

    global args

    parser = argparse.ArgumentParser(description='Manage upstream server for django.')

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
