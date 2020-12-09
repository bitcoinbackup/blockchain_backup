'''
    Utilities for bitcoin tests.

    Copyright 2019-2020 DeNova
    Last modified: 2020-12-08
'''

import os
import shutil
from datetime import datetime, timedelta
from subprocess import CalledProcessError
from time import sleep

from django.core.management import call_command
from django.utils.timezone import now, utc

from blockchain_backup.bitcoin import constants, preferences, state
from blockchain_backup.bitcoin import utils as bitcoin_utils
from blockchain_backup.bitcoin.models import Preferences, State
from blockchain_backup.settings import PROJECT_PATH, TIME_ZONE
from denova.os import command
from denova.os.user import getdir
from denova.python.log import get_log, get_log_path
from denova.python.ve import virtualenv_dir


HOME_BITCOIN_DIR = os.path.join(getdir(), '.bitcoin')
DATA_WITH_BLOCKS_DIR = '/tmp/bitcoin/data-with-blocks'
INITIAL_DATA_DIR = '/tmp/bitcoin/data-initial'

log = get_log()

def setup_tmp_dir():
    '''
        Set up a temporary test directory.

        >>> setup_tmp_dir()
    '''

    TEST_ENV_PATH = os.path.join(PROJECT_PATH, '..', 'test-env')
    TEST_BITCOIN_ENV_PATH = os.path.join(TEST_ENV_PATH, 'bitcoin')

    if not os.path.exists('/tmp/bitcoin'):
        os.mkdir('/tmp/bitcoin')
    if not os.path.exists('/tmp/bitcoin/home-pages'):
        os.mkdir('/tmp/bitcoin/home-pages')
    if not os.path.exists('/tmp/bitcoin/unwriteable-dir'):
        shutil.copytree(os.path.join(TEST_BITCOIN_ENV_PATH, 'unwriteable-dir'),  '/tmp/bitcoin/unwriteable-dir')
    shutil.copy(os.path.join(TEST_BITCOIN_ENV_PATH, 'debug-with-shutdown.log'),  '/tmp/bitcoin')
    shutil.copy(os.path.join(TEST_BITCOIN_ENV_PATH, 'debug-without-shutdown.log'),  '/tmp/bitcoin')
    shutil.copy(os.path.join(TEST_BITCOIN_ENV_PATH, 'state.json'),  '/tmp/bitcoin')

    if not os.path.exists('/tmp/bitcoin/bin'):
        copy_bitcoin_binaries('/tmp/bitcoin/bin')
    if not os.path.exists(INITIAL_DATA_DIR):
        shutil.copytree(os.path.join(TEST_BITCOIN_ENV_PATH, 'data-initial'), INITIAL_DATA_DIR)

    if os.path.exists('/tmp/bitcoin/data-with-blocks-no-backups'):
        shutil.rmtree('/tmp/bitcoin/data-with-blocks-no-backups')
    shutil.copytree(os.path.join(TEST_BITCOIN_ENV_PATH, 'data-initial'), '/tmp/bitcoin/data-with-blocks-no-backups')
    if os.path.exists('/tmp/bitcoin/data-no-blocks'):
        shutil.rmtree('/tmp/bitcoin/data-no-blocks')
    shutil.copytree(os.path.join(TEST_BITCOIN_ENV_PATH, 'data-no-blocks'), '/tmp/bitcoin/data-no-blocks')
    if os.path.exists('/tmp/bitcoin/data-with-missing-file'):
        shutil.rmtree('/tmp/bitcoin/data-with-missing-file')
    shutil.copytree(os.path.join(TEST_BITCOIN_ENV_PATH, 'data-with-missing-file'), '/tmp/bitcoin/data-with-missing-file')
    if os.path.exists(DATA_WITH_BLOCKS_DIR):
        shutil.rmtree(DATA_WITH_BLOCKS_DIR)
    shutil.copytree(os.path.join(TEST_BITCOIN_ENV_PATH, 'data-with-blocks'), DATA_WITH_BLOCKS_DIR)

    if os.path.lexists('/tmp/bitcoin/data'):
        os.remove('/tmp/bitcoin/data')
    elif os.path.exists('/tmp/bitcoin/data'):
        shutil.rmtree('/tmp/bitcoin/data')
    os.symlink(DATA_WITH_BLOCKS_DIR, '/tmp/bitcoin/data')

def copy_bitcoin_binaries(to_dir):
    '''
        Copy bitcoin binaries to the test environment.

        >>> TEMP_DIR = '/tmp/.test'
        >>> if os.path.exists(TEMP_DIR):
        ...     shutil.rmtree(TEMP_DIR)
        >>> copy_bitcoin_binaries(TEMP_DIR)
        True
        >>> if os.path.exists(TEMP_DIR):
        ...     shutil.rmtree(TEMP_DIR)
    '''
    def copy_binary_file(filename, to_dir):

        ok = False

        full_path = command.run('which', filename).stdout.strip()
        if len(full_path) > 0 and os.path.exists(full_path):
            shutil.copy(full_path,  to_dir)
            ok = True

        return ok

    os.makedirs(to_dir)
    ok = copy_binary_file('bitcoind', to_dir)
    if ok:
        ok = copy_binary_file('bitcoin-cli', to_dir)
    if ok:
        ok = copy_binary_file('bitcoin-qt', to_dir)

    return ok

def home_bitcoin_dir_exists():
    '''
        Check if the .bitcoin dir exists
        in the user's home dir.

        >>> home_bitcoin_dir_exists()
        False
    '''

    return os.path.exists(HOME_BITCOIN_DIR)

def delete_home_bitcoin_subdir(subdir_existed):
    '''
        If the .bitcoin dir didn't exist before
        the tests, but exists now, delete it.

        >>> subdir_existed = False
        >>> delete_home_bitcoin_subdir(subdir_existed)
    '''
    if not subdir_existed and os.path.exists(HOME_BITCOIN_DIR):

        if os.path.islink(HOME_BITCOIN_DIR):
            os.remove(HOME_BITCOIN_DIR)
        else:
            shutil.rmtree(HOME_BITCOIN_DIR)

def get_preferences():
    '''
        Get the preferences.

        >>> prefs = get_preferences()
        >>> isinstance(prefs, Preferences)
        True
    '''

    return preferences.get_preferences()

def set_new_preferences(new_preferences):
    '''
        Set the preferences.

        >>> set_new_preferences(None)
    '''
    if new_preferences is None:
        while True:
            try:
                prefs = preferences.get_preferences()
                prefs.delete()
            except:
                break
    else:
        prefs = get_preferences()
        prefs.data_dir = new_preferences.data_dir
        prefs.bin_dir = new_preferences.bin_dir
        prefs.backup_schedule = new_preferences.backup_schedule
        prefs.backup_levels = new_preferences.backup_levels
        prefs.backup_dir = new_preferences.backup_dir
        prefs.extra_args = new_preferences.extra_args
        preferences.save_preferences(prefs)

def get_state():
    '''
        Get the original system's state.

        >>> state = get_state()
        >>> isinstance(state, State)
        True
     '''

    return state.get_state()

def set_new_state(new_state):
    '''
        Set the original system's state.

        >>> set_new_state(None)
     '''
    if new_state is None:
        while True:
            try:
                settings = state.get_state()
                settings.delete()
            except:
                break
    else:
        settings = get_state()
        settings.last_block_time = new_state.last_block_time
        settings.last_known_block = new_state.last_known_block
        settings.last_block_updated = new_state.last_block_updated
        settings.last_backed_up_time = new_state.last_backed_up_time
        settings.last_backup_level = new_state.last_backup_level
        settings.last_update_time = new_state.last_update_time
        settings.latest_bcb_version = new_state.latest_bcb_version
        settings.latest_core_version = new_state.latest_core_version
        state.save_state(settings)

def init_database():
    '''
        Initialize the database for the test environment.
        Loading fixtures doesn't work in doc tests so
        we'll handle it here for all tests.

        >>> init_database()
    '''
    FIXTURE_PATH = os.path.join(PROJECT_PATH, 'bitcoin', 'fixtures')
    PREFERENCES_FIXTURE = os.path.join(FIXTURE_PATH, 'bitcoin.preferences.json')
    STATE_FIXTURE = os.path.join(FIXTURE_PATH, 'bitcoin.state.json')

    # make sure the fixtures are loaded even in doc tests
    call_command("loaddata", f"{PREFERENCES_FIXTURE}", verbosity=0)
    call_command("loaddata", f"{STATE_FIXTURE}", verbosity=0)

    settings = state.get_state()
    settings.last_backed_up_time = now() - timedelta(hours=1)
    settings.last_update_time = now() - timedelta(hours=25)
    state.save_state(settings)

def start_bitcoind():
    '''
        Start bitcoind as a daemon.

        >>> init_database()
        >>> start_bitcoind()
        >>> stop_bitcoind()
    '''

    bin_dir, data_dir = preferences.get_bitcoin_dirs()

    command_args = []
    cmd = os.path.join(bin_dir, bitcoin_utils.bitcoind())
    command_args.append(cmd)

    data_dir = bitcoin_utils.strip_testnet_from_data_dir(data_dir=data_dir)
    command_args.append(f'-datadir={data_dir}')

    # don't allow any interaction with the user's wallet
    command_args.append('-disablewallet')

    extra_args = preferences.get_extra_args()
    if len(extra_args) > 0:
        for extra_arg in extra_args:
            command_args.append(extra_arg)

    command_args.append('-daemon')

    command.background(*command_args)
    log(f'running in background: {command_args}')

    # give bitcoind time to start
    secs = 0
    while (not bitcoin_utils.is_bitcoind_running() and secs < 5):
        sleep(1)
        secs += 1

def stop_bitcoind():
    '''
        Stop bitcoind and determine if it ended properly.

        >>> init_database()
        >>> stop_bitcoind()
    '''
    while (bitcoin_utils.is_bitcoind_running()):
        sleep(5)
        send_bitcoin_cli_cmd('stop')

    # give it a little more time to settle down
    sleep(5)

    log(f'bitcoind running: {bitcoin_utils.is_bitcoind_running()}')

def start_bitcoin_qt():
    '''
        Start bitcoin-qt.

        >>> init_database()
        >>> start_bitcoin_qt()
        >>> stop_bitcoin_qt()
    '''

    bin_dir, data_dir = preferences.get_bitcoin_dirs()

    command_args = []
    cmd = os.path.join(bin_dir, bitcoin_utils.bitcoin_qt())
    command_args.append(cmd)

    data_dir = bitcoin_utils.strip_testnet_from_data_dir(data_dir=data_dir)
    command_args.append(f'-datadir={data_dir}')

    extra_args = preferences.get_extra_args()
    if len(extra_args) > 0:
        for extra_arg in extra_args:
            command_args.append(extra_arg)

    command_args.append('-daemon')

    command.background(*command_args)
    log(f'running : {command_args}')

    # give bitcoind time to start
    secs = 0
    while (not bitcoin_utils.is_bitcoin_qt_running() and secs < 5):
        sleep(1)
        secs += 1

def stop_bitcoin_qt():
    '''
        Stop bitcoin_qt and determine if it ended properly.

        >>> init_database()
        >>> stop_bitcoin_qt()
    '''
    seconds = 0
    while (bitcoin_utils.is_bitcoin_qt_running() and seconds < 60):
        try:
            send_bitcoin_cli_cmd('stop')
            sleep(5)
            seconds += 5
        except:
            pass

    # use brute force if necessary
    if bitcoin_utils.is_bitcoin_qt_running():
        bin_dir = os.path.join(virtualenv_dir(), 'bin')
        args = [os.path.join(bin_dir, 'killmatch'), bitcoin_utils.bitcoin_qt()]
        command.run(*args).stdout

    # give it a little more time to settle down
    sleep(5)

    log(f'bitcoin-qt running: {bitcoin_utils.is_bitcoin_qt_running()}')

def stop_bitcoin_core_apps():
    '''
        Stop all bitcoin core apps.

        >>> stop_bitcoin_core_apps()
    '''
    if bitcoin_utils.is_bitcoin_qt_running():
        stop_bitcoin_qt()

        # if it's still running, then kill it
        if bitcoin_utils.is_bitcoin_qt_running():
            bin_dir = os.path.join(virtualenv_dir(), 'bin')
            args = [os.path.join(bin_dir, 'killmatch'), bitcoin_utils.bitcoin_qt()]
            command.run(*args).stdout

    if bitcoin_utils.is_bitcoind_running():
        stop_bitcoind()

        # if it's still running, then kill it
        if bitcoin_utils.is_bitcoind_running():
            bin_dir = os.path.join(virtualenv_dir(), 'bin')
            args = [os.path.join(bin_dir, 'killmatch'), bitcoin_utils.bitcoind()]
            command.run(*args).stdout

def send_bitcoin_cli_cmd(arg):
    '''
        Send a command via bitcoin-cli.

        >>> init_database()
        >>> start_bitcoind()
        >>> block_count = send_bitcoin_cli_cmd('getblockcount')
        >>> stop_bitcoind()
    '''

    bin_dir, data_dir = preferences.get_bitcoin_dirs()

    command_args = []
    command_args.append(os.path.join(bin_dir, bitcoin_utils.bitcoin_cli()))

    use_test_net = '-testnet' in preferences.get_extra_args()
    if use_test_net:
        command_args.append('-testnet')

    if data_dir is not None:
        data_dir = bitcoin_utils.strip_testnet_from_data_dir(data_dir=data_dir)
        command_args.append(f'-datadir={data_dir}')

    command_args.append(arg)
    log(f'running: {command_args}')

    try:
        result = command.run(*command_args).stdout
        log(f'result: {result}')
    except CalledProcessError as cpe:
        result = None

    return result

def check_bitcoin_log(is_app_running_func=None):
    '''
        Check bitcoin log to see if app shutdown properly.

        >>> check_bitcoin_log(bitcoin_utils.is_bitcoind_running)
        (True, None)
    '''
    from blockchain_backup.bitcoin.manager import BitcoinManager

    manager = BitcoinManager(os.path.basename(get_log_path()), use_fresh_debug_log=False)
    log(f'checking {get_log_path()} for errors')

    shutdown, error_message = manager.check_bitcoin_log(is_app_running_func)
    log(f'shutdown: {shutdown}')
    log(f'error_message: {error_message}')

    return shutdown, error_message

def start_fake_backup():
    '''
        Start a program which has the backup program's name,
        but just keeps itself running for a few minutes
        so we can test for the app to be running.

        >>> start_fake_backup()
        >>> bin_dir = os.path.join(virtualenv_dir(), 'bin')
        >>> sleep(15)
        >>> args = [os.path.join(bin_dir, 'killmatch'), constants.BACKUP_PROGRAM]
        >>> result = command.run(*args)
    '''

    bin_dir = os.path.join(virtualenv_dir(), 'bin')
    config_dir = os.path.join(PROJECT_PATH, 'config')
    args = [os.path.join(bin_dir, constants.BACKUP_PROGRAM), config_dir, '/tmp']
    command.background(*args)

def stop_backup():
    '''
        Stop the backup.

        >>> init_database()
        >>> stop_backup()
    '''
    while bitcoin_utils.is_backup_running():
        sleep(5)

        bin_dir = os.path.join(virtualenv_dir(), 'bin')
        excluded_files = bitcoin_utils.get_excluded_files()
        args = [os.path.join(bin_dir, 'killmatch'),
                f'"{constants.BACKUP_PROGRAM} --exclude {excluded_files}"']
        result = command.run(*args).stdout
        log(f'killing backup result: {result}')

def start_fake_restore():
    '''
        Start a program which has the restore program's name,
        but just keeps itself running for a few minutes
        so we can test for the app to be running.

        >>> start_fake_restore()
        >>> bin_dir = os.path.join(virtualenv_dir(), 'bin')
        >>> sleep(15)
        >>> args = [os.path.join(bin_dir, 'killmatch'), constants.RESTORE_PROGRAM]
        >>> result = command.run(*args)
    '''

    bin_dir = os.path.join(virtualenv_dir(), 'bin')
    config_dir = os.path.join(PROJECT_PATH, 'config')
    args = [os.path.join(bin_dir, constants.RESTORE_PROGRAM), config_dir, '/tmp']
    command.background(*args)

def stop_restore():
    '''
        Stop the restore.

        >>> init_database()
        >>> stop_restore()
    '''
    while bitcoin_utils.is_restore_running():
        sleep(5)

        bin_dir = os.path.join(virtualenv_dir(), 'bin')
        excluded_files = bitcoin_utils.get_excluded_files()
        args = [os.path.join(bin_dir, 'killmatch'),
                f'"{constants.RESTORE_PROGRAM} --exclude {excluded_files}"']
        result = command.run(*args).stdout
        log(f'killing restore result: {result}')

def restore_initial_data():
    '''
        Restore data to an initial state.

        >>> restore_initial_data()
    '''
    def restore_files_and_dirs(from_dir, to_dir):
        # copy all the files/dirs
        entries = os.scandir(from_dir)
        for entry in entries:
            to_entry_path = os.path.join(to_dir, entry.name)

            # don't copy this dir because it has special priv
            if entry.name == 'unwritable-dir':
                pass
            elif entry.is_dir():
                os.mkdir(to_entry_path)
                restore_files_and_dirs(entry.path, to_entry_path)
            else:
                shutil.copy(entry.path, to_entry_path)

    # remove all the files/dirs
    entries = os.scandir(DATA_WITH_BLOCKS_DIR)
    for entry in entries:
        # don't remove this dir because it has special priv
        if entry.name == 'unwritable-dir':
            pass
        elif entry.is_dir():
            shutil.rmtree(entry.path)
        else:
            os.remove(entry.path)

    if os.path.lexists('/tmp/bitcoin/data'):
        os.remove('/tmp/bitcoin/data')
    elif os.path.exists('/tmp/bitcoin/data'):
        shutil.rmtree('/tmp/bitcoin/data')

    restore_files_and_dirs(INITIAL_DATA_DIR, DATA_WITH_BLOCKS_DIR)

    os.symlink(DATA_WITH_BLOCKS_DIR, '/tmp/bitcoin/data')
