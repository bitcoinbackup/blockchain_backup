'''
    Multiprocess-safe locks.

    Requires a running lockserver.

    Copyright 2011-2020 DeNova
    Last modified: 2020-10-10

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import os
import socket
import threading
from contextlib import contextmanager
from datetime import timedelta
from functools import wraps
from time import sleep
from traceback import format_exc

from denova.python.log import get_log
from denova.python.times import now
from denova.python.utils import caller_id, object_name

# constants shared with denova.python.log and denova.python.logwriter are
# in denova.python.log so they can be imported easily by tools
LOCK_SERVER_HOST = 'localhost'
LOCK_SERVER_PORT = 8674
BIND_ADDR = (LOCK_SERVER_HOST, LOCK_SERVER_PORT)
MAX_PACKET_SIZE = 1024

ACTION_KEY = 'action'
LOCKNAME_KEY = 'lockname'
NONCE_KEY = 'nonce'
PID_KEY = 'pid'
OK_KEY = 'ok'
MESSAGE_KEY = 'message'
LOCK_ACTION = 'lock'
UNLOCK_ACTION = 'unlock'

REJECTED_LOCK_MESSAGE = 'Lockserver rejected "{}" lock request: {}'
REJECTED_UNLOCK_MESSAGE = 'Lockserver rejected "{}" unlock request: {}'
WHY_UNKNOWN = 'lockserver did not say why'

DEFAULT_TIMEOUT = timedelta.max

# global variables
log = get_log()
# WARNING: BUG. python globals are not multiprocess-safe.
synchronized_locks = {}

class LockTimeout(Exception):
    pass

class LockFailed(Exception):
    pass

@contextmanager
def locked(lockname=None, timeout=None):
    ''' Get a simple reusable lock as a context manager.

        'name' same as lock(). Default is a name created from the
        calling module and line number.

        'timeout' is the maximum time locked() waits for a lock,
        as a  timedelta. Default is one minute.
        If a lock waits longer than 'timeout',
        locked() logs the failure and raises LockTimeout.
        If your locked code block can take longer, you must set
        'timeout' to the longest expected time.

        With locked() you don't have to initialize each lock in an
        an outer scope, as you do with raw multiprocessing.Lock().

        The lock returned by locked() is also a context manager. You
        don't have to explicitly call acquire() or release().

        >>> with locked():
        ...     print('this is a locked code block')
        this is a locked code block

        >>> with locked(timeout=1):
        ...     print('this is a locked code block with a timeout')
        ...     sleep(2)
        this is a locked code block with a timeout
        >>> print('after locked code block with a timeout')
        after locked code block with a timeout

        The python standard multiprocessing. Lock won't let you call
        multiprocessing.Lock.release() if the lock is already unlocked. The
        context manager returned by locked() enforces that restriction
        painlessly by calling release() automatically for you.

        If for some reason you use 'with locked()' with no name twice on the
        same line, it will return the same lock twice. You're extremely
        unlikely to do that accidentally.
    '''

    try:
        # log('enter locked() {}'.format(lockname)) # DEBUG

        if not lockname:
            lockname = caller_id(ignore=[__file__, r'.*/contextlib.py'])
        # log('lockname: {}'.format(lockname)) # DEBUG
        warning_msg = 'lock timed out called from {}'.format(lockname)
        log(warning_msg)

        # log('call lock({})'.format(lockname)) # DEBUG
        is_locked, nonce, pid = lock(lockname, timeout)

    except Exception as exc:
        #from denova.python.utils import stacktrace

        log('Unexpected exception: {}'.format(str(exc)))
        # don't stop if running test_until_exception
        # error_message = stacktrace().replace('Traceback', 'Stacktrace') # but without 'Traceback' # DEBUG
        # log(error_message)
        # DEBUG log(format_exc())
        raise

    else:
        try:
            yield
        finally:
            unlock(lockname, nonce, pid, timeout)

    # log('exit locked() {}'.format(lockname)) # DEBUG

def lock(lockname, timeout=None):
    '''
        Lock a process or thread to prevent concurrency issues.

        'lockname' is the name of the lock.

        Every process or thread that calls "lock()" from the
        same source file and line number contends for the same
        lock. If you want many instances of a class to run at
        the same time, each instance's lockname for a particular
        call to lock() must use a different lockname.
        Example::

            lockname = 'MyClass {}'.format(self.instance_id())
            lock(lockname)

        You may still choose to include the source path and line number
        from denova.python.process.caller() in your lockname.

        If for some reason you use 'with locked()' with no name twice on the
        same line, the second 'with locked()' will fail. They both have the
        same default lockname with the same caller and line number. You're
        extremely unlikely to do that accidentally.

        >>> pid = os.getpid()
        >>> log('pid: {}'.format(pid))

        >>> log('test simple lock()/unlock()')
        >>> from denova.os.process import is_pid_active
        >>> lockname = 'lock1'
        >>> is_locked, nonce, pid = lock(lockname)
        >>> is_locked
        True
        >>> isinstance(nonce, str)
        True
        >>> is_pid_active(pid)
        True
        >>> unlock(lockname, nonce, pid)
        True

        >>> log('test relock')
        >>> lockname = 'lock1'
        >>> is_locked, nonce, __ = lock(lockname)
        >>> is_locked
        True

        >>> log('while locked, try to lock again should fail')
        >>> try:
        ...     lock(lockname, timeout=timedelta(milliseconds=3))
        ... except LockTimeout as lt:
        ...     print(str(lt))
        lock timed out: lock1

        >>> log('now unlock it')
        >>> unlock(lockname, nonce, pid)
        True

        >>> log('try 2 locks')
        >>> lockname1 = 'lock1'
        >>> is_locked1, nonce1, pid1 = lock(lockname1)
        >>> is_locked1
        True
        >>> lockname2 = 'lock2'
        >>> is_locked2, nonce2, pid2 = lock(lockname2)
        >>> is_locked2
        True
        >>> nonce1 != nonce2
        True
        >>> pid1 == pid2
        True
        >>> unlock(lockname1, nonce1, pid1)
        True
        >>> unlock(lockname2, nonce2, pid2)
        True
    '''

    nonce = None
    pid = os.getpid()

    deadline = get_deadline(timeout)
    # log('lock deadline: {}'.format(deadline)) # DEBUG

    # we can probably factor this out into a general case
    loop_count = 0
    is_locked = False
    last_warning = None
    while not is_locked:
        try:
            # only report every 10 secs
            # if (loop_count % 100) == 0:
                # log('call lock({})'.format(lockname)) # DEBUG

            is_locked, nonce = try_to_lock(lockname, pid)

        except TimeoutError as te:
            log(str(te))

        except LockFailed as lf:
            # we need a better way to handle serious errors
            if 'Wrong nonce' in str(lf):
                raise
            else:
                message = lf.args[0]
                if message != last_warning:
                    last_warning = message
                    log(message)

        except:   # 'bare except' because it catches more than "except Exception"
            log(format_exc())
            raise

        if not is_locked:
            if deadline and now() > deadline:
                warning_msg = 'lock timed out: {}'.format(lockname)
                log.warning(warning_msg)
                raise LockTimeout(warning_msg)

            sleep(0.1)

        loop_count = loop_count + 1

    return is_locked, nonce, pid

def try_to_lock(lockname, pid):
    ''' Try once to lock. '''

    is_locked = False
    nonce = None

    # Create a socket (SOCK_STREAM means a TCP socket)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:

        # Connect to server
        # ConnectionRefusedError not caught because app
        # needs to know if lock failed
        sock.connect(BIND_ADDR)

        # send request
        data = {ACTION_KEY: LOCK_ACTION,
                LOCKNAME_KEY: lockname,
                PID_KEY: pid}
        # log('about to send lock request: {}'.format(data))
        sock.sendall(repr(data).encode())
        # log('finished sending lock request')

        # get response
        data = sock.recv(MAX_PACKET_SIZE)
        # log('finished receiving lock data: {}'.format(data))
        response = eval(data.decode())

        is_locked = (response[OK_KEY] and
                     response[ACTION_KEY] == LOCK_ACTION and
                     response[LOCKNAME_KEY] == lockname)

        if is_locked:
            nonce = response[NONCE_KEY]
            # log('locked: {} with {} nonce'.format(lockname, nonce)) # DEBUG
        else:
            # if the server responded with 'No'
            if MESSAGE_KEY in response:
                message = REJECTED_LOCK_MESSAGE.format(lockname, response[MESSAGE_KEY])
            else:
                message = REJECTED_LOCK_MESSAGE.format(lockname, WHY_UNKNOWN)
            #log(message)
            raise LockFailed(message)

    return is_locked, nonce

def unlock(lockname, nonce, pid, timeout=None):
    '''
        >>> log('Unlock a process or thread that was previously locked.')
        >>> lockname = 'lock1'
        >>> __, nonce, pid = lock(lockname)
        >>> unlock(lockname, nonce, pid)
        True

        >>> log('A bad nonce should fail.')
        >>> lockname = 'lock1'
        >>> __, nonce, pid = lock(lockname)
        >>> try:
        ...    unlock(lockname, 'bad nonce', pid)
        ...    assert False, 'Unexpectedly passed bad nonce'
        ... except LockFailed:
        ...     pass
        >>> unlock(lockname, nonce, pid)
        True
    '''

    deadline = get_deadline(timeout)
    # log('unlock deadline: {}'.format(deadline)) # DEBUG

    # we must be persistent in case the lockserver is busy
    is_locked = True
    last_warning = None
    while is_locked:
        try:
            is_locked = try_to_unlock(lockname, nonce, pid)

        except TimeoutError as te:
            log(str(te))

        except LockFailed as lf:
            # we need a better way to handle serious errors
            if 'Wrong nonce' in str(lf):
                raise
            else:
                message = lf.args[0]
                if message != last_warning:
                    last_warning = message
                    log(message)

        except:   # 'bare except' because it catches more than "except Exception"
            log(format_exc())
            raise

        if is_locked:
            if deadline and now() > deadline:
                warning_msg = 'unlock timed out: {}'.format(lockname)
                log.warning(warning_msg)
                raise LockTimeout(warning_msg)

            sleep(0.1)

    # log('unlocked: {}'.format(lockname)) # DEBUG

    # only returned for testing purposes
    return not is_locked

def try_to_unlock(lockname, nonce, pid):
    ''' Try once to unlock. '''

    is_locked = True

    # Create a socket (SOCK_STREAM means a TCP socket)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:

        # Connect to server
        # ConnectionRefusedError not caught because app
        # needs to know if lock failed
        sock.connect(BIND_ADDR)

        # send request
        data = {ACTION_KEY: UNLOCK_ACTION,
                LOCKNAME_KEY: lockname,
                NONCE_KEY: nonce,
                PID_KEY: pid}
        # log('about to send unlock request: {}'.format(data))
        sock.sendall(repr(data).encode())
        # log('finished sending unlock request')

        # get response
        data = sock.recv(MAX_PACKET_SIZE)
        # log('finished receiving unlock data: {}'.format(data))

        response = eval(data.decode())
        if response[OK_KEY] and response[ACTION_KEY] == UNLOCK_ACTION and response[NONCE_KEY] == nonce:

            is_locked = False

        else:
            # if the server responded with 'No'
            if MESSAGE_KEY in response:
                message = REJECTED_UNLOCK_MESSAGE.format(lockname, response[MESSAGE_KEY])
            else:
                message = REJECTED_UNLOCK_MESSAGE.format(lockname, WHY_UNKNOWN)
            #log(message)
            raise LockFailed(message)

    return is_locked

def synchronized(function):
    ''' Decorator to lock a function so each call completes before
        another call starts.

        If you use both the staticmethod and synchronized decorators,
        @staticmethod must come before @synchronized.
    '''

    @wraps(function)
    def synchronizer(*args, **kwargs):
        ''' Lock function access so only one call at a time is active.'''

        # get a shared lock for the function
        with locked():
            lock_name = object_name(function)
            if lock_name in synchronized_locks:
                synch_lock = synchronized_locks[lock_name]
            else:
                synch_lock = threading.Lock()
                synchronized_locks[lock_name] = synch_lock

        with locked():
            result = function(*args, **kwargs)

        return result

    return synchronizer

def get_deadline(timeout=None):
    '''
        Return a datetime deadline from timeout.

        'timeout' can be seconds or a timedelta. Default is timedelta.max.

        >>> from datetime import datetime
        >>> deadline = get_deadline()
        >>> deadline is None
        True

        >>> deadline = get_deadline(timedelta(seconds=1))
        >>> type(deadline) is datetime
        True

        >>> deadline = get_deadline(1)
        >>> type(deadline) is datetime
        True

        >>> deadline = get_deadline(1.1)
        >>> type(deadline) is datetime
        True

        >>> deadline('bad timeout value')
        Traceback (most recent call last):
        ...
        TypeError: 'datetime.datetime' object is not callable
    '''

    if timeout is None:
        deadline = None
    elif isinstance(timeout, timedelta):
        deadline = now() + timeout
    elif isinstance(timeout, (float, int)):
        deadline = now() + timedelta(seconds=timeout)
    else:
        raise ValueError('timeout must be one of (seconds, timedelta, None), not {}'.format(type(timeout)))

    # log('deadline: {}'.format(deadline))
    return deadline


if __name__ == "__main__":

    import doctest
    doctest.testmod()
