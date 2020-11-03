'''
    Tests for restoring the blockchain.

    Copyright 2018-2020 DeNova
    Last modified: 2020-10-08
'''

from ve import activate, virtualenv_dir
activate(django_app='blockchain_backup')
from django import setup
setup()

import os
from datetime import datetime, timedelta
from time import sleep
from unittest import TestCase
from django.utils.timezone import now, utc
from django.test import Client, RequestFactory

from blockchain_backup.bitcoin import preferences, state, views
from blockchain_backup.bitcoin.models import Preferences, State
from blockchain_backup.bitcoin.tests import utils as test_utils
from blockchain_backup.bitcoin.restore import RestoreTask
from blockchain_backup.bitcoin.utils import is_backup_running, is_bitcoind_running, is_restore_running
from denova.python.log import get_log

log = get_log()

class TestRestore(TestCase):

    def test_restore_with_good_post(self):
        '''
            Test restore with a good post.
        '''

        __, preselected_date_dir = state.get_backup_dates_and_dirs()

        request = self.factory.get('/bitcoin/restore/')
        response = views.Restore.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nAre you sure you want to restore the Bitcoin blockchain? | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'Select backup to restore:' in response.content)
        self.assertTrue(b'<input type="submit" value="Yes, start restoring" name="yes-start-restoring-button" id="yes-start-restoring-id" alt="Yes, start restoring" class="btn btn-primary font-weight-bold " role="button"  title="Restore the blockchain now"/>' in response.content)
        self.assertTrue(b'<input type="submit" value="No, cancel restore" name="no-cancel-restore-button" id="no-cancel-restore-id" alt="No, cancel restore" class="btn btn-secondary font-weight-bold " role="button"  title="Do not restore the blockchain."/>' in response.content)

        client = Client()
        response = client.post('/bitcoin/restore/',
                               {'backup_dates_with_dirs': preselected_date_dir[0] })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nRestoring Bitcoin Blockchain | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'WARNING: Do not shut down your computer until the restore finishes.' in response.content)
        self.assertTrue(b'Starting to restore the blockchain' in response.content)
        self.assertFalse(b'<input type="submit" value="Yes, start restoring" name="yes-start-restoring-button" id="yes-start-restoring-id" alt="Yes, start restoring" class="btn btn-primary font-weight-bold " role="button"  title="Restore the blockchain now"/>' in response.content)

        request = self.factory.get('/bitcoin/interrupt_restore/')
        response = views.Restore.as_view()(request)

    def test_restore_with_bad_post(self):
        '''
            Test restore with a bad post.
        '''

        request = self.factory.get('/bitcoin/restore/')
        response = views.Restore.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nAre you sure you want to restore the Bitcoin blockchain? | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'Select backup to restore:' in response.content)
        self.assertTrue(b'<input type="submit" value="Yes, start restoring" name="yes-start-restoring-button" id="yes-start-restoring-id" alt="Yes, start restoring" class="btn btn-primary font-weight-bold " role="button"  title="Restore the blockchain now"/>' in response.content)
        self.assertTrue(b'<input type="submit" value="No, cancel restore" name="no-cancel-restore-button" id="no-cancel-restore-id" alt="No, cancel restore" class="btn btn-secondary font-weight-bold " role="button"  title="Do not restore the blockchain."/>' in response.content)

        client = Client()
        response = client.post('/bitcoin/restore/', {'backup_dates_with_dirs': 'bad data'})
        request = self.factory.get('/bitcoin/interrupt_restore/')
        views.InterruptRestore.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nAre you sure you want to restore the Bitcoin blockchain? | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'Invalid fields -- details about the errors appear below each field.' in response.content)
        self.assertTrue(b'Select backup to restore:' in response.content)
        self.assertTrue(b'<input type="submit" value="Yes, start restoring" name="yes-start-restoring-button" id="yes-start-restoring-id" alt="Yes, start restoring" class="btn btn-primary font-weight-bold " role="button"  title="Restore the blockchain now"/>' in response.content)
        self.assertTrue(b'<input type="submit" value="No, cancel restore" name="no-cancel-restore-button" id="no-cancel-restore-id" alt="No, cancel restore" class="btn btn-secondary font-weight-bold " role="button"  title="Do not restore the blockchain."/>' in response.content)

    def test_restore_with_missing_blocks(self):
        '''
            Test restore with missing blocks in blockchain.
        '''
        MINUTE = 60
        MAX_SECONDS = 2 * MINUTE

        # remove a block from the blockchain
        data_dir = preferences.get_data_dir()
        block_filename = os.path.join(data_dir, 'blocks', 'blk00000.dat')
        if os.path.exists(block_filename): os.remove(block_filename)

        __, preselected_date_dir = state.get_backup_dates_and_dirs()

        request = self.factory.get('/bitcoin/restore/')
        response = views.Restore.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nAre you sure you want to restore the Bitcoin blockchain? | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'Select backup to restore:' in response.content)
        self.assertTrue(b'<input type="submit" value="Yes, start restoring" name="yes-start-restoring-button" id="yes-start-restoring-id" alt="Yes, start restoring" class="btn btn-primary font-weight-bold " role="button"  title="Restore the blockchain now"/>' in response.content)
        self.assertTrue(b'<input type="submit" value="No, cancel restore" name="no-cancel-restore-button" id="no-cancel-restore-id" alt="No, cancel restore" class="btn btn-secondary font-weight-bold " role="button"  title="Do not restore the blockchain."/>' in response.content)

        client = Client()
        response = client.post('/bitcoin/restore/',
                               {'backup_dates_with_dirs': preselected_date_dir[0] })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nRestoring Bitcoin Blockchain | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'WARNING: Do not shut down your computer until the restore finishes.' in response.content)
        self.assertTrue(b'Starting to restore the blockchain' in response.content)
        self.assertFalse(b'<input type="submit" value="Yes, start restoring" name="yes-start-restoring-button" id="yes-start-restoring-id" alt="Yes, start restoring" class="btn btn-primary font-weight-bold " role="button"  title="Restore the blockchain now"/>' in response.content)

        # wait until the restore finishes
        seconds = 0
        while not is_restore_running() and seconds < MAX_SECONDS:
            sleep(MINUTE)
            seconds += MINUTE

        # wait until bitcoind starts
        test_utils.start_bitcoind()
        seconds = 0
        while not is_bitcoind_running() and seconds < MAX_SECONDS:
            sleep(MINUTE)
            seconds += MINUTE

        self.assertTrue(is_bitcoind_running())

        # allow bitcoind to run for a while
        seconds = 0
        while is_bitcoind_running() and seconds < MAX_SECONDS:
            sleep(MINUTE)
            seconds += MINUTE

        if is_bitcoind_running():
            test_utils.stop_bitcoind()

        shutdown, error_message = test_utils.check_bitcoin_log(is_bitcoind_running)
        self.assertTrue(shutdown)
        self.assertTrue(error_message is None)

    def test_restore_with_missing_links(self):
        '''
            Test restore with missing links in chainstate.
        '''
        MINUTE = 60
        MAX_SECONDS = 2 * MINUTE

        # remove links from the chainstate
        data_dir = preferences.get_data_dir()
        dirname = os.path.join(data_dir, 'chainstate')
        entries = os.scandir(dirname)
        for entry in entries:
            if entry.name.endswith('.ldb'):
                os.remove(entry.path)

        __, preselected_date_dir = state.get_backup_dates_and_dirs()

        request = self.factory.get('/bitcoin/restore/')
        response = views.Restore.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nAre you sure you want to restore the Bitcoin blockchain? | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'Select backup to restore:' in response.content)
        self.assertTrue(b'<input type="submit" value="Yes, start restoring" name="yes-start-restoring-button" id="yes-start-restoring-id" alt="Yes, start restoring" class="btn btn-primary font-weight-bold " role="button"  title="Restore the blockchain now"/>' in response.content)
        self.assertTrue(b'<input type="submit" value="No, cancel restore" name="no-cancel-restore-button" id="no-cancel-restore-id" alt="No, cancel restore" class="btn btn-secondary font-weight-bold " role="button"  title="Do not restore the blockchain."/>' in response.content)

        client = Client()
        response = client.post('/bitcoin/restore/',
                               {'backup_dates_with_dirs': preselected_date_dir[0] })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nRestoring Bitcoin Blockchain | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'WARNING: Do not shut down your computer until the restore finishes.' in response.content)
        self.assertTrue(b'Starting to restore the blockchain' in response.content)
        self.assertFalse(b'<input type="submit" value="Yes, start restoring" name="yes-start-restoring-button" id="yes-start-restoring-id" alt="Yes, start restoring" class="btn btn-primary font-weight-bold " role="button"  title="Restore the blockchain now"/>' in response.content)

        # wait until the restore finishes
        seconds = 0
        while not is_restore_running() and seconds < MAX_SECONDS:
            sleep(MINUTE)
            seconds += MINUTE

        # wait until bitcoind starts
        test_utils.start_bitcoind()
        seconds = 0
        while not is_bitcoind_running() and seconds < MAX_SECONDS:
            sleep(MINUTE)
            seconds += MINUTE

        self.assertTrue(is_bitcoind_running())

        # allow bitcoind to run for a while
        seconds = 0
        while is_bitcoind_running() and seconds < MAX_SECONDS:
            sleep(MINUTE)
            seconds += MINUTE

        if is_bitcoind_running():
            test_utils.stop_bitcoind()

        shutdown, error_message = test_utils.check_bitcoin_log(is_bitcoind_running)
        self.assertTrue(shutdown)
        self.assertTrue(error_message is None)

    def test_restore_with_bad_backup(self):
        '''
            Test restore from a bad back up.
        '''
        MINUTE = 60
        MAX_SECONDS = 2 * MINUTE

        # change the data and backup dirs
        prefs = test_utils.get_preferences()
        prefs.data_dir = '/tmp/bitcoin/data-with-missing-file/testnet3/'
        prefs.backup_dir = '/tmp/bitcoin/data-with-missing-file/testnet3/backups/'
        preferences.save_preferences(prefs)

        __, preselected_date_dir = state.get_backup_dates_and_dirs()

        request = self.factory.get('/bitcoin/restore/')
        response = views.Restore.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nAre you sure you want to restore the Bitcoin blockchain? | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'Select backup to restore:' in response.content)
        self.assertTrue(b'<input type="submit" value="Yes, start restoring" name="yes-start-restoring-button" id="yes-start-restoring-id" alt="Yes, start restoring" class="btn btn-primary font-weight-bold " role="button"  title="Restore the blockchain now"/>' in response.content)
        self.assertTrue(b'<input type="submit" value="No, cancel restore" name="no-cancel-restore-button" id="no-cancel-restore-id" alt="No, cancel restore" class="btn btn-secondary font-weight-bold " role="button"  title="Do not restore the blockchain."/>' in response.content)

        client = Client()
        response = client.post('/bitcoin/restore/',
                               {'backup_dates_with_dirs': preselected_date_dir[0] })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nRestoring Bitcoin Blockchain | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'WARNING: Do not shut down your computer until the restore finishes.' in response.content)
        self.assertTrue(b'Starting to restore the blockchain' in response.content)
        self.assertFalse(b'<input type="submit" value="Yes, start restoring" name="yes-start-restoring-button" id="yes-start-restoring-id" alt="Yes, start restoring" class="btn btn-primary font-weight-bold " role="button"  title="Restore the blockchain now"/>' in response.content)

        # wait until the restore finishes
        seconds = 0
        while not is_restore_running() and seconds < MAX_SECONDS:
            sleep(MINUTE)
            seconds += MINUTE

        self.assertFalse(is_bitcoind_running())
        self.assertFalse(state.get_backups_enabled())

        name = 'last-updated-2020-01-17 14:41'
        last_updated_file = os.path.join(prefs.backup_dir, 'level1', name)
        self.assertFalse(os.path.exists(last_updated_file))

    def test_restore_prompt(self):
        '''
            Test prompting the user when to restore.
        '''

        request = self.factory.get('/bitcoin/restore/')
        response = views.Restore.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nAre you sure you want to restore the Bitcoin blockchain? | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b"All updates after the date you select will be lost." in response.content)
        self.assertTrue(b'Select backup to restore:' in response.content)
        self.assertTrue(b'<input type="submit" value="Yes, start restoring" name="yes-start-restoring-button" id="yes-start-restoring-id" alt="Yes, start restoring" class="btn btn-primary font-weight-bold " role="button"  title="Restore the blockchain now"/>' in response.content)
        self.assertTrue(b'<input type="submit" value="No, cancel restore" name="no-cancel-restore-button" id="no-cancel-restore-id" alt="No, cancel restore" class="btn btn-secondary font-weight-bold " role="button"  title="Do not restore the blockchain."/>' in response.content)

    def test_restore_with_bad_bin_dir(self):
        '''
            Test restoring with a bad bin directory.
        '''
        prefs = preferences.get_preferences()
        prefs.data_dir = '/tmp/bitcoin/data/'
        prefs.bin_dir = '/bad/bitcoin/bin/'
        prefs.restore_dir = '/tmp/bitcoin/data/restores/'
        preferences.save_preferences(prefs)

        request = self.factory.get('/bitcoin/restore/')
        response = views.Restore.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nUnable to Restore the Blockchain | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b"Unable to Restore the Blockchain" in response.content)
        self.assertTrue(b'The Bitcoin binary directory is not valid. Click <a class="btn btn-secondary" role="button" href="/bitcoin/preferences/" title="Click to change your preferences">Preferences</a> to set it.' in response.content)
        self.assertFalse(b'Select backup to restore:' in response.content)
        self.assertFalse(b'<input type="submit" value="Yes, start restoring" name="yes-start-restoring-button" id="yes-start-restoring-id" alt="Yes, start restoring" class="btn btn-primary font-weight-bold " role="button"  title="Restore the blockchain now"/>' in response.content)

    def test_restore_with_bad_data_dir(self):
        '''
            Test restoring with a bad data directory.
        '''
        prefs = preferences.get_preferences()
        prefs.data_dir = '/bad/bitcoin/data/'
        prefs.bin_dir = '/tmp/bitcoin/bin/'
        prefs.restore_dir = '/tmp/bitcoin/data/restores/'
        preferences.save_preferences(prefs)

        request = self.factory.get('/bitcoin/restore/')
        response = views.Restore.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nUnable to Restore the Blockchain | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b"Unable to Restore the Blockchain" in response.content)
        self.assertTrue(b'The Bitcoin data directory is not valid. Click <a class="btn btn-secondary" role="button" href="/bitcoin/preferences/" title="Click to change your preferences">Preferences</a> to set it.' in response.content)
        self.assertFalse(b'Select backup to restore:' in response.content)
        self.assertFalse(b'<input type="submit" value="Yes, start restoring" name="yes-start-restoring-button" id="yes-start-restoring-id" alt="Yes, start restoring" class="btn btn-primary font-weight-bold " role="button"  title="Restore the blockchain now"/>' in response.content)

    def test_restore_with_bitcoind_running(self):
        '''
            Test restoring with bitcoind already running.
        '''
        test_utils.start_bitcoind()
        while not is_bitcoind_running():
            sleep(5)

        request = self.factory.get('/bitcoin/restore/')
        response = views.Restore.as_view()(request)

        # stop the task before we start tests in case something fails
        test_utils.stop_bitcoind()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nBitcoinD Is Running | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'BitcoinD, one of the Bitcoin Core programs, appears to be running' in response.content)
        self.assertFalse(b'Bitcoin-QT, one of the Bitcoin Core programs, appears to be running' in response.content)
        self.assertFalse(b'Bitcoin-TX, one of the Bitcoin Core programs, appears to be running' in response.content)

    def test_restore_with_task_running(self):
        '''
            Test restoring with another task running.
        '''
        # make sure restore is not running
        request = self.factory.get('/bitcoin/interrupt_restore/')
        response = views.InterruptRestore.as_view()(request)
        sleep(20)

        # start the backup task
        request = self.factory.get('/bitcoin/backup/')
        response = views.Backup.as_view()(request)

        request = self.factory.get('/bitcoin/restore/')
        response = views.Restore.as_view()(request)

        # stop the task before we start tests in case something fails
        request = self.factory.get('/bitcoin/interrupt_backup/')
        views.InterruptBackup.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nBackup Task Is Running | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b'The backup task appears to be running' in response.content)
        self.assertFalse(b'The update task appears to be running' in response.content)
        self.assertFalse(b'The restore task appears to be running' in response.content)
        self.assertFalse(b'The access wallet task appears to be running' in response.content)
        self.assertFalse(b'The restore task appears to be running' in response.content)

    def test_interrupt_restore(self):
        '''
            Interrupt the restore.
        '''

        restore_task = RestoreTask('/tmp/bitcoin/data/testnet3/')
        self.assertFalse(restore_task is None)
        self.assertFalse(restore_task.is_interrupted())
        restore_task.interrupt()
        self.assertTrue(restore_task.is_interrupted())

        client = Client()
        response = client.post('/bitcoin/restore/',
          {'backup_dates_with_dirs': '/tmp/bitcoin/data/testnet3/'})
        self.assertEqual(response.status_code, 200)
        sleep(30)
        request = self.factory.get('/bitcoin/interrupt_restore/')
        response = views.InterruptRestore.as_view()(request)
        self.assertEqual(response.status_code, 200)

    def setUp(self):
        ''' Set up for a test. '''

        test_utils.setup_tmp_dir()

        self.home_bitcoin_subdir_exists = test_utils.home_bitcoin_dir_exists()
        test_utils.init_database()

        self.factory = RequestFactory()

        test_utils.stop_bitcoin_core_apps()

    def tearDown(self):

        # make sure nothing is left running
        test_utils.stop_bitcoin_core_apps()
        if is_restore_running():
            views.InterruptRestore.as_view()(self.factory.get('/bitcoin/interrupt_restore/'))
            sleep(20)
        if is_backup_running():
            views.InterruptBackup.as_view()(self.factory.get('/bitcoin/interrupt_backup/'))
            sleep(20)

        test_utils.stop_bitcoind()
        sleep(20)

        # some tests might create a .bitcon in the home dir
        test_utils.delete_home_bitcoin_subdir(self.home_bitcoin_subdir_exists)
