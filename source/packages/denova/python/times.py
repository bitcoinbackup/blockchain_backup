'''
    Times.

    Utilties for times. Great for working with time series.

    Todo: Handle timezones better. See parse_timestamp(timezone=...),

    Copyright 2009-2020 DeNova
    Last modified: 2020-10-29

    This file is open source, licensed under GPLv3 <http://www.gnu.org/licenses/>.
'''

import calendar
import re
import time
# avoid conflict with 'timezone' param
from datetime import timezone as datetime_timezone
from datetime import date, datetime, timedelta

try:
    import pytz
    from pytz.exceptions import UnknownTimeZoneError
except ImportError:
    PYTZ_AVAILABLE = False
else:
    PYTZ_AVAILABLE = True

from denova.net.web_log_parser import LogLine
from denova.python.log import get_log
from denova.python.format import s_if_plural

# map month abbrevs to numeric equivalent
MONTH_MAP = {'Jan': 1,
             'Feb': 2,
             'Mar': 3,
             'Apr': 4,
             'May': 5,
             'Jun': 6,
             'Jul': 7,
             'Aug': 8,
             'Sep': 9,
             'Oct': 10,
             'Nov': 11,
             'Dec': 12}

# ISO 8901 datetime format with microseconds and timezone
ISO_DATETIME_RE = r'(?P<year>\d+)-(?P<month>\d+)-(?P<day>\d+)[ T](?P<hour>\d+):(?P<minute>\d+):(?P<second>\d+)\.(?P<microsecond>\d*)(?P<timezone>.*)'
TIMEZONE_RE = re.compile(r'(?P<name>[a-zA-Z]{3})? *?((?P<sign>[+|-])(?P<hour>\d\d):(?P<minute>\d\d))?')

seconds_in_minute = 60
seconds_in_hour = 60 * seconds_in_minute
seconds_in_day = 24 * seconds_in_hour
microseconds_in_second = 1000000

# we don't define one_month, one_year, etc.
# because the exact definition varies from app to app
one_year = timedelta(days=365) # ignores leap year
one_week = timedelta(days=7)
one_day = timedelta(days=1)
one_hour = timedelta(hours=1)
one_minute = timedelta(minutes=1)
one_second = timedelta(seconds=1)
one_millisecond = timedelta(milliseconds=1)
one_microsecond = timedelta(microseconds=1)
no_time = timedelta(0)

far_past = datetime.min
far_future = datetime.max
# indicate all dates and times
anytime = far_future - one_microsecond

log = get_log()
_compiled_timestamps = []

# some constants are defined after we define functions they need

def now(utc=True):
    ''' Get the current datetime.

        If utc=True, return UTC date/time.

        Returns a datetime object.

        >>> dt = now()
        >>> repr(dt.tzinfo)
        'datetime.timezone.utc'
    '''

    if utc:
        tzinfo = datetime_timezone.utc
    else:
        tzinfo = None

    if utc:
        dt = datetime.utcnow().replace(tzinfo=tzinfo)
    else:
        dt = datetime.now()
    return dt

def get_short_now(utc=True):
    '''Get datetime up to the minute, not the second or millisecond.

        >>> get_short_now().second == 0 and get_short_now().microsecond == 0
        True
        >>> get_short_now(utc=True).second == 0 and get_short_now(utc=True).microsecond == 0
        True
    '''

    if utc:
        tzinfo = datetime_timezone.utc
    else:
        tzinfo = None

    time_now = now(utc=utc)
    return datetime(time_now.year, time_now.month, time_now.day,
                    time_now.hour, time_now.minute,
                    tzinfo=tzinfo)

def timestamp(when=None, microseconds=True):
    ''' Return timestamp as a string in a standard format. Time zone is UTC.

        'when' is a datetime or timestamp string. Defaults to now.

        If 'microseconds' is True microseconds are included. Defaults to True.

        >>> re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d*?\+00:00$', timestamp()) is not None
        True
        >>> re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', timestamp(microseconds=False)) is not None
        True
    '''

    if when:
        if isinstance(when, str):
            when = parse_timestamp(when)
        elif not isinstance(when, datetime):
            raise ValueError("'when' must be a datetime, date/time string, or None")
    else:
        when = now()

    # datetime.str() returns ISO format
    formatted_time = when.isoformat(sep=' ')

    if not microseconds:
        i = formatted_time.rfind('.')
        if i > 0:
            formatted_time = formatted_time[:i]

    #log('formatted_time: {}'.format(formatted_time))

    return formatted_time

def parse_timestamp(timestr, startswith=False, default_year=None, timezone=None):
    ''' Parse a string timestamp. Return datetime.

        Return first timestamp found.

        If no valid timestamp found, raises ValueError.

        If startswith is set to True, only match a timestamp at the
        beginning of timestr. The default is False, which means match
        a timestamp anywhere in timestr.

        Year defaults to current year, which won't be right if, for example,
        a process is running when a new year starts.. Microseconds default
        is zero.

        'timezone' is a timezone string.
        Examples are 'UTC', 'EST' and 'Europe/Amsterdam'.
        To keep django happy, parse_timestamp() defaults to UTC.
        OUTDATED:
        It is used only if the timestr is "naive", meaning has no timezone.
        If timestr does not have a timezone and 'timezone' is specified,
        then 'timezone' is passed to pytz.timezone(), and
        parse_timestamp's returned  datetime has the timezone from
        pytz.timezone(). If pytz is not installed, the returned datetime
        is "naive", meaning it does not have a timezone.

        If timestr does not have a timezone and
        'timezone' is not specified, the returned datetime is "naive",
        meaning it does not have a timezone. It's a good idea to always
        specify 'timezone='.

        parse_timestamp() handles multiple formats.

        >>> # RFC 2616 required formats
        >>> #     RFC 822, updated by RFC 1123
        >>> ts = parse_timestamp('Sun, 06 Nov 1994 08:49:37 GMT')
        >>> ts.year
        1994
        >>> #     RFC 850, obsoleted by RFC 1036
        >>> ts = parse_timestamp('Sunday, 06-Nov-94 08:49:37 GMT')
        >>> ts.year
        94
        >>> #     ANSI C's asctime() format
        >>> ts = parse_timestamp('Sun Nov  6 08:49:37 1994')
        >>> ts.year
        1994
        >>> ts = parse_timestamp('Mon, 27 Apr 2020 15:55:56 GMT')
        >>> ts.day
        27

        >>> # no year
        >>> ts = parse_timestamp('Oct 28 11:06:55.000')
        >>> ts.year > 0
        True
        >>> ts.month
        10
        >>> ts.day
        28
        >>> ts.hour
        11
        >>> ts.minute
        6
        >>> ts.second
        55
        >>> ts.microsecond
        0

        >>> # no microseconds
        >>> parse_timestamp('Tue Jan 15 14:49:13 2000')
        datetime.datetime(2000, 1, 15, 14, 49, 13)

        >>> # no year and no microseconds
        >>> ts = parse_timestamp('Oct 28 11:06:55')
        >>> ts.year > 0
        True
        >>> ts.month
        10
        >>> ts.day
        28
        >>> ts.hour
        11
        >>> ts.minute
        6
        >>> ts.second
        55
        >>> ts.microsecond
        0

        # no year, single digit day, no microseconds
        >>> ts = parse_timestamp('Apr  9 18:17:01')
        >>> ts.year > 0
        True
        >>> ts.month
        4
        >>> ts.day
        9
        >>> ts.hour
        18
        >>> ts.minute
        17
        >>> ts.second
        1
        >>> ts.microsecond
        0

        >>> repr(parse_timestamp('1970-01-18T20:03:11.282Z'))
        'datetime.datetime(1970, 1, 18, 20, 3, 11, 282, tzinfo=datetime.timezone.utc)'

        >>> repr(parse_timestamp('2019-10-17 19:46:30.574Z'))
        'datetime.datetime(2019, 10, 17, 19, 46, 30, 574, tzinfo=datetime.timezone.utc)'

        >>> repr(parse_timestamp('17/Oct/2019:09:35:52 +0000'))
        'datetime.datetime(2019, 10, 17, 9, 35, 52, tzinfo=datetime.timezone.utc)'

        We're not handling this date string because
        different parts of the world interrupt this date differently.
        repr(parse_timestamp('02:07:36 05/08/03 EDT'))
        'datetime.datetime(5, 8, 3, 2, 7, 36)'

        >>> repr(parse_timestamp('2019-10-26 11:38:05.000711', timezone='UTC'))
        'datetime.datetime(2019, 10, 26, 11, 38, 5, 711, tzinfo=datetime.timezone.utc)'

        >>> repr(parse_timestamp('2019/10/17 12:40:36'))
        'datetime.datetime(2019, 10, 17, 12, 40, 36)'

        >>> repr(parse_timestamp('2019-10-23T17:55:00'))
        'datetime.datetime(2019, 10, 23, 17, 55)'

        >>> repr(parse_timestamp('2019-10-23T17:55:00UTC-07:30'))
        'datetime.datetime(2019, 10, 23, 17, 55, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=59400)))'

        >>> repr(parse_timestamp('2019-04-11T12:49:00 UTC+03:00'))
        'datetime.datetime(2019, 4, 11, 12, 49, tzinfo=datetime.timezone(datetime.timedelta(seconds=10800)))'

        >>> repr(parse_timestamp('Oct 28 09:54:48'))
        'datetime.datetime(2020, 10, 28, 9, 54, 48)'

        >>> repr(parse_timestamp(b'Oct 28 09:54:48'))
        'datetime.datetime(2020, 10, 28, 9, 54, 48)'

        >>> if PYTZ_AVAILABLE:
        ...     log.debug('test pytz')
        ...     tz = pytz.timezone('UTC')
        ...     tz.zone
        'UTC'

        >>> if PYTZ_AVAILABLE:
        ...     tz = pytz.timezone('EST')
        ...     tz.zone
        'EST'

        >>> if PYTZ_AVAILABLE:
        ...     # pytz can't handle Daylight Savings
        ...     try:
        ...         pytz.timezone('EDT')
        ...     except pytz.exceptions.UnknownTimeZoneError:
        ...         pass

        >>> if PYTZ_AVAILABLE:
        ...     tz = pytz.timezone('Europe/Amsterdam')
        ...     tz.zone
        'Europe/Amsterdam'
    '''

    def parse_timezone(timezone_str):
        ''' Parse the timezone as an offset from UTC.

            Try the pytz module first.

            Returns tzinfo or None.
        '''

        #log.debug('timezone_str: {}'.format(timezone_str))
        tzinfo = None

        if PYTZ_AVAILABLE:
            try:
                tzinfo = pytz.timezone(timezone_str)
            except UnknownTimeZoneError:
                #log.debug('timezone unknown to pytz: {}'.format(timezone_str))
                pass

        if not tzinfo:
            match = TIMEZONE_RE.search(timezone_str)
            if match:
                mdict = match.groupdict()
                #log.debug('timezone dict: {}'.format(mdict))

                # name must be UTC; if it's not and pytz wasn't able to
                # handle the conversion, then we'll ignore the timezone
                if 'name' in mdict:
                    if mdict['name']:
                        timezone_is_utc = mdict['name'].upper() == 'UTC'
                    else:
                        timezone_is_utc = True
                else:
                    timezone_is_utc = True

                if timezone_is_utc:
                    # timedelta() requires hour/minute
                    if ('sign' in mdict) and ('hour' in mdict) and ('minute' in mdict):

                        tz_sign = mdict['sign']
                        tz_hours = int(mdict['hour'])
                        tz_minutes = int(mdict['minute'])

                        offset = timedelta(hours=tz_hours, minutes=tz_minutes)
                        if tz_sign == '-':
                            offset = -offset
                        tzinfo = datetime_timezone(offset)
            else:
                log.debug(f'no timezone parsed. TIMEZONE_RE did not match. timestr: {timestr}')

        return tzinfo

    def get_timestamp(mdict, timezone):
        """ Timestamp regular expressions

            Match keywords must be the names of datetime.datetime parameters.

            The order of patterns is important. The patterns are tried in order.
            The first one to match is accepted. That means you need to
            list more complete ones first. For example, you should specify
            the tor log format before the syslog format. They are the same
            except the tor log format includes microseconds. So you want to
            match on microseconds if they are available, but still match
            on a different pattern when microseconds aren't available.

            Web log format is a special case handled in the code.
        """

        DATETIME_KEYWORDS = ['year', 'month', 'day',
                             'hour', 'minute', 'second', 'microsecond',
                             'tzinfo']

        #log.debug('mdict {}'.format(mdict)) # DEBUG

        kwargs = {}
        for key in mdict:
            if key == 'timezone':
                value = mdict[key]
                kwargs[key] = value.strip()

            elif key == 'month':
                month = mdict[key]
                try:
                    month = int(month)
                except ValueError:
                    # try to map a text month to an int
                    month = MONTH_MAP[month]
                except AttributeError:
                    raise ValueError('month must be an integer or month string')
                else:
                    if month < 1 or month > 12:
                        raise ValueError('month must be an integer in the range 1 to 12, or month string')
                kwargs[key] = month

            # ignore 'weekday', etc.
            elif key in DATETIME_KEYWORDS:
                value = int(mdict[key])
                kwargs[key] = value

        # datetime() requires year/month/day

        # not all timestamps have a year
        if 'year' not in kwargs:
            # we default to this year, which won't be right if this
            # process runs into a new year.
            kwargs['year'] = default_year or now().year

        #log.debug('get tzinfo. timezone={}'.format(timezone)) # DEBUG
        ''' We want to set tzinfo from the timestr if possible.
            Second choice is the timezone= passed to parse_timestamp().
            Last choice is default to a "naive" datetime, with no tzinfo.
        '''
        tzinfo = None

        # if timestr has a timezone, override any timezone param
        if 'timezone' in kwargs:
            tz = kwargs['timezone']
            del kwargs['timezone']
            #log.debug('kwargs[timezone]: {}'.format(tz)) # DEBUG
            if tz:
                timezone = tz
                #log.debug('set timezone from kwargs: {}'.format(timezone)) # DEBUG

        if timezone:
            if timezone.upper() in ['UTC','GMT', 'Z']:
                tzinfo = datetime_timezone.utc
            else:
                tzinfo = parse_timezone(timezone)

        if tzinfo:
            kwargs['tzinfo'] = tzinfo
            #log.debug('tzinfo: {}'.format(tzinfo))
        #else:
            #log.warning('no tzinfo') # DEBUG

        try:
            timestamp = datetime(**kwargs)
        except ValueError:
            log(f'bad datetime values: {repr(kwargs)}')
            log.exception()

        return timestamp

    RAW_TIMESTAMP_RES = [# iso datetime, which is datetime default
         ISO_DATETIME_RE,

         # short iso datetime with timezone
         r'(?P<year>\d+)-(?P<month>\d+)-(?P<day>\d+)[ T](?P<hour>\d+):(?P<minute>\d+):(?P<second>\d+)(?P<timezone>.*)',

         # short iso datetime
         r'(?P<year>\d+)-(?P<month>\d+)-(?P<day>\d+)[ T](?P<hour>\d+):(?P<minute>\d+):(?P<second>\d+)',

         # nginx error log
         # Example: 2019/10/17 12:40:36
         r'(?P<year>\d+)/(?P<month>\d+)/(?P<day>\d+) (?P<hour>\d+):(?P<minute>\d+):(?P<second>\d+)',

         # RFC 850, obsoleted by RFC 1036, Example: Sunday, 06-Nov-94 08:49:37 GMT
         r'(?P<weekday>[A-Za-z]+),\s+(?P<day>\d+)-(?P<month>[A-Za-z]+)-(?P<year>\d+)\s+(?P<hour>\d+):(?P<minute>\d\d):(?P<second>\d\d)\s+(?P<timezone>.*)',

         # Example: Mon, 27 Apr 2020 15:55:56 GMT
         r'(?P<weekday>[A-Za-z]+),\s(?P<day>\d+)\s+(?P<month>[A-Za-z]+)\s+(?P<year>\d+)\s+(?P<hour>\d+):(?P<minute>\d\d):(?P<second>\d\d)\s+(?P<timezone>.*)',

         # Example: Tue Jan 15 14:49:13 2019
         r'(?P<weekday>[A-Za-z]+)\s+(?P<month>[A-Za-z]+)\s+(?P<day>\d+)\s+(?P<hour>\d+):(?P<minute>\d\d):(?P<second>\d\d)\s+(?P<year>\d+)',

         # tor log
         # Example: Oct 28 11:06:55.000
         r'(?P<month>[A-Za-z]+)\s+(?P<day>\d\d)[ T](?P<hour>\d+):(?P<minute>\d\d):(?P<second>\d\d)\.(?P<microsecond>\d\d\d)',

         # syslog
         # Example: Oct 28 11:06:55
         # same as tor log, but without microseconds
         r'(?P<month>[A-Za-z]+)\s+(?P<day>\d+)[ T](?P<hour>\d+):(?P<minute>\d\d):(?P<second>\d\d)',

         # Example: '02:07:36 05/08/03 EDT'
         # Different parts of the world interpret this differently so we're going to ignore it
         #r'(?P<hour>\d+):(?P<minute>\d\d):(?P<second>\d\d) (?P<year>\d\d)/(?P<month>\d+)/(?P<day>\d+) (?P<timezone>.*)',
        ]

    #log.debug('timestr: {}'.format(repr(timestr))) # DEBUG

    if not _compiled_timestamps:
        # anchor timestamp formats to start of line and compile them
        for raw_re in RAW_TIMESTAMP_RES:

            # if startswith, only match timestamps at the start of the line
            if startswith and not raw_re.startswith(r'^'):
                compiled_re = re.compile(r'^' + raw_re)
            else:
                compiled_re = re.compile(raw_re)

            _compiled_timestamps.append(compiled_re)

    timestamp = None

    if type(timestr) is datetime:
        # save some callers from having to check the type
        timestamp = timestr

    elif type(timestr) is bytes:
        timestr = str(timestr)

    if not timestamp:
        for timestamp_re in _compiled_timestamps:
            if not timestamp:
                try:
                    # sometimes we get "must be str or a bytes-like object"
                    #log.debug('type(timestamp_re): {}'.format(type(timestamp_re))) # DEBUG
                    #log.debug('type(timestr): {}'.format(type(timestr))) # DEBUG
                    match = timestamp_re.search(timestr)
                    if match:
                        #log.debug('timestamp_re matched: {}'.format(timestamp_re)) # DEBUG
                        timestamp = get_timestamp(match.groupdict(), timezone)

                except Exception as e:
                    log.debug(f'unable to parse timestamp: {timestr}')
                    from denova.python.utils import format_exception
                    log.debug(format_exception(e))

    if not timestamp:
        # web log format is a special case (not at start of timestr), so try it last
        try:
            timestamp = LogLine.get_timestamp(timestr)

        except ValueError:
            pass

        except Exception as e:
            log.debug(f'unable to parse timestamp as web log line: {timestr}')
            from denova.python.utils import format_exception
            log.debug(format_exception(e))

    if not timestamp:
        raise ValueError(timestr)

    if timezone:
        # we should have a tzinfo attribute
        try:
            if not timestamp.tzinfo:
                raise Exception(f'tzinfo is None. timestr: {timestr}, timezone={timezone}')
        except AttributeError:
            raise Exception(f'tzinfo not set. timestr: {timestr}, timezone={timezone}')

    return timestamp

def format_time(d):
    ''' Return the item in the ISO 8601 format.

        If d is not str, int, or float, or datetime, throws ValueError.

        A string is any datetime string that parse_timestamp() can parse.
        An int or float is seconds since the epoch.

        >>> format_time(datetime(2012, 7, 6, 17, 57, 12, 4))
        '2012-07-06 17:57:12.000004'
        >>> format_time('2019-10-17 19:46:30.574Z')
        '2019-10-17 19:46:30.000574+00:00'
        >>> format_time('17/Oct/2019:09:35:52 +0000')
        '2019-10-17 09:35:52+00:00'
        >>> format_time('2019-10-23T17:55:00')
        '2019-10-23 17:55:00+00:00'
        >>> format_time(1571760736.9401658)
        '2019-10-22 16:12:16.940166+00:00'
        >>> format_time(1571760736)
        '2019-10-22 16:12:16+00:00'
        >>> format_time(1571760737)
        '2019-10-22 16:12:17+00:00'

        We're not handling this date string because
        different parts of the world interrupt this date differently.
        format_time('02:07:36 05/08/03 EDT')
        '0005-08-03 02:07:36'
    '''

    if d is None:
        raise ValueError

    elif isinstance(d, datetime):
        dt = d

    elif isinstance(d, str):
        dt = parse_timestamp(d, timezone='UTC')

    elif isinstance(d, (float, int)):
        dt = seconds_to_datetime(d)

    else:
        raise ValueError

    return dt.isoformat(sep=' ')

def format_date(date=None):
    ''' Return the date in a standard format.

        If date is not specified or the date is None, formats today's date.
        Time zone is UTC.

        >>> format_date((2012, 7, 6, 17, 57, 12, 4, 188, 0))
        '2012-07-06'
        >>> re.match(r'^\d{4}-\d{2}-\d{2}$', format_date()) is not None
        True
    '''

    if not date:
        date = time.gmtime()
    return time.strftime('%Y-%m-%d', date)

def seconds_human_readable(seconds):
    '''
        Formats seconds in a human readable form.

        If seconds is less than 0, then return None.
        seconds: 115619.434662
         days: 1.0
         minutes: 419
         hours: 32.0
         status: 32 hours, 419 minutes
        seconds: 29994.513938
         days: 0.0
         minutes: 1194
         hours: 8.0
         status: 8 hours, 1194 minutes


        >>> seconds_in_week = seconds_in_day * 7
        >>> seconds_in_year = seconds_in_week * 52
        >>> current = datetime.utcnow()
        >>> hour_ago = current - timedelta(minutes=48, seconds=20)
        >>> seconds = (current - hour_ago).total_seconds()
        >>> seconds_human_readable(seconds)
        '48 minutes'
        >>> hour_ago = current - timedelta(minutes=60)
        >>> seconds = (current - hour_ago).total_seconds()
        >>> seconds_human_readable(seconds)
        '1 hour'
        >>> hours_ago = current - timedelta(hours=5, minutes=6)
        >>> seconds = (current - hours_ago).total_seconds()
        >>> seconds_human_readable(seconds)
        '5 hours, 6 minutes'
        >>> two_days_ago = current - timedelta(days=2)
        >>> seconds = (current - two_days_ago).total_seconds()
        >>> seconds_human_readable(seconds)
        '2 days'
        >>> five_plus_weeks_ago = current - timedelta(days=37)
        >>> seconds = (current - five_plus_weeks_ago).total_seconds()
        >>> seconds_human_readable(seconds)
        '5 weeks, 2 days'
        >>> eight_plus_years_ago = current - timedelta(days=2921)
        >>> seconds = (current - eight_plus_years_ago).total_seconds()
        >>> seconds_human_readable(seconds)
        '8 years, 1 week'
        >>> three_years_ago = current - timedelta(days=1095)
        >>> seconds = (current - three_years_ago).total_seconds()
        >>> seconds_human_readable(seconds)
        '3 years'
    '''

    def format_unit_label(label, units):
        ''' Format the label. '''
        if units == 1:
            status = f'{units} {label}'
        else:
            status = f'{units} {label}s'

        return status

    status = None

    seconds_in_week = seconds_in_day * 7
    seconds_in_year = seconds_in_week * 52

    years = seconds // seconds_in_year
    if years > 0:
        years_status = format_unit_label('year', int(years))
        weeks = (seconds % seconds_in_year) // seconds_in_week
        if weeks > 0:
            weeks_status = format_unit_label('week', int(weeks))
            status = f'{years_status}, {weeks_status}'
        else:
            status = years_status

    if status is None:
        weeks = seconds // seconds_in_week
        if weeks > 0:
            weeks_status = format_unit_label('week', int(weeks))
            days = (seconds % seconds_in_week) // seconds_in_day
            if days > 0:
                days_status = format_unit_label('day', int(days))
                status = f'{weeks_status}, {days_status}'
            else:
                status = weeks_status

    if status is None:
        days = seconds // seconds_in_day
        if days > 0:
            days_status = format_unit_label('day', int(days))
            hours = (seconds % seconds_in_day) // seconds_in_hour
            if hours > 0:
                hours_status = format_unit_label('hour', int(hours))
                status = f'{days_status}, {hours_status}'
            else:
                status = days_status

    if status is None:
        hours = seconds // seconds_in_hour
        if hours > 0:
            hours_status = format_unit_label('hour', int(hours))
            minutes = (seconds % seconds_in_hour) // seconds_in_minute
            if minutes > 0:
                minutes_status = format_unit_label('minute', int(minutes))
                status = f'{hours_status}, {minutes_status}'
            else:
                status = hours_status

    if status is None:
        minutes = seconds // seconds_in_minute
        if minutes > 1:
            status = format_unit_label('minute', int(minutes))
        else:
            secs = seconds % seconds_in_minute
            if secs > 0:
                status = format_unit_label('second', int(secs))

    return status

def timedelta_to_human_readable(td, verbose=True):
    ''' Formats a timedelta in a human readable form.

        If total time is less than a second then shows milliseconds
        instead of microseconds, else rounds to the nearest second.

        >>> timedelta_to_human_readable(timedelta(days=1, seconds=123, minutes=4, hours=26))
        '2 days, 2 hours, 6 minutes, 3 seconds'
        >>> timedelta_to_human_readable(timedelta(seconds=123))
        '2 minutes, 3 seconds'
        >>> timedelta_to_human_readable(timedelta(seconds=65))
        '1 minute, 5 seconds'
        >>> timedelta_to_human_readable(timedelta(milliseconds=85))
        '85 ms'
        >>> timedelta_to_human_readable(timedelta(days=1, seconds=123, minutes=4, hours=26), verbose=False)
        '2days, 2hrs, 6mins, 3secs'
        >>> timedelta_to_human_readable(timedelta(seconds=123), verbose=False)
        '2mins, 3secs'
        >>> timedelta_to_human_readable(timedelta(seconds=65), verbose=False)
        '1min, 5secs'
        >>> timedelta_to_human_readable(timedelta(milliseconds=85), verbose=False)
        '85 ms'
    '''

    tdString = ''

    if td.days or td.seconds:

        # days
        if td.days:
            tdString = f'{td.days} day{s_if_plural(td.days)}'

        # round seconds
        seconds = td.seconds
        if (td.microseconds * 2) >= td.max.microseconds:
            seconds = seconds + 1

        # hours
        hours = seconds // seconds_in_hour
        if hours:
            if tdString:
                tdString = tdString + ', '
            tdString = tdString + f'{hours} hour{s_if_plural(hours)}'

        # minutes
        secondsLeft = seconds - (hours * seconds_in_hour)
        if secondsLeft:
            minutes = secondsLeft // seconds_in_minute
            if minutes:
                if tdString:
                    tdString = tdString + ', '
                tdString = tdString + f'{minutes} minute{s_if_plural(minutes)}'
                secondsLeft = secondsLeft - (minutes * seconds_in_minute)

        # seconds
        if secondsLeft:
            if tdString:
                tdString = tdString + ', '
            tdString = tdString + f'{secondsLeft} second{s_if_plural(secondsLeft)}'

    else:
        milliseconds = (td.microseconds + 1) / 1000
        tdString = f'{milliseconds} ms'

    if not verbose:
        m = re.match('.*( day)', tdString)
        if m:
            tdString = tdString.replace(m.group(1), 'day')

        m = re.match('.*( hour)', tdString)
        if m:
            tdString = tdString.replace(m.group(1), 'hr')

        m = re.match('.*( second)', tdString)
        if m:
            tdString = tdString.replace(m.group(1), 'sec')

        m = re.match('.*( minute)', tdString)
        if m:
            tdString = tdString.replace(m.group(1), 'min')

    return tdString


def get_short_date_time(date_time):
    '''Format the date-time without seconds.

        >>> get_short_date_time(datetime(2012, 6, 1, 12, 30, 0))
        '2012-06-01 12:30'
        >>> get_short_date_time(datetime(2012, 6, 1, 12, 30, 41))
        '2012-06-01 12:30'
        >>> get_short_date_time(datetime(2012, 6, 1, 12, 30, 0, 0))
        '2012-06-01 12:30'
        >>> get_short_date_time(None)
        ''
    '''

    if date_time:
        new_date_time = date_time.isoformat(sep=' ')
        try:
            m = re.match(r'.*?(\d+\:\d+\:\d+).*', new_date_time)
            if m:
                current_time = m.group(1)
                index = current_time.rfind(':')
                new_date_time = new_date_time.replace(m.group(1), current_time[:index])
        except Exception:
            pass

    else:
        new_date_time = ''

    return new_date_time

def datetime_to_date(dt):
    ''' Converts a datetime to a date. If dt is a date, returns a copy.

        >>> datetime_to_date(datetime(2012, 6, 1, 12, 30, 0))
        datetime.date(2012, 6, 1)
        >>> datetime_to_date(datetime(2012, 6, 1, 12, 30, 0, 0))
        datetime.date(2012, 6, 1)
    '''
    return date(dt.year, dt.month, dt.day)

def date_to_datetime(d):
    ''' Converts a date or datetime to a datetime at the beginning of the day.

        >>> date_to_datetime(datetime(2012, 6, 1, 1, 39))
        datetime.datetime(2012, 6, 1, 0, 0, tzinfo=datetime.timezone.utc)
        >>> date_to_datetime(date(2012, 6, 1))
        datetime.datetime(2012, 6, 1, 0, 0, tzinfo=datetime.timezone.utc)
    '''

    return datetime(d.year, d.month, d.day, tzinfo=datetime_timezone.utc)

def timedelta_to_days(td):
    ''' Converts timedelta to floating point days.

        >>> timedelta_to_days(timedelta(seconds=864000))
        10.0
        >>> timedelta_to_days(timedelta(days=4, seconds=43200))
        4.5
    '''

    # !!!!! python 3
    return timedelta_to_seconds(td) / seconds_in_day

def timedelta_to_seconds(td):
    ''' Converts timedelta to floating point seconds.

        >>> timedelta_to_seconds(timedelta(seconds=864000))
        864000.0
        >>> timedelta_to_seconds(timedelta(days=4, seconds=43200))
        388800.0
    '''

    # internally timedelta only stores days, seconds, and microseconds
    # !!!!! python 3
    return (
        (td.days * seconds_in_day) +
        td.seconds +
        ((1.0 * td.microseconds) / microseconds_in_second))

def datetime_to_seconds(dt):
    ''' Converts datetime to floating point seconds since the epoch.

        >>> dt =datetime(2012, 6, 1, 12, 30, 0)
        >>> secs = calendar.timegm(dt.timetuple())
        >>> secs
        1338553800
        >>> dt_secs = datetime_to_seconds(dt)
        >>> dt_secs == secs
        True
    '''

    return calendar.timegm(dt.timetuple())

def seconds_to_datetime(seconds):
    ''' Convert seconds since the epoch to a datetime.

        Convenience function.

        >>> seconds_to_datetime(864000)
        datetime.datetime(1970, 1, 11, 0, 0, tzinfo=datetime.timezone.utc)
    '''

    utc = datetime_timezone.utc
    return datetime.fromtimestamp(float(seconds), tz=utc)

def one_month_before(date):
    ''' Returns one month before.

        Accepts a date or datetime. Returns a datetime.

        >>> one_month_before(date(2012, 6, 1))
        datetime.datetime(2012, 5, 1, 0, 0)
        >>> one_month_before(date(2012, 3, 30))
        datetime.datetime(2012, 2, 29, 0, 0)
        >>> one_month_before(date(2012, 5, 31))
        datetime.datetime(2012, 4, 30, 0, 0)
    '''

    if date.month > 1:
        last_year = date.year
        last_month = date.month - 1
    else:
        last_year = date.year - 1
        last_month = 12

    current_date_range = calendar.monthrange(date.year, date.month)
    last_date_range = calendar.monthrange(last_year, last_month)
    if date.day == current_date_range[1]:
        last_day = last_date_range[1]
    else:
        if date.day > last_date_range[1]:
            last_day = last_date_range[1]
        else:
            last_day = date.day

    earlier = datetime(last_year, last_month, last_day)
    return earlier

def start_of_day(d):
    ''' Returns datetime with no hours, minutes, seconds, or microseconds.

        Accepts a date or datetime. Returns a datetime.

        >>> start_of_day(date(2012, 6, 1))
        datetime.datetime(2012, 6, 1, 0, 0, tzinfo=datetime.timezone.utc)
        >>> start_of_day(datetime(2012, 3, 30, 11, 27))
        datetime.datetime(2012, 3, 30, 0, 0, tzinfo=datetime.timezone.utc)
    '''

    return date_to_datetime(datetime_to_date(d))

def end_of_day(d):
    ''' Returns the latest datetime for the day.

        Accepts a date or datetime. Returns a datetime.

        >>> end_of_day(date(2012, 6, 1))
        datetime.datetime(2012, 6, 1, 23, 59, 59, 999999, tzinfo=datetime.timezone.utc)
        >>> end_of_day(datetime(2012, 3, 30, 11, 27))
        datetime.datetime(2012, 3, 30, 23, 59, 59, 999999, tzinfo=datetime.timezone.utc)
    '''

    return start_of_day(d) + one_day - one_microsecond

def date_range(start, end, lei_convention=False):
    ''' Generates every date in the range from start to end, inclusive.

        To follow the endpoint convention [a, b) and exclude the
        right endpoint, i.e. include the first element and exclude the last,
        set lei_convention=True. See http://mathworld.wolfram.com/Interval.html

        If start is later than end, returns dates in reverse chronological
        order.

        Accepts dates or datetimes. Yields dates.

        >>> list(date_range(date(2012, 6, 1), date(2012, 6, 2)))
        [datetime.date(2012, 6, 1), datetime.date(2012, 6, 2)]
        >>> list(date_range(date(2012, 6, 2), date(2012, 6, 1)))
        [datetime.date(2012, 6, 2), datetime.date(2012, 6, 1)]
        >>> list(date_range(date(2012, 6, 1), date(2012, 6, 1)))
        [datetime.date(2012, 6, 1)]
        >>> list(date_range(date(2012, 6, 1), date(2012, 6, 2), lei_convention=True))
        [datetime.date(2012, 6, 1)]
        >>> list(date_range(date(2012, 6, 2), date(2012, 6, 1), lei_convention=True))
        [datetime.date(2012, 6, 2)]
        >>> list(date_range(datetime(2012, 6, 1, 21, 3), datetime(2012, 6, 2, 0, 0)))
        [datetime.date(2012, 6, 1), datetime.date(2012, 6, 2)]
        >>> list(date_range(datetime(2012, 6, 1, 0, 0), datetime(2012, 6, 2, 23, 59, 59, 999999)))
        [datetime.date(2012, 6, 1), datetime.date(2012, 6, 2)]
        >>> list(date_range(datetime(2012, 6, 2, 23, 59, 59, 999999), datetime(2012, 6, 1, 23, 59, 59, 999999)))
        [datetime.date(2012, 6, 2), datetime.date(2012, 6, 1)]
        >>> list(date_range(datetime(2012, 6, 1, 0, 0), datetime(2012, 6, 1, 23, 59, 59, 999999)))
        [datetime.date(2012, 6, 1)]
    '''

    increasing = start <= end
    day = datetime_to_date(start)

    if lei_convention:
        if increasing:
            if isinstance(end, datetime):
                end = end - one_microsecond
            else:
                end = end - one_day
        else:
            if isinstance(end, datetime):
                end = end + one_microsecond
            else:
                end = end + one_day

    end = datetime_to_date(end)

    yield day
    if increasing:
        while day < end:
            day = day + one_day
            yield day
    else:
        while day > end:
            day = day - one_day
            yield day


class elapsed_time():
    ''' Context manager to compute elapsed time.

        >>> ms = 200
        >>> with elapsed_time() as et:
        ...     time.sleep(float(ms)/1000)
        >>> print(et)
        200 ms
        >>> delta = et.timedelta()
        >>> lower_limit = timedelta(milliseconds=ms)
        >>> upper_limit = timedelta(milliseconds=ms+1)
        >>> assert delta > lower_limit
        >>> assert delta <= upper_limit
    '''

    def __init__(self):
        self.start = now()
        self.end = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.end = now()

    def __str__(self):
        return timedelta_to_human_readable(self.timedelta())

    def timedelta(self):
        ''' Elapsed time as timedelta type.

            If still in block, then elapsed time so far. '''

        if self.end:
            result = self.end - self.start
        else:
            result = now() - self.start
        return result

class log_elapsed_time():
    ''' Context manager to log elapsed time.

        >>> ms = 200
        >>> with log_elapsed_time(log, 'test sleep'):
        ...     time.sleep(float(ms)/1000)
    '''

    def __init__(self, log, msg=None):
        self.start = now()
        # verify 'log' is a log
        if not hasattr(log, 'debug'):
            raise ValueError(f"'log' must be a log, not {type(log)}")
        self.log = log
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        elapsed = now() - self.start
        if self.msg:
            self.log.debug(f'{self.msg} elapsed time {elapsed}')
        else:
            self.log.debug(f'elapsed time {elapsed}')

def date_string_to_date(date_string):
    ''' Convert a string representation of a date into a python date.

        >>> date_string_to_date('2015-04-25')
        datetime.date(2015, 4, 25)
        >>> date_string_to_date('14-01-2015')
        datetime.date(2015, 1, 14)
        >>> date_string_to_date('test')
    '''

    Date_Format1 = r'(\d{4})-(\d{2})-(\d{2})'
    Date_Format2 = r'(\d{2})-(\d{2})-(\d{4})' # the European alternative

    d = None
    m = re.match(Date_Format1, date_string)
    if m:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    else:
        m = re.match(Date_Format2, date_string)
        if m:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))

    return d


# be careful about using the following values
# they are calculated when this module is imported
today = now()
tomorrow = now() + one_day
yesterday = now() - one_day
one_month_ago = one_month_before(today)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
