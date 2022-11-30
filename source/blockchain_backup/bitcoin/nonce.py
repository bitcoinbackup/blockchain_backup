'''
    Create a file to insure requests only come from our server.

    Copyright 2018-2020 DeNova
    Last modified: 2020-12-27
'''

import os
from random import random
from tempfile import gettempdir

from denova.os.command import run
from denova.os.lock import locked
from denova.python.log import Log

NONCE_FILE = os.path.join(gettempdir(), 'blockchain_backup.bitcoin.nonce')

def server_nonce():
    ''' Return saved server nonce.

        To get this nonce, an attacker would have to crack this server,
        or fool the server into sending the nonce.

        >>> nonce = server_nonce()
        >>> nonce is not None
        True
    '''
    if os.path.exists(NONCE_FILE):
        with open(NONCE_FILE) as infile:
            nonce = infile.read()
    else:
        log = Log()
        nonce = str(random())
        with locked():
            with open(NONCE_FILE, 'w') as outfile:
                outfile.write(nonce)
                log(f'server_nonce: {nonce}')
            run(*['chmod', 'g-r,o-r', NONCE_FILE])
            log(f'changed permissions on {NONCE_FILE}')

    return nonce
