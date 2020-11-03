'''
    Blockchain Backup views

    Copyright 2019-2020 DeNova
    Last modified: 2020-09-25
'''

from django.http import HttpResponse
from django.shortcuts import render
from django.views.generic import TemplateView

from blockchain_backup.bitcoin import state
from blockchain_backup.bitcoin.utils import get_bitcoin_version, get_next_backup_in
from blockchain_backup.version import BLOCKCHAIN_BACKUP_VERSION
from denova.python.log import get_log

log = get_log()


class About(TemplateView):
    '''
        Show details about blockchain backup.
    '''

    def get(self, request, *args, **kwargs):
        last_bcb_version = state.get_latest_bcb_version()
        current_core_version = get_bitcoin_version()
        last_core_version = state.get_latest_core_version()
        next_backup_in = get_next_backup_in()

        params = {
                  'bcb_version': BLOCKCHAIN_BACKUP_VERSION,
                  'last_bcb_version': last_bcb_version,
                  'bcb_up_to_date': last_bcb_version >= BLOCKCHAIN_BACKUP_VERSION,

                  'core_version': current_core_version,
                  'last_core_version': last_core_version,
                  'core_up_to_date': last_core_version >= current_core_version,

                  'next_backup_in': next_backup_in,
                 }
        response = render(request, 'about.html', context=params)

        return response

def empty_response(request):
    ''' Respond with nothing useful. '''

    return HttpResponse('')
