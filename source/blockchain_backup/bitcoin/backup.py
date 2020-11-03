'''
    Back up the blockchain.

    Copyright 2018-2020 DeNova
    Last modified: 2020-10-29
'''

import json
import os
from datetime import datetime, timedelta
from shutil import copy, copyfile
from subprocess import CalledProcessError, Popen, PIPE
from threading import Thread
from time import sleep
from traceback import format_exc
from django.core.serializers import serialize
from django.utils.timezone import now
from pytz import timezone

from blockchain_backup.bitcoin import constants, state
from blockchain_backup.bitcoin.manager import BitcoinManager
from blockchain_backup.bitcoin.models import State
from blockchain_backup.bitcoin.preferences import get_backup_dir, get_backup_levels
from blockchain_backup.bitcoin.utils import get_excluded_files, is_backup_running
from blockchain_backup.bitcoin import utils as bitcoin_utils
from blockchain_backup.settings import DEBUG, DATABASE_PATH, TIME_ZONE
from denova.os import command
from denova.os.osid import is_windows
from denova.os.process import get_pid
from denova.python.log import get_log, get_log_path
from denova.python.times import seconds_to_datetime
from denova.python.ve import virtualenv_dir


class BackupTask(Thread):
    '''
        Backup the blockchain.
    '''
    STARTING = 'Starting to back up the blockchain.'
    STARTING_INITIAL = 'Configuring new backup level -- this could take a long time'
    COPYING = '<strong>Copying: </strong>{}'
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

    def __init__(self):
        '''
            Initialize the backup task.

            >>> backup_task = BackupTask()
            >>> backup_task is not None
            True
            >>> backup_task.__init__()
            >>> type(backup_task.locale_tz)
            <class 'pytz.tzfile.Atlantic/Reykjavik'>
            >>> backup_task._interrupted
            False
            >>> backup_task.manager is None
            True
            >>> backup_task.log_name
            'blockchain_backup.bitcoin.backup.log'
        '''
        Thread.__init__(self)

        self._interrupted = False

        self.log = get_log()
        self.log_name = os.path.basename(get_log_path())

        self.manager = None
        self.to_backup_dir = None
        self.backup_level = 1
        self.backup_formatted_time = None

        self.locale_tz = timezone(TIME_ZONE)

    def interrupt(self):
        '''
            Set to true when user clicks the Stop button.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.interrupt()
            >>> backup_task._interrupted
            True
        '''
        self._interrupted = True
        if self.manager:
            self.manager.update_progress(self.STOPPING_BACKUP)

    def is_interrupted(self):
        '''
            Returns true if user clicked the Stop button.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.is_interrupted()
            False
        '''
        return self._interrupted

    def run(self):
        '''
            Start the backup task.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.run()
            True
            >>> backup_task.is_interrupted()
            False
        '''

        self.log('started BackupTask')

        ok = True
        try:
            self.manager = BitcoinManager(self.log_name)
            self.manager.update_menu(constants.DISABLE_ITEM)

            # be sure to check for updates regularly
            bitcoin_utils.check_for_updates()

            ok = self.backup()
            if self.is_interrupted():
                self.interrupt_backup()

            else:
                if ok:
                    self.manager.update_header(self.FINISHED)
                    self.manager.update_notice(self.WALLET_REMINDER)
                    self.manager.update_subnotice('')
                    self.manager.update_menu(constants.ENABLE_ITEM)

                    self.log('starting to update the blockchain')
                    self.manager.update_location(constants.SYNC_URL)
                else:
                    notice_and_button = '{}{}'.format(
                      constants.CLOSE_WINDOW_NOW, bitcoin_utils.get_ok_button())
                    self.manager.update_header(self.HEADER_ERROR)
                    self.manager.update_notice(notice_and_button)
                    self.manager.update_subnotice(self.CONTACT_US)
                    self.manager.update_progress('')
                    self.manager.update_menu(constants.ENABLE_ITEM)

        except: # 'bare except' because it catches more than "except Exception"
            ok = False
            error = format_exc()
            self.log(error)
            if self.manager:
                self.manager.update_notice(self.UNEXPECTED_ERROR)
                if DEBUG:
                    self.manager.update_progress(error)
                else:
                    self.manager.update_progress('&nbsp;')
                self.manager.update_menu(constants.ENABLE_ITEM)

        self.log('finished BackupTask')

        return ok

    def backup(self):
        '''
            Backup now regardless when the last backup ran.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_task.backup()
            True
            >>> backup_task.is_interrupted()
            False
        '''
        ok = True

        if not os.path.exists(self.manager.data_dir):
            os.makedirs(self.manager.data_dir)

        self.manager.update_progress(self.STARTING)

        if not self.is_interrupted():
            self.prep_backup()

        try:
            backup_process = backup_pid = None

            if not self.is_interrupted():
                self.log('starting backup')
                backup_process, backup_pid = self.start_backup()

            if backup_process is not None or backup_pid is not None:

                if not self.is_interrupted():
                    self.wait_for_backup(backup_process)

                if not self.is_interrupted():
                    self.stop_backup(backup_process, backup_pid)

            else:
                self.manager.update_progress(self.NO_MEM_ERROR)
                ok = False

            if not self.is_interrupted():
                self.finish_backup()
        except: # 'bare except' because it catches more than "except Exception"
            self.add_backup_flag()
            ok = False
            self.log(format_exc())

        if ok and not self.is_interrupted():
            self.save_all_metadata()
            self.log('saved all metadata')

        if ok and not self.is_interrupted():
            # remove the old debug logs; we back them up in case there's an error
            for entry in os.scandir(self.manager.data_dir):
                if entry.name.startswith(constants.DEBUG_PREFIX) and \
                entry.name.endswith(constants.LOG_SUFFIX):
                    os.remove(entry.path)
            self.manager.update_subnotice('')
            self.manager.update_progress(self.FINISHED_REMINDER)

        return ok

    def prep_backup(self):
        '''
            Prepare to backup.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_task.prep_backup()
            >>> backup_task.backup_formatted_time is not None
            True
            >>> backup_task.to_backup_dir.startswith('/')
            True
        '''
        backup_time = now()
        time_stamp = backup_time.isoformat(sep=' ')

        if not self.manager.rename_logs(time_stamp=time_stamp):
            self.log('no logs to rename')

        self.backup_formatted_time = bitcoin_utils.format_time(time_stamp)

        self.to_backup_dir, last_backup_time = self.get_backup_dir_and_time()
        if os.path.exists(self.to_backup_dir):
            self.manager.update_progress(self.STARTING)
            self.log(f'backup {os.path.basename(self.to_backup_dir)}')
            self.log(f'last backed up {last_backup_time}')
        else:
            self.manager.update_progress(self.STARTING_INITIAL)
            os.makedirs(self.to_backup_dir)
            self.log(f'created new backup dir: {self.to_backup_dir}')

        # flag that we're using this dir to backup
        self.add_backup_flag()

        # remove the last backup file if it exists
        bitcoin_utils.delete_last_updated_files(self.to_backup_dir)

    def start_backup(self):
        '''
            Start backup.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_task.prep_backup()
            >>> backup_process, backup_pid = backup_task.start_backup()
            >>> backup_process is not None
            True
            >>> backup_pid is None
            True
            >>> test_utils.stop_backup()
        '''
        bin_dir = os.path.join(virtualenv_dir(), 'bin')
        data_dir = self.manager.data_dir
        if not data_dir.endswith(os.sep):
            data_dir += os.sep

        if is_backup_running():
            backup_process = None
            backup_pid = get_pid(constants.BACKUP_PROGRAM)
            self.log('{} is already running using pid: {}'.format(
              constants.BACKUP_PROGRAM, backup_pid))
        else:
            backup_pid = None

            args = []
            # "bcb-backup" is a link to safecopy so we can distinguish it when we kill it
            args.append(os.path.join(bin_dir, constants.BACKUP_PROGRAM))
            args.append('--exclude')
            args.append(get_excluded_files())
            args.append('--verbose')
            args.append('--quick')
            args.append('--delete')
            args.append(f'{data_dir}*')
            args.append(self.to_backup_dir)

            # Popen appears to report "'list' object has no attribute 'split'"
            # the docs state Popen should pass a sequence as the first arg
            backup_process = Popen(args, stdout=PIPE, universal_newlines=True)

        return backup_process, backup_pid

    def wait_for_backup(self, backup_process):
        '''
            Wait for the backup to finish and display data while waiting.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_task.prep_backup()
            >>> backup_process, backup_pid = backup_task.start_backup()
            >>> backup_process is not None
            True
            >>> backup_pid is None
            True
            >>> backup_task.wait_for_backup(backup_process)
            >>> test_utils.stop_backup()
            >>> backup_task.wait_for_backup(None)
            >>> test_utils.stop_backup()
        '''
        def show_line(line):
            if line is not None and line.startswith('Copying:'):
                index = line.rfind(os.sep)
                if index > 0:
                    line = self.COPYING.format(line[index+1:])
                self.manager.update_progress(line)


        self.log('starting to wait for backup')

        if backup_process is None:
            log_path = '/tmp/safecopy.log'

            # wait until the log appears
            while (is_backup_running() and
                   not self.is_interrupted()):
                if not os.path.exists(log_path):
                    sleep(1)

            # then display the backup details
            while (is_backup_running() and
                   not self.is_interrupted()):
                with open(log_path, 'rt') as backup_log:
                    show_line(backup_log.readline())
        else:
            while (backup_process.poll() is None and
                   not self.is_interrupted()):
                show_line(backup_process.stdout.readline())

        if self.is_interrupted():
            self.log('waiting for backup interrupted')
        else:
            self.log('finished waiting for backup')

    def stop_backup(self, backup_process, backup_pid):
        '''
            Stop backup.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_task.prep_backup()
            >>> backup_process, backup_pid = backup_task.start_backup()
            >>> backup_process is not None
            True
            >>> backup_pid is None
            True
            >>> backup_task.stop_backup(backup_process, backup_pid)
            >>> test_utils.start_fake_backup()
            >>> backup_pid = get_pid(constants.BACKUP_PROGRAM)
            >>> backup_task.stop_backup(None, backup_pid)
        '''
        try:
            if backup_process is None and backup_pid is not None:
                if is_backup_running():
                    bin_dir = os.path.join(virtualenv_dir(), 'bin')
                    args = [os.path.join(bin_dir, 'killmatch'),
                            '"{} --exclude {}"'.format(
                             constants.BACKUP_PROGRAM, get_excluded_files())]
                    result = command.run(*args).stdout
                    self.log(f'killing backup result: {result}')

                try:
                    pid, returncode = os.waitpid(backup_pid, os.P_WAIT)
                    self.log(f'waitpid {pid} return code: {returncode}')
                except ChildProcessError:
                    self.log('backup_pid already dead')
            else:
                # if bcb-backup hasn't stopped yet, then kill it
                if backup_process is None:
                    self.log('not back process active')
                else:
                    if backup_process.poll() is None:
                        self.log('killing backup')
                        backup_process.terminate()

                    # wait until backup terminates
                    backup_process.wait()
                    self.log(f'backup return code: {backup_process.returncode}')
        except: # 'bare except' because it catches more than "except Exception"
            self.log(f'error while stopping backup\n{format_exc()}')

    def finish_backup(self):
        '''
            Finish the backup.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_task.prep_backup()
            >>> backup_process, backup_pid = backup_task.start_backup()
            >>> backup_process is not None
            True
            >>> backup_pid is None
            True
            >>> backup_task.finish_backup()
            >>> test_utils.stop_backup()
        '''

        # make sure all the files starting with dot are copied using
        # standard python because argparse in backup tries to expand the filename
        for entry in os.scandir(self.manager.data_dir):
            if entry.name.startswith('.') and entry.name != '.walletlock':
                to_path = os.path.join(self.to_backup_dir, entry.name)
                copyfile(entry.path, to_path)

        # add a last backup file and remove the semaphore file showing we're updating this dir
        last_updated_filename = os.path.join(self.to_backup_dir, '{}{}'.format(
             constants.LAST_UPDATED_PREFIX, self.get_backup_formatted_time()))
        with open(last_updated_filename, 'wt') as f:
            f.write(self.get_backup_formatted_time())

        updating_filename = self.get_backup_flag_name()
        if updating_filename and os.path.exists(updating_filename):
            os.remove(updating_filename)

        # save the last backup time in the database
        backup_time = datetime.strptime(self.get_backup_formatted_time(), '%Y-%m-%d %H:%M')
        state.set_last_backed_up_time(self.locale_tz.localize(backup_time))
        state.set_last_backup_level(self.backup_level)

        self.save_bcb_database()

    def interrupt_backup(self):
        '''
            End user interrupts the backup.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_task.prep_backup()
            >>> backup_process, backup_pid = backup_task.start_backup()

            >>> test_utils.start_fake_backup()
            >>> backup_task.interrupt_backup()
            True
        '''

        MAX_SECS = 3

        seconds = 0

        self.log('interrupting backup')
        if self.to_backup_dir is not None:
            # remove all files that suggest this backup is complete
            bitcoin_utils.delete_last_updated_files(self.to_backup_dir)
            # add a flag that we started to use this dir to backup
            self.add_backup_flag()

        try:
            bin_dir = os.path.join(virtualenv_dir(), 'bin')
            args = [os.path.join(bin_dir, 'killmatch'), constants.BACKUP_PROGRAM]

            attempts = 0
            while is_backup_running() and attempts < 3:
                result = command.run(*args).stdout
                self.log(f'result of stopping backup: {result}')
                if is_backup_running():
                    sleep(3)
                    attempts += 1
        except CalledProcessError as cpe:
            self.log(cpe)
            self.log(format_exc())

        # a new page was displayed so give socketio time to connect
        while seconds < MAX_SECS:
            self.manager.update_header(self.STOPPED_BACKUP_HEADER)
            self.manager.update_progress(self.STOPPED_BACKUP_PROGRESS)
            self.manager.notify_close_window()

            sleep(1)
            seconds += 1

        # return value is for testing purposes only
        return not bitcoin_utils.is_backup_running()

    def add_backup_flag(self):
        '''
            Add a flag so we know we were updating this backup dir.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_task.prep_backup()
            >>> updating_filename = backup_task.add_backup_flag()
            >>> os.path.exists(updating_filename)
            True
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> updating_filename = backup_task.add_backup_flag()
            >>> updating_filename is None
            True
        '''
        updating_filename = self.get_backup_flag_name()
        if updating_filename:
            with open(updating_filename, 'wt') as output_file:
                output_file.write(self.get_backup_formatted_time())

        return updating_filename

    def get_backup_flag_name(self):
        '''
            Add a flag so we know we were updating this backup dir.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_task.get_backup_flag_name() is None
            True
            >>> backup_task.prep_backup()
            >>> backup_task.get_backup_flag_name().startswith('/')
            True
        '''
        if self.to_backup_dir is None:
            backup_flag_name = None
            self.log('warning: backup dir not defined so no backup flag file')
        else:
            backup_flag_name = os.path.join(self.to_backup_dir, '{}{}'.format(
              constants.UPDATING_PREFIX, self.get_backup_formatted_time()))

        return backup_flag_name

    def get_backup_formatted_time(self):
        '''
            Get the formatted time for the backup.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_task.get_backup_formatted_time() is not None
            True
        '''

        if self.backup_formatted_time is None:
            backup_time = now()
            self.log(f'backup_time: {backup_time}')
            self.backup_formatted_time = bitcoin_utils.format_time(backup_time.isoformat(sep=' '))
            self.log(f'backup_formatted time: {self.backup_formatted_time}')

        return self.backup_formatted_time

    def get_backup_dir_and_time(self):
        '''
            Get the oldest backup dir or the one
            that's only been partially backed up.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_dirname, oldest_backup_time = backup_task.get_backup_dir_and_time()
            >>> backup_dirname.startswith('/')
            True
            >>> isinstance(oldest_backup_time, datetime)
            True
        '''
        self.log('getting low level backup dir')

        backup_dirname = None
        oldest_backed_up_time = now() + timedelta(days=1)

        backup_dir = get_backup_dir()
        if os.path.exists(backup_dir):
            backup_dirname, oldest_backed_up_time = self.search_entries(
              backup_dir, oldest_backed_up_time)

        else:
            self.log(f'creating new backup parent: {backup_dir}')
            os.makedirs(backup_dir)
            backup_dirname = os.path.join(backup_dir, '{}{}'.format(
              constants.BACKUPS_LEVEL_PREFIX, '1'))
            oldest_backed_up_time = now()
            self.log('never backed up')

        i = backup_dirname.find(constants.BACKUPS_LEVEL_PREFIX)
        if i > 0:
            self.backup_level = int(backup_dirname[i+len(constants.BACKUPS_LEVEL_PREFIX):])

        self.log(f'backup dirname: {backup_dirname}')
        self.log(f'oldest_backed_up_time: {oldest_backed_up_time}')
        return backup_dirname, oldest_backed_up_time

    def search_entries(self, backup_dir, oldest_backed_up_time):
        '''
            Scan the backup directories.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_dir = '/tmp/bitcoin/data-with-blocks/testnet3/backups/'
            >>> oldest_backup = now() - timedelta(days=10)
            >>> backup_dirname, oldest_backup_time = backup_task.search_entries(
            ...    backup_dir, oldest_backup)
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
                        self.log(f'found a partial updating backup in {entry.name}')
                        break

                    # or for the file that includes the last backup date
                    elif filename.startswith(constants.LAST_UPDATED_PREFIX):
                        backup_with_timestamp = True
                        older_date_found, oldest_backed_up_time = self.compare_dates(
                          filename[len(constants.LAST_UPDATED_PREFIX):], oldest_backed_up_time)
                        if older_date_found:
                            backup_dirname = entry.path
                            backed_up_time = oldest_backed_up_time

                # if there is no backup timestamp, then this is a partial backup
                if not backup_with_timestamp:
                    found_partial = True

                if not found_partial and backed_up_time is None:
                    older_date_found, oldest_backed_up_time = self.compare_dates(
                      seconds_to_datetime(os.path.getmtime(entry.path)), oldest_backed_up_time)
                    if older_date_found:
                        backup_dirname = entry.path
                        backed_up_time = oldest_backed_up_time

            if found_partial:
                break

        if get_backup_levels() > total_backup_levels and not found_partial:
            backup_dirname = os.path.join(backup_dir, '{}{}'.format(
              constants.BACKUPS_LEVEL_PREFIX, total_backup_levels+1))

        return backup_dirname, oldest_backed_up_time

    def compare_dates(self, backed_up_on, oldest_backed_up_time):
        '''
            Compare the dates to find the oldest one.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backed_up = now()
            >>> oldest_backup = now() - timedelta(days=10)
            >>> older_date_found, oldest_backed_up_time = backup_task.compare_dates(
            ...    backed_up, oldest_backup)
            >>> older_date_found
            False
            >>> isinstance(oldest_backed_up_time, datetime)
            True
        '''
        def get_date_with_tz(original_date):
            try:
                new_date = self.locale_tz.localize(original_date)
            except: # 'bare except' because it catches more than "except Exception"
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

    def save_all_metadata(self):
        '''
            Save all the metadata for the data dir to a json file.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_task.prep_backup()
            >>> backup_task.save_all_metadata()
            >>> json_filename = os.path.join(backup_task.to_backup_dir,
            ...                              constants.METADATA_FILENAME)
            >>> os.path.exists(json_filename)
            True
        '''
        root_dir = self.manager.data_dir
        if not root_dir.endswith(os.sep):
            root_dir += os.sep

        json_filename = os.path.join(self.to_backup_dir, constants.METADATA_FILENAME)
        with open(json_filename, 'w') as json_file:
            self.save_metadata(root_dir, root_dir, json_file)

    def save_metadata(self, root_dir, starting_dir, json_file):
        '''
            Save the metadata from the starting_dir.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_task.prep_backup()
            >>> root_dir = backup_task.manager.data_dir
            >>> json_filename = os.path.join('/tmp', constants.METADATA_FILENAME)
            >>> with open(json_filename, 'w') as json_file:
            ...     backup_task.save_metadata(root_dir, root_dir, json_file)
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
                    self.save_metadata(root_dir, entry.path, json_file)

    def save_bcb_database(self):
        '''
            Save the blockchain_backup database.

            >>> from blockchain_backup.settings import DATABASE_NAME
            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_task.prep_backup()
            >>> blockchain_backup_db_backup_dir = backup_task.save_bcb_database()
            >>> blockchain_backup_db_backup_dir is not None
            True
            >>> os.path.exists(os.path.join(blockchain_backup_db_backup_dir, DATABASE_NAME))
            True
        '''
        try:
            database_filename = DATABASE_PATH
            blockchain_backup_db_backup_dir = os.path.join(
              self.to_backup_dir, constants.BLOCKCHAIN_BACKUP_DB_DIR)
            self.log(f'copying {database_filename} to {blockchain_backup_db_backup_dir}')

            if os.path.exists(database_filename):
                if not os.path.exists(blockchain_backup_db_backup_dir):
                    os.makedirs(blockchain_backup_db_backup_dir)

                copy(database_filename, blockchain_backup_db_backup_dir)

                self.save_state(blockchain_backup_db_backup_dir)
            else:
                self.log(f'no such file: {database_filename}')

            self.log('saved blockchain_backup database')
        except: # 'bare except' because it catches more than "except Exception"
            # saving the blockchain_backup database is not
            # critical to maintaining the blockchain
            self.log(format_exc())
            blockchain_backup_db_backup_dir = None

        return blockchain_backup_db_backup_dir

    def save_state(self, blockchain_backup_db_backup_dir):
        '''
            Save the state of the database
            in a json file so it can easily
            be restored.

            >>> from blockchain_backup.settings import DATABASE_NAME
            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_task.prep_backup()
            >>> blockchain_backup_db_backup_dir = '/tmp'
            >>> backup_task.save_state(blockchain_backup_db_backup_dir)
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
            self.log(format_exc())
