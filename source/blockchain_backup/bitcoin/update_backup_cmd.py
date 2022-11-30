#! /usr/bin/env python3
'''
    Start the updating the bitcoin blockchain from the command line.
    Stop updating when no more blocks to update. Then backup the
    blockchain and stop the program.

    BETA TESTING
        To Do:
            Stop bitcoind and/or backup if someone types Ctl-C.

    Copyright 2021 DeNova
    Last modified: 2021-08-24
'''

import ve

# we want to be able to run this program from inside or outside the virtualenv
if not ve.in_virtualenv():
    ve.activate(django_app='blockchain_backup')

import argparse
import os
from subprocess import TimeoutExpired
from time import sleep
from traceback import format_exc

from django import setup
setup()

from blockchain_backup.bitcoin import constants, core_utils
from blockchain_backup.bitcoin import backup_utils
from blockchain_backup.bitcoin.exception import BitcoinException
from blockchain_backup.bitcoin.handle_cli import get_blockchain_info, update_latest_state
from blockchain_backup.bitcoin.preferences import bin_dir_ok, data_dir_ok, get_bitcoin_dirs
from blockchain_backup.settings import PROJECT_PATH
from denova.os import command
from denova.python.log import Log
from denova.python.times import get_short_date_time, now


CURRENT_VERSION = '0.2'
COPYRIGHT = 'Copyright 2018-2022 DeNova'
LICENSE = 'GPLv3'

log = Log()


class UpdateAndBackup():
    '''
        Automatically update the blockchain until 0 blocks
        available, then backup the blockchain, and finally exit.run
    '''

    # only check every half hour
    WAIT_SECONDS = 30 * 30  # seconds

    def __init__(self):

        self.bin_dir = None
        self.data_dir = None
        self.interrupted = False

    def ready(self):
        ''' Check that no conflicting app is running.

            Returns:
                True if ready to start.
                False if any other app that conflicts with this app is running
                         or the preferences aren't configured properly.

            >>> uab = UpdateAndBackup()
            >>> uab.ready()
            <BLANKLINE>
            Auto update and backup ready
            True
        '''

        app_ready = False
        error = None

        if core_utils.is_bitcoin_qt_running():
            error = 'Bitcoin QT is running.'

        elif core_utils.is_bitcoin_tx_running():
            error = 'Bitcoin TX is running.'

        elif core_utils.is_bitcoind_running():
            error = 'BitcoinD is running.'

        else:
            dir_ok, error = data_dir_ok()
            if dir_ok:
                dir_ok = bin_dir_ok()
                if not dir_ok:
                    error = 'Executable dir does not exist'

            app_ready = dir_ok

        if error:
            message = error
            if error.endswith('running'):
                message = f'{error} Stop it before restarting this app again.'
            else:
                message = f'{error} Start Blockchain Backup to adjust the preferences.'

        else:
            message = 'Update and Backup Bitcoin Blockchain Ready'

        log(message)
        print(f'\n{message}')

        return app_ready

    def run(self, args):
        '''
           Update until there aren't any more blocks and then back up blockchain.

            Returns:
                ok: True if blocks updated and backed up successful; otherwise False
        '''
        ok = True

        self.bin_dir, self.data_dir = get_bitcoin_dirs()

        # if no params passed, then update and then backup
        if not args.update and not args.backup:
            args.update = True
            args.backup = True

        if args.update:
            # start with a clean debug log
            debug_log = os.path.join(self.data_dir, 'debug.log')
            if os.path.exists(debug_log):
                os.remove(debug_log)

            ok = self.update()

        if ok and args.backup:
            ok = self.backup()

        return ok

    def update(self):
        '''
            Automatically update the blockchain.

            Returns:
                True if successful.
                False if any errors.
        '''
        ok = True

        try:
            bitcoind_process, bitcoind_pid = core_utils.start_bitcoind(self.bin_dir, self.data_dir)
            if bitcoind_process is None and bitcoind_pid is None:
                self.print_on_same_line('Error starting bitcoind')
                ok = False
            else:
                self.wait_while_updating(bitcoind_process, secs_to_wait=self.WAIT_SECONDS)

                ok, error_message = core_utils.stop_bitcoind(
                  bitcoind_process, bitcoind_pid, self.bin_dir, self.data_dir)

        except BitcoinException as be:
            ok = False
            error_message = str(be)
            log(error_message)

        except KeyboardInterrupt:

            self.interrupted = True
            log('^C typed; interrupting update')

            if core_utils.is_bitcoind_running():
                print('^C typed; Stopping update. Please wait...')

                program = os.path.join(PROJECT_PATH, 'config', 'bitcoin_shutdown.py')
                try:
                    command.run('python3', program)
                except Exception as exc:
                    log(exc)
                    raise

                ok = False

            self.interrupted = False

        except: # 'bare except' because it catches more than "except Exception"
            log(format_exc())

            # sometimes bitcoin exits with a non-zero return code,
            # but it was still ok, so check the logs
            ok, error_message = core_utils.bitcoin_finished_ok(self.data_dir,
                                                               core_utils.is_bitcoind_running)

        if ok:
            self.print_on_same_line(f'Remaining blocks to update at {self.get_current_time()}: 0')
            self.print_on_same_line('Finished updating blockchain')

        return ok

    def wait_while_updating(self, bitcoind_process, secs_to_wait=10):
        '''
            Wait for the blockchain to be updated.

            Args:
                bitcoind_process: the process number of the running bitcoind
                secs_to_wait: seconds to wait for update before checking if done

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> uab = UpdateAndBackup()
            >>> uab.bin_dir = '/tmp/bitcoin/bin'
            >>> uab.data_dir = '/tmp/bitcoin/data/testnet3'
            >>> bitcoind_process, bitcoind_pid = core_utils.start_bitcoind(uab.bin_dir, uab.data_dir)
            >>> uab.wait_while_updating(bitcoind_process)
            >>> core_utils.stop_bitcoind(bitcoind_process, bitcoind_pid, uab.bin_dir, uab.data_dir)
            (False, 'Aborted block database rebuild. Exiting.\\n')
        '''
        log('waiting while updating blockchain')

        # give the system a few seconds to get bitcoind started
        while not core_utils.is_bitcoind_running():
            sleep(secs_to_wait)

        current_block, remaining_blocks = self.get_blocks()
        while core_utils.is_bitcoind_running() and remaining_blocks != 0:

            try:
                if remaining_blocks > 0:
                    message = f'Remaining blocks to update at {self.get_current_time()}: {remaining_blocks}'
                    log(message)
                    print(message)

                bitcoind_process.wait(secs_to_wait)
            except TimeoutExpired:
                pass

            if core_utils.is_bitcoind_running():
                current_block, remaining_blocks = self.get_blocks()

                sleep(secs_to_wait)

        log(f'is_bitcoind_running: {core_utils.is_bitcoind_running()}')

    def get_blocks(self):
        '''
            Get the current and latest blocks.

            >>> # this test always returns -1 because bitcoin is not running
            >>> # the unittest exercise this code more thoroughly
            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> uab = UpdateAndBackup()
            >>> uab.bin_dir = '/tmp/bitcoin/bin'
            >>> uab.data_dir = '/tmp/bitcoin/data/testnet3'
            >>> current_block, remaining_blocks = uab.get_blocks()
            >>> print(current_block)
            -1
            >>> print(remaining_blocks)
            -1
        '''

        blockchain_info = get_blockchain_info(self.bin_dir, self.data_dir)
        if blockchain_info is None or blockchain_info == -1:
            current_block = -1
            remaining_blocks = -1
        else:
            current_block, remaining_blocks, __ = update_latest_state(blockchain_info)

            warnings = blockchain_info['warnings']
            if warnings:
                print(f'\nWarning: {warnings}')

        return current_block, remaining_blocks

    def backup(self):
        '''
            Automatically backup the blockchain.

            Returns:
                True if successful.
                False if any errors.
        '''
        ok = True

        to_backup_dir, backup_formatted_time, backup_level = backup_utils.prep_backup(self.data_dir)
        log(f'starting backup to {backup_level}')
        print(f'Starting backup to level {backup_level}')

        try:
            backup_process, backup_pid = backup_utils.start_backup(self.data_dir, to_backup_dir)

            if backup_process is not None or backup_pid is not None:

                backup_utils.wait_for_backup(backup_process, self.is_interrupted)

                backup_utils.stop_backup(backup_process, backup_pid)

            else:
                log(backup_utils.NO_MEM_ERROR)
                ok = False

            backup_utils.finish_backup(self.data_dir, to_backup_dir, backup_formatted_time, backup_level)

        except KeyboardInterrupt:

            self.interrupted = True

            backup_utils.add_backup_flag(to_backup_dir, backup_formatted_time)
            ok = False
            log('^C typed; interrupting backup')

        except: # 'bare except' because it catches more than "except Exception"
            backup_utils.add_backup_flag(to_backup_dir, backup_formatted_time)
            ok = False
            log(format_exc())

        if ok:
            backup_utils.save_all_metadata(self.data_dir, to_backup_dir)
            log('saved all metadata')

            # remove the old debug logs; we back them up in case there's an error
            for entry in os.scandir(self.data_dir):
                if entry.name.startswith(constants.DEBUG_PREFIX) and \
                   entry.name.endswith(constants.LOG_SUFFIX):
                    os.remove(entry.path)

            log(backup_utils.FINISHED_REMINDER)
            self.print_on_same_line(backup_utils.FINISHED_REMINDER)

        else:
            log(backup_utils.UNEXPECTED_ERROR)
            self.print_on_same_line(backup_utils.UNEXPECTED_ERROR)

        return ok

    def is_interrupted(self):
        '''
            Return True if someone typed ^C.
        '''

        return self.interrupted

    def get_current_time(self):
        '''
            Get the current time.

            Returns:
                A string with the current hours and minutes.
        '''
        current_time = get_short_date_time(now())

        # strip the date
        i = current_time.find(' ')
        current_hour_min = current_time[i+1:]

        # strip the milliseconds
        i = current_hour_min.find('.')
        current_hour_min = current_hour_min[:i]

        i = current_hour_min.find(':')
        current_hour = current_hour_min[:i]
        if len(current_hour) < 2:
            current_hour = f'0{current_hour}'
        current_min = current_hour_min[i+1:]
        if len(current_min) < 2:
            current_min = f'{current_min}0'

        return f'{current_hour}:{current_min}'

    def print_on_same_line(self, message):
        '''
            Print the message on the same line.

            Args:
                message: The text you want displayed on the current line.
        '''

        try:
            CLEAR_LINE = '\r' + ' '*60 + '\r'
            print(CLEAR_LINE, end='')
            print(message, flush=True)
        except Exception:
            print(message)


def parse_args():
    ''' Parsed command line. '''

    global args

    parser = argparse.ArgumentParser(description='Auto update and backup the blockchain.')

    parser.add_argument('--update',
                        help="Update only",
                        action='store_true')
    parser.add_argument('--backup',
                        help="Backup only",
                        action='store_true')
    args = parser.parse_args()

    return args


def main(args):

    update_and_backup = UpdateAndBackup()
    if update_and_backup.ready():

        if update_and_backup.run(args):
            print('Finished')
        else:
            print('Unable to finish')


if __name__ == "__main__":
    args = parse_args()
    main(args)
