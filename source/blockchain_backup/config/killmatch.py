#!/usr/bin/env python3
'''
    Kill processes that match args, e.g. "killmatch scache".
    The match pattern is a regular expression.

    Copyright 2018-2020 DeNova
    Last modified: 2020-10-20
'''

import argparse
import os
import re
import sys
from threading import Thread

from denova.os.command import run
from denova.os.process import is_program_running #, kill
from denova.python.log import get_log

DEBUG = True

log = get_log()

class KillProcess(Thread):
    ''' Kill a pid.

        Allows multiple pids to be killed at the same time,
        each in a separate process.
    '''

    def __init__(self, killpid):
        # this super() is neccessary in some classes, including this one. why?
        super().__init__()
        self.killpid = killpid
        if DEBUG: log(f'in init kill pid: {self.killpid}') # DEBUG

    def run(self):
        try:
            if DEBUG: log(f'in run kill pid: {self.killpid}') # DEBUG
            #kill(self.killpid)
            run('killsafe', self.killpid)
        except Exception as e:
            # unclear why killsafe returns an error even though it
            # does successfully kill the job, but we'll just
            # ignore the error
            log(e)
            print(e)

def main():
    args = parse_args()

    if args.test:
        import doctest
        doctest.testmod()

    else:
        program = args.pattern
        kill_pattern(program)
        if is_program_running(program):
            log(f'unable to kill {program}')

def kill_pattern(pattern):
    log(f'killing all instances of {pattern}')
    raw = run('psgrep', pattern)
    try:
        # kill earlier pids first to try to prevent respawning
        pids = []
        for line in raw.stdout.strip().split('\n'):
            pid = get_pid(line, pattern)
            if pid:
                pids.append(pid)
        pids = sorted(pids)

        for pid in pids:
            kill_pid(pid)

    except Exception as e:
        log(f'error while trying to kill {pattern}')
        log(e)
        raise

def get_pid(line, pattern):
    pid = None

    if DEBUG: log(f'get_pid(line={line}, pattern={pattern})') # DEBUG
    if re.search(pattern, line) and 'killmatch' not in line:
        # find the pid
        pid_pattern = r'(\d+) .*'
        m = re.match(pid_pattern, line)
        if m:
            pid = m.group(1)
            if DEBUG: log(f'pid is {pid}')
        else:
            log(f'no match for "{pid_pattern}" in "{line}"')

    return pid

def kill_pid(pid):
    if pid == os.getpid():
        log(f'not killing current pid {pid}')
    else:
        log(f'killing pid {pid}')
        process = KillProcess(pid)
        process.start()
        if DEBUG: log(f'process started for pid {pid}') # DEBUG

def parse_args():
    ''' Parsed command line. '''

    parser = argparse.ArgumentParser(description='Find running files.')

    parser.add_argument('pattern',
                        nargs='?',
                        help='Pattern of program name to terminate.')
    parser.add_argument('--test',
                        help='Run tests',
                        action='store_true')
    args = parser.parse_args()

    if len(args.pattern) < 1:
        parser.print_help()
        sys.exit('need at least one pattern')

    if DEBUG: log(f'parsed args: {args}')

    return args


if __name__ == '__main__':
    main()
