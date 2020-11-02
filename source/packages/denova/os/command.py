#!/usr/bin/env python3
'''
    Run a command using python subprocess.

    Copyright 2018-2020 DeNova
    Last modified: 2020-10-20
'''

import os
import shlex
import subprocess
import sys
from glob import glob

log = None

def run(*command_args, **kwargs):
    ''' Run a command line.

        Much simpler than using python subprocess directly.

        Returns subprocess.CompletedProcess, or raises
        subprocess.CalledProcessError.

        Example::

            >>> result = run('echo word1 word2')
            >>> result.stdout.strip()
            'word1 word2'

        Or if you prefer less chance of parsing errors::
            >>> result = run('echo', 'word1', 'word2')
            >>> result.stdout.strip()
            'word1 word2'

        By default run() captures stdout and stderr. It returns a
        subprocess.CompletedProcess with stdout and stderr, plus a
        combined stderrout as a string.

        You can also send stdout and stderr to the system stdout/stderr,
        to files, and to file objects. Use run_verbose() if you want standard
        stdout/stderr.

        To send stderr to the system's usual output::

            # this isn't a doctest because in a doctest sys.stdout is a
            # doctest._SpoofOut object.

            import sys
            ...
            run('echo', 'stdout', 'text', stdout=sys.stdout)

        To send stderr to a file::

            >>> with open('/tmp/syr.command.stderr', 'w') as stderr:
            ...     result = run('ls', '/tmp', stderr=stderr)

        If you redir stdout or stderr to a file, the .stdout and .stderr
        values in the result returned from run() are None.

        Each command line arg should be a separate run() arg so
        subprocess.check_output can escape args better.

        Unless output_bytes=True, the .stdout, and .stderr
        attributes of CompletedProcess are returned as unicode strings, not
        bytes. For example stdout is returned as stdout.decode().strip(). The
        default is output_bytes=False. This is separate from
        universal_newlines processing, and does not affect stdin.

        Unless glob=False, args are globbed.

        Except for 'output_bytes' and 'glob', keyword args are passed to subprocess.run().

        On error raises subprocess.CalledProcessError.
        The error has an extra data member called 'output' which is a
        string containing stderr and stdout.
    '''

    """ Because we are using PIPEs, we need to use Popen() instead of
        run(), and call Popen.communicate() to avoid zombie processes.
        But to get run()'s timeout, input and check params, we don't.
        Zombie processes are worrisome, but do no real harm.

        See https://stackoverflow.com/questions/2760652/how-to-kill-or-avoid-zombie-processes-with-subprocess-module
    """

    def format_output(result):
        if (result.stdout is not None) and (not isinstance(result.stdout, str)):
            result.stdout = result.stdout.decode()
            result.stdout = result.stdout.strip()
        if (result.stderr is not None) and (not isinstance(result.stderr, str)):
            result.stderr = result.stderr.decode()
            result.stderr = result.stderr.strip()
        return result

    _init_log()
    result = None

    # if there is a single string arg with a space, it's a command line string
    if len(command_args) == 1 and isinstance(command_args[0], str) and ' ' in command_args[0]:
        # run() is better able to add quotes correctly when each arg is separate
        command_args = shlex.split(command_args[0])

        recommended_args = []
        for arg in command_args:
            recommended_args.append(f"'{arg}'")
        log.warning(f"run({', '.join(recommended_args)}) is recommended to avoid command line parsing errors")

        # apparently subprocess.run(..., shell=True) calls shlex.split()
        # kwargs['shell'] = True

    try:
        command_str = ' '.join(map(str, command_args))

        if 'glob' in kwargs:
            globbing = kwargs['glob']
            del kwargs['glob']
        else:
            globbing = True

        # subprocess.run() wants strings
        args = []
        for arg in command_args:
            arg = str(arg)
            if globbing and ('*' in arg or '?' in arg):
                args.extend(glob(arg))
            else:
                args.append(arg)

        if 'output_bytes' in kwargs:
            output_bytes = kwargs['output_bytes']
            del kwargs['output_bytes']
            log(f'output bytes: {output_bytes}')
        else:
            output_bytes = False

        for output in ['stdout', 'stderr']:
            if output not in kwargs:
                kwargs[output] = subprocess.PIPE

        """
        # how to print program's stderr
        # this also handles unicode encoded bytestreams better

        class CompletedProcessStub:
            pass

        proc = subprocess.Popen(proc_args,
                                **kwargs)

        # stderr to the console's stdout
        proc_stderr = ''
        err_data = proc.stderr.readline()
        while err_data:
            line = err_data.decode()
            proc_stderr = proc_stderr + line
            # lines already have a newline
            print(line, end='')
            err_data = proc.stderr.readline()

        # get any stdout from the proc
        proc_stdout, _ = proc.communicate()

        result = CompletedProcessStub()
        result.resultcode = proc.wait()
        result.stdout = proc_stdout
        result.stderr = proc_stderr

        # much simpler code if we don't need realtime feedback
        """
        result = subprocess.run(args,
                                check=True,
                                **kwargs)

    except subprocess.CalledProcessError as cpe:
        log(f'failed command. returncode: {cpe.returncode} / {command_str}')

        # add .stderrout data member
        cpe.stderrout = None
        if cpe.stderr and cpe.stdout:
            log('have cpe.stderr and cpe.stdout') # DEBUG
            cpe.stderrout = (cpe.stderr.decode().strip() +
                          '/n' +
                          cpe.stdout.decode().strip())
        elif cpe.stderr:
            log('have just cpe.stderr') # DEBUG
            cpe.stderrout = cpe.stderr.decode().strip()
        elif cpe.stdout:
            log('have just cpe.stdout') # DEBUG
            cpe.stderrout = cpe.stdout.decode().strip()
        if cpe.stderrout:
            log(cpe.stderrout)

        raise

    except Exception as e:
        log(f'command got Exception: {command_args}')
        log(f'error NOT subprocess.CalledProcessError: {type(e)}')
        log(e)
        raise

    else:
        result = format_output(result)

    return result

def run_verbose(*args, **kwargs):
    ''' Run program with stdout and stderr directed to
        sys.stdout and sys.stderr.
    '''

    result = run(*args, stdout=sys.stdout, stderr=sys.stderr, **kwargs)

    return result

def background(*command_args, **kwargs):
    ''' Run a command line in background.

        If your command file is not executable and starts with '#!',
        background() will use 'shell=True'.

        Passes along all keywords to subprocess.Popen().
        That means you can force the subprocess to run in the foreground
        with e.g. timeout= or check=. But command.run() is a better
        choice for this case.

        Returns a subprocess.Popen object, or raises
        subprocess.CalledProcessError.

        If you redirect stdout/stderr, be sure to catch exceution errors:

            >>> try:
            ...     program = background('python', '-c', 'not python code',
            ...                          stdout=sys.stdout,
            ...                          stderr=sys.stderr)
            ...     wait(program)
            ... except Exception as exc:
            ...     print(exc)
            argument of type 'NoneType' is not iterable

        The caller can simply ignore the return value, poll() for when
        the command finishes, wait() for the command, or communicate()
        with it.

        Do not use Popen.wait(). Use denova.os.command.wait().
    '''

    if not command_args:
        raise ValueError('missing command')

    _init_log()

    # if there is a single string arg with a space, it's a command line string
    if len(command_args) == 1 and isinstance(command_args[0], str) and ' ' in command_args[0]:
        # run() is better able to add quotes correctly when each arg is separate
        command_args = shlex.split(command_args[0])

    command_str = ' '.join(command_args)
    kwargs_str = ''
    for key in kwargs:
        kwargs_str = kwargs_str + f', {key}={kwargs[key]}'

    try:
        process = subprocess.Popen(command_args, **kwargs)

    except OSError as ose:
        log.debug(f'command: {command_str}')
        log.debug(f'OSError as ose: {ose} ({dir(ose)})')
        log.debug(ose)

        if 'Exec format error' in ose.strerror:
            # if the program file starts with '#!' retry with 'shell=True'.
            program_file = command_args[0]
            with open(program_file) as program:
                first_chars = program.read(2)
                if str(first_chars) == '#!':

                    return subprocess.Popen(command_args, shell=True, **kwargs)

                else:
                    log.debug(f'no #! in {program_file}')
                    raise

        else:
            raise

    except Exception as e:
        log.debug(f'command: {command_str}')
        log.debug(e)
        raise

    else:
        log.debug(f"background process started: \"{' '.join(process.args)}\", pid: {process.pid}")
        return process

def wait(program):
    ''' Wait for a background command to finish.'''

    if not isinstance(program, subprocess.Popen):
        raise ValueError('program must be an instance of subprocess.Popen')

    os.waitpid(program.pid, 0)

def _init_log():
    ''' Initialize log. '''

    global log

    if log is None:
        # log import delayed to avoid recursive import.
        from denova.python.log import get_log
        log = get_log()


if __name__ == "__main__":
    import doctest
    doctest.testmod()
