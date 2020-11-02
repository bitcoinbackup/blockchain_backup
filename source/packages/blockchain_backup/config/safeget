#! /usr/bin/env python3
'''
    Safeget downloads and verifies files from online.

    If you would like a simple custom safeget for your app
    which embeds all the parameters usually passed on the
    command line, contact support@denova.com. It's free.
    Your users then run that simple small program to download
    and fully verify your app, without the hassles.

    Learn more at https://denova.com/open_source/safeget/

    This is intentionally a single file to make it easier
    to verify safeget itself.

    Copyright 2019-2020 DeNova
    Last modified: 2020-11-01
'''

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import tempfile
from glob import glob
from http.cookiejar import CookieJar
from traceback import format_exc
from urllib.parse import urlencode, urlparse
from urllib.request import build_opener, urlopen, HTTPCookieProcessor, ProxyHandler, Request

TMP_DIR = tempfile.mkdtemp(prefix='safeget.')
DEFAULT_TRIES = 20 # from wget default
# use standard text streams for stdin, stdout and stderr
STD_TEXT_STREAMS = True
ALL_TESTS = False

args = None

wget_path = 'wget'
gpg_path = 'gpg'

target_host = None
localpath_hash_cache = {}

testing = False
failed = False

class SafegetException(Exception):
    pass

def main():
    ''' Get dependencies. Get file. Verify file.
        Optionally, install file or run command with file.
    '''

    try:
        if '--test' in sys.argv:
            test()

        else:
            parse_args()
            verify_args()

            if 'app' in args:
                notice(f'Safegetting {args.app}\n')

            if 'noselfcheck' in args and not args.noselfcheck:
                notice('Checking... ')
                verify_safeget_itself()

            if not (installed('wget') and installed('gpg')): # and installed('openssl')
                install_dependencies()

            if is_url(args.target):

                url = args.target
                local_target = os.path.basename(url)
                notice('Downloading... ')
                download(url, local_target)

            else:
                local_target = args.target
                if not os.path.exists(local_target):
                    fail(f'file does not exist: {os.path.abspath(local_target)}')

            verify_file(local_target)

            if args.run:
                notice('Running... ')
                run(args.target, interactive=True)
                print('Finished.')

            if args.after:
                run_command_after(args.after)

            more()

    except SafegetException as sgex:
        if args.debug or testing:
            # show the traceback, or allow test to catch the error
            raise
        else:
            print(sgex)
            more()
            sys.exit(1)

    except KeyboardInterrupt:
        print('stopped by user')
        if args.debug:
            # show the traceback
            # in case the Ctrl-C was to see where the program was stuck
            raise
        else:
            sys.exit(2)

def more():
    ''' Let them know where to get more safeget commands. '''

    if not testing:
        print('\n')
        print('Find more safegets at https://denova.com/open_source/safeget/custom/')

def notice(msg):
    ''' Print short notice message without newline. '''

    print(msg, end='', flush=True)

def verbose(msg):
    ''' Print verbose message. '''

    # args.debug implies args.verbose
    if args.verbose or args.debug:
        print(msg)

def debug(msg):
    ''' Print debug message. '''

    if args is None or args.debug:
        print(msg)

def fail(msg):
    ''' Failure exit. '''

    raise SafegetException(f'Failed: {msg}')

def warn(msg):
    ''' Warn user. '''

    print()
    print(f'Warning: {msg}')

def which(program):
    ''' Return path to command. '''

    WHICH_PATH = '/usr/bin/which'

    # if no 'which', check for command existence with:
    #     run(program, '--help')
    # maybe we need 'which' for windows
    path = run(WHICH_PATH, program)
    if not isinstance(path, str):
        path = path.decode()
    path = path.strip()
    return path

def run(*command_args, **kwargs):
    ''' Run a command line.

        Example::

            # 'ls /tmp'
            run('ls', '/tmp')

        Return command stdout and stderr.

        command_args is an iterable of args instead of a string so
        subprocess.check_output can escape args better.
    '''

    debug(f"run \"{' '.join(command_args)}\"")
    result = None

    # if there is a single arg, it can't be a command line string with args
    if len(command_args) == 1:
        program = command_args[0]
        if ' ' in program:
            # the program's path won't contain a space, so it's a command line
            # run() is better able to add quotes correctly when each arg is separate
            debug(f'DEPRECATED: run({repr(command_args)}) as shell command')
            kwargs['shell'] = True

    try:
        if 'glob' in kwargs:
            globbing = kwargs['glob']
            del kwargs['glob']
        else:
            globbing = True

        interactive = 'interactive' in kwargs
        if interactive:
            del kwargs['interactive']
            kwargs.update(dict(stdin=sys.stdin,
                               stdout=sys.stdout,
                               stderr=sys.stderr))

        # subprocess.run() wants strings
        proc_args = []
        for arg in command_args:
            arg = str(arg)
            if ('*' in arg or '?' in arg) and globbing:
                proc_args.extend(glob(arg))
            else:
                proc_args.append(arg)

        for output in ['stdout', 'stderr']:
            if output not in kwargs:
                kwargs[output] = subprocess.PIPE
        kwargs['universal_newlines'] = STD_TEXT_STREAMS

        proc = subprocess.Popen(proc_args,
                                **kwargs)

        if args.debug:
            # stderr to the console's stdout
            stderr_data = ''
            line = proc.stderr.readline()
            while line:
                stderr_data = stderr_data + line
                # lines already have a newline
                print(line, end='')
                line = proc.stderr.readline()

            # get any stdout from the proc
            stdout_data, _ = proc.communicate()

        else:
            stdout_data, stderr_data = proc.communicate()

        returncode = proc.wait()

        if returncode == 0:
            result = stdout_data

        else:
            raise subprocess.CalledProcessError(returncode, command_args, stdout_data, stderr_data)

    except subprocess.CalledProcessError as cpe:
        debug(cpe)
        if cpe.returncode: debug(f'    returncode: {cpe.returncode}')
        if cpe.stderr: debug('    stderr: {}' + cpe.stderr)
        if cpe.stdout: debug('    stdout: {}' + cpe.stdout)
        raise

    return result

def run_command_after(command):
    ''' Run the command after downloading and verifying file. '''

    MULTIPLE_COMMANDS = ' && '

    notice('Installing... \n')
    while command.find(MULTIPLE_COMMANDS) > 0:
        i = command.find(MULTIPLE_COMMANDS)
        command_args = shlex.split(command[:i])
        run(*command_args)

        command = command[i + len(MULTIPLE_COMMANDS):]

    command_args = shlex.split(command)
    run(*command_args, interactive=True)

    print('Installed.')

def install_dependencies():
    ''' Install dependencies.

        Call this as soon as we know we need wget or gpg.
    '''

    notice('Installing dependencies... ')
    install_wget()
    # we may not need openssl, and it is already installed on osx and linux
    # install_openssl()
    install_gpg()

def install_wget():

    global wget_path

    # wget redirects, retries, and reports errors better than curl.
    # See http://sync-help.bittorrent.com/customer/portal/articles/1666471-checking-connectivity-with-wget
    wget_path = install('wget',
                        windows_url = 'https://eternallybored.org/misc/wget/wget.exe',
                        osx_url = 'http://www.merenbach.com/software/wget')

def install_openssl():

    # openssl checks domains, connections and hashes
    # Binaries - OpenSSLWiki
    #     https://wiki.openssl.org/index.php/Binaries
    open_ssl_path = install('openssl',
                            # we might be able to use the 3MB version: https://slproweb.com/download/Win32OpenSSL_Light-1_1_0g.exe
                            windows_url = 'https://slproweb.com/download/Win32OpenSSL-1_1_0g.exe',
                            is_installer=True)
    debug(f'openssl path: {open_ssl_path}')

def install_gpg():

    global gpg_path

    # gpg is already installed in debian
    gpg_path = install('gpg',
                       # see https://www.gpg4win.org/download.html
                       windows_url='http://files.gpg4win.org/gpg4win-2.3.0.exe',
                       # see https://gpgtools.org/
                       osx_url='https://releases.gpgtools.org/GPG_Suite-2015.09.dmg',
                       is_installer=True)
    debug(f'gpg path: {gpg_path}')

def install(program, windows_url=None, osx_url=None, linux_package=None, is_installer=False):
    ''' If program is not installed, try to install it.

        If is_installer=True, run the file from the url to complete the installation.
        This is not the same as --run, since if we are installing dependencies,
        then this program and not the user decides to run the file.
    '''

    def require_root():
        if not os.geteuid() == 0:
            fail(f'install {program}, or rerun this program as root, so it can install dependencies')

    def already_installed():
        verbose(f'{program} already installed')

    def install_done(program, program_path):
        debug(f'installed {program} to {program_path}')

    def windows_install(program, windows_url):
        url = windows_url
        verify_source(url)
        if not url:
            fail(f'no install url for {program}')

        verbose(f'install {program}')

        tempdir = tempfile.gettempdir()
        basename = os.path.basename(url)
        program_path = os.path.join(tempdir, basename)

        try:
            download(program_path, url, wget=basename.find('wget') >= 0)

        except Exception as e:
            debug(e)
            # !! could be other reasons
            fail(f'rerun this program as admin to install {program}')

        else:
            if is_installer:
                run(program_path)

        return program_path

    def osx_install(program, osx_url):
        if installed(program):
            already_installed()

        else:
            require_root()

            url = osx_url
            verify_source(url)
            if not url:
                fail(f'no install url for {program}')

            require_root()
            verbose(f'{program} not found. installing...')
            program_path = os.path.join('/usr/local/bin', program)
            download(program_path, url, wget=False)
            program = program_path

            if is_installer:
                run(program_path)

            install_done(program, program_path)

        return program

    def linux_install(program, linux_package):
        if installed(program):
            already_installed()

        else:
            require_root()

            if linux_package is None:
                linux_package = program
            verbose(f'install linux package {linux_package}')
            # !! this assumes debian or derivative; what about redhat?
            run('apt-get', 'install', linux_package)
            install_done(program, linux_package)

        return program

    debug(f'install {program}')

    system = platform.system()

    if system == 'Windows':
        program_path = windows_install(program, windows_url)

    elif system == 'Darwin':
        program_path = osx_install(program, osx_url)

    elif system == 'Linux':
        program_path = linux_install(program, linux_package)

    else:
        fail(f'unable to install on {system}')

    return program_path

def installed(program):
    ''' Return True if program installed, else return False.'''

    try:
        which(program)

    except Exception:
        is_installed = False

    else:
        is_installed = True

    return is_installed

def download(url, localpath, wget=True):
    ''' Download file using wget to localpath.

        wget can resume an interrupted download, and retry.
    '''

    verbose(f'download {url} to {os.path.abspath(localpath)}')

    if wget:

        if ok_to_write(localpath):

            # start with the basic parameters
            wget_args = [wget_path,
                         '--tries',
                         str(args.tries),
                         '--output-document',
                         localpath]

            if platform.system() == 'Windows':
                if args.hash or args.sig:
                    # if you verify the file hash or pgp signature, then
                    # "--no-check-certificate" is ok in this rare case,
                    # and Windows needs it
                    wget_args.append('--no-check-certificate')
                else:
                    fail('windows requires a hash or signature')

            # add the proxy commands if appropriate
            if args.proxy:
                wget_args.append('-e')
                wget_args.append('use_proxy=yes')
                wget_args.append('e')
                if args.proxy.startswith('https'):
                    wget_args.append(f'https_proxy={args.proxy}')
                else:
                    wget_args.append(f'http_proxy={args.proxy}')

            # finally add the url to get
            wget_args.append(url)

            # wget is sometimes so slow it looks like a lockup
            run(*wget_args)

    # else no wget available, so use python lib
    else:
        if ok_to_write(localpath):
            with open(localpath, 'wb') as localfile:
                localfile.write(download_data(url))

def download_data(url):
    ''' Get data from url. No wget, so no retrying, etc.

        The amount of data is limited by memory.
        It is better to use wget if you can.
    '''

    verify_source(url)
    # urlopen() returns a bytes object because it can't determine the encoding
    stream = urlopen(url)
    data = stream.read()
    stream.close()

    return data

def parse_args():
    '''
        Return parsed args.

        Do NOT change the "def parse_args():" line above
        without also changing customize.py in the safeget tools dir.
    '''

    global args

    parser = argparse.ArgumentParser(description='Get and verify a file.')

    parser.add_argument('target', help='url of file to download, or file path')

    parser.add_argument('--size', help='file size in bytes') # not an int to allow commas
    parser.add_argument('--hash', nargs='*',
                        help='file hash in form ALGO:HASH, ALGO:URL, or ALGO:FILE. ' +
                        'ALGO is a hash algorithm such as SHA256. HASH is hex literal. ' +
                        'If URL or FILE, the correct hash must appear in the url or file contents')
    parser.add_argument('--pubkey', nargs='*',
                        help='url or file of pgp signing key')
    parser.add_argument('--sig', nargs='*',
                        help='url or file containing pgp detached signature')
    parser.add_argument('--signedmsg', nargs='*',
                        help='url or file containing pgp signed message')
    parser.add_argument('--signedhash', nargs='*',
                        help='url or file of pgp signed message containing file hashes in form "SHA256:URL_OR_FILE..."')
    parser.add_argument('--after',  nargs='*',help='execute command after downloading and verifying the file')
    parser.add_argument('--run', help='runs the verified file', action='store_true')

    parser.add_argument('--proxy', help='must be in the format: https://IP:PORT or http://IP:PORT', nargs='?', dest='proxy', action='store')
    parser.add_argument('--tries', help='times to retry', type=int, default=DEFAULT_TRIES)
    parser.add_argument('--verbose', help='show more details', action='store_true')
    parser.add_argument('--debug', help='show debug details', action='store_true')
    parser.add_argument('--onehost', help='skip warning when sources are not separtate hosts', action='store_true')
    parser.add_argument('--test', help='test this command', action='store_true')

    args = parser.parse_args()
    debug(f'args from argsparse: {vars(args)}')

    return args

def verify_file(local_target):
    ''' Verify local file.

        Network files must be downloaded first.
    '''

    notice('Verifying... ')
    verbose(f'verify target file {os.path.abspath(local_target)}')

    if args.signedmsg or args.signedhash or args.sig:
        get_pubkeys()

    # in decreasing order of strength
    verify_signatures(local_target)
    verify_signed_hashes(local_target)
    verify_explicit_hashes(local_target)
    verify_size(local_target)

    if args.after or args.run:
        notice(f'Verified {os.path.basename(local_target)}... ')
    else:
        print(f'Verified {os.path.basename(local_target)}')

def verify_args():
    ''' Verify args. '''

    if not (args.sig or
            args.signedhash or
            args.hash):
        fail('File signature, signed hash, or explicit hash required')

    if args.size and not (args.sig or
                          args.signedhash or
                          args.hash):
        fail('File size alone is not enough verification. File signature, signed hash, or explicit hash required.')

    if args.sig and not args.pubkey:
        fail('Detached signature found, but required PGP public key not found.')

    if args.signedhash and not args.pubkey:
        fail('Signed hash found, but required PGP public key not found.')

    if args.pubkey and not(args.sig or
                           args.signedmsg or
                           args.signedhash):
        fail('PGP public key found. Did you want to include a file signature, or signed message, or signed hash?')

    verify_source(args.target)

def verify_source(source):
    ''' Verify file source.

        Urls must use a secure protocol on a host different than the target file host.

        Local files are considered a trusted source.
    '''

    global target_host

    SAFE_PROTOCOLS = ['https', 'sftp']

    if is_url(source):
        parts = urlparse(source)
        if parts.scheme not in SAFE_PROTOCOLS:
            fail('url does not use a safe protocol ({}): {}'.
                 format(' or '.join(SAFE_PROTOCOLS), source))

        host = parse_host(source)

        if target_host is None:
            # verify_source() assumes first source to verify is target
            if source != args.target:
                fail('safeget error: target source must be verified first')
            target_host = host

        if not args.onehost:
            if source != args.target and target_host == host:
                # this was a fail(), but too many people use one host
                if args.debug:
                    print(f'target: {args.target}')
                warn(f'url is same host as target: {source}. Use --onehost to skip this warning.')
                # fail('url is same host as target: {}'.format(source))

def verify_safeget_itself():
    '''
        Verify safeget itself by checking the online
        database for original file size and hashes.
    '''

    '''
        Of course verifying a file using data from the file's host
        exposes a single point of failure. If an attacker cracks
        the host, they control both the file and the verification data.
        But this check has proven very valuable anyway.

        First, safeget makes it easy to do multiple checks automatically.
        Not all are strong. But additional checks increase safety, and they
        are cheap.

        Second, there are many errors and attacks that can cause a file
        mismatch, but do not require a web host crack. For example, some
        browsers cache downloaded files. If a file changes during the
        browser session, the browser reuses the old version. This function
        catches those cases.
    '''

    ok, error_message = check_safeget_itself()
    if not ok:
        fail_message = 'Unable to verify safeget.'
        if error_message is not None:
            fail_message = f'\n{error_message}'
        fail(fail_message)

def check_safeget_itself(host=None, target=None):
    '''
        Check safeget itself by checking the online
        database for original file size and hashes.

        The parameters are only passed for testing.
    '''

    def hashes_match(original, local, algo):
        ok = original == local
        if not ok:
            debug(f'The {algo} hash does not match the original: {original}')
            debug(f'                                      local: {local}')
        return ok

    def safeget_ok(result):

        ok = False
        error_message = None

        full_path = os.path.realpath(os.path.abspath(__file__))
        filename = os.path.basename(full_path)

        original_safeget_bytes = result['quick-query']['message']['safeget-bytes']
        if isinstance(original_safeget_bytes, str):
            original_safeget_bytes = int(original_safeget_bytes.replace(',', ''))
        local_safeget_bytes = os.path.getsize(full_path)
        ok = original_safeget_bytes == local_safeget_bytes
        if ok:
            with open(full_path, 'rb') as input_file:
                lines = input_file.read()

            original_safeget_sha512 = result['quick-query']['message']['safeget-sha512']
            local_safeget_sha512 = hashlib.sha512(lines).hexdigest()
            ok = hashes_match(original_safeget_sha512, local_safeget_sha512, 'SHA512')
            if ok:
                original_safeget_sha256 = result['quick-query']['message']['safeget-sha256']
                local_safeget_sha256 = hashlib.sha256(lines).hexdigest()
                ok = hashes_match(original_safeget_sha256, local_safeget_sha256, 'SHA256')

            # if neither hash is ok, then warn the user
            if not ok:
                error_message = f'The hash of {filename} does not match the original.\n'
        else:
            debug(f'safeget does not match: original: {original_safeget_bytes} local: {local_safeget_bytes}')
            error_message = f'Your local copy of {filename} does not match the original.'

        if error_message is not None:
            error_message += ' IMPORTANT: You should download safeget again.'

        return ok, error_message

    HOST = 'https://denova.com'
    API_URL = 'open_source/safeget/api/'

    ok = True
    error_message = None

    if host is None:
        host = HOST

    if target is None:
        target = args.target

    full_api_url = os.path.join(host, API_URL)
    page = None
    if args and args.proxy:
        i = args.proxy.find('://')
        if i > 0:
            algo = args.proxy[:i]
            ip_port = args.proxy[i+len('://'):]
            proxy = {algo: ip_port}
        else:
            fail('--proxy must be in the format: https://IP:PORT or http://IP:PORT')

        proxy_handler = ProxyHandler(proxy)
        opener = build_opener(proxy_handler, HTTPCookieProcessor(CookieJar()))
    else:
        opener = build_opener(HTTPCookieProcessor(CookieJar()))

    HEADERS = {'User-Agent': 'DeNova Safeget 1.0'}
    PARAMS = {'action': 'quick-query', 'api_version': '1.1', 'target': target}
    encoded_params = urlencode(PARAMS).encode()

    request = Request(full_api_url, encoded_params, HEADERS)

    handle = opener.open(request)
    page = handle.read().decode().strip()

    # strip out the html
    i = page.find('{')
    if i >= 0:
        page = page[i:]
    i = page.rfind('}')
    if i >= 0:
        page = page[:i+1]

    result = json.loads(page)
    if isinstance(result, bytes):
        result = result.decode()
    if 'quick-query' in result:
        if result['quick-query']['ok']:
            ok, error_message = safeget_ok(result)

        elif 'message' in result['quick-query']:
            ok = False
            error_message = result['quick-query']['message']
    else:
        ok = False
        error_message = f'Unable to verify safeget: {result}'

    if not ok:
        debug(error_message)

    return ok, error_message

def verify_size(localpath):
    ''' Verify file size. '''

    if args.size:
        verbose('verify file size')

        args_size = args.size
        try:
            if isinstance(args_size, str):
                args_size = int(args_size.replace(',', ''))
        except ValueError:
            raise ValueError('size must be an integer')
        else:
            if os.path.getsize(localpath) == args_size:
                debug('verified file size')
            else:
                fail(f'file size is not {args_size}')

def verify_signed_hashes(localpath):
    ''' Verify signed file hashes match localpath.
    '''

    def check_signed_hash_file(localpath,
                               signed_hash_file,
                               algo):

        matched = False
        if clean_gpg_data(signed_hash_file):
            url_content = readfile(signed_hash_file)
            try:
                matched = search_for_hash(localpath, signed_hash_file, algo, url_content)
            except Exception as e:
                debug(e)
                debug(format_exc())

        return matched

    algos_available = hash_algorithms()

    if args.signedhash:
        verbose('verify target file matches signed hashes')

        matched = False
        for signed_hash_arg in args.signedhash:
            algo, source = parse_hash(signed_hash_arg)

            if algo not in algos_available:
                fail(f"{algo} not in available hash algorithms: {' '.join(algos_available)}")

            # verify hashes are in a pgp signed message

            signed_data_files = verify_signed_messages(source)
            debug(f'{len(signed_data_files)} signed data files')

            # just one has to match
            # hashes for other algorithms, file versions will not match
            for signed_hash_file in signed_data_files:
                if not matched:
                    matched = check_signed_hash_file(localpath,
                                                     signed_hash_file,
                                                     algo)

        if not matched:
            fail(f'no matching signed hash found in {args.signedhash}')

def verify_explicit_hashes(localpath):
    ''' Verify explicit file hashes match localpath.
    '''

    algos_available = hash_algorithms()

    if args.hash:
        verbose('verify data file matches explicit hashes')

        # every explicit hash on the command line must match
        for hash_arg in args.hash:
            algo, hash_or_url = parse_hash(hash_arg)

            if algo not in algos_available:
                fail(f"{algo} not in available hash algorithms: {' '.join(algos_available)}")

            matched = False
            if is_url(hash_or_url):
                url = hash_or_url
                verify_source(url)
                hashpath = temppath()
                download(url, hashpath)
                debug(f'hash url {url} saved in {hashpath}')
                url_content = readfile(hashpath)
                matched = search_for_hash(localpath, hashpath, algo, url_content)

            else:
                expected_hash = hash_or_url
                debug(f'command line arg algo: {algo}, expected_hash: {expected_hash}')
                if algo and expected_hash:
                    actual_hash = hash_data(algo, localpath)
                    matched = compare_hashes(algo, expected_hash, actual_hash)

            if not matched:
                fail(f'{os.path.abspath(localpath)} expected hash did not match actual hash {algo}:{actual_hash}')

def hash_algorithms():
    ''' Return available hash algorithms.

        Make the algos all lower case.

        hashlib's docs do not match its behavior.

        From hashlib.algorithms_available::
            set(['blake2s256', 'BLAKE2s256', 'SHA224', 'SHA1',
                 'SHA384', 'blake2b512', 'MD5-SHA1', 'SHA256',
                 'SHA512', 'MD4', 'md5', 'sha1', 'sha224',
                 'ripemd160', 'MD5', 'BLAKE2b512', 'md4',
                 'sha384', 'md5-sha1', 'sha256', 'sha512',
                 'RIPEMD160', 'whirlpool'])

        This appears to be a representation bug. The
        expression will result in a set of the list elements.
    '''

    """ We can also use openssl:
            # for type in sha sha1 mdc2 ripemd160 sha224 sha256 sha384 sha512 md2 md4 md5 dss1
            for type in sha1 sha256 sha512 md5
            do
                openssl dgst -$type "$@"
            done
    """

    algos = set()
    for algo in hashlib.algorithms_available:
        algos.add(algo.lower())
    debug(f'hashlib.algorithms_available: {algos}')

    return algos

def hash_data(algo, localpath):
    ''' Hash file with algo.

        Uses cache.

        Returns hex of the file's hash as a bytestring.
    '''

    BUFFER_SIZE = 100000

    source = f'{algo}:{localpath}'
    if source not in localpath_hash_cache:

        h = hashlib.new(algo)
        # read directly from file instead of preloaded bytes so we can
        # hash large data without running out of memory
        # open binary because we hash byte by byte
        with open(localpath, 'rb') as datafile:
            data = datafile.read(BUFFER_SIZE)
            while data:
                h.update(data)
                data = datafile.read(BUFFER_SIZE)

        localpath_hash_cache[source] = h.hexdigest().lower()

    return localpath_hash_cache[source]

def hash_failed(algo, expected_hash, actual_hash):
    debug("only one hash has to match; this one didn't")
    debug(f'    expected {algo} hash: {expected_hash}')
    debug(f'    actual {algo} hash: {actual_hash}')

def search_for_hash(localpath, signed_hash_file, algo, url_content):
    debug(f'search_for_hash {algo}:{signed_hash_file}')

    actual_hash = hash_data(algo, localpath)
    ok = actual_hash in url_content
    if ok:
        debug(f'verfied {algo} hash from url')

    else:
        hash_failed(algo, f'not found in {signed_hash_file}', actual_hash)

    return ok

def compare_hashes(algo, expected_hash, actual_hash):
    debug(f'compare_hashes {algo}:{expected_hash}')

    ok = (expected_hash == actual_hash)
    if ok:
        debug(f'verfied explicit {algo} hash')
    else:
        hash_failed(algo, expected_hash, actual_hash)
    return ok

def get_pubkeys():
    ''' Download and import public keys.

        Because keys servers are slow and unreliable, we don't use them.
    '''

    if args.pubkey:
        verbose('get pubkeys')

        PUBKEY_PATTERN = r'\-+\s*BEGIN PGP PUBLIC KEY BLOCK\s*\-+.*?\-+\s*END PGP PUBLIC KEY BLOCK\s*\-+\s*'
        pubkey_paths, online_pubkeys = save_patterns(PUBKEY_PATTERN, args.pubkey)
        for keypath in pubkey_paths:
            debug(f'pubkey path: {keypath}')
            if clean_gpg_data(keypath):
                run(gpg_path, '--import', keypath)
            debug(f'imported pgp public key from: {keypath}')

        if not args.debug:
            for path in online_pubkeys:
                os.remove(path)

def verify_signed_messages(source):
    ''' Get and verify gpg signed messages.

        A pgp signed message begins with "BEGIN PGP SIGNED MESSAGE"
        and ends with "END PGP SIGNATURE". It contains both the signed
        content and the signature.
    '''

    verbose(f'verify signed message at {source}')

    # get pgp signed messages before pgp file signatures because
    # ideally the sigs are signed
    # we want to know if the sigs are good before we use them
    SIGNED_MESSAGE_PATTERN = r'\-+\s*BEGIN PGP SIGNED MESSAGE\s*\-+.*?\-+\s*END PGP SIGNATURE\s*\-+\s*'
    # save_patterns() wants an iterable, so '[source]'
    signedmsg_paths, online_signed_msgs = save_patterns(SIGNED_MESSAGE_PATTERN, [source])

    verified_signedmsg_paths = []
    for signedmsg_path in signedmsg_paths:
        if clean_gpg_data(signedmsg_path):
            # read as a stream so we can handle big files
            with open(signedmsg_path, 'r') as infile:
                try:
                    run(gpg_path, '--verify', stdin=infile)
                    verified_signedmsg_paths.append(signedmsg_path)
                except Exception as ex:
                    debug(f'could not verify signed message saved in {signedmsg_path}')
                    debug(ex)
                else:
                    verbose(f'verified pgp signed message: {signedmsg_path}')

    if not args.debug:
        for path in online_signed_msgs:
            os.remove(path)

    return verified_signedmsg_paths

def verify_signatures(local_target):
    ''' Get and verify gpg detached signatures for a file.

        A pgp detached signature begins with "BEGIN PGP SIGNATURE"
        and ends with "END PGP SIGNATURE". It just contains the
        signature. The signed data is in a separate file.
    '''

    if args.sig:
        verbose('verify pgp detached signature')

        # get pgp detached signatures for a file
        SIG_PATTERN = r'\-+\s*BEGIN PGP SIGNATURE\s*\-+.*?\-+\s*END PGP SIGNATURE\s*\-+\s*'
        sig_paths, online_sigs = save_patterns(SIG_PATTERN, args.sig)
        for sigpath in sig_paths:
            if clean_gpg_data(sigpath):
                try:
                    run(gpg_path, '--verify', sigpath, local_target)
                except Exception as ex:
                    debug(f'could not verify pgp detached signature saved in {sigpath}')
                    debug(ex)
                else:
                    verbose(f'verified pgp detached signature: {args.sig}')

        if not args.debug:
            for path in online_sigs:
                os.remove(path)

def parse_hash(text):
    ''' Text must be:
            hash algorithm
            ':'
            hash or url
    '''
    algo, _, hash_or_url = text.partition(':')
    algo = algo.lower()
    hash_or_url = hash_or_url.lower()
    # if a url with no algo was specified, the second component would start with //
    if (not algo) or (not hash_or_url) or (hash_or_url.startswith('//')):
        fail(f'in hash expected "ALGORITHM:..." e.g. "SHA512:D6E8..." or "SHA256:https://...", got {text}')

    # strip embedded spaces in a hash
    hash_or_url = re.sub(' ', '', hash_or_url)

    return algo, hash_or_url

def extract_patterns(pattern, localpath):
    ''' Extract all instances of text matching pattern from file '''

    paths = []
    content = readfile(localpath)

    debug(f'extracting {pattern} from {localpath}')

    for text in re.findall(pattern, content, flags=re.DOTALL):
        path = temppath()
        with open(path, 'w') as keysfile:
            keysfile.write(text)
        paths.append(path)

    return paths

def save_patterns(pattern, sources):
    ''' Save text matching patterns found in sources.

        'sources' is an iterable. Each item is either a filepath or url.
        save_patterns() reads the item, then searches the contents for the pattern.

        save_patterns() saves pattern matches to temporary files.

        Returns a list of the temporary file paths.
    '''

    online_paths = []
    paths = []

    for source in sources:
        if is_url(source):
            url = source
            verify_source(url)
            path = temppath()
            download(url, path)
            debug(f'url {url} saved in {path}')
            online_paths.append(path)

        else:
            path = source
            if not os.path.exists(path):
                fail(f'file not found: {path}')

        pattern_paths = extract_patterns(pattern, path)
        if not pattern_paths:
            fail(f'no "{pattern}" patterns found: {path}')
        paths.extend(pattern_paths)

    return paths, online_paths

def clean_gpg_data(path):
    ''' Check and clean gpg data file.

        Returns True if data seems ok. Else returns False.

        There are many pubkey and sig pages what looks like a PGP
        formatted data block, with empty content. Example:

            -----BEGIN PGP SIGNED MESSAGE-----
            ...
            -----END PGP SIGNATURE-----

        We extract these examples along with valid pgp data.
        Rightfully gpg throws an error, and we want to ignore the bad data and therefore the error.
    '''

    # very quick check for valid data
    ok = os.path.getsize(path) > 100
    if ok:
        ''' Some of the sigs, such as from r/bitcoin, have leading spaces.
            Some files have '\\n' instead of '\n'
            etc.

            We need to find out why.
        '''

        text = readfile(path)

        text = text.replace('^/s*', '')
        text = text.replace('\\n', '\n')
        text = text.replace('\\r', '')
        text = text.replace('<p>', '\n')
        text = text.replace('</p>', '\n')
        text = text.replace('<br>', '\n')
        text = text.replace('<br/>', '\n')

        assert '\\n' not in text
        with open(path, 'w') as outfile:
            outfile.write(text)

    else:
        debug(f'gpg data file too short: {path}')

    return ok

def temppath():
    ''' return new temporary file path. '''

    _, path = tempfile.mkstemp(dir=TMP_DIR)
    return path

def download_tempfile(url):
    ''' Download data from url into temp file.

        Returns temp file path. '''

    debug(f'download {url} to temp file')
    data = download_data(url)
    path = temppath()
    debug(f'save url data to {path}')
    with open(path, 'wb') as datafile:
        datafile.write(data)
    return path

def ok_to_write(path):
    ''' If path exists and has content, ask to overwrite it.

        If no permission, fail.
    '''

    if os.path.exists(path) and os.path.getsize(path) and not testing:
        verbose(f'{os.path.abspath(path)} already exists')
        prompt = f'\nOk to replace {os.path.abspath(path)}? '
        answer = input(prompt)
        answer = answer.lower()
        debug(f'answered: {answer}')
        ok = answer in ['y', 'yes']
        if not ok:
            fail(f'did not replace {os.path.abspath(path)}')
    else:
        ok = True

    return ok

def readfile(localpath):
    ''' Return contents of localpath as text file. '''

    with open(localpath, 'r') as datafile:
        data = datafile.read()
    return data

def persist(func, *args, **kwargs):
    ''' Retry func until success or KeyboardInterrupt. Report errors.

        This kind of stubborness often defeats DOS attacks.
        Reporting attempted censorship sometimes seems to help.
    '''

    done = False
    retries = 0
    while not done:
        try:
            result = func(*args, **kwargs)

        except Exception as e:
            report(e)
            print(f'{e}; Retrying')
            retries = retries + 1

        else:
            if retries:
                debug(f'Succeeded after {retries} retries')
            done = True

    return result

def report(msg):
    ''' Report if censorship detected. '''

    print(msg)

def is_url(s):
    ''' Returns True if url, else returns False. '''

    return '://' in s

def parse_host(url):
    ''' Returns host of url. '''

    parts = urlparse(url)
    if ':' in parts.netloc:
        host, _ = parts.netloc.split(':')
    else:
        host = parts.netloc

    return host

def test():
    ''' Use bitcoin core as a test case. ISOs take too long to download.

        A fake safeget could lie. So users need to check this safeget
        executable file using other means. For example, pgp signed distro
        package, or pgp sig of hash file from trusted site.
    '''

    """
        https://www.reddit.com/r/Bitcoin/wiki/verifying_bitcoin_core

        Bitcoin Foundation publishes:
            * their pgp public keys
            * signed pgp messages containing hashes of a release
    """

    global testing, failed

    def test_failure(description, *test_args):
        # this test should fail

        global failed

        notice(f'Test {description}\n\t')

        try:
            # use test command line args
            sys.argv = [command_name] + list(test_args) + extra_args
            main()

        except SafegetException as sgex:
            debug(sgex)
            print('Passed: Test of failure condition failed as expected')

        except Exception:
            print('Error in test')
            raise

        else:
            failed = True
            print('Failed: Test of failure condition incorrectly succeeded')

    def test_success(description, *test_args):
        ''' This test should succeed. '''

        global failed

        notice(f'Test {description}\n\t')

        try:
            # use test command line args
            sys.argv = [command_name] + list(test_args) + extra_args
            main()

        except SafegetException as sgex:
            failed = True
            print(sgex)

        except Exception:
            print('Error in test')
            raise

        else:
            print('\tPassed')

    BITCOIN_VERSION = '0.20.1'
    # file to verify
    # url created below
    FILENAME = f'bitcoin-{BITCOIN_VERSION}-x86_64-linux-gnu.tar.gz'

    # bitcoin-core public key
    BITCOIN_PUBKEY_URL = 'https://bitcoincore.org/keys/laanwj-releases.asc'

    # url/file with pgp pubkeys
    LOCAL_PUBKEY = 'laanwj-releases.asc'
    # url/file to verify
    LOCAL_TARGET = FILENAME
    # url/file with signed pgp messages containing hashes
    LOCAL_SIGNED_HASHES_SOURCE = 'verifying_bitcoin_core'
    LOCAL_SIGNED_HASH = 'SHA256:' + LOCAL_SIGNED_HASHES_SOURCE

    # url/file with pgp pubkeys
    ONLINE_PUBKEY = 'https://www.reddit.com/r/Bitcoin/wiki/pgp_keys'
    # url/file with signed pgp messages containing hashes
    ONLINE_SIGNED_HASHES_SOURCE = 'https://www.reddit.com/r/Bitcoin/wiki/verifying_bitcoin_core'
    ONLINE_SIGNED_HASH = 'SHA256:' + ONLINE_SIGNED_HASHES_SOURCE
    # url/file to verify
    ONLINE_TEMPLATE = 'https://bitcoin.org/bin/bitcoin-core-{version}/{filename}'
    ONLINE_TARGET = ONLINE_TEMPLATE.format(version=BITCOIN_VERSION, filename=FILENAME)

    # explicit hashes
    # hash can be a hex string or url, with an algo prefix
    HASH1 = 'SHA256:53ffca45809127c9ba33ce0080558634101ec49de5224b2998c489b6d0fc2b17'
    HASH2 = 'SHA512:be3fceec15ea09f7c7d38e13b5cde69388bd095c052180797db387e8409184ce4bb3daf42693b5cfdf7f3abb486fa6a80bcf2de5b75766abb28099125a7ace2a'

    testing = True
    failed = False

    extra_args = []
    debug_test = '--debug' in sys.argv
    verbose_test = '--verbose' in sys.argv
    if debug_test:
        extra_args.append('--debug')
        print('Test safeget')
    elif verbose_test:
        extra_args.append('--verbose')

    command_name = sys.argv[0]

    # test in a temp dir
    if not os.path.isdir(TMP_DIR):
        os.mkdir(TMP_DIR)
    os.chdir(TMP_DIR)
    if debug_test or verbose_test:
        print(f'test dir is {TMP_DIR}')

    # if local copies of test files are already in TMP_DIR, use them
    if os.path.exists(LOCAL_TARGET) and os.path.exists(LOCAL_PUBKEY) and os.path.exists(LOCAL_SIGNED_HASHES_SOURCE):

        test_success('local target',

                     LOCAL_TARGET,

                     '--pubkey',
                     LOCAL_PUBKEY,

                     '--signedhash',
                     LOCAL_SIGNED_HASH)

    # else test online
    else:

        test_success('online target',

                     ONLINE_TARGET,

                     '--pubkey',
                     ONLINE_PUBKEY,

                     '--signedhash',
                     ONLINE_SIGNED_HASH)

    if ALL_TESTS:

        test_success('explicit hashes',

                     # earlier tests should have made LOCAL_TARGET available
                     LOCAL_TARGET,

                     '--hash',
                     HASH1,
                     HASH2)

        # make sure safeget fails when it should
        # we need lots of test_failure() tests

        test_failure('not enough args',

                     ONLINE_SIGNED_HASH,

                     '--pubkey',
                     ONLINE_PUBKEY)

        test_failure('target missing',

                     'expected_to_fail_' + ONLINE_TARGET,

                     '--hash',
                     HASH1,
                     HASH2,

                     '--pubkey',
                     ONLINE_PUBKEY,

                     '--signedhash',
                     ONLINE_SIGNED_HASH)

        test_failure('wrong hash',

                     LOCAL_TARGET,

                     '--hash',
                     'expected_to_fail_' + HASH1,
                     HASH2,

                     '--pubkey',
                     ONLINE_PUBKEY,

                     '--signedhash',
                     ONLINE_SIGNED_HASH)

        test_failure('wrong pubkey',

                     LOCAL_TARGET,

                     '--hash',
                     HASH1,
                     HASH2,

                     '--pubkey',
                     'expected_to_fail_' + ONLINE_PUBKEY,

                     '--signedhash',
                     ONLINE_SIGNED_HASH)

        test_failure('wrong signed hash',

                     LOCAL_TARGET,

                     '--hash',
                     HASH1,
                     HASH2,

                     '--pubkey',
                     ONLINE_PUBKEY,

                     '--signedhash',
                     'expected_to_fail_' + LOCAL_SIGNED_HASHES_SOURCE)

    print('')

    if failed:
        print('Failed')
        sys.exit(1)

    elif ALL_TESTS:
        print('Passed all tests')


if __name__ == "__main__":
    main()
