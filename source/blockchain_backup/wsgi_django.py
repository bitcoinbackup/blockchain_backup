"""
    Entry point for the django loop
"""

import ve
if not ve.in_virtualenv():
    ve.activate(django_app='blockchain_backup')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
