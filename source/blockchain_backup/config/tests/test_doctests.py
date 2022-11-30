'''
    Run the doctests.

    Copyright 2018-2020 DeNova
    Last modified: 2020-12-08
'''

from ve import activate, virtualenv_dir
activate(django_app='blockchain_backup')
from django import setup
setup()

import os
import doctest
from django.test import TestCase
from denova.python.log import Log

import blockchain_backup.config.bitcoin_shutdown
import blockchain_backup.config.bitcoin_startup
import blockchain_backup.config.check_for_updates
import blockchain_backup.config.remove_host
import blockchain_backup.config.setup
from blockchain_backup.bitcoin.tests import utils as test_utils
import safecopy

log = Log()

class TestDoctests(TestCase):

    def test_bitcoin_shutdown(self):
        ''' Run the bitcoin_shutdown doctests. '''

        test_result = doctest.testmod(blockchain_backup.config.bitcoin_shutdown, report=True)
        self.assertEqual(test_result[0], 0)

    def test_bitcoin_startup(self):
        ''' Run the bitcoin_startup doctests. '''

        test_result = doctest.testmod(blockchain_backup.config.bitcoin_startup, report=True)
        self.assertEqual(test_result[0], 0)

    def test_check_for_updates(self):
        ''' Run the check for updates doctests. '''

        test_result = doctest.testmod(blockchain_backup.config.check_for_updates, report=True)
        self.assertEqual(test_result[0], 0)

    def test_remove_host(self):
        ''' Run the remove_host doctests. '''

        test_result = doctest.testmod(blockchain_backup.config.remove_host, report=True)
        self.assertEqual(test_result[0], 0)

    def test_safecopy(self):
        ''' Run the safecopy doctests. '''

        test_result = doctest.testmod(safecopy, report=True)
        self.assertEqual(test_result[0], 0)

    def test_setup(self):
        ''' Run the setup doctests. '''

        test_result = doctest.testmod(blockchain_backup.config.setup, report=True)
        self.assertEqual(test_result[0], 0)

    def setUp(self):
        ''' Set up for a test. '''

        test_utils.setup_tmp_dir()
