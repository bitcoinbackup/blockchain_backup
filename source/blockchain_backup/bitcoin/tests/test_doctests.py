'''
    Run the doctests.

    Copyright 2018-2020 DeNova
    Last modified: 2020-10-17
'''

from ve import activate, virtualenv_dir
activate(django_app='blockchain_backup')
from django import setup
setup()

import json, os
import doctest
from django.test import TestCase

import blockchain_backup.bitcoin.backup
import blockchain_backup.bitcoin.exception
import blockchain_backup.bitcoin.forms
import blockchain_backup.bitcoin.models
import blockchain_backup.bitcoin.nonce
import blockchain_backup.bitcoin.preferences
import blockchain_backup.bitcoin.restore
import blockchain_backup.bitcoin.state
import blockchain_backup.bitcoin.utils
import blockchain_backup.bitcoin.views
from blockchain_backup.bitcoin.tests import utils as test_utils
from denova.python.log import get_log

log = get_log()

class TestDoctests(TestCase):

    def test_backup(self):
        ''' Run the backup doctests. '''

        # includes approximately 23 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.backup, report=True)
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

        # includes approximately 10 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.preferences, report=True)
        self.assertEqual(test_result[0], 0)

    def test_restore(self):
        ''' Run the restore doctests. '''

        # includes approximately 14 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.restore, report=True)
        self.assertEqual(test_result[0], 0)

    def test_state(self):
        ''' Run the state doctests. '''

        # includes approximately 20 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.state, report=True)
        self.assertEqual(test_result[0], 0)

    def test_utils(self):
        ''' Run the utils doctests. '''

        # includes approximately 31 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.utils, report=True)
        self.assertEqual(test_result[0], 0)

    def test_views(self):
        ''' Run the state doctests. '''

        # includes approximately 9 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.views, report=True)
        self.assertEqual(test_result[0], 0)

    def test_test_utils(self):
        ''' Run the test utils doctests. '''

        # includes approximately 20 doctests
        test_result = doctest.testmod(blockchain_backup.bitcoin.tests.utils, report=True)
        self.assertEqual(test_result[0], 0)

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
