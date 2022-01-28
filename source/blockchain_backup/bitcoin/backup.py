'''
    Back up the blockchain.

    Copyright 2018-2022 DeNova
    Last modified: 2022-01-12
'''

import os
from subprocess import CalledProcessError
from threading import Thread
from time import sleep
from traceback import format_exc
from zoneinfo import ZoneInfo

from blockchain_backup.bitcoin import backup_utils, constants
from blockchain_backup.bitcoin.manager import BitcoinManager
from blockchain_backup.bitcoin.gen_utils import check_for_updates, get_ok_button
from blockchain_backup.settings import DEBUG, TIME_ZONE
from denova.os import command
from denova.python.log import Log, get_log_path
from denova.python.ve import virtualenv_dir


class BackupTask(Thread):
    '''
        Backup the blockchain.
    '''

    def __init__(self):
        '''
            Initialize the backup task.

            >>> backup_task = BackupTask()
            >>> backup_task is not None
            True
            >>> backup_task.__init__()
            >>> type(backup_task.locale_tz)
            <class 'zoneinfo.ZoneInfo.Atlantic/Reykjavik'>
            >>> backup_task._interrupted
            False
            >>> backup_task.manager is None
            True
            >>> backup_task.log_name
            'blockchain_backup.bitcoin.backup.log'
        '''
        Thread.__init__(self)

        self._interrupted = False

        self.log = Log()
        self.log_name = os.path.basename(get_log_path())

        self.manager = None
        self.to_backup_dir = None
        self.backup_formatted_time = None

        self.locale_tz = ZoneInfo(TIME_ZONE)

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
            self.manager.update_progress(backup_utils.STOPPING_BACKUP)

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
            check_for_updates()

            ok = self.backup()
            if self.is_interrupted():
                self.interrupt_backup()

            else:
                if ok:
                    self.manager.update_header(backup_utils.FINISHED)
                    self.manager.update_notice(backup_utils.WALLET_REMINDER)
                    self.manager.update_subnotice('')
                    self.manager.update_menu(constants.ENABLE_ITEM)

                    self.log('starting to update the blockchain')
                    self.manager.update_location(constants.SYNC_URL)
                else:
                    notice_and_button = '{}{}'.format(
                      constants.CLOSE_WINDOW_NOW, get_ok_button())
                    self.manager.update_header(backup_utils.HEADER_ERROR)
                    self.manager.update_notice(notice_and_button)
                    self.manager.update_subnotice(backup_utils.CONTACT_US)
                    self.manager.update_progress('')
                    self.manager.update_menu(constants.ENABLE_ITEM)

        except: # 'bare except' because it catches more than "except Exception"
            ok = False
            error = format_exc()
            self.log(error)
            if self.manager:
                self.manager.update_notice(backup_utils.UNEXPECTED_ERROR)
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
        backup_level = 1

        if not os.path.exists(self.manager.data_dir):
            os.makedirs(self.manager.data_dir)

        self.manager.update_progress(backup_utils.STARTING)

        if not self.is_interrupted():
            result = backup_utils.prep_backup(self.manager.data_dir)
            self.to_backup_dir, self.backup_formatted_time, backup_level = result
            if os.path.exists(self.to_backup_dir):
                self.manager.update_progress(backup_utils.STARTING)
            else:
                self.manager.update_progress(backup_utils.STARTING_INITIAL)

        try:
            backup_process = backup_pid = None

            if not self.is_interrupted():
                self.log('starting backup')
                backup_process, backup_pid = backup_utils.start_backup(self.manager.data_dir,
                                                                       self.to_backup_dir)

            if backup_process is not None or backup_pid is not None:

                if not self.is_interrupted():
                    backup_utils.wait_for_backup(backup_process,
                                                 self.is_interrupted,
                                                 update_progress=self.manager.update_progress)

                if not self.is_interrupted():
                    backup_utils.stop_backup(backup_process, backup_pid)

            else:
                self.manager.update_progress(backup_utils.NO_MEM_ERROR)
                ok = False

            if not self.is_interrupted():
                backup_utils.finish_backup(self.manager.data_dir,
                                            self.to_backup_dir,
                                            self.backup_formatted_time,
                                            backup_level)

        except: # 'bare except' because it catches more than "except Exception"
            backup_utils.add_backup_flag(self.to_backup_dir, self.backup_formatted_time)
            ok = False
            self.log(format_exc())

        if ok and not self.is_interrupted():
            backup_utils.save_all_metadata(self.manager.data_dir, self.to_backup_dir)
            self.log('saved all metadata')

        if ok and not self.is_interrupted():
            # remove the old debug logs; we back them up in case there's an error
            for entry in os.scandir(self.manager.data_dir):
                if entry.name.startswith(constants.DEBUG_PREFIX) and \
                   entry.name.endswith(constants.LOG_SUFFIX):
                    os.remove(entry.path)
            self.manager.update_subnotice('')
            self.manager.update_progress(backup_utils.FINISHED_REMINDER)

        return ok

    def interrupt_backup(self):
        '''
            End user interrupts the backup.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> backup_task = BackupTask()
            >>> backup_task.manager = BitcoinManager(backup_task.log_name)
            >>> backup_task.to_backup_dir, backup_task.backup_formatted_time, __ = backup_utils.prep_backup(backup_task.manager.data_dir)
            >>> backup_process, backup_pid = backup_utils.start_backup(backup_task.manager.data_dir,
            ...                                                        backup_task.to_backup_dir)
            >>> test_utils.start_fake_backup()
            >>> backup_task.interrupt_backup()
            True
        '''

        MAX_SECS = 3

        seconds = 0

        self.log('interrupting backup')
        if self.to_backup_dir is not None:
            # remove all files that suggest this backup is complete
            backup_utils.delete_last_updated_files(self.to_backup_dir)
            # add a flag that we started to use this dir to backup
            backup_utils.add_backup_flag(self.to_backup_dir, self.backup_formatted_time)

        try:
            bin_dir = os.path.join(virtualenv_dir(), 'bin')
            args = [os.path.join(bin_dir, 'killmatch'), constants.BACKUP_PROGRAM]

            attempts = 0
            while backup_utils.is_backup_running() and attempts < 3:
                result = command.run(*args).stdout
                self.log(f'result of stopping backup: {result}')
                if backup_utils.is_backup_running():
                    sleep(3)
                    attempts += 1
        except CalledProcessError as cpe:
            self.log(cpe)
            self.log(format_exc())

        while seconds < MAX_SECS:
            self.manager.update_header(backup_utils.STOPPED_BACKUP_HEADER)
            self.manager.update_progress(backup_utils.STOPPED_BACKUP_PROGRESS)
            self.manager.notify_close_window()

            sleep(1)
            seconds += 1

        # return value is for testing purposes only
        return not backup_utils.is_backup_running()
