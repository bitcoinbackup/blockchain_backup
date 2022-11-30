'''
    Tests for backup of the blockchain.

    Copyright 2018-2021 DeNova
    Last modified: 2021-07-14
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

from blockchain_backup.bitcoin import preferences, state, views
from blockchain_backup.bitcoin.backup_utils import is_backup_running
from blockchain_backup.bitcoin.core_utils import is_bitcoind_running
from blockchain_backup.bitcoin.models import Preferences, State
from blockchain_backup.bitcoin.tests import utils as test_utils
from blockchain_backup.bitcoin.backup import BackupTask
from denova.python.log import Log

log = Log()

class TestBackup(TestCase):

    def test_backup(self):
        '''
            Start the backup via views and wait 1 minute,
            then interrupt it.
        '''

        request = self.factory.get('/bitcoin/backup/')
        response = views.Backup.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nBacking Up Bitcoin's Blockchain | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b"WARNING: Stopping the backup could damage the ability to restore the blockchain." in response.content)
        self.assertTrue(b'If you need to stop the backup, then <a class="btn btn-secondary " href="/bitcoin/interrupt_backup/"' in response.content)
        self.assertTrue(b'Starting to back up the blockchain' in response.content)

        sleep(60)
        test_utils.stop_bitcoind()

    def test_backup_with_bad_bin_dir(self):
        '''
            Test backing up with a bad bin directory.
        '''
        prefs = preferences.get_preferences()
        prefs.data_dir = '/tmp/bitcoin/data/'
        prefs.bin_dir = '/bad/bitcoin/bin/'
        prefs.backup_dir = '/tmp/bitcoin/data/backups/'
        preferences.save_preferences(prefs)

        request = self.factory.get('/bitcoin/backup/')
        response = views.Backup.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nBacking Up Bitcoin's Blockchain | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'The Bitcoin binary directory is not valid.' in response.content)
        self.assertFalse(b'The Bitcoin data directory is not valid.' in response.content)
        self.assertFalse(b'The Bitcoin backup directory is not valid.' in response.content)
        self.assertTrue(b'Click <a class="btn btn-secondary" id="preferences-id" role="button" href="/bitcoin/preferences/" title="Click to change your preferences">Preferences</a> to set it.' in response.content)

    def test_backup_with_bad_data_dir(self):
        '''
            Test backing up with a bad data directory.
        '''
        prefs = preferences.get_preferences()
        prefs.data_dir = '/bad/bitcoin/data/'
        prefs.bin_dir = '/tmp/bitcoin/bin/'
        prefs.backup_dir = '/tmp/bitcoin/data/backups/'
        preferences.save_preferences(prefs)

        request = self.factory.get('/bitcoin/backup/')
        response = views.Backup.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nBacking Up Bitcoin's Blockchain | Blockchain Backup\n</title>" in response.content)
        self.assertFalse(b'The Bitcoin binary directory is not valid.' in response.content)
        self.assertTrue(b'The Bitcoin data directory is not valid.' in response.content)
        self.assertFalse(b'The Bitcoin backup directory is not valid.' in response.content)
        self.assertTrue(b'Click <a class="btn btn-secondary" id="preferences-id" role="button" href="/bitcoin/preferences/" title="Click to change your preferences">Preferences</a> to set it.' in response.content)

    def test_backup_with_bitcoind_running(self):
        '''
            Test backing up with bitcoind already running.
        '''
        test_utils.start_bitcoind()
        while not is_bitcoind_running():
            sleep(5)

        request = self.factory.get('/bitcoin/backup/')
        response = views.Backup.as_view()(request)

        # stop bitcoin in case any tests fail
        test_utils.stop_bitcoind()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nBitcoinD Is Running | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'BitcoinD, one of the Bitcoin Core programs, appears to be running' in response.content)
        self.assertFalse(b'Bitcoin-QT, one of the Bitcoin Core programs, appears to be running' in response.content)
        self.assertFalse(b'Bitcoin-TX, one of the Bitcoin Core programs, appears to be running' in response.content)

    def test_backup_with_task_running(self):
        '''
            Test backing up with another task running.
        '''
        # start another task
        request = self.factory.get('/bitcoin/update/')
        views.Update.as_view()(request)

        request = self.factory.get('/bitcoin/backup/')
        response = views.Backup.as_view()(request)

        # stop the task before we start tests in case something fails
        self.factory.get('/bitcoin/interrupt_update/')
        views.InterruptUpdate.as_view()(request)

        task_title_ok = b"<title>\nUpdate Task Is Running | Blockchain Backup\n</title>" in response.content
        app_title_ok = b"<title>\nBitcoinD Is Running | Blockchain Backup\n</title>" in response.content

        self.assertEqual(response.status_code, 200)
        self.assertTrue(task_title_ok or app_title_ok)
        if task_title_ok:
            self.assertTrue(b'The update task appears to be running' in response.content)
        else:
            self.assertTrue(b'BitcoinD, one of the Bitcoin Core programs, appears to be running' in response.content)
        self.assertFalse(b'The restore task appears to be running' in response.content)
        self.assertFalse(b'The backup task appears to be running' in response.content)
        self.assertFalse(b'The access wallet task appears to be running' in response.content)

    def test_backup_when_backups_disabled(self):
        '''
            Test trying to back up when backups disabled.
        '''

        state.set_backups_enabled(False)

        request = self.factory.get('/bitcoin/backup/')
        response = views.Backup.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/bitcoin/change_backup_status/')
        self.assertFalse(is_backup_running())

        state.set_backups_enabled(True)

    def test_interrupt_backup(self):
        '''
            Interrupt the backup.
        '''

        backup_task = BackupTask()
        self.assertFalse(backup_task is None)
        self.assertFalse(backup_task.is_interrupted())
        backup_task.interrupt()
        self.assertTrue(backup_task.is_interrupted())

        request = self.factory.get('/bitcoin/backup/')
        response = views.Backup.as_view()(request)
        self.assertEqual(response.status_code, 200)
        sleep(60)
        request = self.factory.get('/bitcoin/interrupt_backup/')
        response = views.InterruptBackup.as_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_change_backup_status(self):
        '''
            Test changing the backup status.
        '''
        state.set_backups_enabled(True)
        request = self.factory.get('/bitcoin/change_backup_status/')
        response = views.ChangeBackupStatus.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nBackups Enabled | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'Disable backups' in response.content)
        self.assertTrue(b'Leave backups enabled' in response.content)

        state.set_backups_enabled(False)
        request = self.factory.get('/bitcoin/change_backup_status/')
        response = views.ChangeBackupStatus.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nBackups Disabled | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'Leave backups disabled' in response.content)
        self.assertTrue(b'Enable backups' in response.content)

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
        if is_backup_running():
            log('interrupting backup')
            views.InterruptBackup.as_view()(self.factory.get('/bitcoin/interrupt_backup/'))
            sleep(20)

        # some tests might create a .bitcon in the home dir
        test_utils.delete_home_bitcoin_subdir(self.home_bitcoin_subdir_exists)
