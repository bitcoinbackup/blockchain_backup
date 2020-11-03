"""
    Entry point for the django loop
"""
import os

from ve import venv

os.environ.update(DJANGO_SETTINGS_MODULE='blockchain_backup.settings')
CURRENT_DIR = os.path.abspath(os.path.dirname(__file__)).replace('\\','/')
with venv(CURRENT_DIR):
    from django.core.wsgi import get_wsgi_application

    application = get_wsgi_application()
