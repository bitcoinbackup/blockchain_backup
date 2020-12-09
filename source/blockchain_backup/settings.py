'''
    Django settings for blockchain_backup project.

    Copyright 2018-2020 DeNova
    Last modified: 2020-12-04
'''

import os.path

# django requires a secret key be present in the settings
# during installation and configuration, each user gets their own key
from blockchain_backup.special_settings import SECRET_KEY

# we're just importing constants that we want integrated into django's settings
from denova.django_addons.settings_shared import *

DEBUG = True

PROJECT_PATH = os.path.realpath(os.path.abspath(os.path.dirname(__file__).replace('\\','/')))
# the data dir is in different places for development and final installation
# when creating the final version, the DATA_DIR and DEBUG are set correctly
DATA_DIR = os.path.abspath(os.path.join(PROJECT_PATH, '..', 'data'))
# linux home dir
HOME_DIR = '/home'

TOP_LEVEL_DOMAIN = 'blockchain_backup'

# ROOT_URLCONF must be defined before we can use any other blockchain_backup classes
ROOT_URLCONF = f'{TOP_LEVEL_DOMAIN}.urls'

# URL for home page of website without trailing slash
LOCAL_HOST = f"{TOP_LEVEL_DOMAIN.replace('_', '-')}.local"
CONTENT_HOME_URL = f'http://{LOCAL_HOST}'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', LOCAL_HOST]
if DEBUG:
    ALLOWED_HOSTS.append('testserver')

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/
STATIC_URL = '/static/'
# Absolute path to the directory where django's staticfiles app will collect static files.
STATIC_ROOT = os.path.join(PROJECT_PATH, 'static')
# APP/static files are collected automatically by manage.py
# other dirs with static files
STATICFILES_DIRS = (
    DJANGO_ADDONS_STATIC_DIR,
    os.path.join(PROJECT_PATH, ' ../../../'),
)

SITE_ID = 1

# database
DATABASE_NAME = 'sqlite3.db'
DATABASE_DIR = os.path.join(DATA_DIR, 'db')
DATABASE_PATH = os.path.join(DATABASE_DIR, DATABASE_NAME)
DEFAULT_DATABASE = {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': DATABASE_PATH,
    'OPTIONS': {
        'timeout': 20,
    }
}
DATABASES = {
    'default': DEFAULT_DATABASE,
}

# rebuild the assets if assets change; costly on production system
ASSETS_AUTO_BUILD = DEBUG

PRIMARY_TEMPLATE_DIR = os.path.join(PROJECT_PATH, 'templates')
TEMPLATE_DIRS = (

    # order is important; the first matching template is used

    PROJECT_PATH,
    PRIMARY_TEMPLATE_DIR,
    DJANGO_ADDONS_TEMPLATE_DIR,
)
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': TEMPLATE_DIRS,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': TEMPLATE_CONTEXT_PROCESSORS,
            'debug': DEBUG,
        },
    },
]


# Application definition
INSTALLED_APPS = INSTALLED_APPS + (
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',

    'denova.django_addons',

    'blockchain_backup',
    'blockchain_backup.bitcoin',
)

MIDDLEWARE_CLASSES = MIDDLEWARE

# Password validation
# https://docs.djangoproject.com/en/2.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

CONNECTION_HEARTBEAT = '--heartbeat--'

USE_SOCKETIO = False

if USE_SOCKETIO:
    SOCKETIO_URL_PREFIX = 'ws'
    SOCKETIO_URL = f'/{SOCKETIO_URL_PREFIX}/'

DJANGO_PORT = 8962
SOCKETIO_PORT = 8963
