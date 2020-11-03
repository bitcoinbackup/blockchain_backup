'''
    Tests for preferences.

    Copyright 2018-2020 DeNova
    Last modified: 2020-10-08
'''

from ve import activate, virtualenv_dir
activate(django_app='blockchain_backup')
from django import setup
setup()

import json
import os
import shutil
from datetime import datetime, timedelta
from django.utils.timezone import now, utc
from django.test import Client, RequestFactory, TestCase
from django.test.utils import setup_test_environment

from blockchain_backup.bitcoin import preferences
from blockchain_backup.bitcoin.models import Preferences
from blockchain_backup.bitcoin.tests import utils as test_utils
from blockchain_backup.bitcoin.views import ChangePreferences
from denova.python.log import get_log

log = get_log()


class TestPreferences(TestCase):

    def test_get_page(self):
        '''
            Get the preferences page.
         '''
        request = self.factory.get('/bitcoin/preferences')
        response = ChangePreferences.as_view()(request)
        self.check_basics(response)

        request = self.factory.get('/bitcoin/preferences/')
        response = ChangePreferences.as_view()(request)
        self.check_basics(response)

        response = self.client.get('/bitcoin/preferences/')
        self.assertEqual(response.status_code, 200)

    def test_post_all_good_data(self):
        '''
            Test adding all good data to preferences.
         '''
        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 1,
                                'backup_levels': 2,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '',
                                })
        self.check_good_post(response)

    def test_post_minimum_good_no_backup_dir(self):
        '''
            Test adding the minimum good data with no backup.
         '''
        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 1,
                                'backup_levels': 2,
                                })
        self.check_good_post(response)

    def test_post_minimum_good_no_data_dir(self):
        '''
            Test adding the minimum good data with no data dir.
         '''
        # link up the data directory from the home
        data_dir = '/tmp/bitcoin/data/'
        home_data_dir = os.path.join('/home', os.getlogin(), '.bitcoin')
        if os.path.lexists(home_data_dir):
            if os.path.isdir(home_data_dir):
                os.rmdir(home_data_dir)
            else:
                os.remove(home_data_dir)
        elif os.path.exists(home_data_dir):
            shutil.rmtree(home_data_dir)
        os.symlink(data_dir, home_data_dir)

        response = self.client.post('/bitcoin/preferences/',
                               {'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'backup_schedule': 1,
                                'backup_levels': 2,
                               })
        # remove the link or the data dir
        if os.path.lexists(home_data_dir):
            os.remove(home_data_dir)
        elif os.path.exists(home_data_dir):
            shutil.rmtree(home_data_dir)

        self.check_good_post(response)

    def test_post_good_extra_args(self):
        '''
            Test adding good extra args.
         '''
        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 1,
                                'backup_levels': 2,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '-onlynet=ipv4'
                                })
        self.check_good_post(response)

    def test_post_all_bad_data(self):
        '''
            Test adding all bad data to preferences.
         '''
        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/bitcoin/data/',
                                'bin_dir': '/bitcoin/bin/',
                                'backup_schedule': 0,
                                'backup_levels': 0,
                                'backup_dir': '/bitcoin/data/backups/',
                                'extra_args': '-version',
                                })
        self.check_bad_post(response)
        self.check_all_bad_fields(response)

    def test_post_bad_backup_schedule(self):
        '''
            Test adding a bad backup schedule.
         '''
        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 0,
                                'backup_levels': 2,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '',
                                })
        self.check_bad_post(response)
        self.check_bad_backup_schedule(response)

        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 27,
                                'backup_levels': 2,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '',
                                })
        self.check_bad_post(response)
        self.check_bad_backup_schedule(response)

        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_levels': 2,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '',
                                })
        self.check_bad_post(response)
        self.check_bad_backup_schedule(response)

    def test_post_bad_backup_levels(self):
        '''
            Test adding a bad backup levels.
         '''
        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 1,
                                'backup_levels': 0,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '',
                                })
        self.check_bad_post(response)
        self.check_bad_backup_levels(response)

        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 1,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '',
                                })
        self.check_bad_post(response)
        self.check_bad_backup_levels(response)

    def test_post_bad_extra_args(self):
        '''
            Test adding bad extra args.
         '''
        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 1,
                                'backup_levels': 2,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '-blocksdir -datadir'
                                })
        self.check_bad_post(response)
        self.check_bad_extra_args(response)
        self.assertTrue(b'The -blocksdir option is not permitted. The &quot;blocks&quot; directory must always be a subdirectory of the &quot;Data directory&quot;.' in response.content)
        self.assertFalse(b'The -datadir may only be specified in the &quot;Data directory&quot; field above.' in response.content)

    def test_post_bad_extra_version_arg(self):
        '''
            Test adding a bad extra version_arg.
         '''
        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 1,
                                'backup_levels': 2,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '-version'
                                })
        self.check_bad_post(response)
        self.check_bad_extra_args(response)
        self.assertTrue(b'The -version option is not permitted. You can only use it from the command line.' in response.content)

    def test_post_bad_extra_blocksdir_arg(self):
        '''
            Test adding a bad extra blocksdir arg.
         '''
        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 1,
                                'backup_levels': 2,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '-blocksdir'
                                })
        self.check_bad_post(response)
        self.check_bad_extra_args(response)
        self.assertTrue(b'The -blocksdir option is not permitted. The &quot;blocks&quot; directory must always be a subdirectory of the &quot;Data directory&quot;.' in response.content)

    def test_post_bad_extra_debuglogfile_arg(self):
        '''
            Test adding a bad extra debuglogfile arg.
         '''
        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 1,
                                'backup_levels': 2,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '-debuglogfile'
                                })
        self.check_bad_post(response)
        self.check_bad_extra_args(response)
        self.assertTrue(b'The -debuglogfile option is not permitted.' in response.content)

    def test_post_bad_extra_daemon_arg(self):
        '''
            Test adding a bad extra daemon arg.
         '''
        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 1,
                                'backup_levels': 2,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '-daemon'
                                })
        self.check_bad_post(response)
        self.check_bad_extra_args(response)
        self.assertTrue(b'The -daemon option is already used when running bitcoind so it is not permitted.' in response.content)

    def test_post_bad_extra_disablewallet_arg(self):
        '''
            Test adding a bad extra disablewallet arg.
         '''
        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 1,
                                'backup_levels': 2,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '-disablewallet'
                                })
        self.check_bad_post(response)
        self.check_bad_extra_args(response)
        self.assertTrue(b'The -disablewallet option is already used when running bitcoind so it is not permitted.' in response.content)

    def test_post_bad_extra_server_arg(self):
        '''
            Test adding a bad extra server arg.
         '''
        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 1,
                                'backup_levels': 2,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '-server'
                                })
        self.check_bad_post(response)
        self.check_bad_extra_args(response)
        self.assertTrue(b'The -server RPC option is already used when running bitcoin-qt so it is not permitted.' in response.content)

    def test_post_bad_extra_datadir_arg(self):
        '''
            Test adding a bad extra datadir_arg.
         '''
        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 1,
                                'backup_levels': 2,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '-datadir'
                                })
        self.check_bad_post(response)
        self.check_bad_extra_args(response)
        self.assertTrue(b'The -datadir may only be specified in the &quot;Data directory&quot; field above.' in response.content)

    def test_post_bad_extra_choosedatadir_arg(self):
        '''
            Test adding a bad extra choosedatadir arg.
         '''
        response = self.client.post('/bitcoin/preferences/',
                               {'data_dir': '/tmp/bitcoin/data/',
                                'bin_dir': '/tmp/bitcoin/bin/',
                                'backup_schedule': 1,
                                'backup_levels': 2,
                                'backup_dir': '/tmp/bitcoin/data/backups/',
                                'extra_args': '-choosedatadir'
                                })
        self.check_bad_post(response)
        self.check_bad_extra_args(response)
        self.assertTrue(b'The -choosedatadir option is not supported. Specify it in the &quot;Data directory&quot; field above.' in response.content)

    def check_basics(self, response):
        '''
            Check the basic page.
        '''
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nPreferences | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b'Bitcoin Core directories' in response.content)
        self.assertTrue(b'Bitcoin Core apps' in response.content)
        self.assertTrue(b'Blockchain Backups' in response.content)
        self.assertTrue(b'<input type="submit" value="Save" name="save-button" id="save-id" alt="Save" class="btn btn-primary font-weight-bold " role="button"  title="Save your preferences"/>' in response.content)

    def check_good_post(self, response):
        '''
            Check the post had good data.
        '''
        # if successful post, redirected to the home page
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

        # verify the preferences; the form should
        # have checked, but we'll double check
        self.assertTrue(preferences.data_dir_ok())
        self.assertTrue(preferences.backup_dir_ok())
        self.assertTrue(preferences.bin_dir_ok())

    def check_bad_post(self, response):
        '''
            Check the post had bad data.
        '''
        # remove any directories created during the test
        home_data_dir = os.path.join('/home', os.getlogin(), '.bitcoin')
        if os.path.exists(home_data_dir) and len(os.listdir(home_data_dir)) <= 0:
            os.rmdir(home_data_dir)

        # if validation error, then we stay on the same page
        self.assertEqual(response.status_code, 200)

    def check_all_bad_fields(self, response):
        '''
            Check the post had all bad fields.
        '''
        self.assertTrue(b'Unable to create' in response.content)
        self.assertFalse(b'Bitcoin core programs are not in the path' in response.content)
        self.assertFalse(b'Bitcoin core programs are not in' in response.content)
        self.assertTrue(b'does not exist or is not accessible' in response.content)
        self.assertFalse(b'You need to enter a valid backup directory' in response.content)
        self.assertFalse(b'Unable to write to the backup dir' in response.content)
        self.assertTrue(b'Backup schedule must be set to a minimum of 1 and a maximum of 24 hours.' in response.content)
        self.assertTrue(b'Backup levels must be set to a minimum of 1.' in response.content)
        self.assertTrue(b'Invalid extra args: ' in response.content)

    def check_bad_backup_schedule(self, response):
        '''
            Check the post had bad back levels.
        '''
        self.assertFalse(b'Unable to create' in response.content)
        self.assertFalse(b'Bitcoin core programs are not in the path' in response.content)
        self.assertFalse(b'Bitcoin core programs are not in' in response.content)
        self.assertFalse(b'does not exist or is not accessible' in response.content)
        self.assertFalse(b'You need to enter a valid backup directory' in response.content)
        self.assertFalse(b'Unable to write to the backup dir' in response.content)
        self.assertTrue(b'Backup schedule must be set to a minimum of 1 and a maximum of 24 hours.' in response.content)
        self.assertFalse(b'Backup levels must be set to a minimum of 1.' in response.content)
        self.assertFalse(b'Invalid extra args: ' in response.content)

    def check_bad_backup_levels(self, response):
        '''
            Check the post had bad back levels.
        '''
        self.assertFalse(b'Unable to create' in response.content)
        self.assertFalse(b'Bitcoin core programs are not in the path' in response.content)
        self.assertFalse(b'Bitcoin core programs are not in' in response.content)
        self.assertFalse(b'does not exist or is not accessible' in response.content)
        self.assertFalse(b'You need to enter a valid backup directory' in response.content)
        self.assertFalse(b'Unable to write to the backup dir' in response.content)
        self.assertFalse(b'Backup schedule must be set to a minimum of 1 and a maximum of 24 hours.' in response.content)
        self.assertTrue(b'Backup levels must be set to a minimum of 1.' in response.content)
        self.assertFalse(b'Invalid extra args: ' in response.content)

    def check_bad_extra_args(self, response):
        '''
            Check the post had bad extra args.
        '''
        self.assertFalse(b'Unable to create' in response.content)
        self.assertFalse(b'Bitcoin core programs are not in the path' in response.content)
        self.assertFalse(b'Bitcoin core programs are not in' in response.content)
        self.assertFalse(b'does not exist or is not accessible' in response.content)
        self.assertFalse(b'You need to enter a valid backup directory' in response.content)
        self.assertFalse(b'Unable to write to the backup dir' in response.content)
        self.assertFalse(b'Backup schedule must be set to a minimum of 1 and a maximum of 24 hours.' in response.content)
        self.assertFalse(b'Backup levels must be set to a minimum of 1.' in response.content)
        self.assertTrue(b'Invalid extra args: ' in response.content)
        self.assertTrue(b'Invalid preferences -- details about the errors appear below the fields.' in response.content)

    def setUp(self):
        ''' Set up for a test. '''

        test_utils.setup_tmp_dir()

        self.home_bitcoin_subdir_exists = test_utils.home_bitcoin_dir_exists()

        # Every test needs access to the request factory or client.
        self.factory = RequestFactory()
        self.client = Client()

        test_utils.stop_bitcoin_core_apps()

    def tearDown(self):

        # some tests might create a .bitcon in the home dir
        test_utils.delete_home_bitcoin_subdir(self.home_bitcoin_subdir_exists)
