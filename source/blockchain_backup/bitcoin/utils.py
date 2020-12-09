'''
    Utilities for blockchain backup.

    Copyright 2018-2020 DeNova
    Last modified: 2020-12-08
'''

import json
import os
from datetime import timedelta
from traceback import format_exc

from django.utils.timezone import now

from blockchain_backup import __file__ as blockchain_backup_file
from blockchain_backup.bitcoin import constants, state
from blockchain_backup.core_version import CORE_VERSION
from blockchain_backup.settings import CONNECTION_HEARTBEAT, USE_SOCKETIO
from denova.os.command import background, run
from denova.os.osid import is_windows
from denova.os.process import get_path, is_program_running
from denova.os.user import whoami
from denova.python.log import get_log
from denova.python.times import seconds_human_readable

log = get_log()


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

    return (is_bitcoind_running() or
            is_bitcoin_qt_running() or
            is_bitcoin_tx_running())

def is_backup_running():
    '''
        Return True if backup is running.

        >>> is_backup_running()
        False
    '''

    # backup program is a link to safecopy
    return is_program_running(constants.BACKUP_PROGRAM)

def is_restore_running():
    '''
        Return True if restore is running.

        >>> is_restore_running()
        False
    '''

    # restore program is a link to safecopy
    return is_program_running(constants.RESTORE_PROGRAM)

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
        >>> get_bitcoin_version()
        '0.20.1'
    '''
    from blockchain_backup.bitcoin.preferences import get_bin_dir

    bitcoin_core_version = CORE_VERSION

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

def get_blockchain_context():
    '''
        Get the basic context for a blockchain web page.

        >>> context = get_blockchain_context()
        >>> context['update_facility']
        'denova.blockchain_backup.bitcoin'
        >>> context['update_type']
        'blockchain_socketio_type'
        >>> context['connection_heartbeat']
        '--heartbeat--'
    '''
    context = {'update_facility': constants.BLOCKCHAIN_FACILITY,
               'update_type': constants.BLOCKCHAIN_TYPE,
               'update_interval': '1000',
               'connection_heartbeat': CONNECTION_HEARTBEAT,
               }
    return context

def get_excluded_files():
    '''
        Get the files to exclude from backups and restores.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> get_excluded_files()
        'wallets,wallet.dat,.walletlock,backups,blockchain_backup_database'
    '''
    from blockchain_backup.bitcoin.preferences import get_extra_args

    excluded_files = 'wallets,wallet.dat,.walletlock,backups,{}'.format(
      constants.BLOCKCHAIN_BACKUP_DB_DIR)

    use_test_net = constants.TESTNET_FLAG in get_extra_args()
    if not use_test_net:
        excluded_files += f',{constants.TEST_NET_DIR}'

    # add the subdirectory of the backup if its in the data directory
    backup_subdir = get_backup_subdir()
    if backup_subdir is not None and backup_subdir not in excluded_files:
        excluded_files += f',{backup_subdir}'

    return excluded_files

def get_backup_subdir():
    '''
        Get subdir name if its in the data directory.

        >>> from blockchain_backup.bitcoin.preferences import get_preferences, save_preferences
        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> get_backup_subdir()
        'backups'
        >>> prefs = get_preferences()
        >>> prefs.backup_dir = '/tmp/bitcoin/backups'
        >>> save_preferences(prefs)
        >>> get_backup_subdir() is None
        True
    '''
    from blockchain_backup.bitcoin.preferences import get_backup_dir, get_data_dir

    data_dir = get_data_dir()
    backup_dir = get_backup_dir()

    # get the name of the subdirectory of the backup
    # if its in the data directory
    index = backup_dir.find(data_dir)
    if index >= 0:
        backup_subdir = backup_dir[index + len(data_dir):]
        if backup_subdir.startswith(os.sep):
            backup_subdir = backup_subdir[1:]
        if backup_subdir.endswith(os.sep):
            backup_subdir = backup_subdir[:-1]
    else:
        backup_subdir = None

    return backup_subdir

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

def strip_testnet_from_data_dir(data_dir=None):
    '''
        Get the data dirname without
        the "testnet3" subdir, if appropriate.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> strip_testnet_from_data_dir()
        '/tmp/bitcoin/data'
    '''
    from blockchain_backup.bitcoin.preferences import get_data_dir, get_extra_args

    if data_dir is None:
        data_dir = get_data_dir()

    use_test_net = constants.TESTNET_FLAG in get_extra_args()
    if use_test_net and data_dir.endswith(constants.TEST_NET_SUBDIR):
        new_data_dir = data_dir[:data_dir.rfind(constants.TEST_NET_SUBDIR)]

    else:
        new_data_dir = data_dir

    return new_data_dir

def send_socketio_message(key, html):
    '''
        Send a message to the user via socketio.

        >>> key = 'button'
        >>> html = 'Test'
        >>> send_socketio_message(key, html)
    '''

    if USE_SOCKETIO:
        try:
            update = json.dumps({f'{key}_html': html})
            log(f'socketio update: {update}')
            #socketio_message = {'type': constants.BLOCKCHAIN_TYPE,
            #                    'server_nonce': server_nonce(),
            #                    'update': update,
            #                    'update_time': format_time(str(now())),
            #                   }
            #redis_message = RedisMessage(json.dumps(socketio_message))

            #RedisPublisher(facility=constants.BLOCKCHAIN_FACILITY,
            #               broadcast=True).publish_message(redis_message)

        except ConnectionRefusedError as cre:
            log(str(cre))

        except Exception as e:
            log(str(e))

def is_dir_writeable(data_dir):
    '''
        Return True if a new file
        can be created in the dir.

        >>> data_dir = '/tmp'
        >>> is_dir_writeable(data_dir)
        (True, None)
        >>> data_dir = '/'
        >>> ok, error_message = is_dir_writeable(data_dir)
        >>> ok == False
        True
        >>> error_message.startswith('Unable to write to the data dir')
        True
        >>> data_dir = '/unknown'
        >>> is_dir_writeable(data_dir)
        (False, '"/unknown" directory does not exist.')
    '''
    try:
        filename = os.path.join(data_dir, '.test')
        with open(filename, "wt") as output_file:
            output_file.write('test')
        os.remove(filename)
        ok = True
        error = None
    except PermissionError:
        ok = False
        error = f'Unable to write to the data dir in {data_dir} as {whoami()}.'
        log(error)
    except FileNotFoundError:
        ok = False
        error = f'"{data_dir}" directory does not exist.'
        log(error)

    return ok, error

def format_time(unformatted_time):
    '''
        Format time so seconds, milliseconds, and timezone are stripped.

        >>> format_time('2009-01-12 12:00:00.000000+00:00')
        '2009-01-12 12:00'
    '''

    i = unformatted_time.find('.')
    if i > 0:
        unformatted_time = unformatted_time[:i]
        i = unformatted_time.rfind(':')
        if i > 0:
            unformatted_time = unformatted_time[:i]

    return unformatted_time

def wait_period(formatted_time):
    '''
        Format the period to wait into readable hours and minutes.

        >>> last_backed_up_time = state.get_last_backed_up_time()
        >>> hours_til_next_backup = format_time(str(now() - last_backed_up_time))
        >>> time_period = wait_period(hours_til_next_backup)
        >>> time_period is not None
        True
    '''

    def format_hours_section(hours, extra_hours):
        ''' Format the hours. '''

        hours_section = None
        if hours is not None and hours:
            hours = int(hours) + extra_hours
            if hours > 1:
                if extra_hours > 0:
                    hours_section = f'>{hours} hours'
                else:
                    hours_section = f'{hours} hours'
            elif hours == 1:
                hours_section = f'{hours} hour'

        return hours_section

    def format_minutes_section(minutes):
        ''' Format the minutes. '''

        minutes_section = None
        if minutes is not None and minutes:
            if int(minutes) > 1:
                minutes_section = f'{minutes} minutes'
            elif int(minutes) == 1:
                minutes_section = f'{minutes} minute'

        return minutes_section


    i = formatted_time.rfind(',')
    if i > 0:
        extra_hours = 24
        formatted_time = formatted_time[i+1:].strip()
    else:
        extra_hours = 0

    i = formatted_time.find(':')
    if i >= 0:
        hours = formatted_time[:i]
        minutes = formatted_time[i+1:]
    else:
        hours = None
        minutes = None

    hours_section = format_hours_section(hours, extra_hours)
    minutes_section = format_minutes_section(minutes)

    if hours_section is None and minutes_section is None:
        time_period = 'less than a minute'
    elif hours_section is None:
        time_period = minutes_section
    elif minutes_section is None:
        time_period = hours_section
    else:
        time_period = f'{hours_section} and {minutes_section}'

    return time_period

def get_next_backup_time():
    '''
        Get the next time we need to backup.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> next_backup_time = get_next_backup_time()
        >>> next_backup_time is not None
        True
    '''
    from blockchain_backup.bitcoin.preferences import get_backup_schedule

    last_backed_up_time = state.get_last_backed_up_time()
    bkup_schedule = get_backup_schedule()
    next_backup_time = last_backed_up_time + timedelta(hours=bkup_schedule)

    return next_backup_time

def get_next_backup_in():
    '''
        Get the hours/minutes until next backup.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> next_backup_in = get_next_backup_in()
        >>> next_backup_in is not None
        True
    '''
    next_backup_time = get_next_backup_time()
    seconds = (next_backup_time - now()).total_seconds()
    status = seconds_human_readable(seconds)

    return status

def need_to_backup(data_dir, current_block):
    '''
        Check the time stamp of the last backup
        and whether updates are needed.

        Don't backup too often, make sure enough time
        has passed to make it worth the resources.

        >>> from denova.python.log import get_log_path
        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> log_name = os.path.basename(get_log_path())
        >>> data_dir = '/tmp/bitcoin/data'
        >>> os.chdir(data_dir)
        >>> last_block_updated = state.get_last_block_updated()
        >>> state.set_last_block_updated(551292)
        >>> current_block = 551301
        >>> need_to_backup(data_dir, current_block)
        False
        >>> state.set_last_block_updated(0)
        >>> current_block = 551301
        >>> need_to_backup(data_dir, current_block)
        False
        >>> current_block = 0
        >>> need_to_backup(data_dir, current_block)
        False
        >>> state.set_last_block_updated(last_block_updated)
    '''
    try:
        message = None
        current_time = now()
        next_backup_time = get_next_backup_time()
        need_backup = next_backup_time < current_time

        if need_backup:
            start_access_time = state.get_start_access_time()
            last_access_time = state.get_last_access_time()
            last_backed_up_time = state.get_last_backed_up_time()

            # don't bother backing up if Blockchain Backup hasn't started
            # either bitcoind or bitcoin-qt
            if start_access_time < last_access_time:
                if last_access_time < last_backed_up_time:
                    need_backup = False
                    state.set_last_backed_up_time(now())
                    log('set last backed up time to now because no access since last backup')

        if need_backup:
            # if there's no data yet, than there's no need for a backup
            # 5 items is picked as a quick test
            if len(os.listdir(data_dir)) <= 5:
                need_backup = False
                log('no data so no need to back up')
            else:
                last_block_updated = state.get_last_block_updated()
                if current_block < 0 and last_block_updated == 0:
                    pass # yes, we need to backup; I find this test easier than alternatives
                elif current_block > 0:
                    if last_block_updated == 0 or current_block > last_block_updated:
                        state.set_last_block_updated(current_block)
                else:
                    need_backup = False
                    message = 'The blockchain was not backed up because no new blocks were received.'
                    log(message)

            check_for_updates(current_time=current_time)
    except: # 'bare except' because it catches more than "except Exception"
        # backup if anything in our analysis goes wrong
        need_backup = True
        log(format_exc())

    return need_backup

def delete_last_updated_files(dirname):
    '''
        Delete all the "last-updated" files from the directory.

        Return the number of files deleted.

        >>> dirname = '/tmp/bitcoin/data/testnet3'
        >>> delete_last_updated_files(dirname)
        0
    '''
    files_deleted = 0

    # remove all files that suggest this backup is complete
    entries = os.scandir(dirname)
    for entry in entries:
        if entry.is_file() and entry.name.startswith(constants.LAST_UPDATED_PREFIX):
            os.remove(entry.path)
            files_deleted += 1

    return files_deleted

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

def check_for_updates(current_time=None, force=False, reason=None):
    '''
        Check to see if updates are needed.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> check_for_updates()
        True
    '''

    updates_checked = False

    try:
        if current_time is None:
            current_time = now()

        next_updates_time = state.get_last_update_time() + timedelta(hours=24)
        if force or next_updates_time <= current_time:
            log('starting to check for the latest updates')

            # set the update time now so we don't restart the check too often
            state.set_last_update_time(current_time)

            command_args = []
            command_args.append('python3')
            # get the path for check_for_updates.py, regardless of virtualenv, etc.
            check_program = os.path.realpath(os.path.abspath(os.path.join(
              os.path.dirname(blockchain_backup_file), 'config', 'check_for_updates.py')))
            command_args.append(check_program)
            if reason is not None:
                command_args.append(reason)
            background(*command_args)

            updates_checked = True
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    return updates_checked

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
        if (os.path.exists(os.path.join(entry, bitcoind())) and
        os.path.exists(os.path.join(entry, bitcoin_cli())) and
        os.path.exists(os.path.join(entry, bitcoind()))):
            bin_dir = entry
            break

    return bin_dir

def get_ok_button():
    '''
        Get a button.

        >>> get_ok_button()
        '&nbsp;&nbsp;<a href="/" name="ok-button" id="ok-id" class="btn btn-secondary" title="Click to return to front page." role="button"> <strong>OK</strong> </a><br/>'
    '''

    return get_button('/', 'OK', 'Click to return to front page.')

def get_button(href, label, tooltip):
    '''
        Get a button.

        >>> get_button("/", "OK", "It's ok to return to front page")
        '&nbsp;&nbsp;<a href="/" name="ok-button" id="ok-id" class="btn btn-secondary" title="It\\'s ok to return to front page" role="button"> <strong>OK</strong> </a><br/>'
    '''

    base = label.replace(' ', '-').replace(',', '').replace("'", '').lower()
    name = f'{base}-button'
    id_tag = f'{base}-id'

    button_tag = '&nbsp;&nbsp;<a href="{}" name="{}" id="{}" class="btn btn-secondary" title="{}" role="button"> <strong>{}</strong> </a><br/>'.format(
      href, name, id_tag, tooltip, label)

    return button_tag
