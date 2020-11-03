#!/usr/bin/env python3
'''
    Startup for blockchain_backup.bitcoin_startup.

    Copyright 2019-2020 DeNova
    Last modified: 2020-10-20
'''

import sys

from denova.python.log import get_log

import ve
ve.activate(django_app='blockchain_backup')
from django import setup
setup()

log = get_log()

def main():
    '''
        Placeholder so systemd doesn't complain about a missing ExecStart.
        We don't want bitcoin-core to always be running. We just
        want to always shut it down when the computer is powered down
        if bitcoin-core was running.

        >>> main()
    '''

    log.debug('start blockchain_backup systemd service')


if __name__ == "__main__":
    main()
    sys.exit(0)
