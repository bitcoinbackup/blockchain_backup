#!/usr/bin/env python3
'''
    Copyright 2019-2021 DeNova
    Last modified: 2021-07-11
'''

import argparse
import json
import os
import sys
from datetime import timedelta
from time import sleep
from traceback import format_exc

# we want to be able to run this program from inside or outside the virtualenv
import ve
if not ve.in_virtualenv():
    ve.activate(django_app='blockchain_backup')

try:
    # make sure django's db is ready
    from django import setup
    setup()
except: # 'bare except' because it catches more than "except Exception"
    pass

from django.utils.timezone import now

from denova.net.utils import send_api_request
from denova.python.log import Log

log = Log()

MAX_TRIES = 5

# change IP_ADDRESS and PORT below to the correct info for your proxy
# e.g., '127.0.0.1:8000'
PROXY_TYPE = 'https'
PROXY_DICT = {PROXY_TYPE:'IP_ADDRESS:PORT'}

HOST = 'https://denova.com'
API_URL = 'open/blockchain_backup/api/'
PARAMS = {'action': 'versions', 'api_version': '1.1'}

def main(args):

    if args.reason:
        reason = args.reason
    else:
        reason = None

    check(reason)

def check(reason, max_tries=MAX_TRIES):
    '''
        Check for the updates. If any
        errors happen, retry checks for
        max_tries.

        >>> check('check4updates', max_tries=1)
        True
    '''

    if reason:
        PARAMS['reason'] = reason

    tries = 0
    done = False
    while not done and tries < max_tries:
        try:
            result = send_request(PARAMS)
            if 'versions' in result and result['versions']['ok']:
                done = True
                update_database(result)
            else:
                tries += 1
                log(f'check failed: {result}')
        except json.decoder.JSONDecodeError as jde:
            tries += 1
            log(str(jde))
        except: # 'bare except' because it catches more than "except Exception"
            log(format_exc())
            tries += 1

        if not done and tries < max_tries:
            # give a little more time between each try
            wait_time = 60*15*tries
            log(f'trying again in {15 * tries} minutes')
            sleep(wait_time)

    if tries > max_tries and not done:

        # import late so we can run tests without changing the database
        from blockchain_backup.bitcoin import state

        # set up to retry in another few hour
        state.set_last_update_time(now() - timedelta(hours=20))

    return done

def send_request(params, proxy_dict=None, host=None):
    '''
        Send the request and get the result.

        >>> result = send_request(PARAMS)
        >>> result['versions']['ok']
        True
        >>> result['versions']['message']['blockchain_backup'] is not None
        True
        >>> result['versions']['message']['core'] is not None
        True
    '''
    USER_AGENT = 'Blockchain Backup 1.0'

    if proxy_dict is None:
        proxy_dict = PROXY_DICT
    if host is None:
        host = HOST
    full_api_url = os.path.join(host, API_URL)

    if PROXY_TYPE in proxy_dict and 'IP_ADDRESS:PORT' in proxy_dict[PROXY_TYPE]:
        log('checking for updates')
        content = send_api_request(full_api_url,
                                   params,
                                   user_agent=USER_AGENT)
    else:
        log(f'checking for updates through proxy: {proxy_dict}')
        content = send_api_request(full_api_url,
                                   params,
                                   proxy_dict=proxy_dict,
                                   user_agent=USER_AGENT)

    if content is None or isinstance(content, str):
        log(f'unable to get response from server: "{content}"')
        result = {'versions': {'ok': False}}
    else:
        result = json.loads(content.decode())

    return result

def update_database(result):
    '''
        Update the database.

        >>> result = {'versions': {'ok': True, 'message': {'blockchain_backup': '1.3', 'core': '0.21.0'}}}
        >>> update_database(result)
    '''
    # import late so we can run tests without changing the database
    from blockchain_backup.bitcoin import state

    current_time = now()
    bcb_version = result['versions']['message']['blockchain_backup']

    state.set_last_update_time(current_time)
    state.set_latest_bcb_version(bcb_version)
    log(f'current version: {bcb_version} at {current_time}')

def parse_args():
    ''' Parsed command line. '''

    global args

    parser = argparse.ArgumentParser(description='Check for updates to blockchain_backup and bitcoin core.')

    parser.add_argument('reason',
                        default='check4updates',
                        nargs='?',
                        help="Reason to check for updates")

    args = parser.parse_args()

    return args


if __name__ == "__main__":

    args = parse_args()
    main(args)

    sys.exit(0)
