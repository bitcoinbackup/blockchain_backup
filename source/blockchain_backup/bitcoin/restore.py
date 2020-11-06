'''
    Copyright 2018-2020 DeNova
    Last modified: 2020-11-05
'''

import json
import os
from shutil import rmtree
from subprocess import CalledProcessError, Popen, PIPE
from tempfile import gettempdir
from threading import Thread
from time import sleep
from traceback import format_exc

from django.utils.timezone import now

from blockchain_backup.bitcoin import constants, state
from blockchain_backup.bitcoin import utils as bitcoin_utils
from blockchain_backup.bitcoin.manager import BitcoinManager
from blockchain_backup.bitcoin.state import set_last_backed_up_time
from denova.os import command
from denova.os.process import get_pid
from denova.os.user import whoami
from denova.python.log import get_log, get_log_path, BASE_LOG_DIR
from denova.python.ve import virtualenv_dir



class RestoreTask(Thread):
    '''
        Restore the blackchain.

        Errors users might see that prompt them to need a restore:
          Error loading block database. / Do you want to rebuild the block database now?
    '''

    RESTORE_DONE = 'Restore done'
    RESTORE_FINISHED = '<br/>&nbsp;Finished restore. You are ready to continue using Bitcoin Core.'
    STOPPED_RESTORE = 'Restore stopped on your request'
    RESTORE_BACKUPS_OK = '<strong>Backups were temporarily disabled.</strong> After you successfully <a href="/bitcoin/access_wallet/">Access your wallet</a> or <a href="/bitcoin/update/">Update</a> the blockchain, then you should <a href="/bitcoin/change_backup_status/">re-enable the backups</a>.'
    RESTORE_WARNING = 'Review the details below:'
    RESTORE_UNABLE_TO_START = 'Unable to start restore -- is there enough memory and disk space?'
    RESTORE_ERROR = 'Unexpected error while restoring files. Check logs for details.'
    RESTORE_UNEXPECTED_ERROR = 'Unexpected error occurred while restoring blockchain.'

    STOPPING_RESTORE = 'Stopping restore as you requested'
    STOPPED_RESTORE = "Stopped restoring Bitcoin blockchain"
    STOP_RESTORE_NOT_COMPLETE = "It's very likely Bitcoin Core will not operate until you complete the restore."
    STOP_RESTORE_UNEXPECTED_ERROR = 'Unexpected error occurred while stopping restore.'

    def __init__(self, restore_dir):
        '''
            Initialize the restore task.

            >>> restore_task = RestoreTask(os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1'))
            >>> restore_task is not None
            True
            >>> restore_task.__init__(os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1'))
            >>> restore_task.restore_dir
            '/tmp/bitcoin/data/testnet3/backups/level1'
            >>> restore_task._interrupted
            False
            >>> restore_task.manager is None
            True
            >>> restore_task.log_name
            'blockchain_backup.bitcoin.restore.log'
        '''
        Thread.__init__(self)

        self.restore_dir = restore_dir

        self._interrupted = False

        self.log = get_log()
        self.log_name = os.path.basename(get_log_path())

        self.manager = None

    def interrupt(self):
        '''
            Set to true when user clicks the Stop button.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> restore_task = RestoreTask(os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1'))
            >>> restore_task.interrupt()
            >>> restore_task._interrupted
            True
        '''
        self._interrupted = True
        if self.manager:
            self.manager.update_progress(self.STOPPING_RESTORE)

    def is_interrupted(self):
        '''
            Returns true if user clicked the Stop button.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> restore_task = RestoreTask(os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1'))
            >>> restore_task.is_interrupted()
            False
        '''
        return self._interrupted

    def run(self):
        '''
            Start the restore task.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> restore_task = RestoreTask(os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1'))
            >>> restore_task.run()
            True
            >>> restore_task.is_interrupted()
            False
            >>> restore_task = RestoreTask('/bad/bitcoin/data/testnet3/backups/level1')
            >>> restore_task.run()
            False
            >>> restore_task.is_interrupted()
            False
        '''
        ok = False
        try:
            self.log('started RestoreTask')

            self.manager = BitcoinManager(self.log_name)

            if os.path.exists(self.manager.data_dir) and os.path.exists(self.restore_dir):
                ok = self.restore()
                if self.is_interrupted():
                    self.interrupt_restore()
                self.log('finished RestoreTask')
            else:
                ok = False
                self.log(f'data dir exists: {os.path.exists(self.manager.data_dir)}')
                self.log(f'restore exists: {os.path.exists(self.restore_dir)}')
                self.log('RestoreTask terminated')
                self.manager.update_progress(self.RESTORE_UNEXPECTED_ERROR)
                self.manager.update_menu(constants.ENABLE_ITEM)

        except FileNotFoundError as fne:
            FILE_NOT_FOUND_PREFIX = '[Errno 2] No such file or directory: '
            ok = False
            error = str(fne)
            i = error.find(FILE_NOT_FOUND_PREFIX)
            if i >= 0:
                error = error[len(FILE_NOT_FOUND_PREFIX):]
            self.log(f'file not found: {error}')
            self.remove_last_updated_file()
            if self.manager:
                self.manager.update_notice(error)
                self.manager.update_progress(self.RESTORE_UNEXPECTED_ERROR)
                self.manager.update_menu(constants.ENABLE_ITEM)

        except: # 'bare except' because it catches more than "except Exception"
            ok = False
            self.log(format_exc())
            if self.manager:
                self.manager.update_progress(self.RESTORE_UNEXPECTED_ERROR)
                self.manager.update_menu(constants.ENABLE_ITEM)

        return ok

    def restore(self):
        '''
            Restore blockchain from newest backup,
            or the backup the user selected.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> restore_task = RestoreTask(os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1'))
            >>> restore_task.manager = BitcoinManager(restore_task.log_name)
            >>> restore_task.restore()
            True
            >>> restore_task.is_interrupted()
            False
        '''

        ok = True

        self.log(f'starting restoration from {self.restore_dir}')

        self.manager.update_menu(constants.DISABLE_ITEM)

        bitcoin_utils.check_for_updates(force=True, reason='restore')

        ok = self.restore_files_and_dirs()

        if ok and not self.is_interrupted():
            # pass the args because delete_extra_files is recursive
            ok = self.delete_extra_files(self.restore_dir, self.manager.data_dir)

        if ok and not self.is_interrupted():
            ok = self.restore_metadata()

        if ok and not self.is_interrupted():
            self.restore_bcb_state()

        if not self.is_interrupted():
            if ok:
                # we don't want to warn that a backup is needed
                # just after we restore from a backup
                set_last_backed_up_time(now())
            else:
                self.remove_last_updated_file()

        if self.is_interrupted():
            self.log('restore stopped by user')
            self.manager.update_header(self.RESTORE_STOPPED)
            self.manager.update_notice(self.RESTORE_WARNING)
            self.manager.update_subnotice(' ')
        else:
            if ok:
                self.log('finished bulk restore')
                state.set_backups_enabled(False)
                self.log('stopping backups after restore until user verifies everything ok')
                self.manager.update_header(self.RESTORE_DONE)
                self.manager.notify_done(notice=self.RESTORE_FINISHED)
                self.manager.update_subnotice(self.RESTORE_BACKUPS_OK)
            else:
                self.manager.update_notice(self.RESTORE_WARNING)
                self.manager.update_subnotice(' ')

        self.manager.update_menu(constants.ENABLE_ITEM)

        return ok

    def restore_files_and_dirs(self):
        '''
            Restore files and directories to
            a previous state of the blockchain.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> restore_dir = os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1')
            >>> restore_task = RestoreTask(restore_dir)
            >>> restore_task.manager = BitcoinManager(restore_task.log_name)
            >>> restore_task.restore_files_and_dirs()
            True
            >>> test_utils.stop_restore()
            >>> test_utils.start_fake_restore()
            >>> restore_task = RestoreTask(restore_dir)
            >>> restore_task.manager = BitcoinManager(restore_task.log_name)
            >>> restore_task.restore_files_and_dirs()
            True
            >>> test_utils.stop_restore()
        '''

        ok = True
        try:
            if bitcoin_utils.is_restore_running():
                restore_pid = get_pid(constants.RESTORE_PROGRAM)
                restore_process = None
                self.log('{} is already running using pid: {}'.format(
                  constants.RESTORE_PROGRAM, restore_pid))
            else:
                self.log('starting restore')
                restore_process = self.start_restore()
                restore_pid = None

            if restore_process is not None or restore_pid is not None:
                self.wait_for_restore(restore_process)

                self.stop_restore(restore_process, restore_pid)
            else:
                self.manager.update_progress(self.RESTORE_UNABLE_TO_START)
                ok = False
        except: # 'bare except' because it catches more than "except Exception"
            ok = False
            self.log(format_exc())

        if not ok:
            self.manager.update_progress(self.RESTORE_ERROR)

        return ok

    def start_restore(self):
        '''
            Start restoring the files and directories.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> restore_task = RestoreTask(os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1'))
            >>> restore_task.manager = BitcoinManager(restore_task.log_name)
            >>> restore_process = restore_task.start_restore()
            >>> restore_process is not None
            True
            >>> test_utils.stop_restore()
        '''

        # do NOT use the --delete flag -- the backups dir itself would be deleted
        args = []
        # restore program is a link to safecopy
        bin_dir = os.path.join(virtualenv_dir(), 'bin')
        args.append(os.path.join(bin_dir, constants.RESTORE_PROGRAM))
        args.append('--exclude')
        args.append(bitcoin_utils.get_excluded_files())
        args.append('--verbose')
        args.append('--quick')
        args.append(f'{self.restore_dir}/*')
        args.append(self.manager.data_dir)

        restore_process = Popen(args, stdout=PIPE, universal_newlines=True)

        return restore_process

    def wait_for_restore(self, restore_process):
        '''
            Wait for the restore to finish and display data while waiting.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> restore_task = RestoreTask(os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1'))
            >>> restore_task.manager = BitcoinManager(restore_task.log_name)
            >>> restore_process = restore_task.start_restore()
            >>> restore_process is not None
            True
            >>> restore_task.wait_for_restore(restore_process)
            >>> test_utils.stop_restore()
            >>> restore_task.wait_for_restore(None)
            >>> test_utils.stop_restore()
        '''
        def show_line(line):
            if line is not None and line.startswith('Copying:'):
                index = line.rfind(os.sep)
                if index > 0:
                    line = f'<strong>Copying: </strong>{line[index + 1:]}'
                self.manager.update_progress(line)

        self.log('starting to wait for restore')

        if restore_process is None:
            log_path = os.path.join(BASE_LOG_DIR, whoami(), 'bcb-restore.log')

            # wait until the log appears
            while bitcoin_utils.is_restore_running() and not self.is_interrupted():

                if not os.path.exists(log_path):
                    sleep(1)

            # then display the restore details
            while bitcoin_utils.is_restore_running() and not self.is_interrupted():

                with open(log_path, 'rt') as restore_log:
                    show_line(restore_log.readline())
        else:
            while (restore_process.poll() is None and
                   not self.is_interrupted()):

                show_line(restore_process.stdout.readline())

        self.log('finished waiting for restore')

    def stop_restore(self, restore_process, restore_pid):
        '''
            Stop restore.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> restore_task = RestoreTask(os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1'))
            >>> restore_task.manager = BitcoinManager(restore_task.log_name)
            >>> restore_process = restore_task.start_restore()
            >>> restore_process is not None
            True
            >>> restore_task.stop_restore(restore_process, None)
            >>> test_utils.start_fake_restore()
            >>> restore_pid = get_pid(constants.RESTORE_PROGRAM)
            >>> restore_task.stop_restore(None, restore_pid)
        '''
        try:
            if restore_process is None:
                if bitcoin_utils.is_restore_running():
                    bin_dir = os.path.join(virtualenv_dir(), 'bin')
                    args = [os.path.join(bin_dir, 'killmatch'),
                            '"{} --exclude {}"'.format(
                             constants.RESTORE_PROGRAM, bitcoin_utils.get_excluded_files())]
                    result = command.run(*args).stdout
                    self.log(f'killing restore result: {result}')

                try:
                    pid, returncode = os.waitpid(restore_pid, os.P_WAIT)
                    self.log(f'waitpid {pid} return code: {returncode}')
                except ChildProcessError:
                    self.log('restore_pid already dead')

            else:
                # if bcb-restore hasn't stopped yet, then kill it
                if restore_process.poll() is None:
                    self.log('killing restore')
                    restore_process.terminate()

                # wait until restore terminates
                restore_process.wait()
                self.log(f'restore return code: {restore_process.returncode}')
        except: # 'bare except' because it catches more than "except Exception"
            self.log(f'error while stopping restore\n{format_exc()}')
            self.log(f'error while stopping restore\n{format_exc()}')

    def delete_extra_files(self, from_dir, to_dir):
        '''
            Delete files that are not part
            of the current blockchain.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> from_dir = os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1')
            >>> restore_task = RestoreTask(from_dir)
            >>> restore_task.manager = BitcoinManager(restore_task.log_name)
            >>> restore_task.delete_extra_files(from_dir, restore_task.manager.data_dir)
            True
        '''

        BACKUP_SUBDIR = bitcoin_utils.get_backup_subdir()
        EXCLUDED_FILES = bitcoin_utils.get_excluded_files()

        ok = True

        try:
            to_entries = os.scandir(to_dir)
            for entry in to_entries:
                if entry.name in [EXCLUDED_FILES]:
                    self.log(f'skipping {entry.name}')
                elif entry.name.startswith(constants.LAST_UPDATED_PREFIX):
                    os.remove(entry.path)
                    self.log(f'deleted {entry.path}')
                elif entry.is_file():
                    from_file = os.path.join(from_dir, entry.name)
                    if not os.path.exists(from_file):
                        os.remove(entry.path)
                        self.log(f'deleted {entry.path}')
                elif entry.is_dir() and entry.name != BACKUP_SUBDIR:
                    from_file = os.path.join(from_dir, entry.name)
                    if os.path.exists(from_file):
                        ok = self.delete_extra_files(os.path.join(
                           from_dir, entry.name), entry.path)
                    else:
                        rmtree(entry.path)
                        self.log(f'deleted dir tree: {entry.path}')

                if not ok or self.is_interrupted():
                    break

        except: # 'bare except' because it catches more than "except Exception"
            ok = False
            self.log(format_exc())

        if not ok and not self.is_interrupted():
            self.manager.update_progress(self.RESTORE_ERROR)

        return ok

    def restore_metadata(self):
        '''
            Restore the metadata in the data dir.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> restore_dir = os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1')
            >>> restore_task = RestoreTask(restore_dir)
            >>> restore_task.manager = BitcoinManager(restore_task.log_name)
            >>> restore_task.restore_files_and_dirs()
            True
            >>> restore_task.restore_metadata()
            True
        '''

        self.log('starting to restore metadata')

        missing_files = []
        bad_metadata_files = []
        ok = True

        json_filename = os.path.join(self.restore_dir, constants.METADATA_FILENAME)
        if os.path.exists(json_filename):
            with open(json_filename, 'r') as json_file:
                lines = json_file.readlines()

            for line in lines:

                path, stats = json.loads(line)
                full_path = os.path.join(self.manager.data_dir, path)

                if os.path.exists(full_path):
                    try:
                        os.utime(full_path, (stats['st_atime'], stats['st_mtime']))
                        os.chmod(full_path, stats['st_mode'])
                        os.chown(full_path, stats['st_uid'], stats['st_gid'])
                    except: # 'bare except' because it catches more than "except Exception"
                        bad_metadata_files.append(full_path)
                        self.log(f'Unable to set metadata for {full_path}')
                        self.log(format_exc())
                else:
                    missing_files.append(full_path)

                if self.is_interrupted():
                    break

        else:
            missing_files.append(json_filename)

        if (bad_metadata_files or missing_files) and not self.is_interrupted():
            self.report_errors(bad_metadata_files, missing_files)
            ok = False

        if ok and not self.is_interrupted():
            self.log('finished restoring metadata')

        return ok

    def restore_bcb_state(self):
        '''
            Restore the state of the blockchain_backup database.

            Don't change the preferences as the user
            may have changed them since the last backup.

            >>> from shutil import copyfile
            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> dst_state_ok_json = None
            >>> dst_state_json = os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1/blockchain_backup_database/state.json')
            >>> if os.path.exists(dst_state_json):
            ...     dst_state_ok_json = copyfile(dst_state_json, dst_state_json + '.ok')
            >>> copyfile(os.path.join(gettempdir(), 'bitcoin/state.json'), dst_state_json)
            '/tmp/bitcoin/data/testnet3/backups/level1/blockchain_backup_database/state.json'
            >>> original_last_block_updated = state.get_last_block_updated()
            >>> original_last_known_block = state.get_last_known_block()
            >>> original_last_block_time = state.get_last_block_time()
            >>> original_last_backup_level = state.get_last_backup_level()
            >>> restore_dir = os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1')
            >>> restore_task = RestoreTask(restore_dir)
            >>> restore_task.manager = BitcoinManager(restore_task.log_name)
            >>> restore_task.restore_bcb_state()
            True
            >>> original_last_block_updated != state.get_last_block_updated()
            True
            >>> original_last_known_block != state.get_last_known_block()
            True
            >>> original_last_block_time != state.get_last_block_time()
            True
            >>> if dst_state_ok_json is not None and os.path.exists(dst_state_ok_json):
            ...     x = copyfile(dst_state_ok_json, dst_state_json)
            ...     os.remove(dst_state_ok_json)
            >>> test_utils.init_database()
            >>> restore_dir = '/bad/bitcoin/data/testnet3/backups/level1'
            >>> restore_task = RestoreTask(restore_dir)
            >>> restore_task.manager = BitcoinManager(restore_task.log_name)
            >>> restore_task.restore_bcb_state()
            False
        '''

        ok = False
        blockchain_backup_db_restore_dir = os.path.join(self.restore_dir, constants.BLOCKCHAIN_BACKUP_DB_DIR)
        full_path = os.path.join(blockchain_backup_db_restore_dir, constants.STATE_BACKUP_FILENAME)

        if os.path.exists(full_path):
            try:
                with open(full_path, 'r') as infile:
                    json_data = json.loads(infile.read())
                fields = json_data[0]['fields']

                state.set_last_block_updated(fields['last_block_updated'])
                state.set_last_known_block(fields['last_known_block'])
                state.set_last_block_time(fields['last_block_time'])
                ok = True
                self.log('restored database state')
            except: # 'bare except' because it catches more than "except Exception"
                # restoring the blockchain_backup state is not
                # critical to maintaining the blockchain
                self.log(format_exc())

        else:
            self.log(f'Unable to restore state because {full_path} does not exist')

        return ok

    def interrupt_restore(self):
        '''
            User wants the restoration interrupted.
            This is not recommended because it almost
            always leaves the blockchain in unusable shape.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.init_database()
            >>> restore_dir = os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1')
            >>> restore_task = RestoreTask(restore_dir)
            >>> restore_task.manager = BitcoinManager(restore_task.log_name)
            >>> test_utils.start_fake_restore()
            >>> restore_task.interrupt_restore()
            True
        '''

        max_secs = 3
        seconds = 0

        try:
            bin_dir = os.path.join(virtualenv_dir(), 'bin')
            args = [os.path.join(bin_dir, 'killmatch'), constants.RESTORE_PROGRAM]
            args = [os.path.join('/usr/local/bin', 'killmatch'), constants.RESTORE_PROGRAM]
            self.log(f'args: {args}')

            attempts = 0
            while bitcoin_utils.is_restore_running() and attempts < 5:
                command.run(*args)
                if bitcoin_utils.is_restore_running():
                    sleep(3)
                    attempts += 1
        except CalledProcessError as cpe:
            self.log(cpe)
            self.log(format_exc())

        # a new page was displayed so give socketio time to connect
        while seconds < max_secs:
            self.manager.update_header(self.STOPPED_RESTORE)
            self.manager.update_subnotice(self.STOP_RESTORE_NOT_COMPLETE)
            self.manager.notify_done()

            sleep(1)
            seconds += 1

        # return value is for testing purposes only
        return not bitcoin_utils.is_restore_running()

    def remove_last_updated_file(self):
        '''
            Remove the last updated file so we don't
            try to restore from this directory again
            and will use it to backup the next time.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.setup_tmp_dir()
            >>> subdir_existed = test_utils.home_bitcoin_dir_exists()
            >>> restore_dir = os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1')
            >>> restore_task = RestoreTask(restore_dir)
            >>> restore_task.manager = BitcoinManager(restore_task.log_name)
            >>> restore_task.remove_last_updated_file()
            True
            >>> timestamp = '2019-03-29 16:48'
            >>> filename = os.path.join(restore_dir, '{}{}'.format(constants.LAST_UPDATED_PREFIX, timestamp))
            >>> with open(filename, "wt") as output_file:
            ...     output_file.write(timestamp)
            16
        '''

        ok = False
        filenames = os.listdir(self.restore_dir)
        for filename in filenames:
            if filename.startswith(constants.LAST_UPDATED_PREFIX):
                os.remove(os.path.join(self.restore_dir, filename))
                ok = True
                break

        # don't allow any more backups until the user tells us it's ok
        state.set_backups_enabled(False)

        return ok

    def report_errors(self, bad_metadata_files, missing_files):
        '''
            Report any errors detected during restoration.

            >>> from blockchain_backup.bitcoin.tests import utils as test_utils
            >>> test_utils.setup_tmp_dir()
            >>> subdir_existed = test_utils.home_bitcoin_dir_exists()
            >>> restore_task = RestoreTask(os.path.join(gettempdir(), 'bitcoin/data/testnet3/backups/level1'))
            >>> restore_task.manager = BitcoinManager(restore_task.log_name)
            >>> bad_metadata_files = None
            >>> missing_files = None
            >>> restore_task.report_errors(bad_metadata_files, missing_files)
            ['Please contact support@denova.com for assistance.']
            >>> bad_metadata_files = [os.path.join(gettempdir(), 'bitcoin/data/testnet3/blocks')]
            >>> missing_files = None
            >>> restore_task.report_errors(bad_metadata_files, missing_files)
            ['Please contact support@denova.com for assistance.', 'The following files could not have their metadata restored:', '/tmp/bitcoin/data/testnet3/blocks']
            >>> bad_metadata_files = None
            >>> missing_files = [os.path.join(gettempdir(), 'bitcoin/data/testnet3/chainstate/2560245.ldb')]
            >>> restore_task.report_errors(bad_metadata_files, missing_files)
            ['Please contact support@denova.com for assistance.', 'The following files are missing:', '/tmp/bitcoin/data/testnet3/chainstate/2560245.ldb']
            >>> bad_metadata_files = [os.path.join(gettempdir(), 'bitcoin/data/testnet3/blocks')]
            >>> missing_files = [os.path.join(gettempdir(), 'bitcoin/data/testnet3/chainstate/2560245.ldb')]
            >>> restore_task.report_errors(bad_metadata_files, missing_files)
            ['Please contact support@denova.com for assistance.', 'The following files could not have their metadata restored:', '/tmp/bitcoin/data/testnet3/blocks', 'The following files are missing:', '/tmp/bitcoin/data/testnet3/chainstate/2560245.ldb']
            >>> test_utils.delete_home_bitcoin_subdir(subdir_existed)
        '''

        lines = []
        lines.append('Please contact support@denova.com for assistance.')

        self.remove_last_updated_file()

        if bad_metadata_files:
            lines.append('The following files could not have their metadata restored:')
            for filename in bad_metadata_files:
                lines.append(filename)

        if missing_files:
            lines.append('The following files are missing:')
            for filename in missing_files:
                lines.append(filename)

        if lines:
            for line in lines:
                self.log(line)

            if not self.is_interrupted():
                self.manager.update_progress('\n'.join(lines))

        # only returning the lines so tests can verify everything's working
        return lines
