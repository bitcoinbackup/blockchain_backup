'''
    Copyright 2018-2020 DeNova
    Last modified: 2020-11-08
'''

import os
from subprocess import Popen, TimeoutExpired
from threading import Thread
from time import sleep
from traceback import format_exc

from django.utils.timezone import now

from blockchain_backup.bitcoin import constants, preferences, state
from blockchain_backup.bitcoin.exception import BitcoinException
from blockchain_backup.bitcoin.manager import BitcoinManager
from blockchain_backup.bitcoin.utils import bitcoind, get_ok_button, is_bitcoind_running, need_to_backup
from denova.os.command import background
from denova.os.process import get_pid
from denova.python.log import get_log, get_log_path


class UpdateTask(Thread):
    '''
        Update the blockchain. Stope to backup the
        blockchain according the the user's preferences.
    '''

    STOPPING_UPDATE = 'Waiting for Bitcoin Core to stop'
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

        self.log = get_log()
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
            self.manager.update_progress(self.STOPPING_UPDATE)

            # try to stop bitcoind quickly
            command_args = self.manager.get_bitcoin_cli_cmd('stop')
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
        '''

        ok = need_backup = False
        error_message = None

        self.manager.update_menu(constants.DISABLE_ITEM)

        self.manager.rename_logs()

        try:
            bitcoind_process, bitcoind_pid = self.start_bitcoind()
            if not self.is_interrupted():
                if bitcoind_process is None and bitcoind_pid is None:
                    self.manager.update_notice(self.ERROR_STARTING_BITCOIND)
                    self.manager.update_progress(self.UPDATE_UNEXPECTED_ERROR)
                    ok = False
                else:
                    need_backup = self.wait_while_updating(bitcoind_process)

                ok, error_message = self.stop_bitcoind(
                  bitcoind_process, bitcoind_pid, need_backup)

        except BitcoinException as be:
            ok = False
            error_message = str(be)
            self.log(error_message)

        except: # 'bare except' because it catches more than "except Exception"
            self.log(format_exc())

            # sometimes bitcoin exits with a non-zero return code,
            # but it was still ok, so check the logs
            ok, error_message = self.manager.bitcoin_finished_ok(is_bitcoind_running)

        if ok:
            if not need_backup:
                self.manager.update_progress('&nbsp;')
        elif error_message is not None:
            # don't allow any more backups until the user tells us it's ok
            state.set_backups_enabled(False)
            self.log('error while updating so stopping backups')

            if is_bitcoind_running():
                self.log('retry stopping bitcoind without showing progress')
                self.retry_stopping(show_progress=False)
            self.manager.update_subnotice(f'{self.BITCOIND_ERROR_LABEL} {error_message}')

        return ok, need_backup

    def start_bitcoind(self):
        '''
            Start bitcoind as a daemon.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> need_backup = False
            >>> test_utils.init_database()
            >>> update_task = UpdateTask()
            >>> update_task.manager = BitcoinManager(update_task.log_name)
            >>> bitcoind_process, bitcoind_pid = update_task.start_bitcoind()
            >>> update_task.stop_bitcoind(bitcoind_process, bitcoind_pid, need_backup)
            (False, ' Error opening block database.\\n')
        '''
        if is_bitcoind_running():
            bitcoind_process = None
            bitcoind_pid = get_pid(bitcoind())
            if bitcoind_pid is None:
                sleep(5)
                bitcoind_pid = get_pid(bitcoind())
            self.log(f'bitcoind is already running using pid: {bitcoind_pid}')
        else:
            bitcoind_pid = None
            command_args = []

            if self.manager.bin_dir is None:
                command_args.append(bitcoind())
                ok = True
            else:
                cmd = os.path.join(self.manager.bin_dir, bitcoind())
                command_args.append(cmd)
                ok = os.path.exists(cmd)

            if ok:
                extra_args = preferences.get_extra_args()
                use_test_net = '-testnet' in extra_args

                if self.manager.data_dir is not None:
                    data_dir = self.manager.data_dir
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
                    self.log(f'bitcoind started: {bitcoind_process is not None}')
                except FileNotFoundError as fnfe:
                    raise BitcoinException(str(fnfe))

            else:
                bitcoind_process = None
                self.log(f'{bitcoind()} does not exist in {self.manager.bin_dir}')

        state.set_start_access_time(now())

        return bitcoind_process, bitcoind_pid

    def wait_while_updating(self, bitcoind_process):
        '''
            Wait for the blockchain to be updated.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> update_task = UpdateTask()
            >>> update_task.manager = BitcoinManager(update_task.log_name)
            >>> bitcoind_process, bitcoind_pid = update_task.start_bitcoind()
            >>> need_backup = update_task.wait_while_updating(bitcoind_process)
            >>> print(need_backup)
            False
            >>> update_task.stop_bitcoind(bitcoind_process, bitcoind_pid, need_backup)
            (False, ' Error opening block database.\\n')
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
        while (not is_bitcoind_running() and
               secs < (WAIT_SECONDS*6) and
               not self.is_interrupted()):

            sleep(WAIT_SECONDS)
            secs += WAIT_SECONDS

        self.current_block = self.manager.get_current_block()
        need_backup = need_to_backup(self.manager.data_dir, self.current_block)
        secs_to_wait = get_secs_to_wait()
        while (is_bitcoind_running() and
               not need_backup and
               not self.is_interrupted()):

            try:
                if bitcoind_process is None:
                    sleep(secs_to_wait)
                else:
                    bitcoind_process.wait(secs_to_wait)
            except TimeoutExpired:
                pass

            if is_bitcoind_running() and not self.is_interrupted():
                self.current_block = self.manager.get_current_block()
                need_backup = need_to_backup(self.manager.data_dir, self.current_block)
                secs_to_wait = get_secs_to_wait()

        self.log(f'is_bitcoind_running: {is_bitcoind_running()}')
        self.log(f'need_backup: {need_backup}')
        self.log(f'is_interrupted: {self.is_interrupted()}')
        self.log(f'finished waiting; need backup: {need_backup}')

        return need_backup

    def stop_bitcoind(self, bitcoind_process, bitcoind_pid, need_backup):
        '''
            Stop bitcoind and determine if it ended properly.

            Returns:
                True if shutdown successful; otherwise False.
                Any error message or None.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> need_backup = False
            >>> test_utils.init_database()
            >>> update_task = UpdateTask()
            >>> update_task.manager = BitcoinManager(update_task.log_name)
            >>> bitcoind_process, bitcoind_pid = update_task.start_bitcoind()
            >>> ok, error_message = update_task.stop_bitcoind(bitcoind_process, bitcoind_pid, need_backup)
            >>> print(ok)
            False
            >>> print(error_message)
             Error opening block database.
            <BLANKLINE>
        '''
        def update_progress():
            # only update progress if it hasn't been blanked at an earlier time
            last_progress_update = self.manager.get_last_progress_update()
            if last_progress_update is not None and last_progress_update.strip():
                self.manager.update_progress(self.STOPPING_UPDATE)

        self.manager.update_progress(self.STOPPING_UPDATE)

        self.wait_for_shutdown(bitcoind_process, bitcoind_pid, need_backup)

        self.retry_stopping()

        update_progress()

        ok, error_message, seconds = self.wait_for_status()

        update_progress()

        if not ok:
            self.report_error(bitcoind_process, bitcoind_pid, error_message, seconds)

        if error_message is not None:
            ok = False
            self.manager.update_progress('&nbsp;')

        state.set_last_access_time(now())

        self.log(f'end wait_for_bitcoin: ok: {ok} error: {error_message} bitcoin running: {is_bitcoind_running()}')

        return ok, error_message

    def wait_for_shutdown(self, bitcoind_process, bitcoind_pid, need_backup):
        '''
            Wait for bitcoind to shutdown.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> need_backup = False
            >>> test_utils.init_database()
            >>> update_task = UpdateTask()
            >>> update_task.manager = BitcoinManager(update_task.log_name)
            >>> bitcoind_process, bitcoind_pid = update_task.start_bitcoind()
            >>> update_task.wait_for_shutdown(bitcoind_process, bitcoind_pid, need_backup)
        '''

        try:
            if is_bitcoind_running():
                # get the last block number before we shut down
                self.current_block = self.manager.get_current_block(show_progress=False)
                if need_backup:
                    self.manager.update_subnotice(self.STOP_UPDATE_FOR_BACKUP)
                self.manager.send_bitcoin_cli_cmd('stop', max_attempts=1)

            # wait until bitcoind terminates
            if bitcoind_process is None:
                try:
                    pid, returncode = os.waitpid(bitcoind_pid, os.P_WAIT)
                    self.log(f'waitpid {pid} return code: {returncode}')
                except ChildProcessError:
                    self.log('update_pid already dead')
            else:
                bitcoind_process.wait()
                self.log(f'bitcoind return code: {bitcoind_process.returncode}')
        except: # 'bare except' because it catches more than "except Exception"
            self.log(format_exc())

    def retry_stopping(self, show_progress=True):
        '''
            Retry sending the stop command.
            At times, the process might end, but
            bitcoin itself is still running.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> need_backup = False
            >>> test_utils.init_database()
            >>> update_task = UpdateTask()
            >>> update_task.manager = BitcoinManager(update_task.log_name)
            >>> update_task.retry_stopping()
        '''
        MAX_SECONDS = 30

        seconds = 0
        while is_bitcoind_running():

            sleep(1)
            seconds += 1
            if seconds > MAX_SECONDS:
                seconds = 0
                self.manager.send_bitcoin_cli_cmd('stop')
                if show_progress:
                    self.manager.update_progress(self.STOPPING_UPDATE)

    def wait_for_status(self):
        '''
            Wait for bitcoin to clean up.

            Returns
                True if bitcoin shutdown successfully; otherwise, False.
                Error message from bitcoind if this is one; otherwise, None.
                Seconds waiting.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> need_backup = False
            >>> test_utils.init_database()
            >>> update_task = UpdateTask()
            >>> update_task.manager = BitcoinManager(update_task.log_name)
            >>> update_task.wait_for_status()
            (True, None, 0)
        '''
        WAIT_SECONDS = 10
        MAX_SECONDS = 60

        # if bitcoin is not running, then give it more time to see
        # if the debug log is updated with the status
        seconds = 0
        ok, error_message = self.manager.check_bitcoin_log(is_bitcoind_running)
        while (not ok and
               seconds < MAX_SECONDS and
               not is_bitcoind_running()):

            sleep(WAIT_SECONDS)
            seconds += WAIT_SECONDS
            ok, error_message = self.manager.check_bitcoin_log(is_bitcoind_running)

        if seconds >= MAX_SECONDS:
            self.log(f'waited {seconds} seconds for bitcoin to finish.')
            self.log(f'is_bitcoind_running: {is_bitcoind_running()}')

        return ok, error_message, seconds

    def report_error(self, bitcoind_process, bitcoind_pid, error_message, seconds):
        '''
            Report a serious error about stopping bitcoind.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> update_task = UpdateTask()
            >>> update_task.manager = BitcoinManager(update_task.log_name)
            >>> bitcoind_process, bitcoind_pid = update_task.start_bitcoind()
            >>> need_backup = False
            >>> ok, error_message = update_task.stop_bitcoind(bitcoind_process, bitcoind_pid, need_backup)
            >>> update_task.report_error(bitcoind_process, bitcoind_pid, error_message, 60)
        '''
        # let the user know a serious error has happened
        if is_bitcoind_running():
            if bitcoind_process is None and bitcoind_pid is None:
                if error_message is None:
                    self.manager.update_progress(
                      f'Unable to stop bitcoind after {seconds/60} minutes')
            else:
                if bitcoind_process is None:
                    os.kill(bitcoind_pid, os.SIGTERM)
                else:
                    bitcoind_process.terminate()
                self.log('terminated bitcoin process')
        else:
            # clear the progress because we're no longer
            # waiting for bitcoind to shutdown
            self.manager.update_progress('&nbsp;')

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
        # so give socketio time to connect
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
