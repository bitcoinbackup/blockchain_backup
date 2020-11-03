'''
    Models for bitcoin core.

    Copyright 2018-2020 DeNova
    Last modified: 2020-10-20
'''

from django.core.validators import MaxValueValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _


MAX_LENGTH = 1000 # default max length


class HourField(models.PositiveSmallIntegerField):
    '''
        24 hour clock.

        >>> hf = HourField()
        >>> validators = hf.default_validators
        >>> isinstance(validators, list)
        True
    '''

    default_validators = [MaxValueValidator(24,
                    message='Backup schedule must be less than or equal to 24 hours.')]

class Preferences(models.Model):
    '''
        Preferences for managing bitcoin core.

        >>> Preferences()
        <Preferences: Preferences object (None)>
    '''

    DATA_DIR_HELP = _('The default data directory is in .bitcoin in your home directory.')
    BIN_DIR_HELP = _('Leave blank if bitcoin-qt, bitcoind, and bitcoin-cli are in the path.')
    LEVEL_HELP1 = _('Each level gives you better protection if your blockchain is damaged.')
    LEVEL_HELP2 = _('Warning: Each level requires the same amount of disk space as the blockchain.')
    SCHEDULE_HELP = _('Enter the minimum hours between backups.')
    BACKUP_DIR_HELP = _('The default backup directory is a subdirectory of your data directory.')
    EXTRA_ARGS_HELP = _('Extra arguments wanted to start bitcoind and bitcoin-qt')

    data_dir = models.CharField(_('Data directory for Bitcoin Core.'),
        max_length=MAX_LENGTH, null=True, blank=True,
       help_text=DATA_DIR_HELP)

    bin_dir = models.CharField(_("Directory for Bitcoin Core's programs."),
        max_length=MAX_LENGTH, null=True, blank=True,
        help_text=BIN_DIR_HELP)

    backup_levels = models.PositiveIntegerField(_('Number of backup levels'),
        null=True, blank=True, default=2,
        help_text=f'{LEVEL_HELP1} {LEVEL_HELP2}')

    backup_schedule = HourField(_('Minimum hours between backups'),
        null=True, blank=True, default=24,
        help_text=SCHEDULE_HELP)

    backup_dir = models.CharField(_('Backup directory for Bitcoin Core.'),
        max_length=MAX_LENGTH, null=True, blank=True,
       help_text=BACKUP_DIR_HELP)

    extra_args = models.CharField(_('Extra arguments for bitcoind and bitcoin-qt'),
        max_length=MAX_LENGTH, null=True, blank=True,
        help_text=EXTRA_ARGS_HELP)

    class Meta:
        verbose_name = _('preferences')
        verbose_name_plural = verbose_name

class State(models.Model):
    '''
        State of last session; used internally only.

        >>> State()
        <State: State object (None)>
    '''

    last_block_time = models.DateTimeField(null=True, blank=True,
        help_text='Date/time of the last block updated in blockchain.')

    last_known_block = models.PositiveIntegerField(null=True, blank=True, default=0,
        help_text='Last known block in the blockchain.')

    last_block_updated = models.PositiveIntegerField(null=True, blank=True, default=0,
        help_text='Last block updated in the bitcoin blockchain.')

    start_access_time = models.DateTimeField(null=True, blank=True,
        help_text='Date/time bitcoind or bitcoin-qt started to run through Blockchain Backup.')

    last_access_time = models.DateTimeField(null=True, blank=True,
        help_text='Date/time bitcoind or bitcoin-qt run through Blockchain Backup.')

    last_backed_up_time = models.DateTimeField(null=True, blank=True,
        help_text='Date/time the blockchain was backed up.')

    last_backup_level = models.PositiveIntegerField(null=True, blank=True, default=1,
        help_text='Subdirectory name of the backup dir with the most current backup.')

    last_update_time = models.DateTimeField(null=True, blank=True,
        help_text='Date/time of the last time checked for updates.')

    latest_bcb_version = models.CharField(max_length=MAX_LENGTH, null=True, blank=True,
        help_text='Lastest version of blockchain backup available.')

    latest_core_version = models.CharField(max_length=MAX_LENGTH, null=True, blank=True,
        help_text='Lastest version of bitcoin core available.')

    email = models.EmailField(null=True, blank=True)

    id_code = models.CharField(max_length=MAX_LENGTH, null=True, blank=True)

    extra_args = models.CharField(max_length=MAX_LENGTH, null=True, blank=True)

    backups_enabled = models.BooleanField(default=True)
