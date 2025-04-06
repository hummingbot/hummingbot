"""The compat module provides various Python 2 / Python 3
compatibility functions

"""
# pylint: disable=C0103

import abc
import os
import platform
import re
import socket
import sys as _sys
import time

PY2 = _sys.version_info.major == 2
PY3 = not PY2
RE_NUM = re.compile(r'(\d+).+')

ON_LINUX = platform.system() == 'Linux'
ON_OSX = platform.system() == 'Darwin'
ON_WINDOWS = platform.system() == 'Windows'

# Portable Abstract Base Class
AbstractBase = abc.ABCMeta('AbstractBase', (object,), {})

if _sys.version_info[:2] < (3, 3):
    SOCKET_ERROR = socket.error
else:
    # socket.error was deprecated and replaced by OSError in python 3.3
    SOCKET_ERROR = OSError

try:
    SOL_TCP = socket.SOL_TCP
except AttributeError:
    SOL_TCP = socket.IPPROTO_TCP

if PY3:
    # these were moved around for Python 3
    # pylint: disable=W0611
    from urllib.parse import (quote as url_quote, unquote as url_unquote,
                              urlencode, parse_qs as url_parse_qs, urlparse)
    from io import StringIO

    # Python 3 does not have basestring anymore; we include
    # *only* the str here as this is used for textual data.
    basestring = (str,)

    # for assertions that the data is either encoded or non-encoded text
    str_or_bytes = (str, bytes)

    # xrange is gone, replace it with range
    xrange = range

    # the unicode type is str
    unicode_type = str

    def time_now():
        """
        Python 3 supports monotonic time
        """
        return time.monotonic()

    def dictkeys(dct):
        """
        Returns a list of keys of dictionary

        dict.keys returns a view that works like .keys in Python 2
        *except* any modifications in the dictionary will be visible
        (and will cause errors if the view is being iterated over while
        it is modified).
        """

        return list(dct.keys())

    def dictvalues(dct):
        """
        Returns a list of values of a dictionary

        dict.values returns a view that works like .values in Python 2
        *except* any modifications in the dictionary will be visible
        (and will cause errors if the view is being iterated over while
        it is modified).
        """
        return list(dct.values())

    def dict_iteritems(dct):
        """
        Returns an iterator of items (key/value pairs) of a dictionary

        dict.items returns a view that works like .items in Python 2
        *except* any modifications in the dictionary will be visible
        (and will cause errors if the view is being iterated over while
        it is modified).
        """
        return dct.items()

    def dict_itervalues(dct):
        """
        :param dict dct:
        :returns: an iterator of the values of a dictionary
        :rtype: iterator
        """
        return dct.values()

    def byte(*args):
        """
        This is the same as Python 2 `chr(n)` for bytes in Python 3

        Returns a single byte `bytes` for the given int argument (we
        optimize it a bit here by passing the positional argument tuple
        directly to the bytes constructor.
        """
        return bytes(args)

    class long(int):
        """
        A marker class that signifies that the integer value should be
        serialized as `l` instead of `I`
        """

        def __str__(self):
            return str(int(self))

        def __repr__(self):
            return str(self) + 'L'

    def canonical_str(value):
        """
        Return the canonical str value for the string.
        In both Python 3 and Python 2 this is str.
        """

        return str(value)

    def is_integer(value):
        """
        Is value an integer?
        """
        return isinstance(value, int)
else:
    from urllib import (quote as url_quote, unquote as url_unquote, urlencode) # pylint: disable=C0412,E0611
    from urlparse import (parse_qs as url_parse_qs, urlparse) # pylint: disable=E0401
    from StringIO import StringIO # pylint: disable=E0401

    basestring = basestring
    str_or_bytes = basestring
    xrange = xrange
    unicode_type = unicode # pylint: disable=E0602
    dictkeys = dict.keys
    dictvalues = dict.values
    dict_iteritems = dict.iteritems # pylint: disable=E1101
    dict_itervalues = dict.itervalues # pylint: disable=E1101
    byte = chr
    long = long

    def time_now():
        """
        Python 2 does not support monotonic time
        """
        return time.time()

    def canonical_str(value):
        """
        Returns the canonical string value of the given string.
        In Python 2 this is the value unchanged if it is an str, otherwise
        it is the unicode value encoded as UTF-8.
        """

        try:
            return str(value)
        except UnicodeEncodeError:
            return str(value.encode('utf-8'))

    def is_integer(value):
        """
        Is value an integer?
        """
        return isinstance(value, (int, long))


def as_bytes(value):
    """
    Returns value as bytes
    """
    if not isinstance(value, bytes):
        return value.encode('UTF-8')
    return value


def to_digit(value):
    """
    Returns value as in integer
    """
    if value.isdigit():
        return int(value)
    match = RE_NUM.match(value)
    return int(match.groups()[0]) if match else 0


def get_linux_version(release_str):
    """
    Gets linux version
    """
    ver_str = release_str.split('-')[0]
    return tuple(map(to_digit, ver_str.split('.')[:3]))


HAVE_SIGNAL = os.name == 'posix'

EINTR_IS_EXPOSED = _sys.version_info[:2] <= (3, 4)

LINUX_VERSION = None
if platform.system() == 'Linux':
    LINUX_VERSION = get_linux_version(platform.release())

_LOCALHOST = '127.0.0.1'
_LOCALHOST_V6 = '::1'


def _nonblocking_socketpair(family=socket.AF_INET,
                            socket_type=socket.SOCK_STREAM,
                            proto=0):
    """
    Returns a pair of sockets in the manner of socketpair with the additional
    feature that they will be non-blocking. Prior to Python 3.5, socketpair
    did not exist on Windows at all.
    """
    if family == socket.AF_INET:
        host = _LOCALHOST
    elif family == socket.AF_INET6:
        host = _LOCALHOST_V6
    else:
        raise ValueError('Only AF_INET and AF_INET6 socket address families '
                         'are supported')
    if socket_type != socket.SOCK_STREAM:
        raise ValueError('Only SOCK_STREAM socket socket_type is supported')
    if proto != 0:
        raise ValueError('Only protocol zero is supported')

    lsock = socket.socket(family, socket_type, proto)
    try:
        lsock.bind((host, 0))
        lsock.listen(min(socket.SOMAXCONN, 128))
        # On IPv6, ignore flow_info and scope_id
        addr, port = lsock.getsockname()[:2]
        csock = socket.socket(family, socket_type, proto)
        try:
            csock.connect((addr, port))
            ssock, _ = lsock.accept()
        except Exception:
            csock.close()
            raise
    finally:
        lsock.close()

    # Make sockets non-blocking to prevent deadlocks
    # See https://github.com/pika/pika/issues/917
    csock.setblocking(False)
    ssock.setblocking(False)

    return ssock, csock
