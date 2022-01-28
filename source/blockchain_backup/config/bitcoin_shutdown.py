#!/usr/bin/env python3
'''
    Shut down bitcoin core.

    Copyright 2019-2021 DeNova
    Last modified: 2021-07-14
'''

import os.path
import sys
import time

import ve
ve.activate(django_app='blockchain_backup')
from django import setup
setup()

from blockchain_backup.bitcoin.core_utils import is_bitcoin_core_running, retry_stopping
from blockchain_backup.bitcoin.preferences import get_bitcoin_dirs
from denova.os.command import run
from denova.python.log import Log

log = Log()

def main():
    '''
        Systemd shutdown for blockchain_backup.

        >>> main()
        not running
    '''

    if is_bitcoin_core_running():
        log.debug('bitcoin core is running')
        bin_dir, data_dir = get_bitcoin_dirs()
        if bin_dir and data_dir:
            retry_stopping(bin_dir, data_dir)
            print('stopped bitcoin core')
        else:
            log.debug('unable to find bitcoin core dirs')
            print('no bitcoin core dirs')
    else:
        log.debug('bitcoin core is not running')
        print('not running')


if __name__ == "__main__":
    main()
    sys.exit(0)
