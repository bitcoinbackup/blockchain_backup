#!/usr/bin/env python3
'''
    Build the virtualenv for blockchain_backup.

    Copyright 2018-2020 DeNova
    Last modified: 2020-12-07
'''

import argparse
import os
import shutil
import sys

from denova.os.command import run
from denova.python.build_venv import BuildVenv

class BlockchainBackupBuildVenv(BuildVenv):
    ''' Build the virtualenv for blockchain_backup website.'''

    def __init__(self):

        super(BlockchainBackupBuildVenv, self).__init__()

        self.current_dir = os.path.abspath(os.path.dirname(__file__).replace('\\','/'))
        self.projects_dir = os.path.realpath(os.path.abspath(os.path.join(self.current_dir, '..', '..')))
        self.parent_dir = os.path.dirname(self.projects_dir)

    def parent_dirname(self):
        ''' Directory where virtualenv will be created. '''

        return self.parent_dir

    def virtualenv_dir(self):
        ''' Returns the virtualenv directory. '''

        return os.path.join(self.parent_dir, self.virtual_subdir())

    def virtual_subdir(self):

        return self.VIRTUAL_SUBDIR

    def get_requirements(self):
        ''' Return the list of virtualenv requirements. '''

        return os.path.join(self.current_dir, 'virtualenv.requirements')

    def link_packages(self, site_packages_dir):
        ''' Link packages to the site-packages directory. '''

        def make_exec_and_link(virtual_bin_dir, path, to_path=None):
            ''' Make the path executable and link to virtualenv bin. '''

            run('chmod', '+x', path)
            if to_path:
                run('ln', '-s', path, os.path.join(virtual_bin_dir, to_path))
            else:
                run('ln', '-s', path, virtual_bin_dir)

        print('   linking packages')

        virtual_bin_dir = os.path.join(self.virtualenv_dir(), 'bin')

        # add links to packages and modules used by blockchain backup
        blockchain_backup_pkg = os.path.join(self.projects_dir, 'blockchain_backup')
        run('ln', '-s', os.path.join(blockchain_backup_pkg), site_packages_dir)

        # add a link to the ve module
        ve_module = os.path.join(site_packages_dir, 'denova', 'python', 've.py')
        run('ln', '-s', ve_module, site_packages_dir)

        # add link to apps used by blockchain backup
        make_exec_and_link(virtual_bin_dir, os.path.join(blockchain_backup_pkg, 'config', 'killmatch.py'), to_path='killmatch')
        make_exec_and_link(virtual_bin_dir, os.path.join(blockchain_backup_pkg, 'config', 'killsafe'))

        # create links to safecopy so we can distinguish between a restore and a backup
        safecopy_path = os.path.join(virtual_bin_dir, 'safecopy')
        run('ln', '-s', safecopy_path, os.path.join(virtual_bin_dir, 'bcb-backup'))
        run('ln', '-s', safecopy_path, os.path.join(virtual_bin_dir, 'bcb-restore'))

        # link debian packages
        run('ln', '-s', '/usr/lib/python3/dist-packages/socks.py', site_packages_dir)
        run('ln', '-s', '/usr/lib/python3/dist-packages/websockets', site_packages_dir)


    def finish_build(self):
        ''' Finish build with finally links.'''

        virtual_bin_dir = os.path.join(self.virtualenv_dir(), 'bin')
        if not os.path.exists(os.path.join(virtual_bin_dir, 'uwsgi')):
            run('ln', '-s', '/usr/bin/uwsgi', virtual_bin_dir)

def main():
    print(' Building the virtual environment')
    bcbv = BlockchainBackupBuildVenv()
    bcbv.build()
    print(' Finished building the virtual environment')


if __name__ == "__main__":
    main()

    sys.exit(0)
