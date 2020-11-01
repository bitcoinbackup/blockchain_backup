#!/usr/bin/env python3
'''
    If you get errors while running, see the wiki for help.

    Copyright 2018-2020 DeNova
    Last modified: 2020-10-20
'''

import os
import sys
import ve

DJANGO_APP = 'blockchain_backup'

# we want to be able to run this program from inside or outside the virtualenv
if not ve.in_virtualenv():
    ve.activate(django_app=DJANGO_APP)


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"{DJANGO_APP}.settings")

    import django
    from django.core.management import execute_from_command_line

    django.setup()
    execute_from_command_line(sys.argv)
