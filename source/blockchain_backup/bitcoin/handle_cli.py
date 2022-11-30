'''
    Handle bitcoin-cli.

    Copyright 2018-2021 DeNova
    Last modified: 2021-07-17
'''

import json
import os
from datetime import datetime
from subprocess import CalledProcessError
from time import gmtime, sleep

from django.utils.timezone import now, utc

from blockchain_backup.bitcoin import core_utils, state
from blockchain_backup.bitcoin.exception import BitcoinException
from blockchain_backup.bitcoin.preferences import get_extra_args
from denova.os.command import run
from denova.python.log import Log


log = Log()


def get_blockchain_info(bin_dir, data_dir, progress_func=None):
    '''
        Get the blockchain info.

        Args:
            bin_dir:       bitcoin core's bin dir
            data_dir:      bitcoin core's data dir
            progress_func: function to update the progress to the user

        Returns:
            if no response, then returns None; otherwise, returns the blockchain info

        >>> # this test always returns -1 because bitcoin is not running
        >>> # the unittest exercises this code more thoroughly
        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> bin_dir = '/tmp/bitcoin/bin'
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> get_blockchain_info(bin_dir, data_dir)
    '''

    block_info = send_bitcoin_cli_cmd('getblockchaininfo',
                                      bin_dir,
                                      data_dir,
                                      progress_func=progress_func)

    if block_info is None or block_info == -1:
        blockchain_info = None
    else:
        blockchain_info = json.loads(block_info)

    return blockchain_info

def update_latest_state(blockchain_info):
    '''
        Get the current block and update the latest state.

        Args:
            blockchain_info: data from bitcoin cli about the blockchain

        Returns:
            current_block: int of the current block
            remaining_blocks: blocks that still need to be confirmed.
            recent_confirmation: the time of the most recent confirmation

        >>> blockchain_info = {
        ...                    "chain": "main",
        ...                    "blocks": 2,
        ...                    "headers": 0,
        ...                    "mediantime": 1553711097,
        ...                    "warnings": ""
        ...                   }
        >>> update_latest_state(blockchain_info)
        (2, -1, '')
    '''
    remaining_blocks = -1
    recent_confirmation = ''
    new_blocks_found = False

    if 'headers' in blockchain_info:
        last_known_block = int(blockchain_info['headers'])
    else:
        last_known_block = -1

    if 'blocks' in blockchain_info:
        current_block = int(blockchain_info['blocks'])
    else:
        current_block = -1

    if last_known_block > 0:
        previous_known_block = state.get_last_known_block()
        if last_known_block >= previous_known_block:

            state.set_last_known_block(last_known_block)
            new_blocks_found = True

            if 'mediantime' in blockchain_info:
                epoch_time = gmtime(blockchain_info['mediantime'])
                last_block_time = datetime(
                  epoch_time.tm_year, epoch_time.tm_mon, epoch_time.tm_mday,
                  epoch_time.tm_hour, epoch_time.tm_min, epoch_time.tm_sec, tzinfo=utc)

                state.set_last_block_time(last_block_time)
                recent_confirmation = f'{core_utils.get_most_recent_confirmation(last_block_time)} ago'

        remaining_blocks = last_known_block - current_block
        if not new_blocks_found:
            remaining_blocks = -1

    return current_block, remaining_blocks, recent_confirmation

def send_bitcoin_cli_cmd(arg, bin_dir, data_dir, max_attempts=1, progress_func=None):
    '''
        Send a command via bitcoin-cli.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> bin_dir = '/tmp/bitcoin/bin'
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> send_bitcoin_cli_cmd('getblockchaininfo', bin_dir, data_dir)
        -1
    '''

    def wait(arg):
        ONE_MINUTE = 60

        secs = 0
        while ((core_utils.is_bitcoind_running() or
                core_utils.is_bitcoin_qt_running()) and
               secs < ONE_MINUTE):
            sleep(1)
            secs += 1
        log(f'waited {secs} seconds before retrying "{arg}" command')

    command_args = get_bitcoin_cli_cmd(arg, bin_dir, data_dir)

    attempts = 0
    result = -1
    while (attempts < max_attempts and
           result == -1 and
           (core_utils.is_bitcoind_running() or core_utils.is_bitcoin_qt_running())):

        try:
            result = run(*command_args).stdout
            if attempts > 0:
                log(f'resent "{arg}" command {attempts} times')
        except CalledProcessError as cpe:
            attempts += 1
            progress = handle_bitcoin_cli_error(arg, data_dir, cpe)
            if progress is not None and progress_func is not None:
                progress_func(progress)
                log(f'progress: {progress}')

            if attempts < max_attempts:
                wait(arg)

    return result

def get_bitcoin_cli_cmd(arg, bin_dir, data_dir):
    '''
        Get a command for bitcoin-cli.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> bin_dir = '/tmp/bitcoin/bin'
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> get_bitcoin_cli_cmd('getblockchaininfo', bin_dir, data_dir)
        ['/tmp/bitcoin/bin/bitcoin-cli', '-testnet', '-datadir=/tmp/bitcoin/data', 'getblockchaininfo']
    '''

    command_args = []
    if bin_dir is None:
        command_args.append(core_utils.bitcoin_cli())
    else:
        command_args.append(os.path.join(bin_dir, core_utils.bitcoin_cli()))

    use_test_net = '-testnet' in get_extra_args()
    if use_test_net:
        command_args.append('-testnet')

    if data_dir is not None:
        data_dir = core_utils.strip_testnet_from_data_dir(data_dir=data_dir)
        command_args.append(f'-datadir={data_dir}')

    command_args.append(arg)

    return command_args

def handle_bitcoin_cli_error(arg, data_dir, called_process_error):
    '''
        Handle a process error when sending a message to bitcoin core.

        >>> from blockchain_backup.bitcoin.manager import BitcoinManager
        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
        >>> stderr = 'error code: 1\\nerror message:\\nError loading block database.'
        >>> cpe = CalledProcessError(1, 1, stderr=stderr)
        >>> try:
        ...     handle_bitcoin_cli_error('getblockchaininfo', manager.data_dir, cpe)
        ... except BitcoinException as be:
        ...     str(be)
        'Error loading block database.'
        >>> stderr = 'error code: 1\\nerror message:\\nUnknown error'
        >>> cpe = CalledProcessError(1, 1, stderr=stderr)
        >>> handle_bitcoin_cli_error('stop', manager.data_dir, cpe)
        >>> stderr = 'error code: -28\\nerror message:\\nLoading block index...'
        >>> cpe = CalledProcessError(28, 28, stderr=stderr)
        >>> handle_bitcoin_cli_error('getblockchaininfo', manager.data_dir, cpe)
        'Loading block index...'
    '''

    returncode = called_process_error.returncode
    stdout = called_process_error.stdout
    stderr = called_process_error.stderr

    if stdout and not isinstance(stdout, str):
        stdout = stdout.decode()

    if stderr and not isinstance(stderr, str):
        stderr = stderr.decode()

    abort, progress, log_message = process_bitcoin_cli_error(
      arg, data_dir, returncode, stdout, stderr)

    if log_message is not None:
        log(log_message)

    if abort:
        exception_message = log_message
        if exception_message is None:
            exception_message = stderr
        raise BitcoinException(exception_message)

    return progress

def process_bitcoin_cli_error(arg, data_dir, returncode, stdout, stderr):
    '''
        Process an error from bitcoin_cli.

        >>> from blockchain_backup.bitcoin.manager import BitcoinManager
        >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
        >>> arg = 'getblockchaininfo'
        >>> returncode = 28
        >>> stdout = None
        >>> stderr = 'error code: -28\\nerror message:\\nLoading block index...'
        >>> process_bitcoin_cli_error(arg, manager.data_dir, returncode, stdout, stderr)
        (False, 'Loading block index...', None)
        >>> returncode = 1
        >>> stderr = 'error code: 1\\nerror message:\\nerror: Could not locate RPC credentials.'
        >>> process_bitcoin_cli_error(arg, manager.data_dir, returncode, stdout, stderr)
        (False, None, None)
        >>> returncode = 1
        >>> stderr = 'error code: 1\\nerror message:\\nerror: Could not connect to the server 127.0.0.1:8332'
        >>> process_bitcoin_cli_error(arg, manager.data_dir, returncode, stdout, stderr)
        (False, None, None)
        >>> returncode = 4
        >>> stderr = 'error code: 1\\nerror message:\\nerror: Error loading block database.'
        >>> process_bitcoin_cli_error(arg, manager.data_dir, returncode, stdout, stderr)
        (True, 'Error loading block database.', None)
    '''

    log = Log()

    abort = False
    progress = log_message = None

    if not stderr:
        log_message = f'failed with return code: {returncode} stdout: {stdout}'

    elif stderr.find('error code: -28') >= 0:
        abort, progress = core_utils.check_bitcoin_log(data_dir)
        if progress is None:
            progress = strip_stderr(stderr)

    elif returncode == 1:
        if stderr.find('error: Could not locate RPC credentials.') >= 0:
            # this error doesn't appear to do any harm; it just
            # means that we're restricted on what commands we can issue
            # which is fine as we only want to issue general query commands
            # (e.g., getblockcount, getblockinfo)
            pass
        elif stderr.find('error: Could not connect to the server') >= 0:
            # this error just means the app isn't up yet, so we'll try again
            pass
        else:
            # don't report the error if we're just stopping
            if arg == 'stop':
                log_message = 'error while trying to stop bitcoind\n'
                log_message += strip_stderr(stderr)
            elif stderr.find('error code 1 - "EOF reached"') >= 0:
                # don't try again as this is a known serious error
                abort = True
                log_message = strip_stderr(stderr)
            else:
                # we're going to ignore the error and try again
                # if we haven't hit the max retries
                log_message = strip_stderr(stderr)

    elif returncode == 4:
        if stderr:
            DNS_PROBLEMS = 'Temporary failure in name resolution'
            i = stderr.find(DNS_PROBLEMS)
            if i >= 0:
                progress = f'{DNS_PROBLEMS} -- problems with DNS?'
            else:
                progress = strip_stderr(stderr)
        else:
            log_message = f'failed with return code: {returncode} stdout: {stdout}'

    else:
        log_message = f'failed with return code: {returncode} stderr: {stderr}'

    # don't know the return code
    if strip_stderr(stderr).find('Error loading block database.') >= 0:
        abort = True
        log('aborting connection because error loading block database')

    return abort, progress, log_message

def strip_stderr(stderr):
    '''
        String standard error.

        >>> stderr = 'error message: error: Unknown error.'
        >>> strip_stderr(stderr)
        'Unknown error.'
    '''

    ERROR_MESSAGE = 'error message:'
    ERROR = 'error: '

    i = stderr.find(ERROR_MESSAGE)
    if i >= 0:
        stderr = stderr[i + len(ERROR_MESSAGE):].strip()

    i = stderr.find(ERROR)
    if i >= 0:
        progress = stderr[i + len(ERROR):].strip()
    else:
        progress = stderr.strip()

    return progress.strip('\n')
