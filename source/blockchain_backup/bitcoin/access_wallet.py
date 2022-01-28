'''
    Front end to running bitcoin-qt.

    Copyright 2018-2022 DeNova
    Last modified: 2022-01-25
'''

import os
from subprocess import CalledProcessError, Popen, TimeoutExpired
from threading import Thread
from time import sleep
from traceback import format_exc
from django.utils.timezone import now

from blockchain_backup.bitcoin import constants, core_utils, preferences, state
from blockchain_backup.bitcoin.backup_utils import need_to_backup
from blockchain_backup.bitcoin.exception import BitcoinException
from blockchain_backup.bitcoin.gen_utils import get_ok_button
from blockchain_backup.bitcoin.handle_cli import process_bitcoin_cli_error
from blockchain_backup.bitcoin.manager import BitcoinManager
from blockchain_backup.settings import DEBUG
from denova.os.process import get_pid
from denova.python.log import Log, get_log_path


class AccessWalletTask(Thread):
    '''
        Run bitcoin-qt. If it's scheduled, backup
        the blockchain when the user ends the bitcoint-qt.
    '''

    BITCOIN_QT_RUNNING = 'Is BitcoinD or another copy of BitcoinQT already running?'
    BITCOIN_QT_OTHER_APP_RUNNING = f'Unable to start BitcoinQT. {BITCOIN_QT_RUNNING}'
    BITCOIN_QT_ERROR = '<br/>Bitcoin-QT reported a serious error.<br/>&nbsp;'
    BITCOIN_QT_ERROR_LABEL = '<strong>Bitcoin-QT Error:</strong>'
    BITCOIN_QT_UNEXPECTED_ERROR = 'Unexpected error occurred while running Bitcoin Core QT.'

    def __init__(self):
        Thread.__init__(self)

        self.log = Log()
        self.log_name = os.path.basename(get_log_path())

        self.manager = None

        self.current_block = state.get_last_block_updated()

    def run(self):

        self.log('started AccessWalletTask')
        ok = need_backup = False
        error_message = None
        try:
            self.manager = BitcoinManager(self.log_name)
            self.manager.update_menu(constants.DISABLE_ITEM)

            if not os.path.exists(self.manager.data_dir):
                os.makedirs(self.manager.data_dir)

            ok, error_message = self.run_qt()

            if ok:
                need_backup = need_to_backup(self.manager.data_dir, self.current_block)
                if need_backup:
                    self.log('need to backup')
                    self.manager.update_location(constants.BACKUP_URL)
                else:
                    self.log('continuing to update blockchain')
                    self.manager.update_location(constants.SYNC_URL)
            else:
                # don't allow any more backups until the user tells us it's ok
                state.set_backups_enabled(False)

                if error_message is None:
                    self.log('unexpected error')
                    if DEBUG:
                        notice = format_exc()
                    else:
                        notice = self.BITCOIN_QT_UNEXPECTED_ERROR

                    self.manager.update_progress(f'{notice} {get_ok_button()}')
                else:
                    self.log('bitcoin-qt error')
                    notice_and_button = f'{constants.RESTORE_BITCOIN}{get_ok_button()}'
                    self.manager.update_header(self.BITCOIN_QT_ERROR)
                    self.manager.update_notice(notice_and_button)
                    self.manager.update_subnotice(error_message)
                self.manager.update_menu(constants.ENABLE_ITEM)

        except Exception:
            need_backup = False
            error = format_exc()
            self.log(error)
            if self.manager:
                if DEBUG:
                    self.manager.update_progress(error)
                else:
                    self.manager.update_progress(self.BITCOIN_QT_UNEXPECTED_ERROR)
                self.manager.update_menu(constants.ENABLE_ITEM)

        self.log('finished AccessWalletTask')

    def run_qt(self):
        '''
            Run bitcon-qt.
        '''
        ok = False
        error_message = None

        self.manager.update_menu(constants.DISABLE_ITEM)

        try:
            command_args = self.get_launch_args()
            if command_args is None:
                ok = False
            else:
                core_utils.rename_logs(self.manager.data_dir)

                state.set_start_access_time(now())

                self.log(f'starting bitcoin-qt: {command_args}')
                os.putenv('DISPLAY', ':0.0')

                if core_utils.is_bitcoin_qt_running():
                    bitcoin_pid = get_pid(core_utils.bitcoin_qt())
                    bitcoin_process = None
                else:
                    bitcoin_pid = None
                    bitcoin_process = Popen(command_args)

                if bitcoin_process is not None or bitcoin_pid is not None:
                    self.wait_for_close(bitcoin_process)
                    state.set_last_access_time(now())
                    ok = True
                else:
                    self.manager.update_progress(self.BITCOIN_QT_OTHER_APP_RUNNING)
                    ok = False

        except CalledProcessError as cpe:
            ok = False
            stdout = cpe.stdout
            if stdout and not isinstance(stdout, str):
                stdout = stdout.decode()
            stderr = cpe.stderr
            if stderr and not isinstance(stderr, str):
                stderr = stderr.decode()
            __, error_message, log_message = process_bitcoin_cli_error(
              'getblockchaininfo', self.manager.data_dir, cpe.returncode, stdout, stderr)
            if error_message is None:
                error_message = log_message
            self.log(error_message)

        except BitcoinException as be:
            ok = False
            error_message = str(be)
            self.log(error_message)

        except FileNotFoundError as fnfe:
            ok = False
            error_message = str(fnfe)
            self.log(error_message)

        except Exception:
            self.log(format_exc())

        if ok:
            # check the logs to make sure everything was ok
            ok, error_message = core_utils.bitcoin_finished_ok(
              self.manager.data_dir,
              core_utils.is_bitcoin_qt_running)

        if ok:
            if self.current_block > 0:
                state.set_last_block_updated(self.current_block)

        else:
            if error_message is None:
                error_message = ''

            self.manager.update_subnotice(f'{self.BITCOIN_QT_ERROR_LABEL} {error_message}')

        self.manager.update_progress('&nbsp;')

        return ok, error_message

    def get_launch_args(self):
        '''
            Get all the args to start bitcon-qt as a server.
        '''
        ok = False
        command_args = []

        if self.manager.bin_dir is None:
            command_args.append(core_utils.bitcoin_qt())
            ok = True
        else:
            cmd = os.path.join(self.manager.bin_dir, core_utils.bitcoin_qt())
            command_args.append(cmd)
            ok = os.path.exists(cmd)
            if not ok:
                self.log(f'{core_utils.bitcoin_qt()} does not exist in {self.manager.bin_dir}')

        if ok:
            command_args.append('-server')

            if self.manager.data_dir is not None:
                data_dir = core_utils.strip_testnet_from_data_dir(data_dir=self.manager.data_dir)
                command_args.append(f'-datadir={data_dir}')

            extra_args = preferences.get_extra_args()
            if extra_args:
                for extra_arg in extra_args:
                    command_args.append(extra_arg)
        else:
            command_args = None
            self.log(f'{core_utils.bitcion_qt()} does not exist in {self.manager.bin_dir}')

        return command_args

    def wait_for_close(self, bitcoin_process):
        '''
            Wait for user to close bitcion_qt.
        '''
        initial_wait_seconds = 30
        normal_wait_seconds = 10

        self.log('waiting for bitcoin-qt to be closed by user')
        while core_utils.is_bitcoin_qt_running():

            max_secs = initial_wait_seconds
            secs = 0
            # wait for bitcoin-qt
            while core_utils.is_bitcoin_qt_running() and (secs < max_secs):
                try:
                    if bitcoin_process is None:
                        sleep(1)
                    else:
                        bitcoin_process.wait(1)
                except TimeoutExpired:
                    pass
                secs += 1
            max_secs = normal_wait_seconds

            if core_utils.is_bitcoin_qt_running():
                current_block = self.manager.get_current_block(show_next_backup_time=False)

                if (current_block is not None and current_block > self.current_block):
                    self.current_block = current_block

        self.log(f'current block: {self.current_block}')
        self.log('finished waiting for bitcoin-qt')
