'''
    Tests for updating the blockchain.

    Copyright 2018-2021 DeNova
    Last modified: 2021-07-14
'''

from ve import activate, virtualenv_dir
activate(django_app='blockchain_backup')
from django import setup
setup()

import json
import os
from datetime import datetime, timedelta
from time import sleep
from unittest import TestCase
from django.utils.timezone import now, utc
from django.test import RequestFactory

from blockchain_backup.bitcoin.backup_utils import is_backup_running
from blockchain_backup.bitcoin.core_utils import check_bitcoin_log, is_bitcoind_running
from blockchain_backup.bitcoin.models import Preferences
from blockchain_backup.bitcoin.preferences import get_data_dir, get_preferences, save_preferences
from blockchain_backup.bitcoin.state import get_backups_enabled, set_backups_enabled
from blockchain_backup.bitcoin.tests import utils as test_utils
from blockchain_backup.bitcoin.update import UpdateTask
from blockchain_backup.bitcoin.views import Backup, InterruptBackup, Update, InterruptUpdate
from denova.django_addons.singleton import get_singleton, save_singleton
from denova.python.log import Log

log = Log()

class TestUpdate(TestCase):

    def test_update(self):
        '''
            Start the update via views,
            wait a few minutes, then interrupt it.
        '''

        request = self.factory.get('/bitcoin/update/')
        response = Update.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nUpdating Bitcoin's Blockchain | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b"WARNING: Don't shut down your computer before you" in response.content)
        self.assertTrue(b'<a class="btn btn-secondary " role="button" id="stop_button" href="/bitcoin/interrupt_update/" title="Click to stop updating the blockchain">Stop update</a>' in response.content)
        self.assertTrue(b'Shutting down before this window says it is safe <em>could damage the blockchain</em>.' in response.content)

        sleep(180)
        if is_bitcoind_running():
            test_utils.stop_bitcoind()

    def test_update_with_missing_blocks(self):
        '''
            Start the update with missing blocks.
        '''
        # remove a block from the blockchain
        block_filename = os.path.join(get_data_dir(), 'blocks', 'blk00000.dat')
        if os.path.exists(block_filename):
            os.remove(block_filename)

        request = self.factory.get('/bitcoin/update/')
        response = Update.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nUpdating Bitcoin's Blockchain | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b"WARNING: Don't shut down your computer before you" in response.content)
        self.assertTrue(b'<a class="btn btn-secondary " role="button" id="stop_button" href="/bitcoin/interrupt_update/" title="Click to stop updating the blockchain">Stop update</a>' in response.content)
        self.assertTrue(b'Shutting down before this window says it is safe <em>could damage the blockchain</em>.' in response.content)

        sleep(60)

        self.assertFalse(is_bitcoind_running())

        shutdown, error_message = check_bitcoin_log(get_data_dir(), is_bitcoind_running)
        self.assertTrue(shutdown)
        error = error_message.strip(' ')
        error_found = ('Fatal LevelDB error' in error or
                       'Error opening block database' in error or
                       'Aborted block database rebuild. Exiting.' in error)
        self.assertTrue(error_found)

        self.assertFalse(get_backups_enabled())

    def test_update_with_missing_links(self):
        '''
            Start the update with missing links.
        '''
        # remove links from the chainstate
        dirname = os.path.join(get_data_dir(), 'chainstate')
        entries = os.scandir(dirname)
        for entry in entries:
            if entry.name.endswith('.ldb'):
                os.remove(entry.path)

        request = self.factory.get('/bitcoin/update/')
        response = Update.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nUpdating Bitcoin's Blockchain | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b"WARNING: Don't shut down your computer before you" in response.content)
        self.assertTrue(b'<a class="btn btn-secondary " role="button" id="stop_button" href="/bitcoin/interrupt_update/" title="Click to stop updating the blockchain">Stop update</a>' in response.content)
        self.assertTrue(b'Shutting down before this window says it is safe <em>could damage the blockchain</em>.' in response.content)

        sleep(60)

        self.assertFalse(is_bitcoind_running())

        shutdown, error_message = check_bitcoin_log(get_data_dir(), is_bitcoind_running)
        self.assertTrue(shutdown)
        log(error_message)
        self.assertTrue('Aborted block database rebuild. Exiting.' in error_message or
                        'Error opening block database.' in error_message or
                        'Fatal LevelDB error' in error_message)

        self.assertFalse(get_backups_enabled())

    def test_update_with_bad_bin_dir(self):
        '''
            Test updating with a bad bin directory.
        '''
        prefs = get_preferences()
        prefs.data_dir = '/tmp/bitcoin/data/'
        prefs.bin_dir = '/bad/bitcoin/bin/'
        prefs.backup_dir = '/tmp/bitcoin/data/backups/'
        save_preferences(prefs)

        request = self.factory.get('/bitcoin/update/')
        response = Update.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nUpdating Bitcoin's Blockchain | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'The Bitcoin binary directory is not valid.' in response.content)
        self.assertFalse(b'The Bitcoin data directory is not valid.' in response.content)
        self.assertFalse(b'The Bitcoin backup directory is not valid.' in response.content)
        self.assertTrue(b'Click <a class="btn btn-secondary" id="preferences-id" role="button" href="/bitcoin/preferences/" title="Click to change your preferences">Preferences</a> to set it.' in response.content)

        self.assertTrue(get_backups_enabled())

    def test_update_with_bad_data_dir(self):
        '''
            Test updating with a bad data directory.
        '''
        prefs = get_preferences()
        prefs.data_dir = '/bad/bitcoin/data/'
        prefs.bin_dir = '/tmp/bitcoin/bin/'
        prefs.backup_dir = '/tmp/bitcoin/data/backups/'
        save_preferences(prefs)

        request = self.factory.get('/bitcoin/update/')
        response = Update.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nUpdating Bitcoin's Blockchain | Blockchain Backup\n</title>" in response.content)
        self.assertFalse(b'The Bitcoin binary directory is not valid.' in response.content)
        self.assertTrue(b'The Bitcoin data directory is not valid.' in response.content)
        self.assertFalse(b'The Bitcoin backup directory is not valid.' in response.content)
        self.assertTrue(b'Click <a class="btn btn-secondary" id="preferences-id" role="button" href="/bitcoin/preferences/" title="Click to change your preferences">Preferences</a> to set it.' in response.content)

        self.assertTrue(get_backups_enabled())

    def test_update_with_bitcoin_d_running(self):
        '''
            Test updating with bitcoind already running.
        '''
        # start bitcoind and wait for it to get started
        test_utils.start_bitcoind()
        while not is_bitcoind_running():
            sleep(1)
        log('bitcoind is running')

        request = self.factory.get('/bitcoin/update/')
        response = Update.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nBitcoinD Is Running | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'BitcoinD, one of the Bitcoin Core programs, appears to be running' in response.content)
        self.assertFalse(b'Bitcoin-QT, one of the Bitcoin Core programs, appears to be running' in response.content)
        self.assertFalse(b'Bitcoin-TX, one of the Bitcoin Core programs, appears to be running' in response.content)

        if is_bitcoind_running():
            test_utils.stop_bitcoind()

        self.assertTrue(get_backups_enabled())

    def test_update_with_task_running(self):
        '''
            Test updating with another task running.
        '''
        # start the backup task
        request = self.factory.get('/bitcoin/backup/')
        Backup.as_view()(request)

        request = self.factory.get('/bitcoin/update/')
        response = Update.as_view()(request)

        # stop the task before we start tests in case something fails
        self.factory.get('/bitcoin/interrupt_backup/')
        InterruptBackup.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nBackup Task Is Running | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'The backup task appears to be running' in response.content)
        self.assertFalse(b'The update task appears to be running' in response.content)
        self.assertFalse(b'The access wallet task appears to be running' in response.content)
        self.assertFalse(b'The restore task appears to be running' in response.content)

        self.assertTrue(get_backups_enabled())

    def test_interrupt_update(self):
        '''
            Interrupt the update.
        '''

        set_backups_enabled(True)

        update_task = UpdateTask()
        self.assertFalse(update_task is None)
        self.assertFalse(update_task.is_interrupted())
        update_task.interrupt()
        self.assertTrue(update_task.is_interrupted())

        request = self.factory.get('/bitcoin/update/')
        response = Update.as_view()(request)
        self.assertEqual(response.status_code, 200)
        sleep(60)
        request = self.factory.get('/bitcoin/interrupt_update/')
        InterruptUpdate.as_view()(request)

    def setUp(self):
        ''' Set up for a test. '''

        test_utils.setup_tmp_dir()

        self.home_bitcoin_subdir_exists = test_utils.home_bitcoin_dir_exists()
        self.original_preferences = test_utils.get_preferences()
        test_utils.init_database()

        self.factory = RequestFactory()

        test_utils.stop_bitcoin_core_apps()

    def tearDown(self):

        # make sure nothing is left running
        test_utils.stop_bitcoin_core_apps()
        if is_backup_running():
            InterruptBackup.as_view()(self.factory.get('/bitcoin/interrupt_backup/'))
            sleep(20)

        test_utils.restore_initial_data()

        # some tests might create a .bitcon in the home dir
        test_utils.delete_home_bitcoin_subdir(self.home_bitcoin_subdir_exists)
