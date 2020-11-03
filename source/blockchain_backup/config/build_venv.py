#!/usr/bin/env python3
'''
    Build the virtualenv for blockchain_backup.

    Copyright 2018-2020 DeNova
    Last modified: 2020-10-06
'''

import argparse
import os
import sys

from denova.os.command import run
from denova.python.build_venv import BuildVenv

class BlockchainBackupBuildVenv(BuildVenv):
    ''' Build the virtualenv for blockchain_backup website.'''

    def __init__(self, dev_system):

        super(BlockchainBackupBuildVenv, self).__init__()

        self.dev_system = dev_system

        self.current_dir = os.path.abspath(os.path.dirname(__file__).replace('\\','/'))

        if self.dev_system:
            self.projects_dir = self.PROJECTS_DIR
            self.parent_dir = os.path.join(self.PROJECTS_DIR, 'blockchain_backup')
        else:
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

        print('   linking packages')

        virtual_bin_dir = os.path.join(self.virtualenv_dir(), 'bin')

        run('ln', '-s', os.path.join(self.projects_dir, 'denova'), site_packages_dir)
        run('ln', '-s', os.path.join(self.projects_dir, 'denova/python/ve.py'), site_packages_dir)

        if self.dev_system:
            blockchain_backup_dir = os.path.join(self.parent_dir, 'src')
            run('ln', '-s', blockchain_backup_dir, os.path.join(site_packages_dir, 'blockchain_backup'))
            run('ln', '-s', os.path.join(self.projects_dir, 'denova/django_addons', 'thirdparty', 'django_singleton_admin'), site_packages_dir)
            # add link to apps
            run('ln', '-s', os.path.join(blockchain_backup_dir, 'config', 'safecopy'), virtual_bin_dir)
            run('ln', '-s', os.path.join(self.projects_dir, 'tools', 'killmatch'), virtual_bin_dir)
            run('ln', '-s', os.path.join(self.projects_dir, 'tools', 'killsafe'), virtual_bin_dir)
        else:
            blockchain_backup_dir = os.path.join(self.projects_dir, 'blockchain_backup')
            run('ln', '-s', os.path.join(blockchain_backup_dir, 'config', 'safecopy'), virtual_bin_dir)
            run('ln', '-s', os.path.join(blockchain_backup_dir), site_packages_dir)
            run('ln', '-s', os.path.join(self.projects_dir, 'django_singleton_admin'), site_packages_dir)
            # add link to apps
            run('ln', '-s', os.path.join(blockchain_backup_dir, 'config', 'killmatch.py'), os.path.join(virtual_bin_dir, 'killmatch'))

        # create links to safecopy so we can distinguish between a restore and a backup
        run('ln', '-s', os.path.join(virtual_bin_dir, 'safecopy'), os.path.join(virtual_bin_dir, 'bcb-backup'))
        run('ln', '-s', os.path.join(virtual_bin_dir, 'safecopy'), os.path.join(virtual_bin_dir, 'bcb-restore'))

        # link debian packages
        run('ln', '-s', '/usr/lib/python3/dist-packages/socks.py', site_packages_dir)
        run('ln', '-s', '/usr/lib/python3/dist-packages/websockets', site_packages_dir)


    def finish_build(self):
        ''' Finish build with finally links.'''

        virtual_bin_dir = os.path.join(self.virtualenv_dir(), 'bin')
        if not os.path.exists(os.path.join(virtual_bin_dir, 'uwsgi')):
            run('ln', '-s', '/usr/bin/uwsgi', virtual_bin_dir)

def parse_args():
    ''' Parsed command line. '''

    global args

    parser = argparse.ArgumentParser(description='Create the virtualenv for blockchain-backup.')

    parser.add_argument('--dev',
                        help="Only run on developer's system",
                        action='store_true')

    args = parser.parse_args()

    return args

def main(args):
    print(' Building the virtual environment')
    bcbv = BlockchainBackupBuildVenv(args.dev)
    bcbv.build()
    print(' Finished building the virtual environment')


if __name__ == "__main__":
    main(parse_args())

    sys.exit(0)
