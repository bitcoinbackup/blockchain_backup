import os
import sys
from ve import venv

with venv():

    sys.path.insert(0, os.path.abspath('..'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blockchain_backup.settings')

    from django.core.wsgi import get_wsgi_application

    _django_app = get_wsgi_application()
    #_socketio_app = uWSGISocketIOServer()


    def application(environ, start_response):
        #if environ.get('PATH_INFO').startswith(settings.SOCKETIO_URL):
        #    return _socketio_app(environ, start_response)
        return _django_app(environ, start_response)
