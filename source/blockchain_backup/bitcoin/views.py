'''
    Bitcoin views

    Copyright 2018-2022 DeNova
    Last modified: 2022-01-25
'''

from json import dumps as json_dumps
from json import loads as json2dict
import os
from abc import ABCMeta, abstractmethod
from traceback import format_exc

from django.db.utils import OperationalError
from django.contrib import messages
from django.forms import Form
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView

from blockchain_backup.bitcoin import constants, core_utils, gen_utils, preferences, state
from blockchain_backup.bitcoin.backup_utils import get_next_backup_time, is_backup_running
from blockchain_backup.bitcoin.forms import PreferencesForm, RestoreForm
from blockchain_backup.settings import ALLOWED_HOSTS
from blockchain_backup.version import CURRENT_VERSION
from denova.django_addons.utils import get_remote_ip
from denova.os.user import getdir, whoami
from denova.python.log import Log
from denova.python.times import now, parse_timestamp



PREF_URL = 'href="/bitcoin/preferences/"'
PREF_TITLE = 'title="Click to change your preferences"'
PREF_CLASS = 'class="btn btn-secondary"'
PREF_ID = 'id="preferences-id"'
PREF_ROLE = 'role="button"'
PREF_BUTTON = f'<a {PREF_CLASS} {PREF_ID} {PREF_ROLE} {PREF_URL} {PREF_TITLE}>Preferences</a>'
CLICK_PREF_BUTTON = f'Click {PREF_BUTTON} to set it.'
BAD_BIN_DIR = f"{'The Bitcoin binary directory is not valid.'} {CLICK_PREF_BUTTON}"
BAD_DATA_DIR = f"{'The Bitcoin data directory is not valid.'} {CLICK_PREF_BUTTON}"
BAD_BACKUP_DIR = f"{'The Bitcoin backup directory is not valid.'} {CLICK_PREF_BUTTON}"
NO_BACKUP_IF_CORE_RUNNING = 'The backup cannot proceed until all Bitcoin Core apps have been stopped.'
INVALID_FIELDS = 'Invalid fields -- details about the errors appear below each field.'
BACKUPS_ENABLED = 'Backups enabled'
BACKUPS_DISABLED = 'Blockchain Backup cannot back up until you <a href="/bitcoin/backup/">change the setting</a>.'

# global variables
log = Log()

update_task = None
backup_task = None
restore_task = None
accessing_wallet_task = None
restore_dir = None


class LocalAccessOnly(TemplateView, metaclass=ABCMeta):
    '''
        Restrict web access to only allowed hosts.
    '''

    def get(self, request, *args, **kwargs):

        remote_ip = get_remote_ip(request)
        if remote_ip in ALLOWED_HOSTS:
            response = self.get_page(request, *args, **kwargs)
        else:
            log(f'attempted access from ip: {remote_ip}')
            response = render(request, 'no_remote_access.html', context={'ip': remote_ip})

        return response

    def post(self, request, *args, **kwargs):

        remote_ip = get_remote_ip(request)
        if remote_ip in ALLOWED_HOSTS:
            response = self.post_page(request)
        else:
            log(f'attempted access from ip: {remote_ip}')
            response = render(request, 'no_remote_access.html', context={'ip': remote_ip})

        return response

    @abstractmethod
    def get_page(self, request):
        ''' Get the page for a user with local access. '''
        # keep the following command so when we strip comments, python's ok
        pass

    def post_page(self, request):
        ''' Post the page for a user with local access. '''

        return render(request, 'invalid_access.html')


class Home(LocalAccessOnly):
    '''
        Show the bitcoin core home page.

        Give a few tips if this is the first time.
    '''

    def get_page(self, request):
        # let's see what we know about the environment

        gen_utils.clear_action_updates()

        # last block in django database; may be different from last in blockchain
        last_block_updated = state.get_last_block_updated()
        # ready if blockchain-backup has processed some blockchain data
        bcb_run_already = last_block_updated > 0
        bin_dir_ok = preferences.bin_dir_ok()
        data_dir = preferences.get_data_dir()
        backup_dir_ok, backup_dir_error = preferences.backup_dir_ok()
        backup_dir = preferences.get_backup_dir()
        last_bcb_version = state.get_latest_bcb_version()

        if bcb_run_already:
            data_dir_ok, __ = preferences.data_dir_ok()
        else:
            if data_dir and os.path.exists(data_dir):
                data_dir_ok, __ = preferences.data_dir_ok()
            else:
                data_dir_ok = False

        gen_utils.check_for_updates()

        params = {
                  'data_dir': data_dir,
                  'data_dir_ok': data_dir_ok,
                  'backup_dir': backup_dir,
                  'backup_dir_ok': backup_dir_ok,
                  'backup_dir_error': backup_dir_error,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': last_bcb_version >= CURRENT_VERSION,
                  'need_backup': get_next_backup_time() < now(),
                  'last_backed_up_time': state.get_last_backed_up_time(),
                 }
        #log('params: {}'.format(params))

        response = gen_utils.get_home_page_response(request, bcb_run_already, bin_dir_ok, params)

        return response


class AccessWallet(LocalAccessOnly):
    '''
        Access bitcoin interactively via bitcoin-qt.
    '''

    def get_page(self, request):

        global accessing_wallet_task

        log('accessing bitcoin interactively')

        gen_utils.clear_action_updates()

        core_running = (core_utils.is_bitcoind_running() or
                        core_utils.is_bitcoin_tx_running() or
                        (core_utils.is_bitcoin_qt_running() and not accessing_wallet()))

        # it's ok if bitcoin-qt is running in our task
        if core_running:
            response = warn_core_running(request)

        # tell user if another app is running
        elif is_backup_running() or gen_utils.is_restore_running():
            response = warn_bcb_app_running(request)

        # tell user if another task is running
        elif updating() or backing_up() or restoring():
            response = warn_bcb_task_running(request)

        else:
            SUBNOTICE1 = "Waiting until you exit Bitcoin-QT.<p>Bitcoin-QT will start in another window."
            SUBNOTICE2 = "You can send and receive transactions from that window."
            SUBNOTICE3 = "After you exit Bitcoin-QT, Blockchain Backup will continue updating the blockchain until it's time to back it up."
            SUBNOTICE4 = "Don't forget to back up your wallet routinely."
            SUBNOTICE = f'{SUBNOTICE1} {SUBNOTICE2} {SUBNOTICE3} {SUBNOTICE4}'

            context = gen_utils.get_blockchain_context()

            data_dir_ok, error = preferences.data_dir_ok()
            if not preferences.bin_dir_ok():
                context['notice'] = BAD_BIN_DIR
            elif not data_dir_ok:
                context['notice'] = BAD_DATA_DIR
                context['subnotice'] = error
            else:
                HEADER = 'Accessing Bitcoin Core Wallet Interactively'
                NOTICE = 'WARNING: Do not shut down your computer until Bitcoin-QT stops completely.'

                context['header'] = HEADER
                context['notice'] = NOTICE
                context['subnotice'] = SUBNOTICE

                if accessing_wallet():
                    log('already accessing wallet')

                else:
                    # late import to limit the code that is loaded on start up
                    from blockchain_backup.bitcoin.access_wallet import AccessWalletTask

                    accessing_wallet_task = AccessWalletTask()
                    accessing_wallet_task.start()
                    log('access wallet started')

            response = render(request, 'bitcoin/access_wallet.html', context=context)

        return response


class Update(LocalAccessOnly):
    '''
        Update blockchain in background.
    '''
    def get_page(self, request):

        global update_task

        log('trying to update blockchain')

        gen_utils.clear_action_updates()

        # check that no other bitcoin-core app is running
        if (core_utils.is_bitcoin_qt_running() or core_utils.is_bitcoin_tx_running() or
           (core_utils.is_bitcoind_running() and not updating())):
            response = warn_core_running(request)

        # tell user if another blockchain_backup app is running
        elif is_backup_running() or gen_utils.is_restore_running():
            response = warn_bcb_app_running(request)

        # tell user if another task is running
        elif accessing_wallet() or backing_up() or restoring():
            response = warn_bcb_task_running(request)

        else:
            NOTICE1 = 'WARNING: Don\'t shut down your computer before you <a class="btn btn-secondary " role="button"'
            NOTICE2 = 'id="stop_button" href="/bitcoin/interrupt_update/" title="Click to stop updating the blockchain">Stop update</a>'
            NOTICE = f'{NOTICE1} {NOTICE2}'

            context = gen_utils.get_blockchain_context()

            data_dir_ok, error = preferences.data_dir_ok()
            if not preferences.bin_dir_ok():
                context['notice'] = BAD_BIN_DIR
                log(BAD_BIN_DIR)
            elif not data_dir_ok:
                context['notice'] = BAD_DATA_DIR
                log(error)
            else:
                HEADER = "Updating Bitcoin's blockchain"
                SUBNOTICE = 'Shutting down before this window says it is safe <em>could damage the blockchain</em>.'
                PROGRESS = 'Starting to update the blockchain'

                context['header'] = HEADER
                context['notice'] = NOTICE
                context['subnotice'] = SUBNOTICE
                context['progress'] = PROGRESS

                if updating():
                    log('already updating blockchain')

                else:
                    # late import to limit the code that is loaded on start up
                    from blockchain_backup.bitcoin.update import UpdateTask

                    update_task = UpdateTask()
                    update_task.start()
                    log('UpdateTask started')

            log(f'context: {context}')
            response = render(request, 'bitcoin/update.html', context=context)

        return response


class InterruptUpdate(LocalAccessOnly):
    '''
        Interrupt updating.
    '''

    def get_page(self, request):

        global update_task

        log('stopping update of blockchain')

        # don't check if we are updating() to avoid race
        # it should be ok to call stop() multiple times
        if update_task:
            update_task.interrupt()
            log('interrupted UpdateTask')

        context = gen_utils.get_blockchain_context()

        return render(request, 'bitcoin/interrupt_update.html', context=context)

class Backup(LocalAccessOnly):
    '''
        Backup blockchain.
    '''

    def get_page(self, request):

        global backup_task

        log('backing up blockchain')

        gen_utils.clear_action_updates()

        # check that no other bitcoin-core app is running
        if core_utils.is_bitcoin_core_running():
            message = NO_BACKUP_IF_CORE_RUNNING
            response = warn_core_running(request, message=message)

        # tell user if another app is running
        elif gen_utils.is_restore_running():
            response = warn_bcb_app_running(request, app=constants.RESTORE_PROGRAM)

        # tell user if another task is running
        elif accessing_wallet() or updating() or restoring():
            response = warn_bcb_task_running(request)

        # tell user if backups have been disabled
        elif not state.get_backups_enabled():
            response = HttpResponseRedirect('/bitcoin/change_backup_status/')
            log('tried to backup when backups disabled')
            log(f'response: {response}')

        else:
            SUBNOTICE1 = 'If you need to stop the backup, then <a class="btn btn-secondary " href="/bitcoin/interrupt_backup/"'
            SUBNOTICE2 = 'role="button" id="stop-button" title="Click to stop backing up the blockchain">click here</a>'
            SUBNOTICE = f'{SUBNOTICE1} {SUBNOTICE2}'

            context = gen_utils.get_blockchain_context()

            data_dir_ok, error = preferences.data_dir_ok()
            if not preferences.bin_dir_ok():
                context['notice'] = BAD_BIN_DIR
                context['subnotice'] = ''
            elif not data_dir_ok:
                context['notice'] = BAD_DATA_DIR
                context['subnotice'] = error
            else:
                context['header'] = "Backing up bitcoin's blockchain"
                context['notice'] = 'WARNING: Stopping the backup could damage the ability to restore the blockchain.'
                context['subnotice'] = SUBNOTICE
                context['progress'] = 'Starting to back up the blockchain'

                if backing_up():
                    log('already backing_up blockchain')

                else:
                    # late import to limit the code that is loaded on start up
                    from blockchain_backup.bitcoin.backup import BackupTask

                    backup_task = BackupTask()
                    backup_task.start()
                    log('backup started')

            response = render(request, 'bitcoin/backup.html', context=context)

        return response

class InterruptBackup(LocalAccessOnly):
    '''
        Interrupt backing up the blockchain.
    '''

    def get_page(self, request):

        global backup_task

        # don't check if we are backing_up() to avoid race
        # it should be ok to call interrupt() multiple times
        if backup_task:
            backup_task.interrupt()
        log('interrupted backup')

        context = gen_utils.get_blockchain_context()

        return render(request, 'bitcoin/interrupt_backup.html', context=context)

class ChangeBackupStatus(LocalAccessOnly):
    '''
        Change whether backups enabled or not.
    '''
    form_url = 'bitcoin/change_backup_status.html'

    def get_page(self, request):

        log('change whether backups enabled or not')

        gen_utils.clear_action_updates()
        form = Form()
        context = {}
        backups_enabled = state.get_backups_enabled()
        if backups_enabled:
            context['header'] = 'Blockchain Backup currently backups the blockchain on your schedule.'
            context['notice'] = 'WARNING: If you disable backups, then Blockchain Backup cannot keep your copy of the blockchain safe.'
            context['status'] = 'Enabled'
        else:
            context['header'] = 'Blockchain Backup temporarily disabled backups the blockchain.'
            context['notice'] = 'WARNING: Do <i>not</i> enable backups until Bitcoin Core runs successfully.'
            context['status'] = 'Disabled'
        context['header'] = f"Backups {context['status']}"
        context['form'] = form

        return render(request, self.form_url, context=context)

    def post_page(self, request):

        backups_enabled = ('enable-backups-button' in request.POST or
                           'leave-backups-enabled-button' in request.POST)

        if state.get_backups_enabled() != backups_enabled:
            state.set_backups_enabled(backups_enabled)
            if backups_enabled:
                messages.success(request, BACKUPS_ENABLED)
            else:
                messages.success(request, BACKUPS_DISABLED)

        # send them back to the home page
        response = HttpResponseRedirect('/')

        return response

class Restore(LocalAccessOnly):
    '''
        Restore the blockchain after verifying user wants to do so.
    '''

    BAD_HEADER = 'Unable to Restore the Blockchain'
    NO_GOOD_BACKUP = 'There are no good backups ready to be restored, yet.'
    REMINDER = 'You must backup before you can restore the blockchain.'
    WARNING1 = '<br/>WARNING: All updates after the date you select will be lost.<br/>'
    WARNING2 = '<br/>WARNING: All updates after {} will be lost.<br/>'

    def get_page(self, request):

        log('getting restore page')

        gen_utils.clear_action_updates()

        response = self.check_for_conflicts(request)

        if response is None:
            log('nothing conflicting with restore')
            error_message = more_error_msg = None
            context = gen_utils.get_blockchain_context()

            backup_dates, preselected_date = state.get_backup_dates_and_dirs()
            error_message, more_error_msg = self.check_dirs_ok(backup_dates)
            if error_message is None:

                log('asking for confirmation')
                response = self.ask_user_to_confirm(
                  request, backup_dates, preselected_date, context)

            else:
                log(error_message)
                # show the user the errors
                log(error_message)
                context['header'] = self.BAD_HEADER
                context['notice'] = error_message
                if more_error_msg is None:
                    context['subnotice'] = ''
                else:
                    context['subnotice'] = more_error_msg

                response = render(request, 'bitcoin/restore_not_ready.html', context=context)

        return response

    def post_page(self, request):

        # we use a global because the user might try
        # loading the restore page when it's already running
        global restore_dir

        if 'no-cancel-restore-button' in request.POST:
            # send them back to the home page
            log('user does not want to restore from the backup')
            response = HttpResponseRedirect('/')
        else:
            log('posting restore page')

            form = RestoreForm(request.POST)
            if form.is_valid():
                if 'backup_dates_with_dirs' in form.cleaned_data:
                    # the backup_dates_with_fields is a choice where the directory is returned
                    restore_dir = form.cleaned_data['backup_dates_with_dirs']
                else:
                    # if there's only one option, then the field is not required
                    # so used the one option automatically
                    __, preselected_date_dir = state.get_backup_dates_and_dirs()
                    restore_dir = preselected_date_dir[0]

                log(f'user confirmed ready to restore from: {restore_dir}')

                response = self.restore()
            else:
                log('form is not valid')
                gen_utils.log_bad_fields(form)
                messages.error(request, INVALID_FIELDS)
                response = render(request, 'bitcoin/ready_to_restore.html', {'form': form, })

        return response

    def restore(self):

        global restore_task, restore_dir

        gen_utils.clear_action_updates()

        if restoring():
            log('already restoring blockchain')
        else:
            # late import to limit the code that is loaded on start up
            from blockchain_backup.bitcoin.restore import RestoreTask

            restore_task = RestoreTask(restore_dir)
            restore_task.start()
            log('restore blockchain started')

        context = gen_utils.get_blockchain_context()
        context['header'] = 'Restoring Bitcoin Blockchain'
        context['notice'] = 'WARNING: Do not shut down your computer until the restore finishes.'
        context['progress'] = 'Starting to restore the blockchain'

        response = render(self.request, 'bitcoin/restore.html', context=context)

        return response

    def ask_user_to_confirm(self, request, backup_dates, preselected_date, context):
        ''' Set up to ask the user to confirm they want to restore. '''

        log('ask user to confirm they want to restore the blockchain')

        gen_utils.clear_action_updates()

        form = RestoreForm()
        show_backup_dates = len(backup_dates) > 1
        if show_backup_dates:
            warning = self.WARNING1
        else:
            warning = self.WARNING2.format(preselected_date[1])

        context['header'] = '<h4>Are you sure you want to restore the Bitcoin blockchain?</h4>'
        context['notice'] = warning
        context['subnotice'] = ''
        context['backup_dates_with_dirs'] = backup_dates
        context['backup_dates_with_dirs'] = backup_dates
        context['update_interval'] = '1000'
        context['form'] = form

        response = render(request, 'bitcoin/ready_to_restore.html', context=context)

        return response

    def check_for_conflicts(self, request):
        ''' Check if there are other apps/tasks running. '''

        response = None

        # check that no other bitcoin-core app is running
        if core_utils.is_bitcoin_core_running():
            log(f'bitcoind running: {core_utils.is_bitcoind_running()}')
            log(f'bitcoin_qt running: {core_utils.is_bitcoin_qt_running()}')
            log(f'bitcoin_tx running: {core_utils.is_bitcoin_tx_running()}')

            response = warn_core_running(request)

        # tell user if backup is running
        elif is_backup_running():
            log('backup running')
            response = warn_bcb_app_running(request, app=constants.BACKUP_PROGRAM)

        # tell user if restore is already running
        elif gen_utils.is_restore_running():
            log('restore running')
            response = self.restore()

        # tell user if another task is running
        elif accessing_wallet() or updating() or backing_up():
            log('task running')
            response = warn_bcb_task_running(request)

        return response

    def check_dirs_ok(self, backup_dates):
        ''' Check that all the data dirs are ok. '''

        error_message = more_error_msg = None

        backup_dir_ok, backup_error = preferences.backup_dir_ok()
        if backup_dir_ok:
            good_backup = backup_dates
            log(f'backup_dates {backup_dates}')
        else:
            log(backup_error)

        data_dir_ok, data_error = preferences.data_dir_ok()
        if not preferences.bin_dir_ok():
            error_message = BAD_BIN_DIR
        elif not data_dir_ok:
            error_message = BAD_DATA_DIR + ' ' + data_error
        elif not backup_dir_ok:
            error_message = BAD_BACKUP_DIR + ' ' + backup_error
        elif not good_backup:
            log(f'no good backups in {backup_dates}')
            error_message = self.NO_GOOD_BACKUP
            more_error_msg = self.REMINDER

        log(f'error_message {error_message}')
        log(f'more_error_msg {more_error_msg}')

        return error_message, more_error_msg

class InterruptRestore(LocalAccessOnly):
    '''
        Interrupt restoring the blockchain.
    '''

    def get_page(self, request):

        global restore_task

        gen_utils.clear_action_updates()

        # don't check if we are restoring() to avoid race
        # it should be ok to call interrupt() multiple times
        if restore_task:
            restore_task.interrupt()
        log('interrupted restore')

        context = gen_utils.get_blockchain_context()

        return render(request, 'bitcoin/interrupt_restore.html', context=context)


class ChangePreferences(LocalAccessOnly):
    '''
        Change preferences.
    '''
    form_url = 'bitcoin/preferences.html'

    def get_page(self, request):

        try:
            prefs = preferences.get_preferences()
        except OperationalError as oe:
            gen_utils.report_operational_error(oe)

        try:
            if prefs.data_dir is None:
                prefs.data_dir = os.path.join(getdir(), '.bitcoin')

            if prefs.backup_dir is None and prefs.data_dir is not None:
                prefs.backup_dir = os.path.join(prefs.data_dir,
                                                constants.DEFAULT_BACKUPS_DIR)

            if prefs.bin_dir is None:
                prefs.bin_dir = core_utils.get_path_of_core_apps()

            form = PreferencesForm(instance=prefs)
        except: # 'bare except' because it catches more than "except Exception"
            log(format_exc())
            form = PreferencesForm()

        return render(request, self.form_url,
                 {'form': form, 'context': gen_utils.get_blockchain_context()})

    def post_page(self, request):

        form = PreferencesForm(request.POST)
        if form.is_valid():

            data_dir = form.cleaned_data['data_dir']
            bin_dir = form.cleaned_data['bin_dir']
            backup_schedule = form.cleaned_data['backup_schedule']
            backup_levels = form.cleaned_data['backup_levels']
            backup_dir = form.cleaned_data['backup_dir']
            extra_args = form.cleaned_data['extra_args']

            prefs = preferences.get_preferences()
            prefs.data_dir = data_dir
            prefs.bin_dir = bin_dir
            prefs.backup_schedule = backup_schedule
            prefs.backup_levels = backup_levels
            prefs.backup_dir = backup_dir
            prefs.extra_args = extra_args
            preferences.save_preferences(prefs)
            log('Changed preferences.')
            messages.success(request, 'Changed preferences.')

            # send them back to the home page
            response = HttpResponseRedirect('/')

        else:
            log('form is not valid')
            gen_utils.log_bad_fields(form)
            messages.error(request, 'Invalid preferences -- details about the errors appear below the fields.')
            response = render(request, self.form_url, {'form': form, })

        return response


class InitDataDir(LocalAccessOnly):
    '''
        Initialize the data directory.
    '''
    def get_page(self, request):
        error = None

        data_dir = preferences.get_data_dir()
        if not os.path.exists(data_dir):
            try:
                os.makedirs(data_dir)
            except: # 'bare except' because it catches more than "except Exception"
                error = f'Unable to create {data_dir} as {whoami()}'

        if os.path.exists(data_dir):
            __, error = gen_utils.is_dir_writeable(data_dir)

        if error is not None:
            log(error)
            messages.error(request, error)

        response = HttpResponseRedirect('/')

        return response


class UpdatePage(View):
    ''' Return latest updates for a page. '''

    def post(self, request, *args, **kwargs):

        try:
            data = json2dict(request.body)
        except:
            data = None
            log(format_exc())

        try:
            if 'timestamp' in data:
                try:
                    prev_timestamp = parse_timestamp(data['timestamp'])
                except ValueError:
                    prev_timestamp = None
                except:
                    log(format_exc())
                    prev_timestamp = None
            else:
                prev_timestamp = None

            json_message = gen_utils.get_newest_actions(prev_timestamp=prev_timestamp)
            # log(f'sending updated details to {get_remote_ip(request)}')
        except:
            json_message = None
            log(format_exc())

        return JsonResponse(json_message, safe=False)


class Ajax(LocalAccessOnly):
    '''
        Update html in background using ajax.
    '''

    def get_page(self, request):

        message = {}
        action_updates = gen_utils.get_action_updates()
        for action_update in action_updates:
            key = action_update
            value = action_updates[key]
            if value:
                message[key] = value

        json_message = json_dumps(message)

        return HttpResponse(json_message)


def updating():
    '''
        Return True if update_task has been
        run and the thread is alive.

        >>> updating()
        False
    '''
    global update_task

    return update_task is not None and update_task.is_alive()

def backing_up():
    '''
        Return True if backup_task has been
        run and the thread is alive.

        >>> backing_up()
        False
    '''
    global backup_task

    return backup_task is not None and backup_task.is_alive()

def restoring():
    '''
        Return True if restore_task has been
        run and the thread is alive.

        >>> restoring()
        False
    '''
    global restore_task

    return restore_task is not None and restore_task.is_alive()

def accessing_wallet():
    '''
        Return True if access_wallet_task has been
        run and the thread is alive.

        >>> accessing_wallet()
        False
    '''
    global accessing_wallet_task

    return accessing_wallet_task is not None and accessing_wallet_task.is_alive()

def warn_bcb_app_running(request, app=None):
    '''
        Warn that a denova app is running.

        >>> from django.test import RequestFactory
        >>> no_backup_message = bytearray(
        ...   NO_BACKUP_IF_CORE_RUNNING, encoding='utf-8')
        >>> factory = RequestFactory()
        >>> request = factory.get('/bitcoin/preferences/')
        >>> response = warn_bcb_app_running(request)
        >>> response.status_code == 200
        True
        >>> b'Update' in response.content
        True
    '''

    if app is None:
        if is_backup_running():
            app = constants.BACKUP_PROGRAM
        else:
            app = constants.RESTORE_PROGRAM

    return render(request, 'bitcoin/blockchain_backup_app_running.html', {'app': app})

def warn_core_running(request, message=None):
    '''
        Warn that one of the bitcoin
        core programs is running.

        >>> from django.test import RequestFactory
        >>> no_backup_message = bytearray(NO_BACKUP_IF_CORE_RUNNING, encoding='utf-8')
        >>> factory = RequestFactory()
        >>> request = factory.get('/bitcoin/preferences/')
        >>> response = warn_core_running(request)
        >>> response.status_code == 200
        True
        >>> b'BitcoinD' in response.content
        True
        >>> no_backup_message in response.content
        False
        >>> request = factory.get('/bitcoin/preferences/')
        >>> response = warn_core_running(request, message=NO_BACKUP_IF_CORE_RUNNING)
        >>> response.status_code == 200
        True
        >>> b'BitcoinD' in response.content
        True
        >>> no_backup_message in response.content
        True
    '''

    if core_utils.is_bitcoin_qt_running():
        app = 'Bitcoin-QT'
    elif core_utils.is_bitcoin_tx_running():
        app = 'Bitcoin-TX'
    else:
        app = 'BitcoinD'

    if message is None:
        params = {'app': app}
    else:
        params = {'app': app, 'more': message}

    return render(request, 'bitcoin/core_running.html', params)

def warn_bcb_task_running(request):
    '''
        Warn that another resuce task is running.

        >>> from django.test import RequestFactory
        >>> no_backup_message = bytearray(
        ...   NO_BACKUP_IF_CORE_RUNNING, encoding='utf-8')
        >>> factory = RequestFactory()
        >>> request = factory.get('/bitcoin/preferences/')
        >>> response = warn_bcb_task_running(request)
        >>> response.status_code == 200
        True
        >>> b'Update' in response.content
        True
        >>> no_backup_message in response.content
        False
    '''

    if accessing_wallet():
        app = 'access wallet'
    elif updating():
        app = 'update'
    elif backing_up():
        app = 'backup'
    elif restoring():
        app = 'restore'
    else:
        app = 'update'

    params = {'app': app}

    return render(request, 'bitcoin/task_running.html', params)
