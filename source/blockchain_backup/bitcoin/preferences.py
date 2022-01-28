'''
    Manage blockchain_backup prefs.

    Copyright 2018-2022 DeNova
    Last modified: 2022-01-13
'''

import os
from shutil import rmtree
from traceback import format_exc

from django.db import transaction
from django.db.utils import OperationalError

from blockchain_backup.bitcoin import constants
from blockchain_backup.bitcoin.gen_utils import is_dir_writeable
from blockchain_backup.bitcoin.models import Preferences
from blockchain_backup.version import CURRENT_VERSION
from denova.os.user import getdir, whoami
from denova.python.log import Log


log = Log()

def get_bitcoin_dirs():
    '''
        Get the bin and data dirs for bitcoin.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> bin_dir, data_dir = get_bitcoin_dirs()
        >>> bin_dir
        '/tmp/bitcoin/bin/'
        >>> data_dir
        '/tmp/bitcoin/data/testnet3'
    '''

    data_dir = get_data_dir()
    bin_dir = get_bin_dir()

    return bin_dir, data_dir

def get_data_dir():
    '''
        Get the data dir from the prefs.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> get_data_dir()
        '/tmp/bitcoin/data/testnet3'
    '''

    data_dir = None
    try:
        prefs = get_preferences()
        data_dir = prefs.data_dir
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    if data_dir is None:
        data_dir = os.path.join(getdir(), '.bitcoin')

    use_test_net = '-testnet' in get_extra_args()
    if use_test_net and not data_dir.rstrip(os.sep).endswith(constants.TEST_NET_DIR):
        data_dir = os.path.join(data_dir, constants.TEST_NET_DIR)

    return data_dir


def data_dir_ok(data_dir=None):
    '''
        Verify the data dir includes the appropriate subdirs.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> data_dir_ok('/tmp/bitcoin/data')
        (True, None)
        >>> result, error_message = data_dir_ok('/usr/bin/backups')
        >>> result == False
        True
        >>> error_message == 'Unable to create /usr/bin/backups as {}'.format(whoami())
        True
    '''
    user = whoami()
    error = None

    if data_dir is None:
        data_dir = get_data_dir()

    if not os.path.exists(data_dir):
        try:
            log(f'trying to make data dir at: {data_dir}')
            os.makedirs(data_dir)
        except: # 'bare except' because it catches more than "except Exception"
            error = f'Unable to create {data_dir} as {user}'

    if os.path.exists(data_dir):
        ok, error = is_dir_writeable(data_dir)
    else:
        ok = False
        error = f'Unable to create {data_dir} as {user}'

    if error is not None:
        log(error)

    return ok, error

def get_backup_dir():
    '''
        Get the backup dir from the prefs.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> get_backup_dir()
        '/tmp/bitcoin/data/testnet3/backups/'
        >>> prefs = get_preferences()
        >>> prefs.backup_dir = None
        >>> save_preferences(prefs)
        >>> get_backup_dir()
        '/tmp/bitcoin/data/testnet3/backups'
    '''

    backup_dir = None
    try:
        prefs = get_preferences()
        backup_dir = prefs.backup_dir
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    if backup_dir is None or not backup_dir or backup_dir == get_data_dir():
        backup_dir = os.path.join(get_data_dir(), constants.DEFAULT_BACKUPS_DIR)
        log(f'redefined backup dir to: {backup_dir}')

    return backup_dir

def backup_dir_ok(backup_dir=None):
    '''
        Verify the backup dir can be written to.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> backup_dir_ok(backup_dir='/tmp/bitcoin/backup')
        (True, None)
        >>> ok, error_message = backup_dir_ok(backup_dir='/test')
        >>> ok
        False
        >>> error_message.startswith('Unable to create /test as')
        True
        >>> backup_dir_ok(backup_dir=get_data_dir())
        (False, 'The backup and data directories must be different.')
    '''
    user = whoami()
    error = None

    if backup_dir is None:
        backup_dir = get_backup_dir()

    if backup_dir == get_data_dir():
        ok = False
        error = 'The backup and data directories must be different.'
    else:
        if os.path.exists(backup_dir):
            dir_preexists = True
        else:
            dir_preexists = False
            try:
                os.makedirs(backup_dir)
                log(f'Created {backup_dir} as {user}')
            except: # 'bare except' because it catches more than "except Exception"
                error = f'Unable to create {backup_dir} as {user}'

        if os.path.exists(backup_dir):
            ok, error = is_dir_writeable(backup_dir)
        else:
            ok = False
            error = f'Unable to create {backup_dir} as {user}'

        # don't create the directory while verifying its ok to create it
        if not dir_preexists and os.path.exists(backup_dir):
            rmtree(backup_dir)

    if error is not None:
        log(error)

    return ok, error

def get_bin_dir():
    '''
        Get the bin dir from the prefs.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> bin_dir = get_bin_dir()
        >>> bin_dir is None
        False
        >>> prefs = get_preferences()
        >>> x = prefs.delete()
        >>> bin_dir = get_bin_dir()
        >>> bin_dir is None
        True
    '''

    bin_dir = None
    try:
        prefs = get_preferences()
        bin_dir = prefs.bin_dir
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    # if the bin dir just has blanks, then return None
    if bin_dir is not None and not bin_dir.strip():
        bin_dir = None
        log('bin dir stripped of blanks')

    return bin_dir

def bin_dir_ok(bin_dir=None):
    '''
        Verify the bin dir includes the appropriate apps.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> bin_dir_ok(bin_dir='/tmp/bitcoin/bin')
        True
        >>> bin_dir_ok(bin_dir='/test')
        False
    '''
    # late import to avoid circular imports
    from blockchain_backup.bitcoin import core_utils

    if bin_dir is None:
        bin_dir = get_bin_dir()

    if bin_dir is None:
        bin_dir = core_utils.get_path_of_core_apps()
        ok = bin_dir is not None
        if not ok:
            log('required binaries are not in the path')
    else:
        ok = os.path.exists(bin_dir)
        if ok:
            bitcoind_exists = os.path.exists(os.path.join(bin_dir, core_utils.bitcoind()))
            bitcoin_cli_exists = os.path.exists(os.path.join(bin_dir, core_utils.bitcoin_cli()))
            bitcoin_qt_exists = os.path.exists(os.path.join(bin_dir, core_utils.bitcoin_qt()))

            ok = bitcoind_exists and bitcoin_cli_exists and bitcoin_qt_exists
            if not ok:
                log(f'bitcoind_in {bin_dir}: {bitcoind_exists}')
                log(f'bitcoin_cli_in {bin_dir}: {bitcoin_cli_exists}')
                log(f'bitcoin_qt_in {bin_dir}: {bitcoin_qt_exists}')
        else:
            log(f'Executable dir does not exist: {bin_dir}')

    return ok

def get_backup_schedule():
    '''
        Get the backup schedule.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> schedule = get_backup_schedule()
        >>> schedule > 0 and schedule < 25
        True
        >>> prefs = get_preferences()
        >>> x = prefs.delete()
        >>> get_backup_schedule()
        24
    '''

    backup_schedule = 24
    try:
        prefs = get_preferences()
        backup_schedule = prefs.backup_schedule
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    return backup_schedule

def get_backup_levels():
    '''
        Get the number of backup levels.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> levels = get_backup_levels()
        >>> levels > 0
        True
        >>> prefs = get_preferences()
        >>> x = prefs.delete()
        >>> get_backup_levels()
        2
    '''

    backup_levels = 1
    try:
        prefs = get_preferences()
        backup_levels = prefs.backup_levels
        if backup_levels is None:
            backup_levels = 1
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    return backup_levels

def get_extra_args():
    '''
        Return the extra args used to start bitcoind and bitcoin-qt,
        if it's defined. Otherwise, return None.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> extra_args = get_extra_args()
        >>> type(extra_args)
        <class 'list'>
        >>> prefs = get_preferences()
        >>> x = prefs.delete()
        >>> extra_args = get_extra_args()
        >>> len(extra_args)
        0
    '''

    args = []

    try:
        prefs = get_preferences()
        args_string = prefs.extra_args
        if args_string is not None:
            while args_string:
                start_index = args_string.find('-')
                end_index = args_string.find(' -')
                if end_index > start_index:
                    args.append(args_string[start_index:end_index])
                    args_string = args_string[end_index+1:]
                else:
                    args.append(args_string[start_index:])
                    args_string = ''
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    return args

def get_preferences():
    '''
        Get the record with the user's preferences.

        >>> isinstance(get_preferences(), Preferences)
        True
    '''

    record = None

    try:
        record = Preferences.objects.get()
    except Preferences.DoesNotExist:
        record = Preferences()
    except OperationalError as oe:
        log(str(oe))
        record = Preferences()
    except:  # 'bare except' because it catches more than "except Exception"
        log(format_exc())
        record = Preferences()

    return record

def save_preferences(record):
    '''
        Save the record with the user's preferences.

        >>> prefs = get_preferences()
        >>> save_preferences(prefs)
    '''

    with transaction.atomic():
        try:
            record.save()
        except: # 'bare except' because it catches more than "except Exception"
            log(f'tried to save bitcoin.preferences to {DATABASE_NAME}')
            log(format_exc())
            raise
