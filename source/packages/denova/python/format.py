'''
    Text formating.

    Because this module uses some modules that use this one,
    imports that are not from standard libs should not be
    at global scope. Put the import where it's used.

    Copyright 2008-2020 DeNova
    Last modified: 2020-10-20

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import json
import locale
import os
import pprint
import re
from traceback import format_exc

UNICODE_DECODINGS = ['utf-8',
                     'iso-8859-14',
                     locale.getpreferredencoding(False)]
DETAILED_LOG = '/tmp/denova.python.format.detailed.log'

# delayed import of log so denova.python.log can use this module
_log = None


def log(message):
    global _log
    if not _log:
        from denova.python.log import get_log
        _log = get_log()
    _log(message)


# delayed open of detailed log so other users can use this module
_detailed_log = None


def detailed_log(message):
    global _detailed_log
    if not _detailed_log:
        _detailed_log = open(DETAILED_LOG, 'w')
        # user frequently changes, so loosen access
        os.chmod(DETAILED_LOG, 0o660)
    _detailed_log.write(message)
    _detailed_log.flush()

def pretty(obj, indent=4, base_indent=0):
    ''' Prettyprint 'pprint' replacement.

        Places every dictionary item on a separate line in key order.
        Formats nested dictionaries.

        For long lists, places every item on a separate line.

        'indent' is the increment for each indentation level, and defaults to 4.
        'base_indent' is the current indentation, and defaults to 0.

    >>> import datetime
        >>> data = {
        ...     'a': 1,
        ...     'c': 2,
        ...     'b': 'hi',
        ...     'x': {1: 'a', 2: 'b'},
        ...     'e': datetime.timedelta(days=9, seconds=11045),
        ...     'd': 'ho',
        ...     'g': datetime.datetime(2000, 1, 2, 3, 4, 5, 6),
        ...     'f': datetime.date(2000, 1, 2),
        ...     'h': datetime.time(1, 2, 3, 4),
        ...     }
        >>> data['l'] = [data['a'], data['b'], data['c'], data['d'], data['e'], data['f'], data['g'], data['h'], data['x']]
        >>> p = pretty(
        ...     data,
        ...     indent=4
        ...     )
        >>> print(p)
        {
            'a': 1,
            'b': 'hi',
            'c': 2,
            'd': 'ho',
            'e': datetime.timedelta(days=9, seconds=11045),
            'f': datetime.date(2000, 1, 2),
            'g': datetime.datetime(2000, 1, 2, 3, 4, 5, 6),
            'h': datetime.time(1, 2, 3, 4),
            'l': [
                1,
                'hi',
                2,
                'ho',
                datetime.timedelta(days=9, seconds=11045),
                datetime.date(2000, 1, 2),
                datetime.datetime(2000, 1, 2, 3, 4, 5, 6),
                datetime.time(1, 2, 3, 4),
                {
                    1: 'a',
                    2: 'b',
                },
            ],
            'x': {
                1: 'a',
                2: 'b',
            },
        }

        >>> p1 = eval(p)
        >>> print(pretty(p1, indent=4))
        {
            'a': 1,
            'b': 'hi',
            'c': 2,
            'd': 'ho',
            'e': datetime.timedelta(days=9, seconds=11045),
            'f': datetime.date(2000, 1, 2),
            'g': datetime.datetime(2000, 1, 2, 3, 4, 5, 6),
            'h': datetime.time(1, 2, 3, 4),
            'l': [
                1,
                'hi',
                2,
                'ho',
                datetime.timedelta(days=9, seconds=11045),
                datetime.date(2000, 1, 2),
                datetime.datetime(2000, 1, 2, 3, 4, 5, 6),
                datetime.time(1, 2, 3, 4),
                {
                    1: 'a',
                    2: 'b',
                },
            ],
            'x': {
                1: 'a',
                2: 'b',
            },
        }
    '''

    max_list_width = 60

    if isinstance(obj, dict):
        p = '{\n'
        base_indent += indent
        try:
            keys = sorted(obj.keys())
        except:   # 'bare except' because it catches more than "except Exception"
            keys = obj.keys()
        for key in keys:
            p += (' ' * base_indent) + repr(key) + ': '
            value = obj[key]
            p += pretty(value, indent=indent, base_indent=base_indent)
            p += ',\n'
        base_indent -= indent
        p += (' ' * base_indent) + '}'

    elif isinstance(obj, list):
        p = '[\n'
        base_indent += indent
        for item in obj:
            p += (' ' * base_indent) + pretty(item, indent=indent, base_indent=base_indent)
            p += ',\n'
        base_indent -= indent
        p += (' ' * base_indent) + ']'
        # put short lists on one line
        if len(p) < max_list_width:
            p = p.replace('\n ', ' ')
            p = p.replace('  ', ' ')

    else:
        pp = pprint.PrettyPrinter(indent=indent)
        try:
            p = pp.pformat(obj)
        except:   # 'bare except' because it catches more than "except Exception"
            try:
                log(f'unable to pretty print object: {obj}')
                p = repr(obj)
                log('object len: %d' % len('{}'.format(p)))
            except:   # 'bare except' because it catches more than "except Exception"
                log(format_exc())
                from denova.python.utils import last_exception_only
                p = f'denova.python.format.pretty ERROR:{last_exception_only()}'

    return p

def add_commas(number):
    ''' Add commas to a number,

        >>> print(add_commas(0))
        0
        >>> print(add_commas(1))
        1
        >>> print(add_commas(1234))
        1,234
        >>> print(add_commas(1234567))
        1,234,567
        >>> print(add_commas(0.0))
        0.0
        >>> print(add_commas(0.1234))
        0.1234
        >>> print(add_commas(1.1234))
        1.1234
        >>> print(add_commas(1234.1234))
        1,234.1234
        >>> print(add_commas(1234567.1234))
        1,234,567.1234
    '''

    if '.' in str(number):
        (integer, decimal) = str(number).split('.')
    else:
        integer = str(number)
        decimal = ''

    formattedNumber = ''
    while len(integer) > 3:
        formattedNumber = "," + integer[-3:] + formattedNumber
        integer = integer[:-3]
    formattedNumber = integer + formattedNumber

    if decimal:
        formattedNumber += '.' + decimal

    return formattedNumber

def s_if_plural(number):
    ''' Return an empty string if the number is one, else return the letter \'s\'.
        This is used to form standard plural nouns.

        >>> print('house' + s_if_plural(0))
        houses
        >>> print('house' + s_if_plural(1))
        house
        >>> print('house' + s_if_plural(2))
        houses

    '''

    if number == 1:
        result = ''
    else:
        result = 's'
    return result

def replace_angle_brackets(s):
    ''' Replace '<' with '&lt;' and '>' with '&gt;'.

        This allows html to display correctly when embedded in html. '''

    s = s.replace('<', '&lt;')
    s = s.replace('>', '&gt;')
    return s

def camel_back(s):
    ''' Combine words into a string with no spaces and every word capitalized.
        Already capitalized letters after the first letter are preserved.

        >>> camel_back('wikipedia article name')
        'WikipediaArticleName'
        >>> camel_back('WikiPedia CamelBack')
        'WikiPediaCamelBack'

        '''

    words = s.split(' ');
    camel_back_words = []
    for word in words:
        # the word may itself be camel back, or at least have some capitalized letters
        camel_back_words.append(word[:1].capitalize() + word[1:])
    return ''.join(camel_back_words)

def pretty_html(html, parser=None):
    ''' Prettyprint html.

        Requires BeautifulSoup, python3-tidylib, or python3-utidylib.

        'parser' specifies the parser used by BeautifulSoup. 'html5lib'
        is the most lenient and the default. 'lxml' is the fastest.

        >>> html = '<head><title>Test HTML</title></head><body>The test text</body>'
        >>> html_prettied = pretty_html(html)
        >>> assert isinstance(html_prettied, str)
        >>> '<html>' in html_prettied
        True
        >>> '</html>' in html_prettied
        True

        >>> bytes_html = b'<head><title>Test HTML</title></head><body>The test text</body>'
        >>> pretty_bytes_html = pretty_html(bytes_html)
        >>> assert isinstance(pretty_bytes_html, bytes)
        >>> b'<html>' in pretty_bytes_html
        True
        >>> b'</html>' in pretty_bytes_html
        True
    '''

    def append_line(line):
        line = line.strip()
        log(f'line: {line}') # DEBUG
        lines.append(line)

    #log('type(html): {}'.format(type(html)))
    #log('repr(html): {}'.format(repr(html)))
    WAS_STRING = isinstance(html, str)
    #log('WAS_STRING: {}'.format(WAS_STRING))
    if WAS_STRING:
        html = to_bytes(html)
        #log('type(html) after to_bytes: {}'.format(type(html)))

    if parser is None:
        parser = 'html5lib'
        log('using html5lib parser')

    # try various html prettyprinters
    p_html = None

    try:
        from bs4 import BeautifulSoup

        log(f'clean html with beautifulsoup prettify, parser: {parser}')

        soup = BeautifulSoup(html, features=parser)
        p_html = soup.prettify(encoding='utf-8')

    except ImportError:
        pass

    except:   # 'bare except' because it catches more than "except Exception"
        log(format_exc())

    if not p_html:
        try:
            # python3-tidylib
            from tidylib import tidy_document

            if b'<frameset' in html:
                raise ValueError('tidy_document() does not work with framesets')

            p_html, errors = tidy_document(html)
            if errors:
                # rss is not html
                if '<rss> is not recognized' in errors:
                    log("Warning: tidy prettyprinter can't format rss")
                else:
                    log("Warning: tidy prettyprinter found errors")
                    # log("see {}".format(DETAILED_LOG))
                    # detailed_log('tidy error: {}\n'.format(errors))
            elif not p_html:
                log('tidy returned an empty page')

        except ImportError:
            log('No module named tidylib. Install debian package python3-tidylib or pypi package pytidylib.')
        except:   # 'bare except' because it catches more than "except Exception"
            log(format_exc())

    if not p_html:
        try:
            # python3-utidylib
            import tidy

            options = dict(output_xhtml=1, add_xml_decl=1, indent=1, tidy_mark=0)
            try:
                p_html = str(tidy.parseString(html, **options))
            except AttributeError as aerr:
                # not debugged:
                #      module 'tidy' has no attribute 'parseString'
                # maybe need to install/reinstall python3-utidylib
                log.warning(str(aerr))

        except ImportError:
            log('No module named tidy')
        except:   # 'bare except' because it catches more than "except Exception"
            log(format_exc())

        else:
            if not p_html:
                log('empty string from python3-utidylib')

    if not p_html:
        # import late to avoid conflicts
        from denova.python.utils import stacktrace

        # ad hoc prettyprinter, indents tag/endtag blocks

        log('denova.python.format() NOT WORKING') # DEBUG
        log(stacktrace()) # the caller needs to handle a returned value of None
        return None

        # split into lines
        lines = []
        line = ''
        quote_char = None # or quote char
        for ch in html:

            #log('ch: {}'.format(repr(ch))) # DEBUG
            # if type(html) is bytes, then type(ch) is int
            if isinstance(ch, int):
                ch = chr(ch)
                #log('ch changed to: {}'.format(repr(ch))) # DEBUG

            if quote_char:
                #log('in quote') # DEBUG
                # don't look for tags in quoted strings
                line = line + ch
                if ch == quote_char:
                    quote_char = None

            elif ch in ('"', "'"):
                #log('start quote: {}'.format(ch)) # DEBUG
                quote_char = ch
                line = line + ch

            # look for tags
            elif ch == '<':
                log('start tag, end of previous line') # DEBUG
                if line:
                    lines.append(line.strip())
                line = '<'
            elif ch == '>':
                log('end tag char') # DEBUG
                if line:
                    log('end tag char, so end of line') # DEBUG
                    line = line + ch
                    append_line(line)
                    line = ''
                else:
                    log('probably not a tag') # DEBUG
                    line = line + ch

            else:
                line = line + ch

        # finish last line, if any
        if line:
            append_line(line)
        #log('lines done')

        # indent blocks with endtags
        start_tag_pattern = re.compile(b'^<\s*([A-Za-z]+)\b.*>')
        end_tag_pattern = re.compile(b'^</\s*([A-Za-z]+)\b.*>')
        reversed_rough = []
        tags = []
        indent = 0
        for line in reversed(lines):

            end_match = end_tag_pattern.match(line)
            if end_match:
                endtag = end_match.group(1)
                tags.append(endtag)
                reversed_rough.append((indent * b'    ') + line)
                indent += 1

            else:
                start_match = start_tag_pattern.match(line)
                if start_match:
                    starttag = start_match.group(1)
                    if starttag in tags:
                        del tags[tags.index(starttag)]
                        if indent:
                            indent -= 1
                reversed_rough.append((indent * b'    ') + line)

        # remove excess indent
        first = reversed_rough[-1]
        excess_count = len(first) - len(first.lstrip())
        excess = b' ' * excess_count
        reversed_lines = []
        for line in reversed_rough:
            if line.startswith(excess):
                line = line[excess_count:]
            reversed_lines.append(line)

        # join lines
        lines = reversed(reversed_lines)
        p_html = b'\n'.join(lines)

    assert p_html, 'Unable to prettyprint. Tried BeautifulSoup, python3-tidylib, python3-utidylib, and ad hoc'
    #log('p_html:\n{}'.format(p_html)) # DEBUG

    #log('at end of p_html() WAS_STRING: {}'.format(WAS_STRING)) # DEBUG
    if WAS_STRING:
        #log('at end of p_html() call to_string(html)') # DEBUG
        p_html = to_string(p_html)
    #log('at end of p_html() type(html): {}'.formattype(html))) # DEBUG

    return p_html

def pretty_json(json_string, indent=4):
    ''' Prettyprint json string.

        >>> json_string = '{"b": 2, "a": 1, "d": {"y": "b", "x": "a"}, "c": 3}'
        >>> print(pretty_json(json_string))
        {
            "a": 1,
            "b": 2,
            "c": 3,
            "d": {
                "x": "a",
                "y": "b"
            }
        }

    '''

    decoded = json.loads(json_string)
    encoded = json.dumps(decoded, indent=indent, sort_keys=True)
    return encoded

def pretty_called_process_error(cpe):
    ''' Pretty-print subprocess.CalledProcessError '''

    def pretty_text(label, text):
        if text:
            text = text.decode().strip()
            text.replace('\n', '\n\t\t')
            text = '\t' + label + ':\n\t\t' + text

        else:
            text = ''

        return text

    pretty = 'subprocess.CalledProcessError\n'

    command_args = list(map(str, cpe.args))
    command_str = ' '.join(command_args)
    pretty = pretty + '\t' + command_str + '\n'
    pretty = pretty + '\t' + f'error returncode: {cpe.returncode}' + '\n'
    pretty = pretty + pretty_text('stdout', cpe.stdout)
    pretty = pretty + pretty_text('stderr', cpe.stderr)

    return pretty

def encode_unicode(string):
    ''' DEPRECATED. Use to_bytes().

        Deprecated because no one can remember what .encode()
        and .decode() do.

        Convert string to bytes.
        Replacement for STRING.encode().

        If not decoded raises UnicodeEncodeError.
    '''

    return to_bytes(string)

def decode_unicode(string):
    ''' DEPRECATED. Use to_string().

        Deprecated because no one can remember what .encode()
        and .decode() do.

        Convert bytes to a unicode string.
        Replacement for bytes.decode().
    '''

    return to_string(string)

def read_unicode(stream, errors=None):
    ''' Try to decode a stream of bytes to a unicode string.
        Replacement for stream.read().

        There has got to be a standard way to do this that works, but haven't found it.

        If not decoded raises UnicodeDecodeError.

        If stream is not bytes raises TypeError.

        To do:
            Use encoding hints, e.g. http's Content-Encoding::
                content-type = text/html; charset=UTF-8
                or from python::
                    charset = denova.net.http_addons.content_encoding_charset(params)
                or html's content-type::
                    <meta http-equiv="content-type" content="text/html; charset=UTF-8">
    '''

    if errors is None:
        errors = 'strict'

    decodings = UNICODE_DECODINGS
    decoded = None

    data = stream.read()

    if isinstance(data, str):
        decoded = data

    else:
        for encoding in decodings:
            if decoded is None:
                try:
                    decoded = str(data, encoding, errors)

                except UnicodeDecodeError:
                    pass

    if decoded is None:
        raise UnicodeDecodeError(f'unable to decode unicode using {repr(UNICODE_DECODINGS)}')

    return decoded

def to_bytes(obj):
    ''' Convert string to bytes.

        'obj' must be a string or bytes. If obj is bytes or bytearray, it is unchanged.

        Convenience function because no one can remember what .encode()
        and .decode() do.

        Replacement for string.encode().
    '''

    if isinstance(obj, (bytearray, bytes)):
        encoded = obj

    else:
        if repr(obj).startswith("b'"): raise Exception(f'apparent byte literal as string: {obj}') # DEBUG
        encoded = None
        for encoding in UNICODE_DECODINGS:
            if encoded is None:
                try:
                    encoded = obj.encode(encoding)
                    if isinstance(encoded, str):
                        log(f'unable to encode string. type after encoding is {type(encoded)}')
                        encoded = None

                except UnicodeEncodeError:
                    pass

        if encoded is None:
            raise UnicodeEncodeError(f'unable to encode unicode using {repr(UNICODE_DECODINGS)}')

        assert isinstance(encoded, bytes)

    return encoded

def to_string(obj):
    ''' Convert bytes to string.

        'obj' must be a string or bytes. If obj is a string, it is unchanged.

        If not decoded raises UnicodeDecodeError.

        Replacement for bytes.decode().
    '''

    if isinstance(obj, str):
        decoded = obj

    else:
        decoded = None
        for encoding in UNICODE_DECODINGS:
            if decoded is None:
                try:
                    decoded = obj.decode(encoding)

                except UnicodeDecodeError:
                    pass

        if decoded is None:
            raise UnicodeDecodeError(f'unable to decode unicode using {repr(UNICODE_DECODINGS)}')

        assert isinstance(decoded, str)

    return decoded


if __name__ == "__main__":
    import doctest
    doctest.testmod()
