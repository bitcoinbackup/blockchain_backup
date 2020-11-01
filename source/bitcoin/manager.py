'''
    Utilities to manage bitcoin core.

    Copyright 2018-2020 DeNova
    Last modified: 2020-10-20
'''

import json
import os
import re
import shutil
from datetime import datetime
from subprocess import CalledProcessError
from time import gmtime, sleep
from django.utils.timezone import now, utc

from blockchain_backup.bitcoin import constants, state, utils
from blockchain_backup.bitcoin.exception import BitcoinException
from blockchain_backup.bitcoin.preferences import get_bitcoin_dirs, get_extra_args
from blockchain_backup.bitcoin.views import set_action_update
from denova.os import command
from denova.python.log import get_log


class BitcoinManager():
    '''
        Manage bitcoin's blockchain.
    '''

    def __init__(self, log_name, use_fresh_debug_log=True):
        '''
            Initialize bitcoin core manager.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager is not None
            True
        '''

        self.log = get_log(filename=log_name)

        self.bin_dir, self.data_dir = get_bitcoin_dirs()
        if use_fresh_debug_log:
            self.debug_log = utils.get_fresh_debug_log(self.data_dir)
        else:
            self.debug_log = utils.get_debug_log_name(self.data_dir)

        self.total_blocks_needed = None
        self.new_blocks_found = False

        self.last_progress_update = None
        self.last_notice_update = None
        self.last_subnotice_update = None
        self.last_header_update = None

        # give socketio time to connect
        sleep(5)

    def get_current_block(self, show_progress=True, show_next_backup_time=True):
        '''
            Get the current block and update the progress, if appropriate.

            >>> # this test always returns -1 because bitcoin is not running
            >>> # the unittest exercise this code more thoroughly
            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.get_current_block()
            -1
        '''

        blockchain_info = self.get_blockchain_info()
        return self.update_blockchain_info(
          blockchain_info, show_progress=show_progress,
          show_next_backup_time=show_next_backup_time)

    def get_blockchain_info(self):
        '''
            Get the blockchain info.

            >>> # this test always returns -1 because bitcoin is not running
            >>> # the unittest exercises this code more thoroughly
            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.get_blockchain_info()
            -1
        '''

        return self.send_bitcoin_cli_cmd('getblockchaininfo')

    def update_blockchain_info(self, block_info, show_progress=True, show_next_backup_time=True):
        '''
            Give the user feedback and get the current block.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> blockchain_info = json.dumps({
            ...                    "chain": "main",
            ...                    "blocks": 569083,
            ...                    "headers": 569083,
            ...                    "mediantime": 1553711097,
            ...                    "warnings": ""
            ...                   })
            >>> manager.update_blockchain_info(blockchain_info)
            569083
            >>> manager.update_blockchain_info(blockchain_info, show_progress=False)
            569083
            >>> manager.update_blockchain_info(blockchain_info, show_next_backup_time=False)
            569083
            >>> blockchain_info = json.dumps({
            ...                    "chain": "main",
            ...                    "blocks": 569167,
            ...                    "headers": 569167,
            ...                    "mediantime": 1553711097,
            ...                    "warnings": "Something's wrong"
            ...                   })
            >>> manager.update_blockchain_info(blockchain_info)
            569167
            >>> blockchain_info = None
            >>> manager.update_blockchain_info(blockchain_info)
            -1
            >>> blockchain_info = -1
            >>> manager.update_blockchain_info(blockchain_info)
            -1
        '''

        if block_info is None or block_info == -1:
            current_block = -1
        else:
            blockchain_info = json.loads(block_info)
            warnings = blockchain_info['warnings']
            if warnings:
                current_block = int(blockchain_info['blocks'])
                self.update_progress(warnings)
            else:
                current_block, progress = self.format_blockchain_update(
                  blockchain_info, self.data_dir, show_next_backup_time=show_next_backup_time)
                if show_progress and progress is not None:
                    self.update_progress(progress)

        return current_block

    def send_bitcoin_cli_cmd(self, arg, max_attempts=1):
        '''
            Send a command via bitcoin-cli.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.send_bitcoin_cli_cmd('getblockchaininfo')
            -1
        '''

        def wait(arg):
            ONE_MINUTE = 60

            secs = 0
            while ((utils.is_bitcoind_running() or
                    utils.is_bitcoin_qt_running()) and
                   secs < ONE_MINUTE):
                sleep(1)
                secs += 1
            self.log(f'waited {secs} seconds before retrying "{arg}" command')

        command_args = self.get_bitcoin_cli_cmd(arg)

        attempts = 0
        result = -1
        while (attempts < max_attempts and
               result == -1 and
               (utils.is_bitcoind_running() or utils.is_bitcoin_qt_running())):

            try:
                result = command.run(*command_args).stdout
                if attempts > 0:
                    self.log(f'resent "{arg}" command {attempts} times')
            except CalledProcessError as cpe:
                attempts += 1
                self.handle_bitcoin_cli_error(arg, cpe)

                if attempts < max_attempts:
                    wait(arg)

        return result

    def get_bitcoin_cli_cmd(self, arg):
        '''
            Get a command for bitcoin-cli.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.get_bitcoin_cli_cmd('getblockchaininfo')
            ['/tmp/bitcoin/bin/bitcoin-cli', '-testnet', '-datadir=/tmp/bitcoin/data', 'getblockchaininfo']
        '''

        command_args = []
        if self.bin_dir is None:
            command_args.append(utils.bitcoin_cli())
        else:
            command_args.append(os.path.join(self.bin_dir, utils.bitcoin_cli()))

        use_test_net = '-testnet' in get_extra_args()
        if use_test_net:
            command_args.append('-testnet')

        if self.data_dir is not None:
            data_dir = utils.strip_testnet_from_data_dir(data_dir=self.data_dir)
            command_args.append(f'-datadir={data_dir}')

        command_args.append(arg)

        return command_args

    def handle_bitcoin_cli_error(self, arg, called_process_error):
        '''
            Handle a process error when sending a message to bitcoin core.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> stderr = 'error code: 1\\nerror message:\\nError loading block database.'
            >>> cpe = CalledProcessError(1, 1, stderr=stderr)
            >>> try:
            ...     manager.handle_bitcoin_cli_error('getblockchaininfo', cpe)
            ... except BitcoinException as be:
            ...     str(be)
            'Error loading block database.'
            >>> stderr = 'error code: 1\\nerror message:\\nUnknown error'
            >>> cpe = CalledProcessError(1, 1, stderr=stderr)
            >>> manager.handle_bitcoin_cli_error('stop', cpe)
            >>> stderr = 'error code: -28\\nerror message:\\nLoading block index...'
            >>> cpe = CalledProcessError(28, 28, stderr=stderr)
            >>> manager.handle_bitcoin_cli_error('getblockchaininfo', cpe)
        '''

        returncode = called_process_error.returncode
        stdout = called_process_error.stdout
        stderr = called_process_error.stderr

        if stdout and not isinstance(stdout, str):
            stdout = stdout.decode()

        if stderr and not isinstance(stderr, str):
            stderr = stderr.decode()

        abort, progress, log_message = self.process_bitcoin_cli_error(
          arg, returncode, stdout, stderr)

        if progress is not None:
            self.update_progress(progress)

        if log_message is not None:
            self.log(log_message)

        if abort:
            exception_message = log_message
            if exception_message is None:
                exception_message = stderr
            raise BitcoinException(exception_message)

    def process_bitcoin_cli_error(self, arg, returncode, stdout, stderr):
        '''
            Process an error from bitcoin_cli.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> arg = 'getblockchaininfo'
            >>> returncode = 28
            >>> stdout = None
            >>> stderr = 'error code: -28\\nerror message:\\nLoading block index...'
            >>> manager.process_bitcoin_cli_error(arg, returncode, stdout, stderr)
            (False, 'Loading block index...', None)
            >>> returncode = 1
            >>> stderr = 'error code: 1\\nerror message:\\nerror: Could not locate RPC credentials.'
            >>> manager.process_bitcoin_cli_error(arg, returncode, stdout, stderr)
            (False, None, None)
            >>> returncode = 1
            >>> stderr = 'error code: 1\\nerror message:\\nerror: Could not connect to the server 127.0.0.1:8332'
            >>> manager.process_bitcoin_cli_error(arg, returncode, stdout, stderr)
            (False, None, None)
            >>> returncode = 4
            >>> stderr = 'error code: 1\\nerror message:\\nerror: Error loading block database.'
            >>> manager.process_bitcoin_cli_error(arg, returncode, stdout, stderr)
            (True, 'Error loading block database.', None)
        '''

        log = get_log()

        abort = False
        progress = log_message = None

        if not stderr:
            log_message = f'failed with return code: {returncode} stdout: {stdout}'

        elif stderr.find('error code: -28') >= 0:
            abort, progress = self.check_bitcoin_log()
            if progress is None:
                progress = self.strip_stderr(stderr)

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
                    log_message += self.strip_stderr(stderr)
                elif stderr.find('error code 1 - "EOF reached"') >= 0:
                    # don't try again as this is a known serious error
                    abort = True
                    log_message = self.strip_stderr(stderr)
                else:
                    # we're going to ignore the error and try again
                    # if we haven't hit the max retries
                    log_message = self.strip_stderr(stderr)

        elif returncode == 4:
            if stderr:
                DNS_PROBLEMS = 'Temporary failure in name resolution'
                i = stderr.find(DNS_PROBLEMS)
                if i >= 0:
                    progress = f'{DNS_PROBLEMS} -- problems with DNS?'
                else:
                    progress = self.strip_stderr(stderr)
            else:
                log_message = f'failed with return code: {returncode} stdout: {stdout}'

        else:
            log_message = f'failed with return code: {returncode} stderr: {stderr}'

        # don't know the return code
        if self.strip_stderr(stderr).find('Error loading block database.') >= 0:
            abort = True
            log('aborting connection because error loading block database')

        return abort, progress, log_message

    def bitcoin_finished_ok(self, is_app_running_func):
        '''
            Check the log and verify a clean exit.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> test_utils.start_bitcoind()
            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', manager.debug_log)
            '/tmp/bitcoin/data/testnet3/debug.log'
            >>> manager.bitcoin_finished_ok(utils.is_bitcoind_running)
            (True, None)
            >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', manager.debug_log)
            '/tmp/bitcoin/data/testnet3/debug.log'
            >>> if os.path.exists(manager.debug_log): os.remove(manager.debug_log)
            >>> manager.bitcoin_finished_ok(utils.is_bitcoind_running)
            (False, 'Error: Unable to determine status of bitcoin because debug.log is missing.')
            >>> test_utils.stop_bitcoind()
            >>> manager.bitcoin_finished_ok(utils.is_bitcoin_qt_running)
            (False, 'Error: Unable to determine status of bitcoin because debug.log is missing.')
            >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', manager.debug_log)
            '/tmp/bitcoin/data/testnet3/debug.log'
        '''

        if os.path.exists(self.debug_log):
            shutdown, error_message = self.check_bitcoin_log(is_app_running_func)
            ok = shutdown and error_message is None

        else:
            ok = False
            error_message = 'Error: Unable to determine status of bitcoin because debug.log is missing.'

        if error_message is not None:
            self.log(error_message)

        return ok, error_message

    def check_bitcoin_log(self, is_app_running_func=None):
        '''
            Check the log and see if the app shutdown.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', manager.debug_log)
            '/tmp/bitcoin/data/testnet3/debug.log'
            >>> manager.check_bitcoin_log(utils.is_bitcoind_running)
            (True, None)
            >>> if os.path.exists(manager.debug_log): os.remove(manager.debug_log)
            >>> manager.check_bitcoin_log(utils.is_bitcoind_running)
            (True, None)
            >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', manager.debug_log)
            '/tmp/bitcoin/data/testnet3/debug.log'
        '''

        shutdown = False
        error_message = None

        if os.path.exists(self.debug_log):
            with open(self.debug_log, 'r') as input_file:
                shutdown, error_message = self.get_log_errors(input_file)

                if error_message is not None:
                    error_message = error_message.strip(':')
                    self.log(f'error message: {error_message}')

        elif is_app_running_func is not None:
            self.log(f'{self.debug_log} not found')
            shutdown = not is_app_running_func()

        return shutdown, error_message

    def get_log_errors(self, log_file):
        '''
            Get the errors if there are any from the log file.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', manager.debug_log)
            '/tmp/bitcoin/data/testnet3/debug.log'
            >>> with open('/tmp/bitcoin/data/testnet3/debug.log', 'r') as log_file:
            ...     manager.get_log_errors(log_file)
            (True, None)
        '''

        SHUTDOWN_OK = 'Shutdown: done\n'
        IO_ERROR = 'IO error'
        ERROR_LOADING_DATABASE = 'Error loading block database.'
        ERROR_OPENING_DATABASE = 'Error opening block database'
        ABORTED_BLOCK_REBUILD = 'Aborted block database rebuild'
        CORRUPTED_BLOCK = 'Corrupted block database detected.'
        SYSTEM_ERROR = 'System error while flushing: Database I/O error'
        NO_GENESIS_BLOCK_ERROR = 'Error: Incorrect or no genesis block found. Wrong datadir for network?'
        EOF_ERROR = 'EOF reached'
        FAILED_TO_READ_BLOCK = 'Failed to read block'
        FATAL_INTERNAL_ERROR = 'A fatal internal error occurred, see debug.log for details'
        UNKNOWN_ERROR1 = 'Error:'
        UNKNOWN_ERROR2 = 'ERROR:'

        shutdown = False
        error_message = unknown_error_message = None
        unknown_error = False

        for line in log_file:
            self.log(line)
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
                if re.match(f'.*?{UNKNOWN_ERROR1}', line):
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
                break

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

    def rename_logs(self, time_stamp=None):
        '''
            Rename the debug and manager logs.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', manager.debug_log)
            '/tmp/bitcoin/data/testnet3/debug.log'
            >>> manager.rename_logs()
            True
            >>> shutil.copyfile('/tmp/bitcoin/debug-with-shutdown.log', manager.debug_log)
            '/tmp/bitcoin/data/testnet3/debug.log'
        '''
        ok = False

        if utils.is_bitcoin_core_running():
            ok = True
        else:
            if time_stamp is None:
                time_stamp = str(now())

            if os.path.exists(self.debug_log):
                shutil.move(self.debug_log,
                            os.path.join(self.data_dir,
                                         f'{constants.DEBUG_PREFIX}{time_stamp}{constants.LOG_SUFFIX}'))
                ok = True

        return ok

    def get_last_progress_update(self):
        '''
            Get the last progress message.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.get_last_progress_update()
        '''

        return self.last_progress_update

    def notify_close_window(self, notice=constants.CLOSE_WINDOW_NOW):
        '''
            Notify user we stopped activity successfully.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.notify_close_window()
            >>> manager.notify_close_window(notice='Serious error')
        '''

        notice_and_button = f'{notice}{utils.get_ok_button()}'
        self.update_notice(notice_and_button)
        self.update_alert_color('green')
        self.update_menu(constants.ENABLE_ITEM)

    def notify_done(self, notice=constants.CLOSE_WINDOW_NOW):
        '''
            Notify user and clear progress.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.notify_done()
            >>> manager.notify_done(notice='Serious error')
        '''

        self.notify_close_window(notice=notice)
        self.update_progress('&nbsp;')

    def update_header(self, text):
        '''
            Send an updated header to the user.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.update_header('Test Header')
        '''

        if self.last_header_update != text:
            self.last_header_update = text
            html = text.replace('\n', '<br/>')
            set_action_update('header', html)
            utils.send_socketio_message('header', html)
            self.log(f'header: {text}')

    def update_notice(self, text):
        '''
            Send a notice to the user.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.update_notice('Warning')
        '''

        if self.last_notice_update != text:
            self.last_notice_update = text
            html = text.replace('\n', '<br/>')
            set_action_update('notice', html)
            utils.send_socketio_message('notice', html)
            self.log(f'notice: {text}')

    def update_subnotice(self, text):
        '''
            Send a sub-notice to the user.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.update_subnotice('More info')
        '''

        if self.last_subnotice_update != text:
            self.last_subnotice_update = text
            html = text.replace('\n', '<br/>')
            set_action_update('subnotice', html)
            utils.send_socketio_message('subnotice', html)
            self.log(f'subnotice: {text}')

    def update_progress(self, text):
        '''
            Send progress update to user.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.update_progress('Details')
        '''

        if self.last_progress_update != text:
            self.last_progress_update = text
            html = text.replace('\n', '<br/>')
            set_action_update('progress', html)
            utils.send_socketio_message('progress', html)
            self.log(f'progress: {text}')

    def update_alert_color(self, color):
        '''
            Change the color of the alert box.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.update_alert_color('green')
        '''

        html = f'style=max-width: 40rem; background-color:{color}'
        set_action_update('alert', html)
        utils.send_socketio_message('alert', html)

    def update_menu(self, menu_state):
        '''
            Update whether the menu is active or not.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.update_menu(constants.DISABLE_ITEM)
        '''

        html = f'state={menu_state}'
        set_action_update('nav-link', html)
        utils.send_socketio_message('nav-link', html)

    def update_location(self, location):
        '''
            Send browser to a new location.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.update_location(constants.BACKUP_URL)
        '''

        set_action_update(constants.LOCATION_NAME, location)
        utils.send_socketio_message(constants.LOCATION_NAME, location)

    def format_blockchain_update(self, blockchain_info, data_dir, show_next_backup_time=True):
        '''
            Format the update to the blockchain.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> blockchain_info = {
            ...                    "chain": "main",
            ...                    "blocks": 569060,
            ...                    "headers": 569164,
            ...                    "bestblockhash": "0000000000000000001ded7310261af91403b97bf02e227b26cccc35bde3eccd",
            ...                    "difficulty": 6379265451411.053,
            ...                    "mediantime": 1553711097,
            ...                    "warnings": ""
            ...                   }
            >>> data_dir = '/tmp/bitcoin/data/testnet3'
            >>> current_block, progress = manager.format_blockchain_update(
            ...   blockchain_info, data_dir, show_next_backup_time=False)
            >>> current_block == 569060
            True
            >>> progress.find('Next backup in:') > 0
            False
            >>> current_block, progress = manager.format_blockchain_update(
            ...   blockchain_info, data_dir)
            >>> current_block == 569060
            True
            >>> progress.find('Next backup in:') > 0
            True
            >>> blockchain_info = {
            ...                    "chain": "main",
            ...                    "blocks": 2,
            ...                    "headers": 0,
            ...                    "mediantime": 1553711097,
            ...                    "warnings": ""
            ...                   }
            >>> data_dir = '/tmp/bitcoin/data/testnet3'
            >>> manager.format_blockchain_update(blockchain_info, data_dir)
            (2, None)
        '''

        progress = None

        last_known_block = int(blockchain_info['headers'])
        current_block = int(blockchain_info['blocks'])
        epoch_time = gmtime(blockchain_info['mediantime'])
        last_block_time = datetime(
          epoch_time.tm_year, epoch_time.tm_mon, epoch_time.tm_mday,
          epoch_time.tm_hour, epoch_time.tm_min, epoch_time.tm_sec, tzinfo=utc)

        if last_known_block > 0:
            previous_known_block = state.get_last_known_block()
            if last_known_block > previous_known_block:
                state.set_last_known_block(last_known_block)
                state.set_last_block_time(last_block_time)
                self.new_blocks_found = True

            time_behind = f'{utils.get_most_recent_confirmation(last_block_time)} ago'
            remaining_blocks = last_known_block - current_block
            if remaining_blocks < 0 or not self.new_blocks_found:
                remaining_blocks = 'Unknown'

            rows = []
            rows.append(self.format_row('Number of blocks to update', remaining_blocks))
            rows.append(self.format_row('Most recent confirmation',
                                        time_behind,
                                        title='Most recent transaction confirmed on your Bitcoin node'))

            if show_next_backup_time:
                status = utils.get_next_backup_in()
                if status is not None:
                    rows.append(self.format_row('Next backup in', status))

            elif current_block > 0:
                need_backup = utils.need_to_backup(data_dir, current_block)
                if need_backup and utils.is_bitcoin_qt_running():
                    rows.append(self.format_row('<font color="red">Backup needed</font>',
                    'Stop Bitcoin-QT as soon as possible to protect your blockchain. The backup will start automatically.'))

            progress = f"<table cellspacing=\"5\">{''.join(rows)}</table>"

        return current_block, progress

    def format_row(self, label, value, title=None):
        '''
            Format a row in a 2 column table.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> manager.format_row('Test', 100)
            '<tr><td><strong>Test:&nbsp;&nbsp;</strong></td><td valign="bottom">100</td></tr>'
            >>> manager.format_row('Another test', 59, title='Help text')
            '<tr><td><span title="Help text"><strong>Another test:&nbsp;&nbsp;</strong></span></td><td><span title="Help text">59</span></td></tr>'
        '''

        FORMAT1 = '<tr><td><strong>{}:&nbsp;&nbsp;</strong></td><td valign="bottom">{}</td></tr>'
        FORMAT2 = '<tr><td><span title="{}"><strong>{}:&nbsp;&nbsp;</strong></span></td><td><span title="{}">{}</span></td></tr>'

        if title is None:
            row = FORMAT1.format(label, value)
        else:
            row = FORMAT2.format(title, label, title, value)

        return row

    def strip_stderr(self, stderr):
        '''
            String standard error.

            >>> manager = BitcoinManager('blockchain_backup.bitcoin.manager.log')
            >>> stderr = 'error message: error: Unknown error.'
            >>> manager.strip_stderr(stderr)
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
