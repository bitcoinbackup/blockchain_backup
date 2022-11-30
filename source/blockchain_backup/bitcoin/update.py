'''
    Copyright 2018-2021 DeNova
    Last modified: 2021-07-16
'''

import os
from subprocess import TimeoutExpired
from threading import Thread
from time import sleep
from traceback import format_exc

from blockchain_backup.bitcoin import constants, core_utils, state
from blockchain_backup.bitcoin.backup_utils import need_to_backup
from blockchain_backup.bitcoin.exception import BitcoinException
from blockchain_backup.bitcoin.gen_utils import get_ok_button
from blockchain_backup.bitcoin.handle_cli import get_bitcoin_cli_cmd
from blockchain_backup.bitcoin.manager import BitcoinManager
from denova.os.command import background
from denova.python.log import Log, get_log_path


class UpdateTask(Thread):
    '''
        Update the blockchain. Stope to backup the
        blockchain according the the user's preferences.
    '''

    STOPPED_UPDATE = 'Update stopped on your request'
    STOP_UPDATE_FOR_BACKUP = 'Stopping update so backup can start.'
    UPDATE_UNEXPECTED_ERROR = 'Unexpected error occurred during update.'
    ERROR_STARTING_BITCOIND = 'Unable to start bitcoind -- is Bitcoin-QT or BitcoinD already running?'
    BITCOIND_ERROR = '<br/>&nbsp;The Bitcoin Core program, bitcoind, reported a serious error.'
    BITCOIND_ERROR_LABEL = '<strong>The Bitcoin Core program, bitcoind, Error:</strong>'

    def __init__(self):
        '''
            Initialize the update task.

            >>> update_task = UpdateTask()
            >>> update_task is not None
            True
            >>> update_task.__init__()
            >>> update_task._interrupted
            False
            >>> update_task.manager is None
            True
            >>> update_task.log_name
            'blockchain_backup.bitcoin.update.log'
        '''
        self._interrupted = False
        self.manager = None

        self.log = Log()
        self.log_name = os.path.basename(get_log_path())

        self.current_block = state.get_last_block_updated()

        Thread.__init__(self)

    def interrupt(self):
        '''
            Set to true when user clicks the Stop button.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> update_task = UpdateTask()
            >>> update_task.interrupt()
            >>> update_task._interrupted
            True
        '''
        self._interrupted = True
        if self.manager:
            self.manager.update_progress(constants.STOPPING_UPDATE)

            # try to stop bitcoind quickly
            command_args = get_bitcoin_cli_cmd('stop', self.manager.bin_dir, self.manager.data_dir)
            try:
                background(*command_args)
            # but if it doesn't work, that's ok;
            # more robust efforts will be made elsewhere
            except: # 'bare except' because it catches more than "except Exception"
                self.log(format_exc())

    def is_interrupted(self):
        '''
            Returns true if user clicked the Stop button.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> update_task = UpdateTask()
            >>> update_task.is_interrupted()
            False
        '''
        return self._interrupted

    def run(self):
        '''
            Start the update task.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> update_task = UpdateTask()
            >>> update_task.run()
            >>> update_task.is_interrupted()
            False
        '''

        self.log('started UpdateTask')
        try:
            need_backup = False
            ok = False
            error = None

            self.manager = BitcoinManager(self.log_name)

            if not os.path.exists(self.manager.data_dir):
                os.makedirs(self.manager.data_dir)

            try:
                if self.is_interrupted():
                    ok = True
                    self.log('self interrupted before update started')
                else:
                    # don't start the update if a backup needs to be run
                    UNKNOWN_BLOCKS = -1
                    if need_to_backup(self.manager.data_dir, UNKNOWN_BLOCKS):
                        ok = True
                        need_backup = True
                    else:
                        ok, need_backup = self.update()
            except Exception:
                self.log(format_exc())

            if self.current_block > 0:
                state.set_last_block_updated(self.current_block)

            self.manager.update_menu(constants.ENABLE_ITEM)
            if need_backup and not self.is_interrupted():
                self.log('starting backup')
                self.manager.update_location(constants.BACKUP_URL)
            else:
                self.report_update_stopped(ok, error)

        except: # 'bare except' because it catches more than "except Exception"
            ok = False
            need_backup = False
            self.log(format_exc())

        self.log('ended UpdateTask')

    def update(self):
        '''
            Update the blockchain using bitcoind.

            Returns whether the update ended successfully and
                    whether a backup should start.

            If any errors while running, bitcoind, disable automatic
            backups so the user can decide how to proceed.


            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> update_task = UpdateTask()
            >>> update_task.manager = BitcoinManager(update_task.log_name)
            >>> update_task.update()
            (False, False)
            >>> update_task.is_interrupted()
            False
        '''

        ok = need_backup = False
        error_message = None

        self.manager.update_menu(constants.DISABLE_ITEM)

        core_utils.rename_logs(self.manager.data_dir)

        try:
            bitcoind_process, bitcoind_pid = core_utils.start_bitcoind(self.manager.bin_dir,
                                                                       self.manager.data_dir)
            if not self.is_interrupted():
                if bitcoind_process is None and bitcoind_pid is None:
                    self.manager.update_notice(self.ERROR_STARTING_BITCOIND)
                    self.manager.update_progress(self.UPDATE_UNEXPECTED_ERROR)
                    ok = False
                else:
                    need_backup = self.wait_while_updating(bitcoind_process)

                if core_utils.is_bitcoind_running():
                    if need_backup:
                        self.manager.update_subnotice(self.STOP_UPDATE_FOR_BACKUP)
                    else:
                        self.manager.update_progress(constants.STOPPING_UPDATE)

                    # get the last block number before we shut down
                    self.current_block = self.manager.get_current_block(show_progress=False)
                else:
                    self.manager.update_progress(constants.STOPPING_UPDATE)

                ok, error_message = core_utils.stop_bitcoind(
                                                             bitcoind_process,
                                                             bitcoind_pid,
                                                             self.manager.bin_dir,
                                                             self.manager.data_dir,
                                                             update_progress=self.manager.update_progress)

        except BitcoinException as be:
            ok = False
            error_message = str(be)
            self.log(error_message)

        except: # 'bare except' because it catches more than "except Exception"
            self.log(format_exc())

            # sometimes bitcoin exits with a non-zero return code,
            # but it was still ok, so check the logs
            ok, error_message = core_utils.bitcoin_finished_ok(self.manager.data_dir,
                                                               core_utils.is_bitcoind_running)

        if ok:
            if not need_backup:
                self.manager.update_progress('&nbsp;')
        elif error_message is not None:
            # don't allow any more backups until the user tells us it's ok
            state.set_backups_enabled(False)
            self.log('error while updating so stopping backups')

            if core_utils.is_bitcoind_running():
                self.log('retry stopping bitcoind without showing progress')
                core_utils.retry_stopping(manager.bin_dir, self.manager.data_dir, show_progress=False)
            self.manager.update_subnotice(f'{self.BITCOIND_ERROR_LABEL} {error_message}')

        return ok, need_backup

    def wait_while_updating(self, bitcoind_process):
        '''
            Wait for the blockchain to be updated.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> update_task = UpdateTask()
            >>> update_task.manager = BitcoinManager(update_task.log_name)
            >>> bin_dir = update_task.manager.bin_dir
            >>> data_dir = update_task.manager.data_dir
            >>> bitcoind_process, bitcoind_pid = core_utils.start_bitcoind(bin_dir, data_dir)
            >>> need_backup = update_task.wait_while_updating(bitcoind_process)
            >>> print(need_backup)
            False
            >>> core_utils.stop_bitcoind(bitcoind_process,
            ...                          bitcoind_pid,
            ...                          update_task.manager.bin_dir,
            ...                          update_task.manager.data_dir)
            (False, 'Aborted block database rebuild. Exiting.\\n')
        '''
        def get_secs_to_wait():
            ''' Wait longer if no real data available yet. '''

            if self.current_block > 0:
                secs_to_wait = WAIT_SECONDS
            else:
                secs_to_wait = WAIT_SECONDS * 2

            return secs_to_wait

        WAIT_SECONDS = 30  # seconds

        self.log('waiting while updating blockchain')

        # give the system a few seconds to get it started
        secs = 0
        while (not core_utils.is_bitcoind_running() and
               secs < (WAIT_SECONDS*6) and
               not self.is_interrupted()):

            sleep(WAIT_SECONDS)
            secs += WAIT_SECONDS

        self.current_block = self.manager.get_current_block()
        need_backup = need_to_backup(self.manager.data_dir, self.current_block)
        secs_to_wait = get_secs_to_wait()
        while (core_utils.is_bitcoind_running() and
               not need_backup and
               not self.is_interrupted()):

            try:
                if bitcoind_process is None:
                    sleep(secs_to_wait)
                else:
                    bitcoind_process.wait(secs_to_wait)
            except TimeoutExpired:
                pass

            if core_utils.is_bitcoind_running() and not self.is_interrupted():
                self.current_block = self.manager.get_current_block()
                need_backup = need_to_backup(self.manager.data_dir, self.current_block)
                secs_to_wait = get_secs_to_wait()

        self.log(f'utils.is_bitcoind_running: {core_utils.is_bitcoind_running()}')
        self.log(f'need_backup: {need_backup}')
        self.log(f'is_interrupted: {self.is_interrupted()}')
        self.log(f'finished waiting; need backup: {need_backup}')

        return need_backup

    def update_progress_stopping(self):
        ''' Only update progress if it hasn't been blanked at an earlier time. '''

        last_progress_update = self.manager.get_last_progress_update()
        if last_progress_update is not None and last_progress_update.strip():
            self.manager.update_progress(constants.STOPPING_UPDATE)

    def report_update_stopped(self, ok, error):
        '''
            Report to the user that bitcoind stopped.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> update_task = UpdateTask()
            >>> update_task.manager = BitcoinManager(update_task.log_name)
            >>> ok = False
            >>> update_task.report_update_stopped(ok, 'Unknown error')
        '''
        # a new page might have been displayed
        # so give long polling time to connect
        MAX_SECS = 3

        seconds = 0
        while seconds < MAX_SECS:
            if ok:
                self.log('update stopped')

                self.manager.update_header(self.STOPPED_UPDATE)
                self.manager.notify_done()
            else:
                self.log('bitcoind stopped, updating user that everything is not ok')
                if error is None:
                    self.manager.update_header(constants.RESTORE_BITCOIN)
                    self.manager.update_progress('&nbsp;')

                self.manager.update_notice(f'{self.BITCOIND_ERROR}{get_ok_button()}')

            sleep(1)
            seconds += 1
