"""
    Entry point for the socketio loop
"""

import os

from ve import venv

os.environ.update(DJANGO_SETTINGS_MODULE='blockchain_backup.settings')
CURRENT_DIR = os.path.abspath(os.path.dirname(__file__)).replace('\\','/')
with venv(CURRENT_DIR):

    from ws4redis.uwsgi_runserver import uWSGIWebsocketServer

    application = uWSGIWebsocketServer()
