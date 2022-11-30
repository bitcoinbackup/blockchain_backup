'''
    Tests the views for blockchain_backup.

    Copyright 2018-2021 DeNova
    Last modified: 2021-05-02
'''

from ve import activate, virtualenv_dir
activate(django_app='blockchain_backup')
from django import setup
setup()

import os
from datetime import datetime, timedelta
from time import sleep
from django.http.response import Http404
from django.utils.timezone import now, utc
from django.test import Client, RequestFactory, TestCase

from blockchain_backup import views
from blockchain_backup.bitcoin.tests import utils
from denova.python.log import Log

log = Log()

class ViewsTestCase(TestCase):

    def test_about(self):
        '''
            Show the About page.
        '''

        factory = RequestFactory()
        request = factory.get('/about')
        response = views.About.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'<title>\nAbout Blockchain Backup | Blockchain Backup\n</title>' in response.content)
        self.assertTrue(b'Current version' in response.content)
        self.assertTrue(b'<strong>Copyright:</strong>' in response.content)
        self.assertTrue(b'Next backup in' in response.content)
        self.assertTrue(b'Bitcoin Core version' in response.content)

    def test_csrf_failure(self):
        '''
            Test csrf failure returns a 403.
        '''

        client = Client(enforce_csrf_checks=True)
        response = client.post('/error_report/')
        self.assertEqual(response.status_code, 403)

    def test_empty_response(self):
        '''
            Show the getting an empty response.
        '''

        factory = RequestFactory()
        request = factory.get('/about')
        response = views.empty_response(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'' in response.content)
