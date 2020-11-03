#!/usr/bin/env python3
'''
    Shut down bitcoin core.

    Copyright 2019-2020 DeNova
    Last modified: 2020-10-22
'''

import os.path
import sys
import time

import ve
ve.activate(django_app='blockchain_backup')
from django import setup
setup()

from blockchain_backup.bitcoin import utils
from denova.os.command import run
from denova.python.log import get_log

log = get_log()

def main():
    '''
        Systemd shutdown for blockchain_backup.

        >>> main()
        not running
    '''

    if utils.is_bitcoin_core_running():
        log.debug('bitcoin core is running')
        bin_dir = utils.get_bitcoin_bin_dir()
        if bin_dir:
            bitcoin_cli = os.path.join(bin_dir, utils.bitcoin_cli())
            log.debug('stop bitcoin core')
            run(bitcoin_cli, 'stop')

            # bitcoin core returns immediatly after 'stop'
            # but takes a while to shut down
            time.sleep(1)
            if utils.is_bitcoin_core_running():
                log.debug('waiting for bitcoin core to stop')
                while utils.is_bitcoin_core_running():
                    time.sleep(1)

            log.debug('stopped bitcoin core')
            print('stopped bitcoin core')
        else:
            log.debug('unable to find bitcoin core bin dir')
            print('no bitcoin core bin dir')
    else:
        log.debug('bitcoin core is not running')
        print('not running')


if __name__ == "__main__":
    main()
    sys.exit(0)
