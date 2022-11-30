'''
    Bitcoin constants

    Copyright 2018-2021 DeNova
    Last modified: 2021-06-10
'''
import os

BLOCKCHAIN_FACILITY = 'denova.blockchain_backup.bitcoin'
BLOCKCHAIN_TYPE = 'blockchain_long_polling_type'

USE_LONG_POllING = False

BACKUP_URL = '/bitcoin/backup/'
SYNC_URL = '/bitcoin/update/'

METADATA_FILENAME = '.metadata'
BACKUP_PROGRAM = 'bcb-backup'
RESTORE_PROGRAM = 'bcb-restore'

DEFAULT_BACKUPS_DIR = 'backups'
BACKUPS_LEVEL_PREFIX = 'level'
UPDATING_PREFIX = 'updating-'
LAST_UPDATED_PREFIX = 'last-updated-'
BLOCKCHAIN_BACKUP_DB_DIR = 'blockchain_backup_database'
STATE_BACKUP_FILENAME = 'state.json'

TEST_NET_DIR = 'testnet3'
TEST_NET_SUBDIR = os.path.join(os.sep, TEST_NET_DIR)

ENABLE_ITEM = 'enabled'
DISABLE_ITEM = 'disabled'

LOG_SUFFIX = '.log'
DEBUG_LOG = f'debug{LOG_SUFFIX}'
DEBUG_PREFIX = 'debug-'
TESTNET_FLAG = '-testnet'

LOCATION_NAME = 'location'

CLOSE_WINDOW = 'You may proceed safely now.'
CLOSE_WINDOW_NOW = f'&nbsp;{CLOSE_WINDOW}&nbsp;'
RESTORE_BITCOIN = '<br/>&nbsp;You may need to <a href="/bitcoin/restore/">Restore</a> the blockchain.'

STOPPING_UPDATE = 'Waiting for Bitcoin Core to stop'
