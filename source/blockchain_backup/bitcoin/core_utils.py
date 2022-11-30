'''
    Utilities for bitcoin core.

    Copyright 2018-2021 DeNova
    Last modified: 2021-07-16
'''

import os
import re
import shutil
from subprocess import Popen
from time import sleep
from traceback import format_exc

from blockchain_backup.bitcoin import constants, state
from blockchain_backup.bitcoin.exception import BitcoinException
from blockchain_backup.bitcoin.preferences import get_bin_dir, get_data_dir, get_extra_args
from blockchain_backup.bitcoin.handle_cli import send_bitcoin_cli_cmd
from denova.os.command import run
from denova.os.osid import is_windows
from denova.os.process import get_path, get_pid, is_program_running
from denova.python.log import Log
from denova.python.times import now, seconds_human_readable

log = Log()

def bitcoin_qt():
    '''
        Name of bitcoin-qt program.

        >>> bitcoin_qt()
        'bitcoin-qt'
    '''

    program = 'bitcoin-qt'

    if is_windows():
        program += '.exe'

    return program

def bitcoin_cli():
    '''
        Name of bitcoin-cli program.

        >>> bitcoin_cli()
        'bitcoin-cli'
    '''

    program = 'bitcoin-cli'

    if is_windows():
        program += '.exe'

    return program

def bitcoind():
    '''
        Name of bitcoind program.

        >>> bitcoind()
        'bitcoind'
    '''

    program = 'bitcoind'

    if is_windows():
        program += '.exe'

    return program

def bitcoin_tx():
    '''
        Name of bitcoin-tx program.

        >>> bitcoin_tx()
        'bitcoin-tx'
    '''

    program = 'bitcoin-tx'

    if is_windows():
        program += '.exe'

    return program

def is_bitcoind_running():
    '''
        Return True if program is running.

        >>> is_bitcoind_running()
        False
    '''

    return is_program_running(bitcoind())

def is_bitcoin_qt_running():
    '''
        Return True if program is running.

        >>> is_bitcoin_qt_running()
        False
    '''

    return is_program_running(bitcoin_qt())

def is_bitcoin_tx_running():
    '''
        Return True if program is running.

        >>> is_bitcoin_tx_running()
        False
    '''

    return is_program_running(bitcoin_tx())

def is_bitcoin_core_running():
    '''
        Return True if any of the
        bitcoin core programs are running.

        >>> is_bitcoin_core_running()
        False
    '''

    return (is_bitcoind_running() or is_bitcoin_qt_running() or is_bitcoin_tx_running())

def start_bitcoind(bin_dir, data_dir):
    '''
        Start bitcoind as a daemon.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> bin_dir = '/tmp/bitcoin/bin'
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> bitcoind_process, bitcoind_pid = start_bitcoind(bin_dir, data_dir)
        >>> stop_bitcoind(bitcoind_process, bitcoind_pid, bin_dir, data_dir)
        (True, None)
    '''

    if is_bitcoind_running():
        bitcoind_process = None
        bitcoind_pid = get_pid(bitcoind())
        if bitcoind_pid is None:
            ##sleep(5)
            bitcoind_pid = get_pid(bitcoind())
        log(f'bitcoind is already running using pid: {bitcoind_pid}')
    else:
        bitcoind_pid = None
        command_args = []

        if bin_dir is None:
            command_args.append(bitcoind())
            ok = True
        else:
            cmd = os.path.join(bin_dir, bitcoind())
            command_args.append(cmd)
            ok = os.path.exists(cmd)

        if ok:
            extra_args = get_extra_args()
            use_test_net = '-testnet' in extra_args

            if data_dir is not None:
                if use_test_net and data_dir.endswith(constants.TEST_NET_SUBDIR):
                    data_dir = data_dir[:data_dir.rfind(constants.TEST_NET_SUBDIR)]
                command_args.append(f'-datadir={data_dir}')

            # don't allow any interaction with the user's wallet
            command_args.append('-disablewallet')

            if extra_args:
                for extra_arg in extra_args:
                    command_args.append(extra_arg)

            command_args.append('-daemon')

            try:
                bitcoind_process = Popen(command_args)
                log(f'bitcoind started: {bitcoind_process is not None}')
            except FileNotFoundError as fnfe:
                raise BitcoinException(str(fnfe))

        else:
            bitcoind_process = None
            log(f'{bitcoind()} does not exist in {bin_dir}')

    state.set_start_access_time(now())

    return bitcoind_process, bitcoind_pid

def stop_bitcoind(bitcoind_process, bitcoind_pid, bin_dir, data_dir, update_progress=None):
    '''
        Stop bitcoind and determine if it ended properly.

        Returns:
            True if shutdown successful; otherwise False.
            Any error message or None.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> bin_dir = '/tmp/bitcoin/bin'
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> bitcoind_process, bitcoind_pid = start_bitcoind(bin_dir, data_dir)
        >>> ok, error_message = stop_bitcoind(bitcoind_process, bitcoind_pid, bin_dir, data_dir)
        >>> ok == True
        True
        >>> error_message == None
        True
    '''

    wait_for_shutdown(bitcoind_process, bitcoind_pid, bin_dir, data_dir)

    retry_stopping(bin_dir, data_dir, update_progress)

    if update_progress:
        update_progress(constants.STOPPING_UPDATE)

    ok, error_message, seconds = wait_for_status(data_dir)

    if update_progress:
        update_progress(constants.STOPPING_UPDATE)

    if not ok:
        report_shutdown_error(bitcoind_process,
                              bitcoind_pid,
                              error_message,
                              seconds,
                              update_progress=update_progress)

    if error_message is not None:
        ok = False

    state.set_last_access_time(now())

    log(f'end wait_for_bitcoin: ok: {ok} error: {error_message} bitcoin running: {is_bitcoind_running()}')

    return ok, error_message

def wait_for_shutdown(bitcoind_process, bitcoind_pid, bin_dir, data_dir):
    '''
        Wait for bitcoind to shutdown.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> bin_dir = '/tmp/bitcoin/'
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> bitcoind_process, bitcoind_pid = start_bitcoind(bin_dir, data_dir)
        >>> wait_for_shutdown(bitcoind_process, bitcoind_pid, bin_dir, data_dir)
    '''

    try:
        if is_bitcoind_running():
            send_bitcoin_cli_cmd('stop', bin_dir, data_dir, max_attempts=1)

        # wait until bitcoind terminates
        if bitcoind_process is None:
            try:
                pid, returncode = os.waitpid(bitcoind_pid, os.P_WAIT)
                log(f'waitpid {pid} return code: {returncode}')
            except ChildProcessError:
                log('update_pid already dead')
        else:
            bitcoind_process.wait()
            log(f'bitcoind return code: {bitcoind_process.returncode}')
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

def retry_stopping(bin_dir, data_dir, update_progress=None):
    '''
        Retry sending the stop command.
        At times, the process might end, but
        bitcoin itself is still running.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> bin_dir = '/tmp/bitcoin/'
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> retry_stopping(bin_dir, data_dir)
    '''
    MAX_SECONDS = 30

    seconds = 0
    while is_bitcoind_running():

        sleep(1)
        seconds += 1
        if seconds > MAX_SECONDS:
            seconds = 0
            send_bitcoin_cli_cmd('stop', bin_dir, data_dir)
            if update_progress:
                update_progress(constants.STOPPING_UPDATE)

def wait_for_status(data_dir):
    '''
        Wait for bitcoin to clean up.

        Args
            data_dir: directory where bitcoin core stores the blockchain

        Returns
            ok: True if bitcoin shutdown successfully; otherwise, False.
            error_message: Error message from bitcoind if there is one; otherwise, None.
            seconds: Seconds waited for status.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> __, error_message, seconds = wait_for_status(data_dir)
        >>> error_message is None
        True
        >>> seconds == 0
        True
    '''
    WAIT_SECONDS = 10
    MAX_SECONDS = 60

    # if bitcoin is not running, then give it more time to see
    # if the debug log is updated with the status
    seconds = 0
    ok, error_message = check_bitcoin_log(data_dir, is_bitcoind_running)
    while (not ok and seconds < MAX_SECONDS and not is_bitcoind_running()):

        sleep(WAIT_SECONDS)
        seconds += WAIT_SECONDS
        ok, error_message = check_bitcoin_log(data_dir, is_bitcoind_running)

    if seconds >= MAX_SECONDS:
        log(f'waited {seconds} seconds for bitcoin to finish.')
        log(f'is_bitcoind_running: {is_bitcoind_running()}')

    return ok, error_message, seconds

def report_shutdown_error(bitcoind_process, bitcoind_pid, error_message, seconds, update_progress=None):
    '''
        Report a serious error about stopping bitcoind.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> bin_dir = '/tmp/bitcoin/'
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> bitcoind_process, bitcoind_pid = start_bitcoind(bin_dir, data_dir)
        >>> ok, error_message = stop_bitcoind(bitcoind_process, bitcoind_pid, bin_dir, data_dir)
        >>> report_shutdown_error(bitcoind_process, bitcoind_pid, error_message, 60)
    '''
    # let the user know a serious error has happened
    if is_bitcoind_running():
        if bitcoind_process is None and bitcoind_pid is None:
            if error_message is None and update_progress:
                update_progress(
                  f'Unable to stop bitcoind after {seconds/60} minutes')
        else:
            if bitcoind_process is None:
                os.kill(bitcoind_pid, os.SIGTERM)
            else:
                bitcoind_process.terminate()
            log('terminated bitcoin process')
    else:
        if update_progress:
            # clear the progress because we're no longer
            # waiting for bitcoind to shutdown
            update_progress('&nbsp;')

def get_bitcoin_bin_dir():
    ''' Return bitcoin bin dir, or None if bitcoin not running.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> path = get_bitcoin_bin_dir()
        >>> (path is None) or ('bitcoin' in path)
        True
    '''

    path = None
    for program in [bitcoin_qt(), bitcoin_tx(), bitcoind()]:
        if path is None:
            path = get_path(program)

    if path:
        bindir = os.path.dirname(path)
    else:
        bindir = None

    return bindir

def get_bitcoin_version():
    '''
        Get the version of bitcoin core.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> version = get_bitcoin_version()
        >>> len(version) > 0
        True
    '''
    bitcoin_core_version = ''

    try:
        VERSION_PREFIX = ' version v'

        command_args = []

        bin_dir = get_bin_dir()
        if bin_dir is None:
            command_args.append(bitcoind())
        else:
            command_args.append(os.path.join(bin_dir, bitcoind()))

        command_args.append('--version')

        result = run(*command_args)
        i = result.stdout.find('\n')
        if i > 0:
            stdout = result.stdout[:i]
        else:
            stdout = result.stdout
        i = stdout.find(VERSION_PREFIX)
        if i > 0:
            bitcoin_core_version = stdout[i + len(VERSION_PREFIX):]
            log(f'bitcoin core version: {bitcoin_core_version}')
        else:
            log(f'unable to find version; stdout: {stdout}')

    except FileNotFoundError:
        log(f'FileNotFoundError: {command_args}')
    except PermissionError:
        log(f'PermissionError: {command_args}')
    except: # 'bare except' because it catches more than "except Exception"
        log('unable to get bitcoin core version: {command_args}')

    return bitcoin_core_version

def get_fresh_debug_log(data_dir):
    '''
        Get the debug log name and
        clear it so all entries are from
        the new session.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> get_fresh_debug_log('/tmp/bitcoin/data/testnet3')
        '/tmp/bitcoin/data/testnet3/debug.log'
    '''

    debug_log_name = get_debug_log_name(data_dir)
    if os.path.exists(debug_log_name):
        os.remove(debug_log_name)

    return debug_log_name

def get_debug_log_name(data_dir):
    '''
        Get the debug log name.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> get_debug_log_name('/tmp/bitcoin/data')
        '/tmp/bitcoin/data/debug.log'
        >>> get_debug_log_name('/tmp/bitcoin/data/testnet3')
        '/tmp/bitcoin/data/testnet3/debug.log'
    '''
    debug_log_name = os.path.join(data_dir, constants.DEBUG_LOG)

    return debug_log_name

def bitcoin_finished_ok(data_dir, is_app_running_func):
    '''
        Check the log and verify a clean exit.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> test_utils.start_bitcoind()
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> debug_log = os.path.join(data_dir, 'debug.log')
        >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', debug_log)
        '/tmp/bitcoin/data/testnet3/debug.log'
        >>> bitcoin_finished_ok(data_dir, is_bitcoind_running)
        (True, None)
        >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', debug_log)
        '/tmp/bitcoin/data/testnet3/debug.log'
        >>> if os.path.exists(debug_log): os.remove(debug_log)
        >>> ok, error_message = bitcoin_finished_ok(data_dir, is_bitcoind_running)
        >>> ok is False
        True
        >>> error_message is not None
        True
        >>> test_utils.stop_bitcoind()
        >>> ok, error_message = bitcoin_finished_ok(data_dir, is_bitcoin_qt_running)
        >>> ok is False
        True
        >>> error_message is not None
        True
        >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', debug_log)
        '/tmp/bitcoin/data/testnet3/debug.log'
    '''

    debug_log = get_debug_log_name(data_dir)
    if os.path.exists(debug_log):
        shutdown, error_message = check_bitcoin_log(data_dir, is_app_running_func)
        ok = shutdown and error_message is None

    else:
        ok = False
        error_message = 'Error: Unable to determine status of bitcoin because debug.log is missing.'

    if error_message is not None:
        log(error_message)

    return ok, error_message

def check_bitcoin_log(data_dir, is_app_running_func=None):
    '''
        Check the log and see if the app shutdown.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> debug_log = '/tmp/bitcoin/data/testnet3/debug.log'
        >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', debug_log)
        '/tmp/bitcoin/data/testnet3/debug.log'
        >>> check_bitcoin_log(data_dir, is_bitcoind_running)
        (True, None)
        >>> if os.path.exists(debug_log): os.remove(debug_log)
        >>> check_bitcoin_log(data_dir, is_bitcoind_running)
        (True, None)
        >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', debug_log)
        '/tmp/bitcoin/data/testnet3/debug.log'
    '''

    shutdown = False
    error_message = None
    debug_log = get_debug_log_name(data_dir)

    if os.path.exists(debug_log):
        with open(debug_log, 'r') as input_file:
            shutdown, error_message = log_errors(input_file)

            if error_message is not None:
                error_message = error_message.strip(':')
                log(f'error message: {error_message}')

    elif is_app_running_func is not None:
        log(f'{debug_log} not found')
        shutdown = not is_app_running_func()

    return shutdown, error_message

def log_errors(log_file):
    '''
        Get the errors if there are any from the log file.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> debug_log = '/tmp/bitcoin/data/testnet3/debug.log'
        >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', debug_log)
        '/tmp/bitcoin/data/testnet3/debug.log'
        >>> with open('/tmp/bitcoin/data/testnet3/debug.log', 'r') as log_file:
        ...     log_errors(log_file)
        (True, None)
    '''

    SHUTDOWN_OK = 'Shutdown: done\n'
    IO_ERROR = 'IO error'
    LOADING_BANLIST = 'Loading banlist...'
    ERROR_LOADING_DATABASE = 'Error loading block database.'
    ERROR_OPENING_DATABASE = 'Error opening block database'
    ABORTED_BLOCK_REBUILD = 'Aborted block database rebuild'
    CORRUPTED_BLOCK = 'Corrupted block database detected.'
    SYSTEM_ERROR = 'System error while flushing: Database I/O error'
    NO_GENESIS_BLOCK_ERROR = 'Error: Incorrect or no genesis block found. Wrong datadir for network?'
    EOF_ERROR = 'EOF reached'
    FAILED_TO_READ_BLOCK = 'Failed to read block'
    FATAL_INTERNAL_ERROR = 'A fatal internal error occurred, see debug.log for details'
    FAILED_TO_OPEN_ANCHOR = 'ERROR: DeserializeFileDB: Failed to open file'
    PRECHECK_ERROR = 'ERROR: PreChecks: '
    UNKNOWN_ERROR1 = 'Error:'
    UNKNOWN_ERROR2 = 'ERROR:'

    shutdown = False
    error_message = unknown_error_message = None
    unknown_error = False

    for line in log_file:
        log(line.strip())
        match = re.match(f'.*?{IO_ERROR}', line)
        if not match:
            match = re.match(f'.*?{ERROR_LOADING_DATABASE}', line)
        if not match:
            match = re.match(f'.*?{ERROR_OPENING_DATABASE}', line)
        if not match:
            match = re.match(f'.*?{ABORTED_BLOCK_REBUILD}', line)
        if not match:
            match = re.match(f'.*?{CORRUPTED_BLOCK}', line)
        if not match:
            match = re.match(f'.*?{SYSTEM_ERROR}', line)
        if not match:
            match = re.match(f'.*?{NO_GENESIS_BLOCK_ERROR}', line)
        if not match:
            match = re.match(f'.*?{EOF_ERROR}', line)
        if not match:
            match = re.match(f'.*?{FAILED_TO_READ_BLOCK}', line)
        if not match:
            match = re.match(f'.*?{FATAL_INTERNAL_ERROR}', line)
        if not match:
            # ignore precheck errors and see if they turn into something more serious
            if re.match(f'.*?{PRECHECK_ERROR}', line):
                pass
            # ignore failure to open anchors.dat
            elif re.match(f'.*?{FAILED_TO_OPEN_ANCHOR}.*?anchors.dat', line):
                pass
            # ignore loading the ban list
            elif re.match(f'.*?{LOADING_BANLIST}', line):
                pass
            elif re.match(f'.*?{UNKNOWN_ERROR1}', line):
                unknown_error = True
                unknown_error_message = line
            elif re.match(f'.*?{UNKNOWN_ERROR2}', line):
                unknown_error = True
                unknown_error_message = line

        if match:
            shutdown = True
            i = line.find(' ')
            if i > 0:
                error_message = line[i+1:]
            else:
                error_message = line

        elif line.endswith(SHUTDOWN_OK):
            shutdown = True
            break

    if error_message is None and unknown_error:
        i = unknown_error_message.find(' ')
        if i > 0:
            error_message = unknown_error_message[i+1:]
        else:
            error_message = unknown_error_message

    return shutdown, error_message

def rename_logs(data_dir, time_stamp=None):
    '''
        Rename the debug and manager logs.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> debug_log = '/tmp/bitcoin/data/testnet3/debug.log'
        >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', debug_log)
        '/tmp/bitcoin/data/testnet3/debug.log'
        >>> rename_logs(data_dir)
        False
        >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', debug_log)
        '/tmp/bitcoin/data/testnet3/debug.log'
    '''
    ok = False

    if is_bitcoin_core_running():
        ok = True
    else:
        if time_stamp is None:
            time_stamp = str(now())

        debug_log = get_fresh_debug_log(data_dir)
        if os.path.exists(debug_log):
            shutil.move(debug_log,
                        os.path.join(data_dir,
                                     f'{constants.DEBUG_PREFIX}{time_stamp}{constants.LOG_SUFFIX}'))
            ok = True

    return ok

def strip_testnet_from_data_dir(data_dir=None):
    '''
        Get the data dirname without
        the "testnet3" subdir, if appropriate.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> strip_testnet_from_data_dir()
        '/tmp/bitcoin/data'
    '''
    if data_dir is None:
        data_dir = get_data_dir()

    use_test_net = constants.TESTNET_FLAG in get_extra_args()
    if use_test_net and data_dir.endswith(constants.TEST_NET_SUBDIR):
        new_data_dir = data_dir[:data_dir.rfind(constants.TEST_NET_SUBDIR)]

    else:
        new_data_dir = data_dir

    return new_data_dir

def get_most_recent_confirmation(last_block_time):
    '''
        Get and format the most recent
        confirmation of the blockchain.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> get_most_recent_confirmation(now())
        'Up to date'
    '''
    seconds = (now() - last_block_time).total_seconds()
    time_behind = seconds_human_readable(seconds)
    if time_behind is None or time_behind == '0 seconds':
        time_behind = 'Up to date'

    return time_behind

def get_path_of_core_apps():
    '''
        Get the path of the bitcoin core apps.

        >>> bin_dir = get_path_of_core_apps()
        >>> len(bin_dir) > 0
        True
    '''
    bin_dir = None

    entries = os.get_exec_path()
    for entry in entries:
        found = (os.path.exists(os.path.join(entry, bitcoind())) and
                 os.path.exists(os.path.join(entry, bitcoin_cli())) and
                 os.path.exists(os.path.join(entry, bitcoind())))

        if found:
            bin_dir = entry
            break

    return bin_dir
