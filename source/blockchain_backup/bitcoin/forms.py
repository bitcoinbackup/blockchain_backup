'''
    Forms for bitcoin.

    Copyright 2018-2020 DeNova
    Last modified: 2020-11-05
'''

import os
from traceback import format_exc
from django.forms import ChoiceField, Form, ModelForm, ValidationError
from django.utils.translation import ugettext_lazy as _

from blockchain_backup.bitcoin.constants import DEFAULT_BACKUPS_DIR
from blockchain_backup.bitcoin.models import Preferences
from blockchain_backup.bitcoin.preferences import bin_dir_ok, data_dir_ok
from blockchain_backup.bitcoin.state import get_backup_dates_and_dirs
from blockchain_backup.bitcoin.utils import is_dir_writeable
from denova.python.log import get_log
from denova.os.user import getdir, whoami


class RestoreForm(Form):
    def __init__(self, *args, **kwargs):
        '''
            Initialize the restore form's date/dir selection.

            >>> restoreForm = RestoreForm()
            >>> restoreForm is not None
            True
            >>> isinstance(restoreForm.fields['backup_dates_with_dirs'], ChoiceField)
            True
            >>> restoreForm.required
            False
        '''
        super(RestoreForm, self).__init__(*args, **kwargs)
        backup_dates, preselected_date = get_backup_dates_and_dirs()
        self.required = len(backup_dates) > 1
        self.fields['backup_dates_with_dirs'] = ChoiceField(
            choices=backup_dates, initial=preselected_date, required=self.required)


class PreferencesForm(ModelForm):

    def __init__(self, *args, **kwargs):
        '''
            Initialize the preferences form.

            >>> prefs = PreferencesForm()
            >>> prefs is not None
            True
            >>> prefs.log is not None
            True
        '''
        super(PreferencesForm, self).__init__(*args, **kwargs)
        self.log = get_log()

    def clean_data_dir(self):
        '''
            Clean the data directory.

            >>> from tempfile import gettempdir
            >>> prefs = PreferencesForm()
            >>> prefs.cleaned_data = {'data_dir': os.path.join(gettempdir(), 'bitcoin/data')}
            >>> prefs.clean_data_dir()
            '/tmp/bitcoin/data'
            >>> prefs.cleaned_data = {'data_dir': None}
            >>> data_dir = prefs.clean_data_dir()
            >>> data_dir.endswith('.bitcoin')
            True
        '''

        data_dir = self.cleaned_data['data_dir']
        if data_dir is None:
            data_dir = os.path.join(getdir(), '.bitcoin')
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
            self.cleaned_data['data_dir'] = data_dir

        ok, error = data_dir_ok(data_dir)

        if ok and error is None:
            data_dir = self.cleaned_data['data_dir']
        else:
            self.log(error)
            raise ValidationError(error)

        return data_dir

    def clean_bin_dir(self):
        '''
            Clean the bin directory.

            >>> from tempfile import gettempdir
            >>> prefs = PreferencesForm()
            >>> prefs.cleaned_data = {'bin_dir': os.path.join(gettempdir(), 'bitcoin/bin')}
            >>> try:
            ...     bin_dir = prefs.clean_bin_dir()
            ...     bin_dir == os.path.join(gettempdir(), 'bitcoin/bin')
            ... except ValidationError as ve:
            ...     str(ve) == 'Bitcoin core programs are not in the path'
            True
        '''
        bin_dir = self.cleaned_data['bin_dir']

        if bin_dir is None or not bin_dir.strip():
            if bin_dir_ok():
                error = None
            else:
                error = _('Bitcoin core programs are not in the path')
        elif not os.path.exists(bin_dir):
            error = _(f'{bin_dir} does not exist or is not accessible to {whoami()}.')
        elif not bin_dir_ok(bin_dir):
            error = _(f'Bitcoin core programs are not in {bin_dir}')
        else:
            error = None

        if error is not None:
            self.log(error)
            raise ValidationError(error)

        return bin_dir

    def clean_backup_dir(self):
        '''
            Clean the backup directory.

            >>> from tempfile import gettempdir
            >>> prefs = PreferencesForm()
            >>> temp_dir = gettempdir()
            >>> prefs.cleaned_data = {'data_dir': os.path.join(temp_dir, 'bitcoin/data'), 'backup_dir': os.path.join(temp_dir, 'bitcoin/data/backups')}
            >>> prefs.clean_backup_dir()
            '/tmp/bitcoin/data/backups'
            >>> prefs.cleaned_data = {'data_dir': os.path.join(temp_dir, 'bitcoin/data'), 'backup_dir': None}
            >>> backup_dir = prefs.clean_backup_dir()
            >>> backup_dir == os.path.join(temp_dir, 'bitcoin/data', DEFAULT_BACKUPS_DIR)
            True
            >>> prefs.cleaned_data = {'data_dir': None, 'backup_dir': None}
            >>> try:
            ...     backup_dir = prefs.clean_backup_dir()
            ... except ValidationError as ve:
            ...     print(ve)
            ['You need to enter a valid backup directory']
        '''

        error = None
        backup_dir = self.cleaned_data['backup_dir']

        if backup_dir is None or not backup_dir.strip():
            data_dir = self.cleaned_data['data_dir']
            if data_dir is None:
                error = 'You need to enter a valid backup directory'
            else:
                backup_dir = os.path.join(data_dir, DEFAULT_BACKUPS_DIR)
                try:
                    if not os.path.exists(backup_dir):
                        os.makedirs(backup_dir)
                except: # 'bare except' because it catches more than "except Exception"
                    error = f'Unable to create {backup_dir}'
                    self.log(format_exc())

        elif not os.path.exists(backup_dir):
            try:
                os.makedirs(backup_dir)
            except PermissionError:
                error = f'Unable to create {backup_dir} because of a permission error'
            except: # 'bare except' because it catches more than "except Exception"
                error = f'Unable to create {backup_dir}'
                self.log(format_exc())

        if error is None:
            if os.path.exists(backup_dir):
                __, error = is_dir_writeable(backup_dir)

        if error is not None:
            self.log(error)
            raise ValidationError(error)

        return backup_dir

    def clean_backup_schedule(self):
        '''
            Verify the backup schedule the user entered are valid.

            >>> prefs = PreferencesForm()
            >>> prefs.cleaned_data = {'backup_schedule': 1}
            >>> prefs.clean_backup_schedule()
            1
            >>> prefs.cleaned_data = {'backup_schedule': 25}
            >>> try:
            ...     prefs.clean_backup_schedule()
            ... except ValidationError as ve:
            ...     print(str(ve))
            ['Backup schedule must be set to a minimum of 1 and a maximum of 24 hours.']
        '''

        error = None
        backup_schedule = self.cleaned_data['backup_schedule']

        if backup_schedule is None or backup_schedule < 1 or backup_schedule > 24:
            error = 'Backup schedule must be set to a minimum of 1 and a maximum of 24 hours.'
            self.log(error)
            raise ValidationError(error)

        return backup_schedule

    def clean_backup_levels(self):
        '''
            Verify the backup levels the user entered are valid.

            >>> prefs = PreferencesForm()
            >>> prefs.cleaned_data = {'backup_levels': 3}
            >>> prefs.clean_backup_levels()
            3
            >>> prefs.cleaned_data = {'backup_levels': 0}
            >>> try:
            ...     prefs.clean_backup_levels()
            ... except ValidationError as ve:
            ...     print(str(ve))
            ['Backup levels must be set to a minimum of 1.']
        '''

        error = None
        backup_levels = self.cleaned_data['backup_levels']

        if backup_levels is None or backup_levels < 1:
            error = 'Backup levels must be set to a minimum of 1.'
            self.log(error)
            raise ValidationError(error)

        return backup_levels

    def clean_extra_args(self):
        '''
            Verify the extra args for bitcoind the user entered are not invalid.

            >>> prefs = PreferencesForm()
            >>> prefs.cleaned_data = {'extra_args': None}
            >>> extra_args = prefs.clean_extra_args()
            >>> extra_args == None
            True
            >>> prefs.cleaned_data = {'extra_args': '-blocksdir'}
            >>> try:
            ...     prefs.clean_extra_args()
            ... except ValidationError as ve:
            ...     print(str(ve))
            ['Invalid extra args: The -blocksdir option is not permitted. The "blocks" directory must always be a subdirectory of the "Data directory".']
        '''

        error = None
        extra_args = self.cleaned_data['extra_args']

        if extra_args is None or not extra_args.strip():
            pass

        else:
            InvalidArgs = 'Invalid extra args: '
            if '-version' in extra_args:
                error = InvalidArgs + 'The -version option is not permitted. You can only use it from the command line.'
            elif '-blocksdir' in extra_args:
                error = InvalidArgs + 'The -blocksdir option is not permitted. The "blocks" directory must always be a subdirectory of the "Data directory".'
            elif '-debuglogfile' in extra_args:
                error = InvalidArgs + 'The -debuglogfile option is not permitted.'
            elif '-daemon' in extra_args:
                error = InvalidArgs + 'The -daemon option is already used when running bitcoind so it is not permitted.'
            elif '-disablewallet' in extra_args:
                error = InvalidArgs + 'The -disablewallet option is already used when running bitcoind so it is not permitted.'
            elif '-server' in extra_args:
                error = InvalidArgs + 'The -server RPC option is already used when running bitcoin-qt so it is not permitted.'
            elif '-datadir' in extra_args:
                error = InvalidArgs + 'The -datadir may only be specified in the "Data directory" field above.'
            elif '-choosedatadir' in extra_args:
                error = InvalidArgs + 'The -choosedatadir option is not supported. Specify it in the "Data directory" field above.'

        if error is not None:
            self.log(error)
            raise ValidationError(error)

        return extra_args

    class Meta:
        model = Preferences
        fields = ['data_dir', 'bin_dir', 'backup_schedule', 'backup_levels', 'backup_dir', 'extra_args']
