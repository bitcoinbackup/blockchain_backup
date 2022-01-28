'''
    Tests for the home page.

    Copyright 2018-2022 DeNova
    Last modified: 2022-01-25
'''

from ve import activate, virtualenv_dir
activate(django_app='blockchain_backup')
from django import setup
setup()

import os, shutil
from datetime import datetime, timedelta
from django.utils.timezone import now, utc
from django.test import RequestFactory, TestCase

from blockchain_backup.bitcoin import preferences, state
from blockchain_backup.bitcoin.models import Preferences, State
from blockchain_backup.bitcoin.tests import utils as test_utils
from blockchain_backup.bitcoin.views import get_home_page_response
from blockchain_backup.version import CURRENT_VERSION
from denova.python.log import Log

log = Log()

class TestHome(TestCase):

    SAVE_HOME_PAGES = True

    def test_never_installed_bitcoin(self):
        '''
            Show home page for someone who
            has never used nor installed bitcoin.
        '''
        bin_dir_ok = False
        data_dir = None
        data_dir_ok = False
        backup_dir = None
        backup_dir_ok = False
        backup_dir_error = None
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = True
        need_backup = False
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }
        bcb_run_already = False
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'never_installed_bitcoin.html')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nGetting Started | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b'Get started:' in response.content)
        self.assertFalse(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access<br/>wallet </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary btn-block" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def test_installed_bitcoin_but_no_data_nor_backup_dirs(self):
        '''
            Show the home page when someone has installed
            bitcoin, but data and backup dirs are not valid.
        '''
        bin_dir_ok = True
        data_dir = None
        data_dir_ok = False
        backup_dir = None
        backup_dir_ok = False
        backup_dir_error = None
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = True
        need_backup = False
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }
        bcb_run_already = False
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'bitcoin_installed_no_data_no_backup.html')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Blockchain Backup is Almost Ready | Blockchain Backup' in response.content)
        self.assertTrue(b'Bitcoin Core is installed' in response.content)
        self.assertTrue(b"but you need to configure the data and backup directories." in response.content)
        self.assertFalse(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access<br/>wallet </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary btn-block" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def test_installed_bitcoin_but_no_data_dir(self):
        '''
            Show the home page when someone has installed
            bitcoin with a valid backup dir, but data dir is not valid.
        '''
        bin_dir_ok = True
        data_dir = None
        data_dir_ok = False
        backup_dir = '/tmp/bitcoin/data/backups/'
        backup_dir_ok = True
        backup_dir_error = None
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = True
        need_backup = False
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }
        bcb_run_already = False
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'bitcoin_installed_no_data.html')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Blockchain Backup is Almost Ready | Blockchain Backup' in response.content)
        self.assertTrue(b'Bitcoin Core is installed' in response.content)
        self.assertTrue(b"but the data directory isn't where expected." in response.content)
        self.assertFalse(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access<br/>wallet </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary btn-block" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def test_installed_bitcoin_but_no_backup_dir(self):
        '''
            Show the home page when someone has installed
            bitcoin with a valid data dir, but backup dir is not valid.
        '''
        bin_dir_ok = True
        data_dir = '/tmp/bitcoin/data/'
        data_dir_ok = True
        backup_dir = None
        backup_dir_ok = False
        backup_dir_error = None
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = True
        need_backup = False
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }
        bcb_run_already = False
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'bitcoin_installed_no_backup.html')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Blockchain Backup is Almost Ready | Blockchain Backup' in response.content)
        self.assertTrue(b'Bitcoin Core is installed' in response.content)
        self.assertTrue(b"but the backup directory isn't configured properly" in response.content)
        self.assertFalse(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access<br/>wallet </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary btn-block" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def test_inactive_user_needs_blockchain(self):
        '''
            Show the home page a blockchain backup
            user has everything configured, but
            has never used blockchain_backup nor bitcoin.
        '''
        bin_dir_ok = True
        data_dir = '/tmp/bitcoin/data'
        data_dir_ok = True
        backup_dir = '/tmp/bitcoin/data/backups'
        backup_dir_ok = True
        backup_dir_error = None
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = True
        need_backup = True
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }

        # link up a data directory without any data
        if os.path.lexists(data_dir):
            os.remove(data_dir)
        elif os.path.exists(data_dir):
            shutil.rmtree(data_dir)
        os.symlink('/tmp/bitcoin/data-no-blocks', data_dir)

        bcb_run_already = False
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'denova_ready_needs_blockchain.html')

        # link up a data directory with data
        if os.path.lexists(data_dir):
            os.remove(data_dir)
        elif os.path.exists(data_dir):
            shutil.rmtree(data_dir)
        os.symlink('/tmp/bitcoin/data-with-blocks', data_dir)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nYou are ready to get the blockchain | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b'Before you can start using your wallet, you must update' in response.content)
        self.assertTrue(b'<a href="/bitcoin/update/" name="start-update-button" id="start-update-id" class="btn btn-secondary" role="button"  title="Start updating the blockchain."> <strong>Start Update </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access<br/>wallet </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary btn-block" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def test_inactive_user_needs_backup(self):
        '''
            Show the home page a blockchain backup
            user has everything configured, but
            has never used blockchain_backup and needs to backup
            pre-existing data.
        '''
        bin_dir_ok = True
        data_dir = '/tmp/bitcoin/data'
        data_dir_ok = True
        backup_dir = '/tmp/bitcoin/data/testnet3/backups'
        backup_dir_ok = True
        backup_dir_error = None
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = True
        need_backup = True
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }

        # link up a data directory with data
        if os.path.lexists(data_dir):
            os.remove(data_dir)
        elif os.path.exists(data_dir):
            shutil.rmtree(data_dir)
        os.symlink('/tmp/bitcoin/data-with-blocks-no-backups', data_dir)

        bcb_run_already = False
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'denova_ready_needs_backup.html')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Welcome to Blockchain Backup! | Blockchain Backup' in response.content)
        self.assertTrue(b'The first step is to' in response.content)
        self.assertTrue(b'As soon as your first backup is done' in response.content)
        self.assertFalse(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access<br/>wallet </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def test_reactivated_user(self):
        '''
            Show the home page a blockchain backup
            user has everything configured with
            data and backups, but the database is not up-to-date.
        '''
        bin_dir_ok = True
        data_dir = '/tmp/bitcoin/data'
        data_dir_ok = True
        backup_dir = '/tmp/bitcoin/data/testnet3/backups'
        backup_dir_ok = True
        backup_dir_error = None
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = True
        need_backup = True
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }

        # link up a data directory with data
        if os.path.lexists(data_dir):
            os.remove(data_dir)
        elif os.path.exists(data_dir):
            shutil.rmtree(data_dir)
        os.symlink('/tmp/bitcoin/data-with-blocks', data_dir)

        bcb_run_already = True
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'denova_reactivated.html')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nBlockchain Backup Adds Resilience to Bitcoin Core | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access<br/>wallet </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary btn-block" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def test_active_user_all_good(self):
        '''
            Show the home page when an active
            user has everything configured.
        '''
        bin_dir_ok = True
        data_dir = '/tmp/bitcoin/data/'
        data_dir_ok = True
        backup_dir = '/tmp/bitcoin/data/backups/'
        backup_dir_ok = True
        backup_dir_error = None
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = True
        need_backup = False
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }
        bcb_run_already = True
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'active_user_all_good.html')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nBlockchain Backup Adds Resilience to Bitcoin Core | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access<br/>wallet </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary btn-block" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def test_active_user_needs_backup(self):
        '''
            Show the home page when an active
            user has everything configured, but
            needs a backup.
        '''
        bin_dir_ok = True
        data_dir = '/tmp/bitcoin/data/'
        data_dir_ok = True
        backup_dir = '/tmp/bitcoin/data/backups/'
        backup_dir_ok = True
        backup_dir_error = None
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = True
        need_backup = True
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }
        bcb_run_already = True
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'active_user_all_good.html')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nBlockchain Backup Adds Resilience to Bitcoin Core | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b'Your blockchain was last backed up at' in response.content)
        self.assertTrue(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access<br/>wallet </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary btn-block" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def test_active_user_need_bcb_upgrade(self):
        '''
            Show the home page when an active
            user has everything configured,
            but blockchain_backup needs to updated.
        '''
        bin_dir_ok = True
        data_dir = '/tmp/bitcoin/data/'
        data_dir_ok = True
        backup_dir = '/tmp/bitcoin/data/backups/'
        backup_dir_ok = True
        backup_dir_error = None
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = False
        need_backup = False
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }
        bcb_run_already = True
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'active_user_need_bcb_upgrade.html')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nBlockchain Backup Adds Resilience to Bitcoin Core | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b'You are not running the latest version of' in response.content)
        self.assertTrue(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access<br/>wallet </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary btn-block" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def test_active_user_need_core_upgrade(self):
        '''
            Show the home page when an active
            user has everything configured,
            but bitcoin core needs to updated.
        '''
        bin_dir_ok = True
        data_dir = '/tmp/bitcoin/data/'
        data_dir_ok = True
        backup_dir = '/tmp/bitcoin/data/backups/'
        backup_dir_ok = True
        backup_dir_error = None
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = True
        need_backup = False
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }
        bcb_run_already = True
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'active_user_need_core_upgrade.html')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nBlockchain Backup Adds Resilience to Bitcoin Core | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access<br/>wallet </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary btn-block" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertTrue(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def test_active_bcb_user_no_bin_dir(self):
        '''
            Show the home page an active blockchain backup
            user but the bin dir is not found.
        '''
        bin_dir_ok = False
        data_dir = '/tmp/bitcoin/data/'
        data_dir_ok = True
        backup_dir = '/tmp/bitcoin/data/backups/'
        backup_dir_ok = True
        backup_dir_error = None
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = True
        need_backup = False
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }
        bcb_run_already = True
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'active_user_no_bin.html')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nDirectories Inaccessible | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b'If you moved any of these directories to a new location' in response.content)
        self.assertFalse(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access<br/>wallet </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary btn-block" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def test_active_bcb_user_no_data_dir(self):
        '''
            Show the home page an active blockchain backup
            user but the data dir is not found.
        '''
        bin_dir_ok = True
        data_dir = '/tmp/bitcoin/unwriteable-dir/'
        data_dir_ok = False
        backup_dir = '/tmp/bitcoin/data/backups/'
        backup_dir_ok = True
        backup_dir_error = None
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = True
        need_backup = False
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }
        bcb_run_already = True
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'active_user_no_data.html')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nDirectories Inaccessible | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b'If you moved any of these directories to a new location' in response.content)
        self.assertFalse(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access<br/>wallet </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary btn-block" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def test_active_bcb_user_no_backup_dir(self):
        '''
            Show the home page an active blockchain backup
            user but the backup dir is not found.
        '''
        bin_dir_ok = True
        data_dir = '/tmp/bitcoin/data/'
        data_dir_ok = True
        backup_dir = '/bitcoin/data/backups/'
        backup_dir_ok = False
        backup_dir_error = 'Unable to create'
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = True
        need_backup = False
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }
        bcb_run_already = True
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'active_user_no_backup.html')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nBad Backup Directory | Blockchain Backup\n</title>' in response.content)
        self.assertFalse(b'Unable to write to the backup dir in' in response.content)
        self.assertFalse(b'If you moved any of these directories to a new location' in response.content)
        self.assertTrue(b'Unable to create' in response.content)
        self.assertFalse(b'The backup and data directories must be different.' in response.content)
        self.assertFalse(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access<br/>wallet </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary btn-block" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def test_active_bcb_user_unwriteable_backup_dir(self):
        '''
            Show the home page an active blockchain backup
            user but unable to write to the backup dir.
        '''
        bin_dir_ok = True
        data_dir = '/tmp/bitcoin/data/'
        data_dir_ok = True
        backup_dir = '/bitcoin/data/unwriteable-dir/'
        backup_dir_ok = False
        backup_dir_error = 'Unable to write to the backup dir in'
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = True
        need_backup = False
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }
        bcb_run_already = True
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'active_user_no_backup.html')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nBad Backup Directory | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b'Unable to write to the backup dir in' in response.content)
        self.assertFalse(b'If you moved any of these directories to a new location' in response.content)
        self.assertFalse(b'Unable to create' in response.content)
        self.assertFalse(b'The backup and data directories must be different.' in response.content)
        self.assertFalse(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access&nbsp;wallet </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary btn-block" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def test_active_bcb_user_backup_data_dirs_same(self):
        '''
            Show the home page an active blockchain backup
            user but the backup and data dirs are the same.
        '''
        bin_dir_ok = True
        data_dir = '/tmp/bitcoin/data/'
        data_dir_ok = True
        backup_dir = '/tmp/bitcoin/data/'
        backup_dir_ok = False
        backup_dir_error = 'The backup and data directories must be different.'
        need_backup = True
        last_bcb_version = CURRENT_VERSION
        bcb_up_to_date = True
        need_backup = False
        last_backed_up_time = None
        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': bcb_up_to_date,
                  'need_backup': need_backup,
                  'last_backed_up_time': last_backed_up_time,
                 }
        bcb_run_already = True
        response = get_home_page_response(self.request, bcb_run_already, bin_dir_ok, params)
        self.save_page(response.content, 'active_user_no_backup.html')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nBad Backup Directory | Blockchain Backup\n</title>' in response.content)
        self.assertFalse(b'Unable to write to the backup dir in' in response.content)
        self.assertFalse(b'If you moved any of these directories to a new location' in response.content)
        self.assertFalse(b'Unable to create' in response.content)
        self.assertTrue(b'The backup and data directories must be different.' in response.content)
        self.assertFalse(b'<a href="/bitcoin/access_wallet/" name="access-wallet-button" id="access-wallet-id" class="btn btn-secondary btn-block" role="button"  title="Access your Bitcoin Core wallet"> <strong>Access&nbsp;wallet </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/update/" name="update-blockchain-button" id="update-blockchain-id" class="btn btn-secondary btn-block" role="button"  title="Update the blockchain"> <strong>Update<br/>blockchain </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/backup/" name="back-up-button" id="back-up-id" class="btn btn-secondary btn-block" role="button"  title="Back up the blockchain"> <strong>Back up </strong> </a>' in response.content)
        self.assertFalse(b'<a href="/bitcoin/restore/" name="restore-button" id="restore-id" class="btn btn-secondary btn-block" role="button"  title="Restore the blockchain"> <strong>Restore </strong> </a>' in response.content)

    def save_page(self, content, filename):
        if self.SAVE_HOME_PAGES:
            HOME_PAGES_DIR = '/tmp/bitcoin/home-pages'
            if not os.path.exists(HOME_PAGES_DIR):
                os.makedirs(HOME_PAGES_DIR)
            with open(os.path.join(HOME_PAGES_DIR, filename), 'wt') as f:
                f.write(content.decode())

    def setUp(self):
        ''' Set up for a test. '''

        test_utils.setup_tmp_dir()

        self.home_bitcoin_subdir_exists = test_utils.home_bitcoin_dir_exists()
        # Every test needs access to the request for the home page.
        factory = RequestFactory()
        self.request = factory.get('/')

        test_utils.stop_bitcoin_core_apps()

    def tearDown(self):

        # some tests might create a .bitcon in the home dir
        test_utils.delete_home_bitcoin_subdir(self.home_bitcoin_subdir_exists)

        test_utils.stop_bitcoin_core_apps()
