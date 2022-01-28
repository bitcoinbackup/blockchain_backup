'''
    Maintain the state of blockchain_backup
    and the blockchain.

    Copyright 2018-2022 DeNova
    Last modified: 2022-01-17
'''

import os
from datetime import datetime
from traceback import format_exc

from django.db import transaction
from django.db.utils import OperationalError
from django.utils.timezone import now, utc

from blockchain_backup.bitcoin import constants, preferences
from blockchain_backup.bitcoin.models import State
from blockchain_backup.settings import DATABASE_NAME
from blockchain_backup.version import CURRENT_VERSION
from denova.python.log import Log

log = Log()

def get_last_block_updated():
    '''
        Get the last block updated in the django database;
        may be different from last in blockchain.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_last_block_updated(567220)
        >>> get_last_block_updated()
        567220
    '''

    last_updated = 0

    try:
        state = get_state()
        last_updated = state.last_block_updated
        if last_updated is None:
            last_updated = 0
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())
        last_updated = -1

    return last_updated

def set_last_block_updated(last_block):
    '''
        Set the last block updated in the django database;
        may be different from last in blockchain.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_last_block_updated(567220)
        >>> get_last_block_updated()
        567220
    '''

    try:
        # sometimes we use -1 as a way to
        # show the last block is unknown
        if last_block < 0:
            last_block = 0

        state_settings = get_state()
        if state_settings.last_block_updated != last_block:
            state_settings.last_block_updated = last_block
            save_state(state_settings)
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

def get_last_known_block():
    '''
        Get the last_known_block.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_last_known_block(152)
        >>> get_last_known_block()
        152
    '''

    last_known_block = 0

    try:
        state = get_state()
        last_known_block = state.last_known_block
        if last_known_block is None:
            last_known_block = 0
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    return last_known_block

def set_last_known_block(last_known_block):
    '''
        Set the last_known_block.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_last_known_block(152)
        >>> get_last_known_block()
        152
    '''

    try:
        state_settings = get_state()
        if state_settings.last_known_block != last_known_block:
            state_settings.last_known_block = last_known_block
            save_state(state_settings)
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

def get_last_block_time():
    '''
        Get the last_block_time.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_last_block_time(datetime(2009, 1, 12, 0, 0, tzinfo=utc))
        >>> get_last_block_time()
        datetime.datetime(2009, 1, 12, 0, 0, tzinfo=<UTC>)
    '''

    last_block_time = datetime(2009, 1, 12, 0, 0, tzinfo=utc)

    try:
        state = get_state()
        last_block_time = state.last_block_time
        if last_block_time is None:
            last_block_time = datetime(2009, 1, 12, 0, 0, tzinfo=utc)
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    return last_block_time

def set_last_block_time(last_block_time):
    '''
        Set the last_block_time.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_last_block_time(datetime(2009, 1, 12, 0, 0, tzinfo=utc))
        >>> get_last_block_time()
        datetime.datetime(2009, 1, 12, 0, 0, tzinfo=<UTC>)
    '''

    try:
        state_settings = get_state()
        if state_settings.last_block_time != last_block_time:
            state_settings.last_block_time = last_block_time
            save_state(state_settings)
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

def get_start_access_time():
    '''
        Get the start time bitcoind or bitcoin-qt run through Blockchain Backup.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_start_access_time(datetime(2009, 1, 12, 0, 0, tzinfo=utc))
        >>> get_start_access_time()
        datetime.datetime(2009, 1, 12, 0, 0, tzinfo=<UTC>)
    '''

    start_access_time = None

    try:
        state = get_state()
        start_access_time = state.start_access_time
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    if start_access_time is None:
        start_access_time = now()
        set_start_access_time(start_access_time)

    return start_access_time

def set_start_access_time(start_access_time):
    '''
        Set the start_time bitcoind or bitcoin-qt run through Blockchain Backup.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_start_access_time(datetime(2009, 1, 12, 0, 0, tzinfo=utc))
        >>> get_start_access_time()
        datetime.datetime(2009, 1, 12, 0, 0, tzinfo=<UTC>)
    '''

    try:
        state_settings = get_state()
        if state_settings.start_access_time != start_access_time:
            state_settings.start_access_time = start_access_time
            save_state(state_settings)
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

def get_last_access_time():
    '''
        Get the last time bitcoind or bitcoin-qt run through Blockchain Backup.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_last_access_time(datetime(2009, 1, 12, 0, 0, tzinfo=utc))
        >>> get_last_access_time()
        datetime.datetime(2009, 1, 12, 0, 0, tzinfo=<UTC>)
    '''

    last_access_time = None

    try:
        state = get_state()
        last_access_time = state.last_access_time
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    if last_access_time is None:
        last_access_time = now()
        set_last_access_time(last_access_time)

    return last_access_time

def set_last_access_time(last_access_time):
    '''
        Set the last_time bitcoind or bitcoin-qt run through Blockchain Backup.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_last_access_time(datetime(2009, 1, 12, 0, 0, tzinfo=utc))
        >>> get_last_access_time()
        datetime.datetime(2009, 1, 12, 0, 0, tzinfo=<UTC>)
    '''

    try:
        state_settings = get_state()
        if state_settings.last_access_time != last_access_time:
            state_settings.last_access_time = last_access_time
            save_state(state_settings)
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

def get_last_backed_up_time():
    '''
        Get the last time the blockchain was backed up.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_last_backed_up_time(datetime(2009, 1, 12, 0, 0, tzinfo=utc))
        >>> get_last_backed_up_time()
        datetime.datetime(2009, 1, 12, 0, 0, tzinfo=<UTC>)
    '''

    last_backed_up_time = None

    try:
        state = get_state()
        last_backed_up_time = state.last_backed_up_time
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    # if the last backup time hasn't been set, then
    # assume we just backed up
    if last_backed_up_time is None:
        last_backed_up_time = now()
        set_last_backed_up_time(last_backed_up_time)

    return last_backed_up_time

def set_last_backed_up_time(last_backed_up_time):
    '''
        Set the last_time backed up.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_last_backed_up_time(datetime(2009, 1, 12, 0, 0, tzinfo=utc))
        >>> get_last_backed_up_time()
        datetime.datetime(2009, 1, 12, 0, 0, tzinfo=<UTC>)
    '''

    try:
        state_settings = get_state()
        if state_settings.last_backed_up_time != last_backed_up_time:
            state_settings.last_backed_up_time = last_backed_up_time
            save_state(state_settings)
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

def get_last_backup_level():
    '''
        Get the last_backup_level.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_last_backup_level(1)
        >>> get_last_backup_level()
        1
    '''

    last_backup_level = 1

    try:
        state = get_state()
        last_backup_level = state.last_backup_level
        if last_backup_level is None:
            last_backup_level = 1
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    return last_backup_level

def set_last_backup_level(last_backup_level):
    '''
        Set the last_backup_level.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_last_backup_level(1)
        >>> get_last_backup_level()
        1
    '''

    try:
        state_settings = get_state()
        if state_settings.last_backup_level != last_backup_level:
            state_settings.last_backup_level = last_backup_level
            save_state(state_settings)
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

def get_last_update_time():
    '''
        Get the last time the system checked_for_updates.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_last_update_time(datetime(2009, 1, 12, 0, 0, tzinfo=utc))
        >>> get_last_update_time()
        datetime.datetime(2009, 1, 12, 0, 0, tzinfo=<UTC>)
    '''

    last_update_time = datetime(2009, 1, 12, 0, 0, tzinfo=utc)

    try:
        state = get_state()
        last_update_time = state.last_update_time
        if last_update_time is None:
            last_update_time = datetime(2009, 1, 12, 0, 0, tzinfo=utc)
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    return last_update_time

def set_last_update_time(last_update_time):
    '''
        Set the last time checked_for_updates online.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_last_update_time(datetime(2009, 1, 12, 0, 0, tzinfo=utc))
        >>> get_last_update_time()
        datetime.datetime(2009, 1, 12, 0, 0, tzinfo=<UTC>)
    '''

    try:
        state_settings = get_state()
        if state_settings.last_update_time != last_update_time:
            state_settings.last_update_time = last_update_time
            save_state(state_settings)
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

def get_latest_bcb_version():
    '''
        Get the lastest blockchain_backup version from online.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> latest_bcb_version = get_latest_bcb_version()
        >>> latest_bcb_version == CURRENT_VERSION
        True
    '''

    # use the default if nothing else known
    latest_bcb_version = CURRENT_VERSION

    try:
        state_settings = get_state()
        latest_bcb_version = state_settings.latest_bcb_version
        if latest_bcb_version is None:
            latest_bcb_version = CURRENT_VERSION
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    return latest_bcb_version

def set_latest_bcb_version(latest_bcb_version):
    '''
        Set the latest_bcb_version.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_latest_bcb_version('1.0')
        >>> get_latest_bcb_version()
        '1.0'
    '''

    try:
        state_settings = get_state()
        if state_settings.latest_bcb_version != latest_bcb_version:
            state_settings.latest_bcb_version = latest_bcb_version
            save_state(state_settings)
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

def get_backups_enabled():
    '''
        Get whether backups are enabled.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> get_backups_enabled()
        True
    '''

    enabled = True
    try:
        state_settings = get_state()
        enabled = state_settings.backups_enabled
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    return enabled

def set_backups_enabled(enabled):
    '''
        Set whether backups are enabled.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> set_backups_enabled(False)
        >>> get_backups_enabled()
        False
    '''

    try:
        state_settings = get_state()
        if state_settings.backups_enabled != enabled:
            state_settings.backups_enabled = enabled
            save_state(state_settings)
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

def get_all_backup_dates_and_dirs(backup_dir=None):
    '''
        Get a list of backup dates with their parent directory.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> backup_dates = get_all_backup_dates_and_dirs()
        >>> len(backup_dates) > 0
        True
        >>> backup_dates = get_all_backup_dates_and_dirs(backup_dir='/tmp/test')
        >>> backup_dates is None
        True
    '''
    def get_date_and_dir(entry):
        ''' Get the path and date if its a valid backup. '''

        backed_up_time = None

        if entry.is_dir() and entry.name.startswith(constants.BACKUPS_LEVEL_PREFIX):
            filenames = os.listdir(entry.path)
            for filename in filenames:
                # save the timestamp if there's a timestamp file
                if filename.startswith(constants.LAST_UPDATED_PREFIX):
                    backed_up_time = filename[len(constants.LAST_UPDATED_PREFIX):]

        return backed_up_time

    backup_dates_with_dirs = []

    if backup_dir is None:
        backup_dir = preferences.get_backup_dir()

    if os.path.exists(backup_dir):
        # scan the backup directories
        entries = os.scandir(backup_dir)
        for entry in entries:
            # look inside each backup level
            backed_up_time = get_date_and_dir(entry)
            if backed_up_time is not None:
                backup_dates_with_dirs.append((entry.path, backed_up_time))

        if not backup_dates_with_dirs:
            log(f'no completed backups in {backup_dir}')
    else:
        backup_dates_with_dirs = None
        log(f'no backup dir in {backup_dir} so no backup dates')

    return backup_dates_with_dirs

def get_backup_dates_and_dirs():
    '''
        Get the list of backup dates/dirs and the most recent date/dir.

        The list is a set of tuples with the full path to
        the each directory and its backup date.

        If there are no complete backups, then return an empty
        string and None for the preselected date.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> backup_dates, preselected_date = get_backup_dates_and_dirs()
        >>> len(backup_dates) > 0
        True
        >>> preselected_date is not None
        True
    '''

    preselected_date = None
    backup_dates = []

    dates = get_all_backup_dates_and_dirs()
    if dates:
        backup_dates = sorted(dates, reverse=True, key=lambda tup:tup[1])
        preselected_date = backup_dates[0]

    return backup_dates, preselected_date

def get_state():
    '''
        Get the record with the system's state.

        >>> isinstance(get_state(), State)
        True
    '''
    record = None

    try:
        record = State.objects.get()
    except State.DoesNotExist:
        record = State()
    except OperationalError as oe:
        log(str(oe))
        record = State()
    except:  # 'bare except' because it catches more than "except Exception"
        log(format_exc())
        record = State()

    return record

def save_state(record):
    '''
        Save the record with the system's state.

        >>> save_state(get_state())
    '''

    with transaction.atomic():
        try:
            record.save()
        except: # 'bare except' because it catches more than "except Exception"
            log(f'tried to save bitcoin.state to {DATABASE_NAME}')
            log(format_exc())
            raise
