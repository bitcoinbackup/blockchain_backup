'''
    General utilities for blockchain backup.

    Copyright 2018-2022 DeNova
    Last modified: 2022-01-25
'''

import os
from datetime import timedelta
from json import dumps as dict2json
from time import sleep
from traceback import format_exc

from django.http import HttpResponse
from django.shortcuts import render

from blockchain_backup import __file__ as blockchain_backup_file
from blockchain_backup.bitcoin import constants, state
from blockchain_backup.settings import DATABASE_PATH
from denova.os.command import background
from denova.os.process import is_program_running
from denova.os.user import whoami
from denova.python.log import Log
from denova.python.times import now, timestamp

log = Log()

# updates to send to the user
action_updates = {}
time_actions_updated = None


def is_restore_running():
    '''
        Return True if restore is running.

        >>> is_restore_running()
        False
    '''

    # restore program is a link to safecopy
    return is_program_running(constants.RESTORE_PROGRAM)

def is_dir_writeable(data_dir):
    '''
        Return True if a new file
        can be created in the dir.

        >>> data_dir = '/tmp'
        >>> is_dir_writeable(data_dir)
        (True, None)
        >>> data_dir = '/'
        >>> ok, error_message = is_dir_writeable(data_dir)
        >>> ok == False
        True
        >>> error_message.startswith('Unable to write to the dir in')
        True
        >>> data_dir = '/unknown'
        >>> is_dir_writeable(data_dir)
        (False, '"/unknown" directory does not exist.')
    '''
    try:
        filename = os.path.join(data_dir, '.test')
        with open(filename, "wt") as output_file:
            output_file.write('test')
        os.remove(filename)
        ok = True
        error = None
    except PermissionError:
        ok = False
        error = f'Unable to write to the dir in {data_dir} as {whoami()}.'
        log(error)
    except FileNotFoundError:
        ok = False
        error = f'"{data_dir}" directory does not exist.'
        log(error)
    except OSError as ose:
        ok = False
        error = f'error accessing "{data_dir}" directory; {ose}'
        log(error)

    return ok, error

def get_blockchain_context():
    '''
        Get the basic context for a blockchain web page.

        >>> context = get_blockchain_context()
        >>> context['update_facility']
        'denova.blockchain_backup.bitcoin'
        >>> context['update_type']
        'blockchain_long_polling_type'
    '''
    context = {'update_facility': constants.BLOCKCHAIN_FACILITY,
               'update_type': constants.BLOCKCHAIN_TYPE,
               'use_long_polling': constants.USE_LONG_POllING,
               'update_interval': 1000,
               }
    return context

def format_time(unformatted_time):
    '''
        Format time so seconds, milliseconds, and timezone are stripped.

        >>> format_time('2009-01-12 12:00:00.000000+00:00')
        '2009-01-12 12:00'
    '''

    i = unformatted_time.find('.')
    if i > 0:
        unformatted_time = unformatted_time[:i]
        i = unformatted_time.rfind(':')
        if i > 0:
            unformatted_time = unformatted_time[:i]

    return unformatted_time

def wait_period(formatted_time):
    '''
        Format the period to wait into readable hours and minutes.

        >>> last_backed_up_time = state.get_last_backed_up_time()
        >>> hours_til_next_backup = format_time(str(now() - last_backed_up_time))
        >>> time_period = wait_period(hours_til_next_backup)
        >>> time_period is not None
        True
    '''

    def format_hours_section(hours, extra_hours):
        ''' Format the hours. '''

        hours_section = None
        if hours is not None and hours:
            hours = int(hours) + extra_hours
            if hours > 1:
                if extra_hours > 0:
                    hours_section = f'>{hours} hours'
                else:
                    hours_section = f'{hours} hours'
            elif hours == 1:
                hours_section = f'{hours} hour'

        return hours_section

    def format_minutes_section(minutes):
        ''' Format the minutes. '''

        minutes_section = None
        if minutes is not None and minutes:
            if int(minutes) > 1:
                minutes_section = f'{minutes} minutes'
            elif int(minutes) == 1:
                minutes_section = f'{minutes} minute'

        return minutes_section


    i = formatted_time.rfind(',')
    if i > 0:
        extra_hours = 24
        formatted_time = formatted_time[i+1:].strip()
    else:
        extra_hours = 0

    i = formatted_time.find(':')
    if i >= 0:
        hours = formatted_time[:i]
        minutes = formatted_time[i+1:]
    else:
        hours = None
        minutes = None

    hours_section = format_hours_section(hours, extra_hours)
    minutes_section = format_minutes_section(minutes)

    if hours_section is None and minutes_section is None:
        time_period = 'less than a minute'
    elif hours_section is None:
        time_period = minutes_section
    elif minutes_section is None:
        time_period = hours_section
    else:
        time_period = f'{hours_section} and {minutes_section}'

    return time_period

def check_for_updates(current_time=None, force=False, reason=None):
    '''
        Check to see if updates are needed.

        >>> from blockchain_backup.bitcoin.tests import utils as test_utils
        >>> test_utils.init_database()
        >>> check_for_updates()
        True
    '''

    updates_checked = False

    try:
        if current_time is None:
            current_time = now()

        next_updates_time = state.get_last_update_time() + timedelta(hours=24)
        if force or next_updates_time <= current_time:
            log('starting to check for the latest updates')

            # set the update time now so we don't restart the check too often
            state.set_last_update_time(current_time)

            command_args = []
            command_args.append('python3')
            # get the path for check_for_updates.py, regardless of virtualenv, etc.
            check_program = os.path.realpath(os.path.abspath(os.path.join(
              os.path.dirname(blockchain_backup_file), 'config', 'check_for_updates.py')))
            command_args.append(check_program)
            if reason is not None:
                command_args.append(reason)
            background(*command_args)

            updates_checked = True
    except: # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    return updates_checked

def get_ok_button():
    '''
        Get a button.

        >>> get_ok_button()
        '&nbsp;&nbsp;<a href="/" name="ok-button" id="ok-id" class="btn btn-secondary" title="Click to return to front page." role="button"> <strong>OK</strong> </a><br/>'
    '''

    return get_button('/', 'OK', 'Click to return to front page.')

def get_button(href, label, tooltip):
    '''
        Get a button.

        >>> get_button("/", "OK", "It's ok to return to front page")
        '&nbsp;&nbsp;<a href="/" name="ok-button" id="ok-id" class="btn btn-secondary" title="It\\'s ok to return to front page" role="button"> <strong>OK</strong> </a><br/>'
    '''

    base = label.replace(' ', '-').replace(',', '').replace("'", '').lower()
    name = f'{base}-button'
    id_tag = f'{base}-id'

    button_tag = '&nbsp;&nbsp;<a href="{}" name="{}" id="{}" class="btn btn-secondary" title="{}" role="button"> <strong>{}</strong> </a><br/>'.format(
      href, name, id_tag, tooltip, label)

    return button_tag

def get_home_page_response(request,
                           bcb_run_already,
                           bin_dir_ok,
                           params):
    '''
        Get the home page depending on the known environment.

        >>> from django.test import RequestFactory
        >>> factory = RequestFactory()
        >>> request = factory.get('/')
        >>> bin_dir_ok = True
        >>> data_dir = '/tmp/bitcoin/data/'
        >>> data_dir_ok = True
        >>> backup_dir = '/tmp/bitcoin/data/backups/'
        >>> backup_dir_ok = True
        >>> need_backup = True
        >>> last_bcb_version = CURRENT_VERSION
        >>> bcb_up_to_date = True
        >>> need_backup = False
        >>> last_backed_up_time = None
        >>> params = {
        ...           'data_dir': data_dir,
        ...           'data_dir_ok': data_dir_ok,
        ...           'backup_dir': backup_dir,
        ...           'backup_dir_ok': backup_dir_ok,
        ...           'last_bcb_version': last_bcb_version,
        ...           'bcb_up_to_date': bcb_up_to_date,
        ...           'need_backup': need_backup,
        ...           'last_backed_up_time': last_backed_up_time,
        ...          }
        >>> bcb_run_already = True
        >>> response = get_home_page_response(request, bcb_run_already, bin_dir_ok, params)
        >>> response.status_code == 200
        True
        >>> b'href="/bitcoin/access_wallet/' in response.content
        True
        >>> b'href="/bitcoin/update/' in response.content
        True
        >>> b'href="/bitcoin/backup/' in response.content
        True
        >>> b'href="/bitcoin/restore/' in response.content
        True
        '''

    data_dir_ok = params['data_dir_ok']
    backup_dir_ok = params['backup_dir_ok']
    all_dirs_available = bin_dir_ok and data_dir_ok and backup_dir_ok

    if bcb_run_already:
        if all_dirs_available:
            response = render(request, 'bitcoin/home.html', context=params)
        elif not backup_dir_ok:
            response = render(request, 'bitcoin/bad_backup_dir.html', context=params)
        else:
            response = render(request, 'bitcoin/missing_info.html', context=params)

    else:
        if all_dirs_available:

            response = get_home_page(request, data_dir_ok, params)

        # Bitcoin Core is installed, but not all vital dirs are ok
        elif bin_dir_ok:

            response = report_dirs_not_configured(request,
                                                  data_dir_ok,
                                                  backup_dir_ok,
                                                  params)

        else:
            response = render(request, 'bitcoin/get_started.html', context=params)

    return response

def get_home_page(request, data_dir_ok, params):
    '''
        Get the home page depending on the config.

        >>> from django.test import RequestFactory
        >>> from blockchain_backup.version import CURRENT_VERSION
        >>> factory = RequestFactory()
        >>> request = factory.get('/')
        >>> bin_dir_ok = True
        >>> data_dir = '/tmp/bitcoin/data/'
        >>> data_dir_ok = True
        >>> backup_dir = '/tmp/bitcoin/data/backups/'
        >>> backup_dir_ok = True
        >>> need_backup = True
        >>> last_bcb_version = CURRENT_VERSION
        >>> bcb_up_to_date = True
        >>> need_backup = False
        >>> last_backed_up_time = None
        >>> params = {
        ...           'data_dir': data_dir,
        ...           'data_dir_ok': data_dir_ok,
        ...           'backup_dir': backup_dir,
        ...           'backup_dir_ok': backup_dir_ok,
        ...           'last_bcb_version': last_bcb_version,
        ...           'bcb_up_to_date': bcb_up_to_date,
        ...           'need_backup': need_backup,
        ...           'last_backed_up_time': last_backed_up_time,
        ...          }
        >>> bcb_run_already = True
        >>> response = get_home_page(request, data_dir_ok, params)
        >>> response.status_code == 200
        True
        >>> b'Blockchain Backup Adds Resilience to Bitcoin Core' in response.content
        True
    '''

    blockchain_has_data = False
    if data_dir_ok:
        data_dir = params['data_dir']
        blocks_dir = os.path.join(data_dir, 'blocks')
        chainstate_dir = os.path.join(data_dir, 'chainstate')
        if os.path.exists(blocks_dir) and os.path.exists(chainstate_dir):
            blocks_items = os.listdir(blocks_dir)
            chainstate_items = os.listdir(chainstate_dir)
            blockchain_has_data = blocks_items and chainstate_items

    if blockchain_has_data:
        log('getting home page')
        if state.get_all_backup_dates_and_dirs():
            response = render(request, 'bitcoin/home.html', context=params)
        else:
            response = render(request, 'bitcoin/need_first_backup.html', context=params)
    else:
        response = render(request, 'bitcoin/need_update.html', context=params)

    return response

def set_action_update(key, value):
    '''
        Set an update for Blockchain Backup's actions.

        >>> set_action_update('header-id', 'Test')
        'Test'
    '''
    global action_updates, time_actions_updated

    log(f'set {key} action: {value}')
    action_updates[key] = value
    time_actions_updated = now()

    return action_updates[key]

def get_action_updates():
    '''
        Get the action updates.

        >>> set_action_update('header-id', 'Test')
        'Test'
        >>> get_action_updates()
        {'header-id': 'Test'}
    '''

    return action_updates

def clear_action_updates():
    '''
        Clear all action_updates.

        >>> clear_action_updates()
        >>> action_updates
        {}
    '''
    global action_updates, time_actions_updated

    action_updates.clear()
    time_actions_updated = now()

def get_newest_actions(prev_timestamp=None):
    ''' Wait for new actions.

        Return actions, or None if there aren't any.

        >>> actions = get_newest_actions()
        >>> 'timestamp' in actions
        True
        >>> 'data' in actions
        True
    '''

    if time_actions_updated is None and action_updates is None:

        log('no new actions yet')
        actions = get_json_update(timestamp(now()), {})

    else:
        if prev_timestamp:

            while time_actions_updated <= prev_timestamp or len(action_updates) == 0:
                sleep(1)
            log(f'got newest actions {time_actions_updated} > {prev_timestamp}')

        actions = get_json_update(time_actions_updated, action_updates)

    return actions

def get_json_update(update_time, current_actions):
    '''
        Get the updated data in json format.

        >>> notice = '&nbsp;You may proceed safely now.&nbsp;&nbsp;&nbsp;<a href="/" name="ok-button" id="ok-id" class="btn btn-secondary" title="Click to return to front page." role="button"> <strong>OK</strong> </a><br/>'
        >>> json_update = get_json_update(now(),
        ...                               {'nav-link': 'state=enabled',
        ...                                'progress-id': '&nbsp;',
        ...                                'header-id': 'Update stopped on your request',
        ...                                'notice-id': notice,
        ...                                'alert-id': 'style=max-width: 40rem; background-color:green'})
        >>> 'timestamp' in json_update
        True
        >>> 'data' in json_update
        True
    '''

    log(f'current actions: {current_actions} / type: {type(current_actions)}')
    timestamped_data = dict(timestamp=timestamp(update_time),
                            data=current_actions)
    log(f'timestamped_data: {timestamped_data} / type: {type(timestamped_data)}')
    json_update = dict2json(timestamped_data)
    log(f'json_update: {json_update} / type: {type(json_update)}')

    return json_update

def log_bad_fields(form):
    '''
        Track the bad fields entered.

        >>> from blockchain_backup.bitcoin.forms import RestoreForm
        >>> form = RestoreForm()
        >>> log_bad_fields(form)
    '''

    # get details of invalid prefeences
    details = {}
    # see django.contrib.formtools.utils.security_hash()
    # for example of form traversal
    for field in form:
        if hasattr(form, 'cleaned_data') and field.name in form.cleaned_data:
            name = field.name
        else:
            # mark invalid data
            name = '__invalid__' + field.name
        details[name] = field.data
    log(f'{details}')
    try:
        if form.name.errors:
            log('  ' + form.name.errors)
        if form.email.errors:
            log('  ' + form.email.errors)
    except: # 'bare except' because it catches more than "except Exception"
        pass

def report_dirs_not_configured(request, data_dir_ok, backup_dir_ok, params):
    '''
        Report which critical directories aren't available.

        >>> from django.test import RequestFactory
        >>> factory = RequestFactory()
        >>> request = factory.get('/')
        >>> bin_dir_ok = True
        >>> data_dir_ok = True
        >>> backup_dir_ok = True
        >>> params = {
        ...           'data_dir_ok': data_dir_ok,
        ...           'backup_dir_ok': backup_dir_ok,
        ...          }
        >>> response = report_dirs_not_configured(request, data_dir_ok, backup_dir_ok, params)
        >>> response.status_code == 200
        True
        >>> b'Blockchain Backup is Almost Ready' in response.content
        True
    '''

    if not data_dir_ok and not backup_dir_ok:
        response = render(request, 'bitcoin/core_found_no_data_no_backup.html', context=params)
    elif not data_dir_ok:
        response = render(request, 'bitcoin/core_found_no_data.html', context=params)
    else:
        response = render(request, 'bitcoin/core_found_no_backup.html', context=params)

    return response

def report_operational_error(oe):
    '''
        Report operational error.

        # oe should be an OperationalError, but we just
        # use the string format so we'll simplify the test
        >>> oe = 'Unable to write to database'
        >>> report_operational_error(oe)
        <HttpResponse status_code=200, "text/html; charset=utf-8">
    '''

    error_message = str(oe).capitalize()
    log(f'{error_message}. Database in {DATABASE_PATH}')

    return HttpResponse(f'{error_message}.<br/>Database in {DATABASE_PATH}')
