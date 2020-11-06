'''
    Tests the views for bitcoin.

    Many of the tests are in their own
    class, e.g., test_backup.py

    Copyright 2018-2020 DeNova
    Last modified: 2020-11-05
'''

from ve import activate, virtualenv_dir
activate(django_app='blockchain_backup')
from django import setup
setup()

import os
from datetime import datetime, timedelta
from time import sleep
from django.http.response import Http404
from django.utils.timezone import now, utc
from django.test import Client, RequestFactory, TestCase

from blockchain_backup.bitcoin import preferences, views
from blockchain_backup.bitcoin.tests import utils as test_utils
from blockchain_backup.settings import ALLOWED_HOSTS
from denova.python.log import get_log

log = get_log()

class TestViews(TestCase):

    def test_home(self):
        '''
            Show the home page when nothing has been configured.
        '''
        test_utils.set_new_preferences(None)
        test_utils.set_new_state(None)

        request = self.factory.get('/')
        response = views.Home.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nGetting Started | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b'Get started:' in response.content)
        self.assertFalse(b'<a class="btn btn-secondary" role="button" href="/bitcoin/access_wallet/">Access wallet' in response.content)
        self.assertFalse(b'<a class="btn btn-secondary" role="button" href="/bitcoin/update/">Update' in response.content)
        self.assertFalse(b'<a class="btn btn-secondary" role="button" href="/bitcoin/backup/">Back up' in response.content)
        self.assertFalse(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary" role="button"  title="Restore the blockchain"> <strong>Restore</strong> </a>' in response.content)

    def test_preferences(self):
        '''
            Configuring the prefernces when nothing has been configured.
        '''
        test_utils.set_new_preferences(None)
        test_utils.set_new_state(None)

        client = Client(HTTP_X_FORWARDED_FOR='localhost')
        response = client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 1,
                                'backup_levels': 2,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '',
                                })

        # if successful post, redirected to the home page
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

        # verify the preferences; the form should
        # have checked, but we'll double check
        self.assertTrue(preferences.data_dir_ok())
        self.assertTrue(preferences.backup_dir_ok())
        self.assertTrue(preferences.bin_dir_ok())

    def test_backup(self):
        '''
            Test backing up on a fresh install.
        '''

        test_utils.set_new_preferences(None)
        test_utils.set_new_state(None)

        request = self.factory.get('/bitcoin/backup/')
        response = views.Backup.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"<title>\nBacking Up Bitcoin's Blockchain | Blockchain Backup\n</title>" in response.content)
        self.assertTrue(b'The Bitcoin binary directory is not valid.' in response.content)

    def test_restore(self):
        '''
            Test restoring.
        '''
        request = self.factory.get('/bitcoin/restore/')
        response = views.Restore.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nAre you sure you want to restore the Bitcoin blockchain? | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b"All updates after" in response.content)
        self.assertTrue(b'Select backup to restore:' in response.content)
        self.assertFalse(b'<title>\nUnable to Restore the Blockchain | Blockchain Backup\n</title>' in response.content)
        self.assertFalse(b'The Bitcoin binary directory is not valid. Click <a class="btn btn-secondary" role="button" href="/bitcoin/preferences/" title="Click to change your preferences">Preferences</a> to set it.' in response.content)

    def test_restore_fresh_install(self):
        '''
            Test restoring on a fresh install.
        '''

        test_utils.set_new_preferences(None)
        test_utils.set_new_state(None)

        request = self.factory.get('/bitcoin/restore/')
        response = views.Restore.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(b'<title>\nBlockchain Backup adds resilience to Bitcoin Core | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b"Unable to Restore the Blockchain" in response.content)
        self.assertTrue(b'The Bitcoin binary directory is not valid. Click <a class="btn btn-secondary" role="button" href="/bitcoin/preferences/" title="Click to change your preferences">Preferences</a> to set it.' in response.content)
        self.assertFalse(b"All updates after" in response.content)
        self.assertFalse(b'Select backup to restore:' in response.content)

    def test_good_local_access(self):
        '''
            Test that only local hosts can access a page.
        '''

        for host in ALLOWED_HOSTS:
            client = Client(HTTP_X_FORWARDED_FOR=host)
            response = client.get('/')
            self.assertTrue(b'<title>\nBlockchain Backup adds resilience to Bitcoin Core | Blockchain Backup\n</title>' in response.content)
            self.assertFalse(b'<title>\nNo Remote Access Permitted | Blockchain Backup\n</title>' in response.content)
            self.assertFalse(b'You can only access Blockchain Backup from the same machine' in response.content)

    def test_bad_local_access(self):
        '''
            Test a remote ip address cannot access page.
        '''

        client = Client(HTTP_X_FORWARDED_FOR='1.1.1.1')
        response = client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nNo Remote Access Permitted | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b'You can only access Blockchain Backup from the same machine' in response.content)

    def test_init_data_dir(self):
        '''
            Test initializing the data dir with a click.
        '''

        request = self.factory.get('/bitcoin/init_data_dir/')
        response = views.InitDataDir.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

    def setUp(self):
        ''' Set up for a test. '''

        test_utils.setup_tmp_dir()

        self.home_bitcoin_subdir_exists = test_utils.home_bitcoin_dir_exists()
        test_utils.init_database()

        self.factory = RequestFactory()

        test_utils.stop_bitcoin_core_apps()

    def tearDown(self):

        # some tests might create a .bitcon in the home dir
        test_utils.delete_home_bitcoin_subdir(self.home_bitcoin_subdir_exists)

        test_utils.stop_bitcoin_core_apps()
