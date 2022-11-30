'''
    Utilities for backing up the blockchain.

    Copyright 2018-2022 DeNova
    Last modified: 2022-04-13
'''

import json
import os

from datetime import datetime, timedelta
from shutil import copy, copyfile
from subprocess import Popen, PIPE
from time import sleep
from traceback import format_exc
from zoneinfo import ZoneInfo

from django.core.serializers import serialize
from django.utils.timezone import now

from blockchain_backup.bitcoin import constants, preferences, state
from blockchain_backup.bitcoin.models import State
from blockchain_backup.bitcoin.core_utils import rename_logs
from blockchain_backup.bitcoin.gen_utils import check_for_updates, format_time
from blockchain_backup.settings import DATABASE_NAME, TIME_ZONE
from denova.os import command
from denova.os.osid import is_windows
from denova.os.process import get_pid, is_program_running
from denova.os.user import whoami
from denova.python.log import Log, BASE_LOG_DIR
from denova.python.times import seconds_to_datetime, seconds_human_readable
from denova.python.ve import virtualenv_dir


STARTING = 'Starting to back up the blockchain.'
STARTING_INITIAL = 'Configuring new backup level -- this could take a long time'
FINISHED = 'Finished backup of the blockchain.'
FINISHED_REMINDER = "Finished backing up the blockchain.<p>Don't forget to backup your wallet."
WALLET_REMINDER = 'Do not forget to back up your wallet.'
NO_MEM_ERROR = 'Unable to start backup -- is there enough memory and disk space?'
HEADER_ERROR = 'Error while backing up the blockchain.'
UNEXPECTED_ERROR = 'Unexpected error occurred during backup.'
CONTACT_US = 'Contact support@denova.com'

STOPPING_BACKUP = 'Stopping backup as you requested'
STOPPED_BACKUP_HEADER = "Stopped backing up Bitcoin blockchain"
BACKUP_INCOMPLETE = "Don't forget that the latest backup is incomplete."
DIR_UNUSABLE = 'It cannot be used to restore the blockchain.'
STOPPED_BACKUP_PROGRESS = f'{BACKUP_INCOMPLETE} {DIR_UNUSABLE}'

log = Log()


def prep_backup(data_dir):
    '''
        Prepare to backup.

        Args:
            data_dir: directory where Bitcoin Core's data is stored

        Return:
            to_backup_dir: full path to directory used for current backup
            backup_formatted_time: timestamp when backup started
            backup_level: the backup number (minimum is 1)

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> to_backup_dir, backup_formatted_time, backup_level = prep_backup(data_dir)
        >>> to_backup_dir.startswith('/')
        True
        >>> backup_formatted_time is not None
        True
    '''
    backup_time = now()
    time_stamp = backup_time.isoformat(sep=' ')

    if not rename_logs(data_dir, time_stamp=time_stamp):
        log('no logs to rename')

    backup_formatted_time = format_time(time_stamp)

    to_backup_dir, last_backup_time, backup_level = get_backup_dir_and_time()
    if os.path.exists(to_backup_dir):
        log(f'backup {os.path.basename(to_backup_dir)}')
        log(f'last backed up {last_backup_time}')
    else:
        os.makedirs(to_backup_dir)
        log(f'created new backup dir: {to_backup_dir}')

    # flag that we're using this dir to backup
    add_backup_flag(to_backup_dir, backup_formatted_time)

    # remove the last backup file if it exists
    delete_last_updated_files(to_backup_dir)

    log(f'to_backup_dir {to_backup_dir}')
    log(f'backup_formatted_time {backup_formatted_time}')

    return to_backup_dir, backup_formatted_time, backup_level

def start_backup(data_dir, to_backup_dir):
    '''
        Start backup.

        Args:
            dir_dir: directory where Bitcoin Core's executable live
            data_dir: directory where Bitcoin Core's data is stored
            to_backup_dir: full path to directory used for current backup

        Return:
            backup_process: process number for the backup job
            backup_pid: the pid for the backup job

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> bin_dir = '/tmp/bitcoin/bin'
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> to_backup_dir, backup_formatted_time, backup_level = prep_backup(data_dir)
        >>> backup_process, backup_pid = start_backup(data_dir, to_backup_dir)
        >>> backup_process is not None
        True
        >>> backup_pid is None
        True
        >>> test_utils.stop_backup()
    '''

    bin_dir = os.path.join(virtualenv_dir(), 'bin')

    if not data_dir.endswith(os.sep):
        data_dir += os.sep

    if is_backup_running():
        backup_process = None
        backup_pid = get_pid(constants.BACKUP_PROGRAM)
        log(f'{constants.BACKUP_PROGRAM} is already running using pid: {backup_pid}')
    else:
        backup_pid = None

        args = []
        # "bcb-backup" is a link to safecopy so we can distinguish it when we kill it
        args.append(os.path.join(bin_dir, constants.BACKUP_PROGRAM))
        args.append('--verbose')
        args.append('--quick')
        args.append('--delete')
        args.append('--exclude')
        args.append(get_excluded_files())
        args.append(f'{data_dir}*')
        args.append(to_backup_dir)
        log(f'args: {args}')

        # Popen appears to report "'list' object has no attribute 'split'"
        # the docs state Popen should pass a sequence as the first arg
        backup_process = Popen(args, stdout=PIPE, universal_newlines=True)

    return backup_process, backup_pid

def wait_for_backup(backup_process, is_interrupted, update_progress=None):
    '''
        Wait for the backup to finish and display data while waiting.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> def is_interrupted():
        ...     return False
        >>> bin_dir = '/tmp/bitcoin/bin'
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> to_backup_dir, backup_formatted_time, backup_level = prep_backup(data_dir)
        >>> backup_process, backup_pid = start_backup(data_dir, to_backup_dir)
        >>> backup_process is not None
        True
        >>> backup_pid is None
        True
        >>> wait_for_backup(backup_process, is_interrupted)
        >>> test_utils.stop_backup()
        >>> wait_for_backup(None, is_interrupted)
        >>> test_utils.stop_backup()
    '''
    def show_line(line, update_progress):

        COPYING = '<strong>Copying: </strong>{}'
        VERIFIED = '<strong>Verified: </strong>{}'
        COPYING_START = 'Copying "'
        EQUAL_START = 'already equal: '

        # check safecopy's log to see which files are backed up
        if line is not None:
            show = False

            if COPYING_START in line:
                index = line.rfind(os.sep)
                if index > 0:
                    line = COPYING.format(line[index+1:]).strip('"')
                    log(f'copy line: {line}')
                show = True

            elif EQUAL_START in line:
                index = line.find(EQUAL_START)
                line = VERIFIED.format(line[index+len(EQUAL_START):])
                log(f'verified line: {line}')
                show = True

            if show:
                if update_progress:
                    update_progress(line)
                else:
                    print(line)


    log('starting to wait for backup')

    if backup_process is None:
        log_path = os.path.join(BASE_LOG_DIR, whoami(), 'bcb-backup.log')

        log('waiting until the log appears')
        while (is_backup_running() and not is_interrupted()):
            if not os.path.exists(log_path):
                sleep(1)

        log('displaying backup details')
        while (is_backup_running() and not is_interrupted()):
            with open(log_path, 'rt') as backup_log:
                show_line(backup_log.readline(), update_progress)
    else:
        log('waiting for backup process to finish or be interrupted')
        while backup_process.poll() is None and not is_interrupted():
            show_line(backup_process.stdout.readline(), update_progress)

    if is_interrupted():
        log('waiting for backup interrupted')
    else:
        log('finished waiting for backup')

def stop_backup(backup_process, backup_pid):
    '''
        Stop backup.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> bin_dir = '/tmp/bitcoin/bin'
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> to_backup_dir, backup_formatted_time, backup_level = prep_backup(data_dir)
        >>> backup_process, backup_pid = start_backup(data_dir, to_backup_dir)
        >>> backup_process is not None
        True
        >>> backup_pid is None
        True
        >>> stop_backup(backup_process, backup_pid)
        >>> test_utils.start_fake_backup()
        >>> backup_pid = get_pid(constants.BACKUP_PROGRAM)
        >>> stop_backup(None, backup_pid)
    '''
    try:
        if backup_process is None and backup_pid is not None:
            if is_backup_running():
                bin_dir = os.path.join(virtualenv_dir(), 'bin')
                args = [os.path.join(bin_dir, 'killmatch'),
                        f'"{constants.BACKUP_PROGRAM}"']
                result = command.run(*args).stdout
                log(f'killing backup result: {result}')

            try:
                pid, returncode = os.waitpid(backup_pid, os.P_WAIT)
                log(f'waitpid {pid} return code: {returncode}')
            except ChildProcessError:
                log('backup_pid already dead')
        else:
            # if bcb-backup hasn't stopped yet, then kill it
            if backup_process is None:
                log('not back process active')
            else:
                if backup_process.poll() is None:
                    log('killing backup')
                    backup_process.terminate()

                # wait until backup terminates
                backup_process.wait()
                log(f'backup return code: {backup_process.returncode}')
    except: # 'bare except' because it catches more than "except Exception"
        log(f'error while stopping backup\n{format_exc()}')

def finish_backup(data_dir, to_backup_dir, backup_formatted_time, backup_level):
    '''
        Finish the backup.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> bin_dir = '/tmp/bitcoin/bin'
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> to_backup_dir, backup_formatted_time, backup_level = prep_backup(data_dir)
        >>> backup_process, backup_pid = start_backup(data_dir, to_backup_dir)
        >>> backup_process is not None
        True
        >>> backup_pid is None
        True
        >>> finish_backup(data_dir, to_backup_dir, backup_formatted_time, backup_level)
        >>> test_utils.stop_backup()
    '''

    # make sure all the files starting with dot are copied using
    # standard python because argparse in backup tries to expand the filename
    for entry in os.scandir(data_dir):
        if entry.name.startswith('.') and entry.name != '.walletlock':
            to_path = os.path.join(to_backup_dir, entry.name)
            copyfile(entry.path, to_path)

    # add a last backup file and remove the semaphore file showing we're updating this dir
    last_updated_filename = os.path.join(to_backup_dir, '{}{}'.format(
         constants.LAST_UPDATED_PREFIX, backup_formatted_time))

    with open(last_updated_filename, 'wt') as f:
        f.write(backup_formatted_time)

    updating_filename = get_backup_flag_name(to_backup_dir, backup_formatted_time)

    # save the last backup time in the database
    backup_time = datetime.fromisoformat(backup_formatted_time).replace(tzinfo=ZoneInfo(TIME_ZONE))
    log(f'finished backup: {backup_time}')
    state.set_last_backed_up_time(backup_time)
    state.set_last_backup_level(backup_level)

    save_bcb_database(data_dir, to_backup_dir)

def add_backup_flag(to_backup_dir, backup_formatted_time):
    '''
        Add a flag so we know we were updating this backup dir.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> to_backup_dir, backup_formatted_time, backup_level = prep_backup(data_dir)
        >>> updating_filename = add_backup_flag(to_backup_dir, backup_formatted_time)
        >>> os.path.exists(updating_filename)
        True
    '''
    updating_filename = get_backup_flag_name(to_backup_dir, backup_formatted_time)
    if updating_filename:
        with open(updating_filename, 'wt') as output_file:
            output_file.write(backup_formatted_time)

    return updating_filename

def get_backup_flag_name(to_backup_dir, backup_formatted_time):
    '''
        Add a flag so we know we were updating this backup dir.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> to_backup_dir, backup_formatted_time, backup_level = prep_backup(data_dir)
        >>> get_backup_flag_name(to_backup_dir, backup_formatted_time).startswith('/')
        True
    '''
    if to_backup_dir is None:
        backup_flag_name = None
        log('warning: backup dir not defined so no backup flag file')
    else:
        backup_flag_name = os.path.join(to_backup_dir, '{}{}'.format(
          constants.UPDATING_PREFIX, backup_formatted_time))

    return backup_flag_name

def get_backup_dir_and_time():
    '''
        Get the oldest backup dir or the one
        that's only been partially backed up.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> backup_dirname, oldest_backup_time, backup_level = get_backup_dir_and_time()
        >>> backup_dirname.startswith('/')
        True
        >>> isinstance(oldest_backup_time, datetime)
        True
    '''
    log('getting low level backup dir')

    backup_dirname = None
    oldest_backed_up_time = now() + timedelta(days=1)

    backup_dir = preferences.get_backup_dir()
    if os.path.exists(backup_dir):
        backup_dirname, oldest_backed_up_time = search_entries(
          backup_dir, oldest_backed_up_time)

    else:
        log(f'creating new backup parent: {backup_dir}')
        os.makedirs(backup_dir)
        backup_dirname = os.path.join(backup_dir, '{}{}'.format(
          constants.BACKUPS_LEVEL_PREFIX, '1'))
        oldest_backed_up_time = now()
        log('never backed up')

    i = backup_dirname.find(constants.BACKUPS_LEVEL_PREFIX)
    if i > 0:
        backup_level = int(backup_dirname[i+len(constants.BACKUPS_LEVEL_PREFIX):])
    else:
        backup_level = 0
        log(f'unable to find backup level in {backup_dirname}; i: {i}')
        log(f'oldest_backed_up_time: {oldest_backed_up_time}')

    return backup_dirname, oldest_backed_up_time, backup_level

def search_entries(backup_dir, oldest_backed_up_time):
    '''
        Scan the backup directories.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> backup_dir = '/tmp/bitcoin/data-with-blocks/testnet3/backups/'
        >>> oldest_backup = now() - timedelta(days=10)
        >>> backup_dirname, oldest_backup_time = search_entries(backup_dir, oldest_backup)
        >>> backup_dirname.startswith('/')
        True
        >>> isinstance(oldest_backup_time, datetime)
        True
    '''

    total_backup_levels = 0
    found_partial = False
    backup_dirname = os.path.join(backup_dir, f'{constants.BACKUPS_LEVEL_PREFIX}1')

    entries = os.scandir(backup_dir)
    for entry in entries:
        # look inside each backup level
        if entry.is_dir() and entry.name.startswith(constants.BACKUPS_LEVEL_PREFIX):
            total_backup_levels += 1
            backed_up_time = None
            backup_with_timestamp = False
            filenames = os.listdir(entry.path)
            for filename in filenames:
                # for a partial backup
                if filename.startswith(constants.UPDATING_PREFIX):
                    backup_dirname = entry.path
                    backed_up_time = seconds_to_datetime(os.path.getmtime(entry.path))
                    backup_with_timestamp = True
                    found_partial = True
                    log(f'found a partial updating backup in {entry.name}')
                    break

                # or for the file that includes the last backup date
                elif filename.startswith(constants.LAST_UPDATED_PREFIX):
                    backup_with_timestamp = True
                    older_date_found, oldest_backed_up_time = compare_dates(
                      filename[len(constants.LAST_UPDATED_PREFIX):], oldest_backed_up_time)
                    if older_date_found:
                        backup_dirname = entry.path
                        backed_up_time = oldest_backed_up_time

            # if there is no backup timestamp, then this is a partial backup
            if not backup_with_timestamp:
                found_partial = True

            if not found_partial and backed_up_time is None:
                older_date_found, oldest_backed_up_time = compare_dates(
                  seconds_to_datetime(os.path.getmtime(entry.path)), oldest_backed_up_time)
                if older_date_found:
                    backup_dirname = entry.path
                    backed_up_time = oldest_backed_up_time

        if found_partial:
            break

    if preferences.get_backup_levels() > total_backup_levels and not found_partial:
        backup_dirname = os.path.join(backup_dir, '{}{}'.format(
          constants.BACKUPS_LEVEL_PREFIX, total_backup_levels+1))

    return backup_dirname, oldest_backed_up_time

def compare_dates(backed_up_on, oldest_backed_up_time):
    '''
        Compare the dates to find the oldest one.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> backed_up = now()
        >>> oldest_backup = now() - timedelta(days=10)
        >>> older_date_found, oldest_backed_up_time = compare_dates(
        ...    backed_up, oldest_backup)
        >>> older_date_found
        False
        >>> isinstance(oldest_backed_up_time, datetime)
        True
    '''
    def get_date_with_tz(original_date):
        if original_date.tzinfo is None:
            new_date = original_date.replace(tzinfo=ZoneInfo(TIME_ZONE))
        else:
            new_date = original_date

        return new_date

    older_date_found = False
    oldest_backed_up_time = get_date_with_tz(oldest_backed_up_time)
    if isinstance(backed_up_on, str):
        backed_up_time = get_date_with_tz(datetime.strptime(backed_up_on, '%Y-%m-%d %H:%M'))
    else:
        backed_up_time = get_date_with_tz(backed_up_on)

    if backed_up_time < oldest_backed_up_time:
        oldest_backed_up_time = backed_up_time
        older_date_found = True

    return older_date_found, oldest_backed_up_time

def save_all_metadata(data_dir, to_backup_dir):
    '''
        Save all the metadata for the data dir to a json file.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> to_backup_dir, backup_formatted_time, backup_level = prep_backup(data_dir)
        >>> save_all_metadata(data_dir, to_backup_dir)
        >>> json_filename = os.path.join(to_backup_dir, constants.METADATA_FILENAME)
        >>> os.path.exists(json_filename)
        True
    '''
    root_dir = data_dir
    if not root_dir.endswith(os.sep):
        root_dir += os.sep

    json_filename = os.path.join(to_backup_dir, constants.METADATA_FILENAME)
    with open(json_filename, 'w') as json_file:
        save_metadata(root_dir, root_dir, json_file)

def save_metadata(root_dir, starting_dir, json_file):
    '''
        Save the metadata from the starting_dir.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> to_backup_dir, backup_formatted_time, backup_level = prep_backup(data_dir)
        >>> root_dir = data_dir
        >>> json_filename = os.path.join('/tmp', constants.METADATA_FILENAME)
        >>> with open(json_filename, 'w') as json_file:
        ...     save_metadata(root_dir, data_dir, json_file)
        >>> os.path.exists(json_filename)
        True
    '''

    entries = os.scandir(starting_dir)
    for entry in entries:
        # there's no need to change the status of wallets
        if (entry.name.startswith(constants.DEFAULT_BACKUPS_DIR) or
        entry.name.startswith('wallet') or entry.name == '.walletlock'):

            pass

        else:
            # remove the root dir so if the directory is moved, everything still works
            path = entry.path.replace(root_dir, '')

            stat_result = os.stat(entry.path)
            stats_dict = {'st_mode': stat_result.st_mode,
                          'st_ino': stat_result.st_ino,
                          'st_dev': stat_result.st_dev,
                          'st_nlink': stat_result.st_nlink,
                          'st_uid': stat_result.st_uid,
                          'st_gid': stat_result.st_gid,
                          'st_size': stat_result.st_size,
                          'st_atime': stat_result.st_atime,
                          'st_mtime': stat_result.st_mtime,
                          'st_ctime': stat_result.st_ctime
                         }
            if is_windows():
                stats_dict['st_file_attributes'] = stat_result.st_file_attributes

            file_stats = json.dumps([path, stats_dict])
            json_file.write(f'{file_stats}\n')

            if entry.is_dir() and entry.name != 'wallets':
                save_metadata(root_dir, entry.path, json_file)

def save_bcb_database(data_dir, to_backup_dir):
    '''
        Save the blockchain_backup database.

        >>> from blockchain_backup.settings import DATABASE_NAME
        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> to_backup_dir, backup_formatted_time, backup_level = prep_backup(data_dir)
        >>> blockchain_backup_db_backup_dir = save_bcb_database(data_dir, to_backup_dir)
        >>> blockchain_backup_db_backup_dir is not None
        True
        >>> os.path.exists(os.path.join(blockchain_backup_db_backup_dir, DATABASE_NAME))
        True
    '''
    try:

        if os.path.exists(DATABASE_NAME):
            blockchain_db_dir = os.path.join(data_dir, constants.BLOCKCHAIN_BACKUP_DB_DIR)
            if not os.path.exists(blockchain_db_dir):
                os.makedirs(blockchain_db_dir)
            log(f'copying {DATABASE_NAME} to {blockchain_db_dir}')
            copy(DATABASE_NAME, blockchain_db_dir)

            blockchain_backup_db_backup_dir = os.path.join(
              to_backup_dir, constants.BLOCKCHAIN_BACKUP_DB_DIR)
            if not os.path.exists(blockchain_backup_db_backup_dir):
                os.makedirs(blockchain_backup_db_backup_dir)
            log(f'copying {DATABASE_NAME} to {blockchain_backup_db_backup_dir}')
            copy(DATABASE_NAME, blockchain_backup_db_backup_dir)

            save_state(blockchain_backup_db_backup_dir)
        else:
            log(f'no such file: {DATABASE_NAME}')

        log('saved blockchain_backup database')
    except: # 'bare except' because it catches more than "except Exception"
        # saving the blockchain_backup database is not
        # critical to maintaining the blockchain
        log(format_exc())
        blockchain_backup_db_backup_dir = None

    return blockchain_backup_db_backup_dir

def save_state(blockchain_backup_db_backup_dir):
    '''
        Save the state of the database
        in a json file so it can easily
        be restored.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> data_dir = '/tmp/bitcoin/data/testnet3'
        >>> to_backup_dir, backup_formatted_time, backup_level = prep_backup(data_dir)
        >>> blockchain_backup_db_backup_dir = '/tmp'
        >>> save_state(blockchain_backup_db_backup_dir)
        >>> os.path.exists(os.path.join(blockchain_backup_db_backup_dir, constants.STATE_BACKUP_FILENAME))
        True
    '''
    try:
        data = serialize('json', State.objects.all(), indent=4)
        full_path = os.path.join(blockchain_backup_db_backup_dir, constants.STATE_BACKUP_FILENAME)
        with open(full_path, 'w') as outfile:
            outfile.write(data)
    except: # 'bare except' because it catches more than "except Exception"
        # saving the blockchain_backup state is not
        # critical to maintaining the blockchain
        log(format_exc())

def get_backup_subdir():
    '''
        Get subdir name if its in the data directory.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> get_backup_subdir()
        'backups'
        >>> prefs = preferences.get_preferences()
        >>> prefs.backup_dir = '/tmp/bitcoin/backups'
        >>> preferences.save_preferences(prefs)
        >>> get_backup_subdir() is None
        True
    '''
    data_dir = preferences.get_data_dir()
    backup_dir = preferences.get_backup_dir()

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

def get_next_backup_time():
    '''
        Get the next time we need to backup.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> next_backup_time = get_next_backup_time()
        >>> next_backup_time is not None
        True
    '''
    last_backed_up_time = state.get_last_backed_up_time()
    bkup_schedule = preferences.get_backup_schedule()
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

def is_backup_running():
    '''
        Return True if backup is running.

        >>> is_backup_running()
        False
    '''

    # backup program is a link to safecopy
    return is_program_running(constants.BACKUP_PROGRAM)

def get_excluded_files():
    '''
        Get the files to exclude from backups and restores.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> excluded_paths = get_excluded_files()
        >>> '/tmp/bitcoin/data/testnet3/backups/' in excluded_paths
        True
        >>> 'wallets' in excluded_paths
        True
        >>> 'wallet.da' in excluded_paths
        True
        >>> '.walletlock' in excluded_paths
        True
        >>> 'blockchain_backup_database' in excluded_paths
        True
    '''

    excluded_paths = preferences.get_backup_dir()
    excluded_files = f'wallets,wallet.dat,.walletlock,{constants.BLOCKCHAIN_BACKUP_DB_DIR}'

    use_test_net = constants.TESTNET_FLAG in preferences.get_extra_args()
    if not use_test_net:
        excluded_files += f',{constants.TEST_NET_DIR}'

    # add the subdirectory of the backup if its in the data directory
    backup_subdir = get_backup_subdir()
    if backup_subdir is not None and backup_subdir not in excluded_files:
        excluded_files += f',{backup_subdir}'

    data_dir = preferences.get_data_dir()

    for excluded_file in excluded_files.split(','):
        excluded_path = os.path.join(data_dir, excluded_file)
        if excluded_path not in excluded_paths:
            excluded_paths += ','
            excluded_paths += excluded_path

    return excluded_paths

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
