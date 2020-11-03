#!/usr/bin/env python3
'''
    Configure links to the local python3 lib
    so setup.py can run which uses libraries
    not accessible from pypi.

    Copyright 2018-2020 DeNova
    Last modified: 2020-10-14
'''

import os
import subprocess
import sys

def main():

    if python_needs_patch():
        patch_python35_lib()

    setup_python3_lib()

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

def setup_python3_lib():
    '''
        Find the local dist-packages and
        add links to the denova package.
    '''

    # find the local dist-packages path
    lib_dir = None
    sys_path = sys.path
    for path in sys_path:
        if 'dist-packages' in path:
            if lib_dir is None:
                lib_dir = path
            elif 'local/lib/python' in path:
                lib_dir = path

    if lib_dir is None:
        lib_dir = '/usr/lib/python3/dist-packages'

    current_dir = os.path.abspath(os.path.dirname(__file__)).replace('\\','/')
    packages_dir = os.path.realpath(os.path.abspath(os.path.join(current_dir, '..', '..')))
    link_lib(lib_dir, os.path.join(packages_dir, 'denova'))
    link_lib(lib_dir, os.path.join(packages_dir, 'denova', 'python', 've.py'))

def link_lib(lib_dir, original_path):
    ''' Link a file/directory to the python3 lib. '''

    if not os.path.exists(os.path.join(lib_dir, os.path.basename(original_path))):
        args = ['ln', '-s', original_path, lib_dir]
        subprocess.run(args, check=True)


if __name__ == "__main__":
    main()
