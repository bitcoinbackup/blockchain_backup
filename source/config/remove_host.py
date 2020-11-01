#!/usr/bin/env python3
'''
    Remove blockchain-backup.local from /etc/hosts.

    Copyright 2018-2020 DeNova
    Last modified: 2020-10-20
'''

import sys

def main():
    '''
        On Linux systems, remove
        blockchain-backup.local from /etc/hosts.
    '''

    SERVER_NAME = 'blockchain-backup.local'
    HOSTS_FILENAME = '/etc/hosts'

    if os.path.exists(HOSTS_FILENAME):
        with open(HOSTS_FILENAME, 'rt') as input_file:
            lines = input_file.readlines()

        new_lines = []
        for line in lines:
            if SERVER_NAME in line:
                i = line.find(SERVER_NAME)
                new_line = line[:i]
                if line[i+len(SERVER_NAME)] == ' ':
                    i += 1
                if len(line) > i+len(SERVER_NAME):
                    new_line += line[i+len(SERVER_NAME):]
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        with open(HOSTS_FILENAME, 'wt') as output_file:
            output_file.write(''.join(new_lines))


if __name__ == "__main__":
    main()

    sys.exit(0)
