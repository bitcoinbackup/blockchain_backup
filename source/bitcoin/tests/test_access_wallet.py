'''
    Tests for accessing the bitcoin wallet.

    Copyright 2018-2020 DeNova
    Last modified: 2020-10-07
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
from django.test import RequestFactory

from blockchain_backup.bitcoin.models import Preferences
from blockchain_backup.bitcoin.preferences import get_data_dir, get_preferences, save_preferences
from blockchain_backup.bitcoin.state import get_backups_enabled
from blockchain_backup.bitcoin.tests import utils as test_utils
from blockchain_backup.bitcoin.access_wallet import AccessWalletTask
from blockchain_backup.bitcoin.utils import is_backup_running, is_bitcoind_running, is_bitcoin_qt_running
from blockchain_backup.bitcoin.views import Backup, InterruptBackup, AccessWallet
from denova.python.log import get_log

log = get_log()

class TestAccessWallet(TestCase):

    def test_access_wallet(self):
        '''
            Start to access_wallet via views
            and wait 3 minutes, then interrupt it.
        '''

        request = self.factory.get('/bitcoin/access_wallet/')
        response = AccessWallet.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nAccessing Bitcoin Core Wallet | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b"WARNING: Do not shut down your computer until Bitcoin-QT stops completely." in response.content)
        self.assertTrue(b'Bitcoin-QT will start in another window.' in response.content)
        self.assertFalse(b'Shutting down before this window says it is safe <em>could damage the blockchain</em>.' in response.content)

        sleep(180)
        self.assertFalse(b'Unexpected error occurred while running Bitcoin Core QT.' in response.content)
        test_utils.stop_bitcoin_qt()

    def test_access_wallet_with_bad_bin_dir(self):
        '''
            Test accessing the wallet with a bad bin directory.
        '''
        prefs = get_preferences()
        prefs.data_dir = '/tmp/bitcoin/data/'
        prefs.bin_dir = '/bad/bitcoin/bin/'
        prefs.backup_dir = '/tmp/bitcoin/data/backups/'
        save_preferences(prefs)
        sleep(10)

        request = self.factory.get('/bitcoin/access_wallet/')
        response = AccessWallet.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nAccessing Bitcoin Core Wallet | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'The Bitcoin binary directory is not valid.' in response.content)
        self.assertFalse(b'The Bitcoin data directory is not valid.' in response.content)
        self.assertFalse(b'The Bitcoin backup directory is not valid.' in response.content)
        self.assertTrue(b'Click <a class="btn btn-secondary" role="button" href="/bitcoin/preferences/" title="Click to change your preferences">Preferences</a> to set it.' in response.content)

    def test_access_wallet_with_bad_data_dir(self):
        '''
            Test accessing the wallet with a bad data directory.
        '''
        prefs = get_preferences()
        prefs.data_dir = '/bad/bitcoin/data/'
        prefs.bin_dir = '/tmp/bitcoin/bin/'
        prefs.backup_dir = '/tmp/bitcoin/data/backups/'
        save_preferences(prefs)

        request = self.factory.get('/bitcoin/access_wallet/')
        response = AccessWallet.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nAccessing Bitcoin Core Wallet | Blockchain Backup\n</title>" in response.content)
        self.assertFalse(b'The Bitcoin binary directory is not valid.' in response.content)
        self.assertTrue(b'The Bitcoin data directory is not valid.' in response.content)
        self.assertFalse(b'The Bitcoin backup directory is not valid.' in response.content)
        self.assertTrue(b'Click <a class="btn btn-secondary" role="button" href="/bitcoin/preferences/" title="Click to change your preferences">Preferences</a> to set it.' in response.content)

    def test_access_wallet_with_bitcoind_running(self):
        '''
            Test accessing the wallet with bitcoind already running.
        '''
        # start bitcoind and wait for it to get started
        test_utils.start_bitcoind()
        while not is_bitcoind_running():
            sleep(1)

        request = self.factory.get('/bitcoin/access_wallet/')
        response = AccessWallet.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nBitcoinD Is Running | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'BitcoinD, one of the Bitcoin Core programs, appears to be running' in response.content)
        self.assertFalse(b'Bitcoin-QT, one of the Bitcoin Core programs, appears to be running' in response.content)
        self.assertFalse(b'Bitcoin-TX, one of the Bitcoin Core programs, appears to be running' in response.content)

        test_utils.stop_bitcoind()

    def test_access_wallet_with_task_running(self):
        '''
            Test accessing the wallet with another task running.
        '''
        # start the backup task
        request = self.factory.get('/bitcoin/backup/')
        Backup.as_view()(request)

        request = self.factory.get('/bitcoin/access_wallet/')
        response = AccessWallet.as_view()(request)

        # stop the task before we start tests in case something fails
        self.factory.get('/bitcoin/interrupt_backup/')
        InterruptBackup.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nBackup Task Is Running | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'The backup task appears to be running' in response.content)
        self.assertFalse(b'The update task appears to be running' in response.content)
        self.assertFalse(b'The access wallet task appears to be running' in response.content)
        self.assertFalse(b'The restore task appears to be running' in response.content)

    def test_access_wallet_with_bad_data(self):
        '''
            Test access wallet with bad data
        '''
        MINUTE = 60
        WAIT_SECONDS = 10
        MAX_SECONDS = 3 * MINUTE

        # remove a block from the blockchain
        block_filename = os.path.join(get_data_dir(), 'blocks', 'blk00000.dat')
        if os.path.exists(block_filename):
            os.remove(block_filename)

        request = self.factory.get('/bitcoin/access_wallet/')
        response = AccessWallet.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nAccessing Bitcoin Core Wallet | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b"WARNING: Do not shut down your computer until Bitcoin-QT stops completely." in response.content)
        self.assertTrue(b'Bitcoin-QT will start in another window.' in response.content)
        self.assertFalse(b'Shutting down before this window says it is safe <em>could damage the blockchain</em>.' in response.content)

        done = False
        error_found = False
        error_message = None
        secs = 0
        while not done:
            shutdown, error_message = test_utils.check_bitcoin_log()
            if error_message:
                error = error_message.strip(' ')
                error_found = 'Fatal LevelDB error' in error or 'Error opening block database' in error
            done = shutdown or error_found or not get_backups_enabled() or secs > MAX_SECONDS
            if not done:
                sleep(WAIT_SECONDS)
                secs += WAIT_SECONDS

        if not error_found:
            shutdown, error_message = test_utils.check_bitcoin_log()
            self.assertTrue(shutdown)
            error = error_message.strip(' ')
            error_found = 'Fatal LevelDB error' in error or 'Error opening block database' in error
        self.assertTrue(error_found)

        test_utils.stop_bitcoin_qt()

        self.assertFalse(get_backups_enabled())

    def setUp(self):
        ''' Set up for a test. '''

        test_utils.setup_tmp_dir()

        self.home_bitcoin_subdir_exists = test_utils.home_bitcoin_dir_exists()
        test_utils.init_database()

        self.factory = RequestFactory()

        test_utils.stop_bitcoin_core_apps()

    def tearDown(self):

        # make sure nothing is left running
        if is_backup_running():
            InterruptBackup.as_view()(self.factory.get('/bitcoin/interrupt_backup/'))
            sleep(20)

        # make sure bitcoin-qt shuts down; 60 secs may not be enough,
        # but don't want to waste time waiting needlessly
        if is_bitcoin_qt_running():
            sleep(60)
            test_utils.stop_bitcoin_qt()

        # some tests might create a .bitcom in the home dir
        test_utils.delete_home_bitcoin_subdir(self.home_bitcoin_subdir_exists)
