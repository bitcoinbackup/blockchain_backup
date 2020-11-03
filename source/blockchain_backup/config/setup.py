#!/usr/bin/env python3
'''
    Set up blockchain_backup.

    Copyright 2018-2020 DeNova
    Last modified: 2020-10-26
'''

import os
import random
import string
import sys
from shutil import copyfile
from subprocess import CalledProcessError

from denova.net.openssl import generate_certificate
from denova.os.command import run, run_verbose
from denova.os.fs import cd
from denova.os.osid import is_windows
from denova.python import text_file
from denova.python.log import get_log

log = get_log()

SERVER_NAME = 'blockchain-backup.local'
HOME_DIR = '/home'

def main():

    PROJECT_DIR = os.path.join(os.sep, 'var', 'local', 'blockchain-backup')

    user = get_user()

    print('')
    print(f'--- Starting to set up Blockchain Backup for {user} ---')
    config_logs(PROJECT_DIR, user)
    config_safelog()

    config_webserver(PROJECT_DIR, user)
    print('--- Finished setting up Blockchain Backup ---')
    print('')

    print("What's Next?")
    print('   To use your wallet always go to:')
    print(f'      http://{SERVER_NAME}')
    print(f"   Or go to https://{SERVER_NAME} and add a security exception.")
    print('')

def get_user():
    ''' Get the user that will run the bitcoin-core. '''

    user = None

    # look for a user with the .bitcoin subdirectory
    users = 0
    if os.path.exists(HOME_DIR):
        entries = os.scandir(HOME_DIR)
        for entry in entries:
            if os.path.exists(os.path.join(entry.path, '.bitcoin')):
                user = entry.name
                users += 1

    # if there's more than 1 user found,
    # let the installer decide which to use
    if users > 1:
        user = None

    while user is None or user.lower() == 'root':
        print('\n')
        print('Your Bitcoin Core wallet should not run as root.')
        user = input("Username to use: ")
        if user.lower() == 'root' or user.strip() == '':
            user = None

    return user

def config_webserver(project_dir, user):
    ''' Configure a local webserver for blockchain backup. '''

    PACKAGES_DIR = os.path.join(project_dir, 'packages')
    BLOCKCHAIN_BACKUP_PACKAGE_DIR = os.path.join(PACKAGES_DIR, 'blockchain_backup')
    CONFIG_DIR = os.path.join(BLOCKCHAIN_BACKUP_PACKAGE_DIR, 'config')

    with cd(CONFIG_DIR):
        config_special_settings(BLOCKCHAIN_BACKUP_PACKAGE_DIR)
        config_user(user)
        build_venv()

    config_perms(os.path.join(project_dir, 'data'), user)
    # we want the user to be able to update blockchain_backup without requiring root access
    config_perms(PACKAGES_DIR, user)

    print(' Configuring the web server')
    add_server_name_to_hosts()

    config_systemd(user)

    # generate the ssl cert before the rest of the nginx config
    gen_nginx_ssl_cert()

    # configure and start nginx
    if not os.path.exists('/etc/nginx/sites-enabled/blockchain-backup'):
        run('ln', '-s', '/etc/nginx/sites-available/blockchain-backup', '/etc/nginx/sites-enabled')
    run('systemctl', 'restart', 'nginx')

    # configure blockchain-backup's servers
    run('systemctl', 'enable', 'blockchain-backup-django-server')
    run('systemctl', 'start', 'blockchain-backup-django-server')
    """
    run('systemctl', 'enable', 'blockchain-backup-socketio-server')
    run('systemctl', 'start', 'blockchain-backup-socketio-server')
    """

    # configure bitcoin-core
    run('systemctl', 'enable', 'blockchain-backup-bitcoin-core')
    run('systemctl', 'start', 'blockchain-backup-bitcoin-core')

def config_special_settings(dirname):
    '''
        Configure django with an unique key.

        >>> import shutil
        >>> CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
        >>> parent_dir = os.path.dirname(CURRENT_DIR)
        >>> dirname = '/tmp/blockchain_backup'
        >>> shutil.copy(os.path.join(parent_dir, 'special_settings.py'), dirname)
        '/tmp/blockchain_backup'
        >>> config_special_settings(dirname)
    '''

    SECRET_KEY_PREFIX = 'SECRET_KEY = '

    filename = os.path.join(dirname, 'special_settings.py')
    if os.path.exists(filename):

        try:
            with open(filename, 'rt') as input_file:
                lines = input_file.readlines()

            # create a new secret key for django that doesn't contain any single quotes
            # the key will have characters made up from ascii, digits, and punctuation marks
            chars = string.ascii_letters + string.digits + '.?*+=@#$%()'
            django_key = random.choice(string.ascii_letters)
            django_key += ''.join(random.choice(chars) for x in range(75))

            with open(filename, 'wt') as output_file:
                for line in lines:
                    if line.startswith(SECRET_KEY_PREFIX):
                        line = f"{SECRET_KEY_PREFIX}'{django_key}'\n"
                    output_file.write(line)

        except Exception as e:
            log(e)
            raise

    else:
        log(f'{filename} not found')

def config_time_zone(dirname):
    '''
        Configure time zone if running on windows.

        >>> import shutil
        >>> CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
        >>> parent_dir = os.path.dirname(os.path.dirname(CURRENT_DIR))
        >>> dirname = '/tmp/blockchain_backup'
        >>> shutil.copy(os.path.join(parent_dir, 'denova', 'django_addons', 'settings_shared.py'), dirname)
        '/tmp/blockchain_backup'
        >>> config_time_zone('/tmp/blockchain_backup')
    '''
    TIME_ZONE_PREFIX = 'TIME_ZONE = '

    if is_windows():
        filename = os.path.join(os.path.dirname(dirname), 'django_addons', 'settings_shared.py')
        if os.path.exists(filename):

            try:
                with open(filename, 'rt') as input_file:
                    lines = input_file.readlines()

                with open(filename, 'wt') as output_file:
                    for line in lines:
                        if line.startswith(TIME_ZONE_PREFIX):
                            tz = 'Atlantic/Reykjavik'
                            line = f"{TIME_ZONE_PREFIX}'{tz}'\n"
                        output_file.write(line)

            except Exception as e:
                log(e)
                raise

        else:
            log(f'{filename} not found')

def config_user(user):
    ''' Configure the user name in the config files. '''

    ACCESS_LOG = "accesslog='/var/local/log/{}/blockchain_backup.gunicorn.access.log'\n"
    ERROR_LOG = "errorlog='/var/local/log/{}/blockchain_backup.gunicorn.error.log'\n"

    entries = os.scandir('.')
    for entry in entries:
        if entry.name.endswith('.ini') or entry.name == 'gunicorn.conf.py':
            new_lines = []
            lines = text_file.read(entry.path)
            for line in lines:
                if line.startswith('user = '):
                    new_lines.append(f'user = {user}\n')
                elif line.startswith("user='"):
                    new_lines.append(f"user='{user}'\n")
                elif line.startswith('accesslog='):
                    new_lines.append(ACCESS_LOG.format(user))
                elif line.startswith('errorlog='):
                    new_lines.append(ERROR_LOG.format(user))
                else:
                    new_lines.append(line)

            text_file.write(entry.path, new_lines)

def build_venv():
    ''' Build the virtual environment. '''

    try:
        # we use stdout=sys.stdout so print() updates goto the screen
        python_command = os.path.join(os.sep, 'usr', 'bin', 'python3')
        run_verbose(python_command, './build_venv.py')
    except CalledProcessError as cpe:
        msg = f'Unable to build virtual environment.\nerror returncode: {cpe.returncode}' + '\n'
        # shouldn't be any stdout since we directed it to sys.stdout
        if cpe.stdout:
            msg = msg + f'stdout: {cpe.stdout.decode().strip()}\n'
        if cpe.stderr:
            msg = msg + f'stderr: {cpe.stderr.decode().strip()}\n'
        log(msg)
        sys.exit(f'Unable to build virtual environment. See {log.pathname}')
        raise
    except Exception as e:
        print('Error setting up virtual environment.')
        log(e)
        raise

def config_perms(target_dir, user):
    ''' Configure the permissions for the dir. '''

    run('chown', '-R', f'{user}:{user}', target_dir)
    run('chmod', '-R', 'u=rwx,g=rx,o=rx', target_dir)

def config_systemd(user):
    ''' Configure the user name in the systemd files. '''

    entries = os.scandir('/etc/systemd/system')
    for entry in entries:
        if entry.name.startswith('blockchain-backup'):
            new_lines = []
            lines = text_file.read(entry.path)
            for line in lines:
                if line.startswith('User='):
                    new_lines.append(f'User={user}\n')
                elif line.startswith('Group='):
                    new_lines.append(f'Group={user}\n')
                elif (line.endswith('--start user') or
                      line.endswith('--stop user')):
                    index = line.rfind(' user')
                    new_lines.append(f'{line[:index]} {user}\n')
                else:
                    new_lines.append(line)

            text_file.write(entry.path, new_lines)

def add_server_name_to_hosts():
    ''' Add blockchain-backup.local to /etc/hosts. '''

    HOSTS_FILENAME = '/etc/hosts'

    found_line = False
    with open(HOSTS_FILENAME, 'rt') as input_file:
        lines = input_file.readlines()

    new_lines = []
    for line in lines:
        if line.startswith('127.0.0.1'):
            found_line = True
            if SERVER_NAME not in line:
                new_lines.append(f'{line.strip()} {SERVER_NAME}\n')
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if not found_line:
        new_lines.append(f'127.0.0.1 {SERVER_NAME}')

    with open(HOSTS_FILENAME, 'wt') as output_file:
        output_file.write(''.join(new_lines))

def config_logs(project_dir, primary_user):
    ''' Configure the log directory and logging server. '''

    def config_user_log_dir(user_log_dir, user):
        if not os.path.exists(user_log_dir):
            os.mkdir(user_log_dir)

        run('chown', f'{user}:{user}', user_log_dir)
        run('chmod', 'u+rwx,g-rwx,o-rwx', user_log_dir)


    MAIN_LOG_DIR = os.path.join(os.sep, 'var', 'local', 'log')
    if not os.path.exists(MAIN_LOG_DIR):
        os.makedirs(MAIN_LOG_DIR)
    run('chmod', 'u+rwx,g+rx,o+rx', MAIN_LOG_DIR)

    config_user_log_dir(os.path.join(MAIN_LOG_DIR, 'root'), 'root')
    config_user_log_dir(os.path.join(MAIN_LOG_DIR, 'www-data'), 'www-data')

    entries = os.scandir(HOME_DIR)
    for entry in entries:
        if entry.is_dir():
            user = entry.name
            try:
                # configure a subdirectory in the main log dir
                config_user_log_dir(os.path.join(MAIN_LOG_DIR, user), user)
            except CalledProcessError:
                if user == primary_user:
                    raise Exception(f'Unable to configure log directory for {user}')
                else:
                    pass

    primary_user_log_dir = os.path.join(MAIN_LOG_DIR, primary_user)
    if not os.path.exists(primary_user_log_dir):
        config_user_log_dir(primary_user_log_dir, primary_user)

def config_safelog():
    ''' Configure safelog server from denova.com
        if they are not already installed and running.
    '''

    current_dir = os.path.abspath(os.path.dirname(__file__)).replace('\\','/')
    packages_dir = os.path.realpath(os.path.abspath(os.path.join(current_dir, '..', '..')))
    blockchain_backup_dir = os.path.join(packages_dir, 'blockchain_backup')

    # only copy the safelog script, if it doesn't already exist
    safelog_path = os.path.join('/usr', 'sbin', 'safelog')
    if not os.path.exists(safelog_path):
        copyfile(os.path.join(blockchain_backup_dir, 'config', 'safelog'), safelog_path)

    # only copy the safelog service, if it doesn't already exist
    safelog_service_path = os.path.join('/etc', 'systemd', 'system', 'safelog.service')
    if not os.path.exists(safelog_service_path):
        copyfile(os.path.join(blockchain_backup_dir, 'config', 'safelog.service'), safelog_service_path)
        run('systemctl', 'enable', 'safelog')
        run('systemctl', 'start', 'safelog')

def gen_nginx_ssl_cert():
    '''
        Generate SSL certficate for nginx.

        >>> from denova.os.user import whoami
        >>> if whoami() == 'root':
        ...     gen_nginx_ssl_cert() == 'New nginx certificate generated'
        ... else:
        ...     print(True)
        True
    '''

    print(' Generating nginx certificate')

    DIR_NAME = '/etc/nginx/ssl/blockchain-backup'

    # generate a key for blockchain_backup's website
    if not os.path.exists(DIR_NAME):
        os.makedirs(DIR_NAME)

    if os.path.exists(DIR_NAME):
        generate_certificate(SERVER_NAME, DIR_NAME, name=SERVER_NAME)

    return 'New nginx certificate generated'


if __name__ == "__main__":
    main()

    sys.exit(0)
