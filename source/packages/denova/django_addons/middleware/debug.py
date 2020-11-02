'''
    Log Django debug pages.

    Copyright 2010-2020 DeNova
    Last modified: 2020-10-22

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import os
from tempfile import NamedTemporaryFile

try:
    from django.utils.deprecation import MiddlewareMixin
except ModuleNotFoundError:
    import sys
    sys.exit('Django required')

from denova.django_addons.utils import is_django_error_page
from denova.python.log import get_log

log = get_log()


class DebugMiddleware(MiddlewareMixin):
    ''' Write to debugging log.

        Logs Django debug pages and says it's an error. '''

    def process_response(self, request, response):

        def logit(why):
            log(why)
            log(f'response: {response!r}')
            log(f'request: {request!r}')

        try:
            if is_django_error_page(response.content):
                with NamedTemporaryFile(
                    prefix='django.debug.page.', suffix='.html',
                    delete=False) as htmlfile:
                    htmlfile.write(response.content)
                os.chmod(htmlfile.name, 0o644)
                log(f'django app error: django debug page at {htmlfile.name}')
            elif response.status_code >= 400:
                logit(f'http error {response.status_code:d}')
        except AttributeError as ae:
            log(f'ignored in denova.django_addons.middleware.DebugMiddleware.process_response(): {ae}')

        return response
