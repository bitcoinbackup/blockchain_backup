#!/usr/bin/env python3
'''
    Start the blockchain backup web server.

    Copyright 2019-2021 DeNova
    Last modified: 2021-07-21
'''

import argparse
import os
from subprocess import CalledProcessError
from time import sleep
from traceback import format_exc


# get the current directory before we enter the virtual environment
CURRENT_DIR = os.path.abspath(os.path.dirname(__file__)).replace('\\','/')
os.chdir(CURRENT_DIR)
from ve import activate
activate(django_app='blockchain_backup')

from django.db.utils import OperationalError

from denova.os.fs import cd
from denova.os.command import run as raw_run
from denova.python.log import Log
import blockchain_backup.settings
from blockchain_backup.settings import PROJECT_PATH

START_COMMAND = 'start'
STOP_COMMAND = 'stop'
STATUS_COMMAND = 'status'
RESTART_COMMAND = 'restart'
ENABLE_COMMAND = 'enable'
DISABLE_COMMAND = 'disable'
DELETE_LOGS_COMMAND = 'rmlogs'

log = Log()


def main(args):
    ''' Start, stop, or restart the denova stack. '''

    try:
        if args.start:
            cmd = START_COMMAND
            start()

        elif args.stop:
            cmd = STOP_COMMAND
            stop()

        elif args.status:
            cmd = STATUS_COMMAND
            status()

        elif args.restart:
            cmd = RESTART_COMMAND
            # don't just use systemctl restart in
            # case use socketio changed
            stop()
            log('restarting the denova stack')
            start()

        elif args.enable:
            cmd = ENABLE_COMMAND
            start()

        elif args.disable:
            cmd = DISABLE_COMMAND
            disable()

        elif args.rmlogs:
            cmd = DELETE_LOGS_COMMAND
            delete_logs()

        else:
            cmd = 'Warning: No start/stop/restart/enable/disable'

    except:
        debug(format_exc())

    else:
        msg = f'finished: {cmd}'
        log(msg)

def start():
    ''' Start the denova stack. '''

    debug('Starting blockchain backup stack')

    delete_logs()

    run('systemctl', 'enable', os.path.join(CURRENT_DIR, 'blockchain-backup-server.service'))
    run('systemctl', 'start', 'blockchain-backup-server')

    # sometimes after blockchain-backup-server.py is done,
    # systemd takes a while longer to stop
    # so you may want to prefix  the next line with 'watch '
    run('systemctl', '--no-pager', 'status', 'blockchain-backup-server')

def stop():
    ''' Stop the blockchain backup stack.

        We do not stop safelog nor safelock
        because other processes use them.
    '''

    run('systemctl', 'stop', 'blockchain-backup-server')

    log("finished stopping blockchain backup stack")

def status():
    ''' Show blockchain backup stack status. '''

    def systemctl_status(args):
        program, service = args

        # check if program is running
        result = run('pgrep', '--full', program)
        running = result is not None and len(result.stdout) > 0

        if running:
            result = run('systemctl', 'status', service)

            loaded = 'Loaded: loaded' in result.stderrout
            active = 'Active: active' in result.stderrout
            if loaded and active:
                debug(f'up: {service}')
            elif loaded:
                debug(f'loaded but not active: {service}')
            elif active:
                debug(f'active but not loaded: {service}')
            else:
                debug(f'{service}:\n{result.stderrout}')

        else:
            debug(f'down: {service}')

    log('Show blockchain backup stack status')

    for program in [('blockchain-backup-server'),]:

        systemctl_status(program)

def disable():
    ''' Disable the blockchain backup stack. '''

    debug("Starting to disable blockchain server")

    stop()

    run('systemctl', 'disable', 'blockchain-backup-server')

    log("finished disabling blockchain backup server" )

def delete_logs():
    ''' Delete logs. '''

    # dir may be empty or non-existent, so no os.path.exists()
    raw_run('rm', '-fr', '/var/local/log/root/blockchain*.log')
    raw_run('rm', '-fr', '/var/local/log/www-data/*')

def run(*args, **kwargs):
    result = None
    try:
        result = raw_run(*args, **kwargs)

    except CalledProcessError as scpe:
        # log(scpe) # DEBUG
        if scpe.stderrout:
            debug(f'error output:\n\t{scpe.stderrout}')
    except:
        # log(format_exc()) # DEBUG
        debug(format_exc())

    # log(f'after "{args}: ', result.stderrout) # DEBUG

    return result

def remove_files(*command_args):
    ''' Remove temporary files. Ignore errors. '''

    args = ['rm']
    for path in command_args:
        args.append(path)
        if path.startswith('-'):
            ok = True
        else:
            if '*' in path:
                ok = True
            elif os.path.exists(path):
                ok = True
            else:
                ok = False

    if ok:
        try:
            raw_run(*args)
        except Exception:
            pass

def debug(message):
    if message:
        print(message)
        log(message)

def parse_args():
    ''' Parsed command line. '''

    global args

    parser = argparse.ArgumentParser(description='Manage blockchain backup stack.')

    parser.add_argument(f'--{START_COMMAND}',
                        help="Start the blockchain backup stack",
                        action='store_true')
    parser.add_argument(f'--{STOP_COMMAND}',
                        help="Stop the blockchain backup stack",
                        action='store_true')
    parser.add_argument(f'--{STATUS_COMMAND}',
                        help="Show blockchain backup stack status",
                        action='store_true')
    parser.add_argument(f'--{RESTART_COMMAND}',
                        help="Stop and start the blockchain backup stack",
                        action='store_true')
    parser.add_argument(f'--{ENABLE_COMMAND}',
                        help="Enable and start the blockchain backup stack",
                        action='store_true')
    parser.add_argument(f'--{DISABLE_COMMAND}',
                        help="Disable the blockchain backup stack service files",
                        action='store_true')
    parser.add_argument(f'--{DELETE_LOGS_COMMAND}',
                        help="Delete logs",
                        action='store_true')
    args = parser.parse_args()

    return args


if __name__ == "__main__":
    args = parse_args()
    main(args)
