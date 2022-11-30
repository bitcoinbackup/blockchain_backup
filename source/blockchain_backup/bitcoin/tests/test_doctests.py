'''
    Run the doctests.

    Copyright 2018-2021 DeNova
    Last modified: 2021-07-17
'''

from ve import activate, virtualenv_dir
activate(django_app='blockchain_backup')
from django import setup
setup()

import json, os
import doctest
from django.test import TestCase

import blockchain_backup.bitcoin.auto_update
import blockchain_backup.bitcoin.backup
import blockchain_backup.bitcoin.backup_utils
import blockchain_backup.bitcoin.core_utils
import blockchain_backup.bitcoin.exception
import blockchain_backup.bitcoin.forms
import blockchain_backup.bitcoin.gen_utils
import blockchain_backup.bitcoin.handle_cli
import blockchain_backup.bitcoin.models
import blockchain_backup.bitcoin.nonce
import blockchain_backup.bitcoin.preferences
import blockchain_backup.bitcoin.restore
import blockchain_backup.bitcoin.state
import blockchain_backup.bitcoin.update
import blockchain_backup.bitcoin.views
from blockchain_backup.bitcoin.tests import utils as test_utils
from denova.python.log import Log

log = Log()

class TestDoctests(TestCase):

    fixtures = ['bitcoin.preferences.json',]

    def setUp(self):
        ''' Set up for a test. '''

        test_utils.setup_tmp_dir()

        self.home_bitcoin_subdir_exists = test_utils.home_bitcoin_dir_exists()

        test_utils.stop_bitcoin_core_apps()

    def tearDown(self):

        test_utils.restore_initial_data()

        # some tests might create a .bitcon in the home dir
        test_utils.delete_home_bitcoin_subdir(self.home_bitcoin_subdir_exists)

        test_utils.stop_bitcoin_core_apps()

    def test_auto_update(self):
        ''' Run the auto update doctests. '''

        # includes approximately 3 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.auto_update, report=True)
        self.assertEqual(test_result[0], 0)

    def test_backup(self):
        ''' Run the backup doctests. '''

        # includes approximately 6 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.backup, report=True)
        self.assertEqual(test_result[0], 0)

    def test_backup_utils(self):
        ''' Run the backup utils doctests. '''

        # includes approximately 21 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.backup_utils, report=True)
        self.assertEqual(test_result[0], 0)

    def test_core_utils(self):
        ''' Run the core utils doctests. '''

        # includes approximately 24 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.core_utils, report=True)
        self.assertEqual(test_result[0], 0)

    def test_forms(self):
        ''' Run the forms doctests. '''

        # includes approximately 2 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.forms, report=True)
        self.assertEqual(test_result[0], 0)

    def test_exception(self):
        ''' Run the exception doctests. '''

        # includes approximately 1 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.exception, report=True)
        self.assertEqual(test_result[0], 0)

    def test_gen_utils(self):
        ''' Run the general utils doctests. '''

        # includes approximately 18 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.gen_utils, report=True)
        self.assertEqual(test_result[0], 0)

    def test_handle_cli(self):
        ''' Run the handle cli doctests. '''

        # includes approximately 7 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.handle_cli, report=True)
        self.assertEqual(test_result[0], 0)

    def test_manager(self):
        ''' Run the manager doctests. '''

        # includes approximately 24 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.manager, report=True)
        self.assertEqual(test_result[0], 0)

    def test_models(self):
        ''' Run the models doctests. '''

        # includes approximately 3 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.models, report=True)
        self.assertEqual(test_result[0], 0)

    def test_nonce(self):
        ''' Run the nonce doctests. '''

        # includes approximately 1 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.nonce, report=True)
        self.assertEqual(test_result[0], 0)

    def test_preferences(self):
        ''' Run the preferences doctests. '''

        # includes approximately 12 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.preferences, report=True)
        self.assertEqual(test_result[0], 0)

    def test_restore(self):
        ''' Run the restore doctests. '''

        # includes approximately 15 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.restore, report=True)
        self.assertEqual(test_result[0], 0)

    def test_state(self):
        ''' Run the state doctests. '''

        # includes approximately 24 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.state, report=True)
        self.assertEqual(test_result[0], 0)

    def test_update(self):
        ''' Run the update doctests. '''

        # includes approximately 7 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.update, report=True)
        self.assertEqual(test_result[0], 0)

    def test_views(self):
        ''' Run the state doctests. '''

        # includes approximately 7 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.views, report=True)
        self.assertEqual(test_result[0], 0)

    def test_test_utils(self):
        ''' Run the test utils doctests. '''

        # includes approximately 21 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.tests.utils, report=True)
        self.assertEqual(test_result[0], 0)
