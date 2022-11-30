'''
    Blockchain Backup views

    Copyright 2019-2021 DeNova
    Last modified: 2021-07-14
'''

from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.template import RequestContext
from django.views.generic import TemplateView

from blockchain_backup.bitcoin import state
from blockchain_backup.bitcoin.backup_utils import get_next_backup_in
from blockchain_backup.bitcoin.core_utils import get_bitcoin_version
from blockchain_backup.version import CURRENT_VERSION
from denova.python.log import Log

log = Log()


class About(TemplateView):
    '''
        Show details about blockchain backup.
    '''

    def get(self, request, *args, **kwargs):
        last_bcb_version = state.get_latest_bcb_version()
        current_core_version = get_bitcoin_version()
        next_backup_in = get_next_backup_in()

        params = {
                  'bcb_version': CURRENT_VERSION,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': last_bcb_version >= CURRENT_VERSION,

                  'core_version': current_core_version,

                  'next_backup_in': next_backup_in,
                 }
        response = render(request, 'about.html', context=params)

        return response

class StaticView(TemplateView):
    ''' Return contents of filepath.

        Usually nginx serves static files, but selenium bypasses nginx.
        This views is used when django gets a request for a staticfile
        such as favicon.ico.
    '''

    def get(self, request, *args, **kwargs):

        if 'filepath' in kwargs:
            filepath = kwargs['filepath']
        else:
            filepath = ''

        with open(filepath, 'rb') as infile:
            contents = infile.read()

        return HttpResponse(contents)


def csrf_failure(request, reason=""):
    ''' Handle CSRF failures so we can show a more reasonable message. '''

    log(f'csrf failure: {reason}')

    if reason != 'CSRF cookie not set.':
        reason = None

    return HttpResponseForbidden(render(request, '403_csrf.html',
                                 context=RequestContext(request, {'reason': reason}).flatten()))


def empty_response(request):
    ''' Respond with nothing useful. '''

    return HttpResponse('')
