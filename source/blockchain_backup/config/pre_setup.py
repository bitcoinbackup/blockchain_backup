#!/usr/bin/env python3
'''
    Install and configure denova package
    and the ve module.

    Copyright 2018-2020 DeNova
    Last modified: 2020-12-03
'''

import os
import subprocess
import sys

def main():

    if python_needs_patch():
        patch_python35_lib()

    install_denova_package()

def install_denova_package():
    ''' Install the denova packages from pypi. '''

    args = ['pip3', 'install', '--upgrade', 'denova']
    subprocess.run(args, check=True)

def python_needs_patch():
    ''' Return true if running python 3.5.3 or earlier. '''

    version = sys.version_info

    return version.major==3 and version.minor==5 and version.micro<=3

def patch_python35_lib():
    '''
        Patch 3.5.3 or earlier to fix a bug in weakref.
    '''

    PYTHON35_LIB_DIR = '/usr/lib/python3.5'

    filename = os.path.join(PYTHON35_LIB_DIR, 'weakref.py')
    if os.path.exists(filename):
        changed_lines = False

        with open(filename, 'rt') as input_file:
            lines = input_file.readlines()

        if len(lines) > 118:
            if 'def remove(wr, selfref=ref(self))' in lines[108]:
                changed_lines = True
                lines[108] = '        def remove(wr, selfref=ref(self), _atomic_removal=_remove_dead_weakref):\n'
            if changed_lines and 'remove_dead_weakref(d, wr.key)' in lines[116]:
                lines[116] = '                    _atomic_removal(d, wr.key)\n'
            else:
                changed_lines = False

        if changed_lines:
            with open(filename, 'wt') as output_file:
                output_file.write(''.join(lines))


if __name__ == "__main__":
    main()
