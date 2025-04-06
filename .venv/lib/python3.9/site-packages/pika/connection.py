"""Core connection objects"""
# disable too-many-lines
# pylint: disable=C0302

import abc
import ast
import copy
import functools
import logging
import math
import numbers
import platform
import ssl

import pika.callback
import pika.channel
import pika.compat
import pika.credentials
import pika.exceptions as exceptions
import pika.frame as frame
import pika.heartbeat
import pika.spec as spec
import pika.validators as validators
from pika.compat import (
    xrange,
    url_unquote,
    dictkeys,
    dict_itervalues,
    dict_iteritems)

PRODUCT = "Pika Python Client Library"

LOGGER = logging.getLogger(__name__)


class Parameters(object):  # pylint: disable=R0902
    """Base connection parameters class definition

    """

    # Declare slots to protect against accidental assignment of an invalid
    # attribute
    __slots__ = ('_blocked_connection_timeout', '_channel_max',
                 '_client_properties', '_connection_attempts', '_credentials',
                 '_frame_max', '_heartbeat', '_host', '_locale', '_port',
                 '_retry_delay', '_socket_timeout', '_stack_timeout',
                 '_ssl_options', '_virtual_host', '_tcp_options')

    DEFAULT_USERNAME = 'guest'
    DEFAULT_PASSWORD = 'guest'

    DEFAULT_BLOCKED_CONNECTION_TIMEOUT = None
    DEFAULT_CHANNEL_MAX = pika.channel.MAX_CHANNELS
    DEFAULT_CLIENT_PROPERTIES = None
    DEFAULT_CREDENTIALS = pika.credentials.PlainCredentials(
        DEFAULT_USERNAME, DEFAULT_PASSWORD)
    DEFAULT_CONNECTION_ATTEMPTS = 1
    DEFAULT_FRAME_MAX = spec.FRAME_MAX_SIZE
    DEFAULT_HEARTBEAT_TIMEOUT = None  # None accepts server's proposal
    DEFAULT_HOST = 'localhost'
    DEFAULT_LOCALE = 'en_US'
    DEFAULT_PORT = 5672
    DEFAULT_RETRY_DELAY = 2.0
    DEFAULT_SOCKET_TIMEOUT = 10.0  # socket.connect() timeout
    DEFAULT_STACK_TIMEOUT = 15.0  # full-stack TCP/[SSl]/AMQP bring-up timeout
    DEFAULT_SSL = False
    DEFAULT_SSL_OPTIONS = None
    DEFAULT_SSL_PORT = 5671
    DEFAULT_VIRTUAL_HOST = '/'
    DEFAULT_TCP_OPTIONS = None

    def __init__(self):
        # If not None, blocked_connection_timeout is the timeout, in seconds,
        # for the connection to remain blocked; if the timeout expires, the
        # connection will be torn down, triggering the connection's
        # on_close_callback
        self._blocked_connection_timeout = None
        self.blocked_connection_timeout = (
            self.DEFAULT_BLOCKED_CONNECTION_TIMEOUT)

        self._channel_max = None
        self.channel_max = self.DEFAULT_CHANNEL_MAX

        self._client_properties = None
        self.client_properties = self.DEFAULT_CLIENT_PROPERTIES

        self._connection_attempts = None
        self.connection_attempts = self.DEFAULT_CONNECTION_ATTEMPTS

        self._credentials = None
        self.credentials = self.DEFAULT_CREDENTIALS

        self._frame_max = None
        self.frame_max = self.DEFAULT_FRAME_MAX

        self._heartbeat = None
        self.heartbeat = self.DEFAULT_HEARTBEAT_TIMEOUT

        self._host = None
        self.host = self.DEFAULT_HOST

        self._locale = None
        self.locale = self.DEFAULT_LOCALE

        self._port = None
        self.port = self.DEFAULT_PORT

        self._retry_delay = None
        self.retry_delay = self.DEFAULT_RETRY_DELAY

        self._socket_timeout = None
        self.socket_timeout = self.DEFAULT_SOCKET_TIMEOUT

        self._stack_timeout = None
        self.stack_timeout = self.DEFAULT_STACK_TIMEOUT

        self._ssl_options = None
        self.ssl_options = self.DEFAULT_SSL_OPTIONS

        self._virtual_host = None
        self.virtual_host = self.DEFAULT_VIRTUAL_HOST

        self._tcp_options = None
        self.tcp_options = self.DEFAULT_TCP_OPTIONS

    def __repr__(self):
        """Represent the info about the instance.

        :rtype: str

        """
        return ('<%s host=%s port=%s virtual_host=%s ssl=%s>' %
                (self.__class__.__name__, self.host, self.port,
                 self.virtual_host, bool(self.ssl_options)))

    def __eq__(self, other):
        if isinstance(other, Parameters):
            return self._host == other._host and self._port == other._port  # pylint: disable=W0212
        return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is not NotImplemented:
            return not result
        return NotImplemented

    @property
    def blocked_connection_timeout(self):
        """
        :returns: blocked connection timeout. Defaults to
            `DEFAULT_BLOCKED_CONNECTION_TIMEOUT`.
        :rtype: float|None

        """
        return self._blocked_connection_timeout

    @blocked_connection_timeout.setter
    def blocked_connection_timeout(self, value):
        """
        :param value: If not None, blocked_connection_timeout is the timeout, in
            seconds, for the connection to remain blocked; if the timeout
            expires, the connection will be torn down, triggering the
            connection's on_close_callback

        """
        if value is not None:
            if not isinstance(value, numbers.Real):
                raise TypeError('blocked_connection_timeout must be a Real '
                                'number, but got %r' % (value,))
            if value < 0:
                raise ValueError('blocked_connection_timeout must be >= 0, but '
                                 'got %r' % (value,))
        self._blocked_connection_timeout = value

    @property
    def channel_max(self):
        """
        :returns: max preferred number of channels. Defaults to
            `DEFAULT_CHANNEL_MAX`.
        :rtype: int

        """
        return self._channel_max

    @channel_max.setter
    def channel_max(self, value):
        """
        :param int value: max preferred number of channels, between 1 and
           `channel.MAX_CHANNELS`, inclusive

        """
        if not isinstance(value, numbers.Integral):
            raise TypeError('channel_max must be an int, but got %r' % (value,))
        if value < 1 or value > pika.channel.MAX_CHANNELS:
            raise ValueError('channel_max must be <= %i and > 0, but got %r' %
                             (pika.channel.MAX_CHANNELS, value))
        self._channel_max = value

    @property
    def client_properties(self):
        """
        :returns: client properties used to override the fields in the default
            client properties reported  to RabbitMQ via `Connection.StartOk`
            method. Defaults to `DEFAULT_CLIENT_PROPERTIES`.
        :rtype: dict|None

        """
        return self._client_properties

    @client_properties.setter
    def client_properties(self, value):
        """
        :param value: None or dict of client properties used to override the
            fields in the default client properties reported to RabbitMQ via
            `Connection.StartOk` method.
        """
        if not isinstance(value, (
                dict,
                type(None),
        )):
            raise TypeError('client_properties must be dict or None, '
                            'but got %r' % (value,))
        # Copy the mutable object to avoid accidental side-effects
        self._client_properties = copy.deepcopy(value)

    @property
    def connection_attempts(self):
        """
        :returns: number of socket connection attempts. Defaults to
            `DEFAULT_CONNECTION_ATTEMPTS`. See also `retry_delay`.
        :rtype: int

        """
        return self._connection_attempts

    @connection_attempts.setter
    def connection_attempts(self, value):
        """
        :param int value: number of socket connection attempts of at least 1.
            See also `retry_delay`.

        """
        if not isinstance(value, numbers.Integral):
            raise TypeError('connection_attempts must be an int')
        if value < 1:
            raise ValueError(
                'connection_attempts must be > 0, but got %r' % (value,))
        self._connection_attempts = value

    @property
    def credentials(self):
        """
        :rtype: one of the classes from `pika.credentials.VALID_TYPES`. Defaults
            to `DEFAULT_CREDENTIALS`.

        """
        return self._credentials

    @credentials.setter
    def credentials(self, value):
        """
        :param value: authentication credential object of one of the classes
            from  `pika.credentials.VALID_TYPES`

        """
        if not isinstance(value, tuple(pika.credentials.VALID_TYPES)):
            raise TypeError('credentials must be an object of type: %r, but '
                            'got %r' % (pika.credentials.VALID_TYPES, value))
        # Copy the mutable object to avoid accidental side-effects
        self._credentials = copy.deepcopy(value)

    @property
    def frame_max(self):
        """
        :returns: desired maximum AMQP frame size to use. Defaults to
            `DEFAULT_FRAME_MAX`.
        :rtype: int

        """
        return self._frame_max

    @frame_max.setter
    def frame_max(self, value):
        """
        :param int value: desired maximum AMQP frame size to use between
            `spec.FRAME_MIN_SIZE` and `spec.FRAME_MAX_SIZE`, inclusive

        """
        if not isinstance(value, numbers.Integral):
            raise TypeError('frame_max must be an int, but got %r' % (value,))
        if value < spec.FRAME_MIN_SIZE:
            raise ValueError('Min AMQP 0.9.1 Frame Size is %i, but got %r' % (
                spec.FRAME_MIN_SIZE,
                value,
            ))
        elif value > spec.FRAME_MAX_SIZE:
            raise ValueError('Max AMQP 0.9.1 Frame Size is %i, but got %r' % (
                spec.FRAME_MAX_SIZE,
                value,
            ))
        self._frame_max = value

    @property
    def heartbeat(self):
        """
        :returns: AMQP connection heartbeat timeout value for negotiation during
            connection tuning or callable which is invoked during connection tuning.
            None to accept broker's value. 0 turns heartbeat off. Defaults to
            `DEFAULT_HEARTBEAT_TIMEOUT`.
        :rtype: int|callable|None

        """
        return self._heartbeat

    @heartbeat.setter
    def heartbeat(self, value):
        """
        :param int|None|callable value: Controls AMQP heartbeat timeout negotiation
            during connection tuning. An integer value always overrides the value
            proposed by broker. Use 0 to deactivate heartbeats and None to always
            accept the broker's proposal. If a callable is given, it will be called
            with the connection instance and the heartbeat timeout proposed by broker
            as its arguments. The callback should return a non-negative integer that
            will be used to override the broker's proposal.
        """
        if value is not None:
            if not isinstance(value, numbers.Integral) and not callable(value):
                raise TypeError(
                    'heartbeat must be an int or a callable function, but got %r'
                    % (value,))
            if not callable(value) and value < 0:
                raise ValueError('heartbeat must >= 0, but got %r' % (value,))
        self._heartbeat = value

    @property
    def host(self):
        """
        :returns: hostname or ip address of broker. Defaults to `DEFAULT_HOST`.
        :rtype: str

        """
        return self._host

    @host.setter
    def host(self, value):
        """
        :param str value: hostname or ip address of broker

        """
        validators.require_string(value, 'host')
        self._host = value

    @property
    def locale(self):
        """
        :returns: locale value to pass to broker; e.g., 'en_US'. Defaults to
            `DEFAULT_LOCALE`.
        :rtype: str

        """
        return self._locale

    @locale.setter
    def locale(self, value):
        """
        :param str value: locale value to pass to broker; e.g., "en_US"

        """
        validators.require_string(value, 'locale')
        self._locale = value

    @property
    def port(self):
        """
        :returns: port number of broker's listening socket. Defaults to
            `DEFAULT_PORT`.
        :rtype: int

        """
        return self._port

    @port.setter
    def port(self, value):
        """
        :param int value: port number of broker's listening socket

        """
        try:
            self._port = int(value)
        except (TypeError, ValueError):
            raise TypeError('port must be an int, but got %r' % (value,))

    @property
    def retry_delay(self):
        """
        :returns: interval between socket connection attempts; see also
            `connection_attempts`. Defaults to `DEFAULT_RETRY_DELAY`.
        :rtype: float

        """
        return self._retry_delay

    @retry_delay.setter
    def retry_delay(self, value):
        """
        :param int | float value: interval between socket connection attempts;
            see also `connection_attempts`.

        """
        if not isinstance(value, numbers.Real):
            raise TypeError(
                'retry_delay must be a float or int, but got %r' % (value,))
        self._retry_delay = value

    @property
    def socket_timeout(self):
        """
        :returns: socket connect timeout in seconds. Defaults to
            `DEFAULT_SOCKET_TIMEOUT`. The value None disables this timeout.
        :rtype: float|None

        """
        return self._socket_timeout

    @socket_timeout.setter
    def socket_timeout(self, value):
        """
        :param int | float | None value: positive socket connect timeout in
            seconds. None to disable this timeout.

        """
        if value is not None:
            if not isinstance(value, numbers.Real):
                raise TypeError('socket_timeout must be a float or int, '
                                'but got %r' % (value,))
            if value <= 0:
                raise ValueError(
                    'socket_timeout must be > 0, but got %r' % (value,))
            value = float(value)

        self._socket_timeout = value

    @property
    def stack_timeout(self):
        """
        :returns: full protocol stack TCP/[SSL]/AMQP bring-up timeout in
            seconds. Defaults to `DEFAULT_STACK_TIMEOUT`. The value None
            disables this timeout.
        :rtype: float

        """
        return self._stack_timeout

    @stack_timeout.setter
    def stack_timeout(self, value):
        """
        :param int | float | None value: positive full protocol stack
            TCP/[SSL]/AMQP bring-up timeout in seconds. It's recommended to set
            this value higher than `socket_timeout`. None to disable this
            timeout.

        """
        if value is not None:
            if not isinstance(value, numbers.Real):
                raise TypeError('stack_timeout must be a float or int, '
                                'but got %r' % (value,))
            if value <= 0:
                raise ValueError(
                    'stack_timeout must be > 0, but got %r' % (value,))
            value = float(value)

        self._stack_timeout = value

    @property
    def ssl_options(self):
        """
        :returns: None for plaintext or `pika.SSLOptions` instance for SSL/TLS.
        :rtype: `pika.SSLOptions`|None
        """
        return self._ssl_options

    @ssl_options.setter
    def ssl_options(self, value):
        """
        :param `pika.SSLOptions`|None value: None for plaintext or
            `pika.SSLOptions` instance for SSL/TLS. Defaults to None.

        """
        if not isinstance(value, (SSLOptions, type(None))):
            raise TypeError(
                'ssl_options must be None or SSLOptions but got %r' % (value,))
        self._ssl_options = value

    @property
    def virtual_host(self):
        """
        :returns: rabbitmq virtual host name. Defaults to
            `DEFAULT_VIRTUAL_HOST`.
        :rtype: str

        """
        return self._virtual_host

    @virtual_host.setter
    def virtual_host(self, value):
        """
        :param str value: rabbitmq virtual host name

        """
        validators.require_string(value, 'virtual_host')
        self._virtual_host = value

    @property
    def tcp_options(self):
        """
        :returns: None or a dict of options to pass to the underlying socket
        :rtype: dict|None
        """
        return self._tcp_options

    @tcp_options.setter
    def tcp_options(self, value):
        """
        :param dict|None value: None or a dict of options to pass to the underlying
            socket. Currently supported are TCP_KEEPIDLE, TCP_KEEPINTVL, TCP_KEEPCNT
            and TCP_USER_TIMEOUT. Availability of these may depend on your platform.
        """
        if not isinstance(value, (dict, type(None))):
            raise TypeError(
                'tcp_options must be a dict or None, but got %r' % (value,))
        self._tcp_options = value


class ConnectionParameters(Parameters):
    """Connection parameters object that is passed into the connection adapter
    upon construction."""

    # Protect against accidental assignment of an invalid attribute
    __slots__ = ()

    class _DEFAULT(object):
        """Designates default parameter value; internal use"""

    def __init__( # pylint: disable=R0913,R0914
            self,
            host=_DEFAULT,
            port=_DEFAULT,
            virtual_host=_DEFAULT,
            credentials=_DEFAULT,
            channel_max=_DEFAULT,
            frame_max=_DEFAULT,
            heartbeat=_DEFAULT,
            ssl_options=_DEFAULT,
            connection_attempts=_DEFAULT,
            retry_delay=_DEFAULT,
            socket_timeout=_DEFAULT,
            stack_timeout=_DEFAULT,
            locale=_DEFAULT,
            blocked_connection_timeout=_DEFAULT,
            client_properties=_DEFAULT,
            tcp_options=_DEFAULT,
            **kwargs):
        """Create a new ConnectionParameters instance. See `Parameters` for
        default values.

        :param str host: Hostname or IP Address to connect to
        :param int port: TCP port to connect to
        :param str virtual_host: RabbitMQ virtual host to use
        :param pika.credentials.Credentials credentials: auth credentials
        :param int channel_max: Maximum number of channels to allow
        :param int frame_max: The maximum byte size for an AMQP frame
        :param int|None|callable heartbeat: Controls AMQP heartbeat timeout negotiation
            during connection tuning. An integer value always overrides the value
            proposed by broker. Use 0 to deactivate heartbeats and None to always
            accept the broker's proposal. If a callable is given, it will be called
            with the connection instance and the heartbeat timeout proposed by broker
            as its arguments. The callback should return a non-negative integer that
            will be used to override the broker's proposal.
        :param `pika.SSLOptions`|None ssl_options: None for plaintext or
            `pika.SSLOptions` instance for SSL/TLS. Defaults to None.
        :param int connection_attempts: Maximum number of retry attempts
        :param int|float retry_delay: Time to wait in seconds, before the next
        :param int|float socket_timeout: Positive socket connect timeout in
            seconds.
        :param int|float stack_timeout: Positive full protocol stack
            (TCP/[SSL]/AMQP) bring-up timeout in seconds. It's recommended to
            set this value higher than `socket_timeout`.
        :param str locale: Set the locale value
        :param int|float|None blocked_connection_timeout: If not None,
            the value is a non-negative timeout, in seconds, for the
            connection to remain blocked (triggered by Connection.Blocked from
            broker); if the timeout expires before connection becomes unblocked,
            the connection will be torn down, triggering the adapter-specific
            mechanism for informing client app about the closed connection:
            passing `ConnectionBlockedTimeout` exception to on_close_callback
            in asynchronous adapters or raising it in `BlockingConnection`.
        :param client_properties: None or dict of client properties used to
            override the fields in the default client properties reported to
            RabbitMQ via `Connection.StartOk` method.
        :param tcp_options: None or a dict of TCP options to set for socket
        """
        super(ConnectionParameters, self).__init__()

        if blocked_connection_timeout is not self._DEFAULT:
            self.blocked_connection_timeout = blocked_connection_timeout

        if channel_max is not self._DEFAULT:
            self.channel_max = channel_max

        if client_properties is not self._DEFAULT:
            self.client_properties = client_properties

        if connection_attempts is not self._DEFAULT:
            self.connection_attempts = connection_attempts

        if credentials is not self._DEFAULT:
            self.credentials = credentials

        if frame_max is not self._DEFAULT:
            self.frame_max = frame_max

        if heartbeat is not self._DEFAULT:
            self.heartbeat = heartbeat

        if host is not self._DEFAULT:
            self.host = host

        if locale is not self._DEFAULT:
            self.locale = locale

        if retry_delay is not self._DEFAULT:
            self.retry_delay = retry_delay

        if socket_timeout is not self._DEFAULT:
            self.socket_timeout = socket_timeout

        if stack_timeout is not self._DEFAULT:
            self.stack_timeout = stack_timeout

        if ssl_options is not self._DEFAULT:
            self.ssl_options = ssl_options

        # Set port after SSL status is known
        if port is not self._DEFAULT:
            self.port = port
        else:
            self.port = self.DEFAULT_SSL_PORT if self.ssl_options else self.DEFAULT_PORT

        if virtual_host is not self._DEFAULT:
            self.virtual_host = virtual_host

        if tcp_options is not self._DEFAULT:
            self.tcp_options = tcp_options

        if kwargs:
            raise TypeError('unexpected kwargs: %r' % (kwargs,))


class URLParameters(Parameters):
    """Connect to RabbitMQ via an AMQP URL in the format::

         amqp://username:password@host:port/<virtual_host>[?query-string]

    Ensure that the virtual host is URI encoded when specified. For example if
    you are using the default "/" virtual host, the value should be `%2f`.

    See `Parameters` for default values.

    Valid query string values are:

        - channel_max:
            Override the default maximum channel count value
        - client_properties:
            dict of client properties used to override the fields in the default
            client properties reported to RabbitMQ via `Connection.StartOk`
            method
        - connection_attempts:
            Specify how many times pika should try and reconnect before it gives up
        - frame_max:
            Override the default maximum frame size for communication
        - heartbeat:
            Desired connection heartbeat timeout for negotiation. If not present
            the broker's value is accepted. 0 turns heartbeat off.
        - locale:
            Override the default `en_US` locale value
        - ssl_options:
            None for plaintext; for SSL: dict of public ssl context-related
            arguments that may be passed to :meth:`ssl.SSLSocket` as kwargs,
            except `sock`, `server_side`,`do_handshake_on_connect`, `family`,
            `type`, `proto`, `fileno`.
        - retry_delay:
            The number of seconds to sleep before attempting to connect on
            connection failure.
        - socket_timeout:
            Socket connect timeout value in seconds (float or int)
        - stack_timeout:
            Positive full protocol stack (TCP/[SSL]/AMQP) bring-up timeout in
            seconds. It's recommended to set this value higher than
            `socket_timeout`.
        - blocked_connection_timeout:
            Set the timeout, in seconds, that the connection may remain blocked
            (triggered by Connection.Blocked from broker); if the timeout
            expires before connection becomes unblocked, the connection will be
            torn down, triggering the connection's on_close_callback
        - tcp_options:
            Set the tcp options for the underlying socket.

    :param str url: The AMQP URL to connect to

    """

    # Protect against accidental assignment of an invalid attribute
    __slots__ = ('_all_url_query_values',)

    # The name of the private function for parsing and setting a given URL query
    # arg is constructed by catenating the query arg's name to this prefix
    _SETTER_PREFIX = '_set_url_'

    def __init__(self, url):
        """Create a new URLParameters instance.

        :param str url: The URL value

        """
        super(URLParameters, self).__init__()

        self._all_url_query_values = None

        # Handle the Protocol scheme
        #
        # Fix up scheme amqp(s) to http(s) so urlparse won't barf on python
        # prior to 2.7. On Python 2.6.9,
        # `urlparse('amqp://127.0.0.1/%2f?socket_timeout=1')` produces an
        # incorrect path='/%2f?socket_timeout=1'
        if url[0:4].lower() == 'amqp':
            url = 'http' + url[4:]

        parts = pika.compat.urlparse(url)

        if parts.scheme == 'https':
            # Create default context which will get overridden by the
            # ssl_options URL arg, if any
            self.ssl_options = pika.SSLOptions(
                context=ssl.create_default_context())
        elif parts.scheme == 'http':
            self.ssl_options = None
        elif parts.scheme:
            raise ValueError('Unexpected URL scheme %r; supported scheme '
                             'values: amqp, amqps' % (parts.scheme,))

        if parts.hostname is not None:
            self.host = parts.hostname

        # Take care of port after SSL status is known
        if parts.port is not None:
            self.port = parts.port
        else:
            self.port = (self.DEFAULT_SSL_PORT
                         if self.ssl_options else self.DEFAULT_PORT)

        if parts.username is not None:
            self.credentials = pika.credentials.PlainCredentials(
                url_unquote(parts.username), url_unquote(parts.password))

        # Get the Virtual Host
        if len(parts.path) > 1:
            self.virtual_host = url_unquote(parts.path.split('/')[1])

        # Handle query string values, validating and assigning them
        self._all_url_query_values = pika.compat.url_parse_qs(parts.query)

        for name, value in dict_iteritems(self._all_url_query_values):
            try:
                set_value = getattr(self, self._SETTER_PREFIX + name)
            except AttributeError:
                raise ValueError('Unknown URL parameter: %r' % (name,))

            try:
                (value,) = value
            except ValueError:
                raise ValueError(
                    'Expected exactly one value for URL parameter '
                    '%s, but got %i values: %s' % (name, len(value), value))

            set_value(value)

    def _set_url_blocked_connection_timeout(self, value):
        """Deserialize and apply the corresponding query string arg"""
        try:
            blocked_connection_timeout = float(value)
        except ValueError as exc:
            raise ValueError(
                'Invalid blocked_connection_timeout value %r: %r' % (
                    value,
                    exc,
                ))
        self.blocked_connection_timeout = blocked_connection_timeout

    def _set_url_channel_max(self, value):
        """Deserialize and apply the corresponding query string arg"""
        try:
            channel_max = int(value)
        except ValueError as exc:
            raise ValueError('Invalid channel_max value %r: %r' % (
                value,
                exc,
            ))
        self.channel_max = channel_max

    def _set_url_client_properties(self, value):
        """Deserialize and apply the corresponding query string arg"""
        self.client_properties = ast.literal_eval(value)

    def _set_url_connection_attempts(self, value):
        """Deserialize and apply the corresponding query string arg"""
        try:
            connection_attempts = int(value)
        except ValueError as exc:
            raise ValueError('Invalid connection_attempts value %r: %r' % (
                value,
                exc,
            ))
        self.connection_attempts = connection_attempts

    def _set_url_frame_max(self, value):
        """Deserialize and apply the corresponding query string arg"""
        try:
            frame_max = int(value)
        except ValueError as exc:
            raise ValueError('Invalid frame_max value %r: %r' % (
                value,
                exc,
            ))
        self.frame_max = frame_max

    def _set_url_heartbeat(self, value):
        """Deserialize and apply the corresponding query string arg"""
        try:
            heartbeat_timeout = int(value)
        except ValueError as exc:
            raise ValueError('Invalid heartbeat value %r: %r' % (
                value,
                exc,
            ))
        self.heartbeat = heartbeat_timeout

    def _set_url_locale(self, value):
        """Deserialize and apply the corresponding query string arg"""
        self.locale = value

    def _set_url_retry_delay(self, value):
        """Deserialize and apply the corresponding query string arg"""
        try:
            retry_delay = float(value)
        except ValueError as exc:
            raise ValueError('Invalid retry_delay value %r: %r' % (
                value,
                exc,
            ))
        self.retry_delay = retry_delay

    def _set_url_socket_timeout(self, value):
        """Deserialize and apply the corresponding query string arg"""
        try:
            socket_timeout = float(value)
        except ValueError as exc:
            raise ValueError('Invalid socket_timeout value %r: %r' % (
                value,
                exc,
            ))
        self.socket_timeout = socket_timeout

    def _set_url_stack_timeout(self, value):
        """Deserialize and apply the corresponding query string arg"""
        try:
            stack_timeout = float(value)
        except ValueError as exc:
            raise ValueError('Invalid stack_timeout value %r: %r' % (
                value,
                exc,
            ))
        self.stack_timeout = stack_timeout

    def _set_url_ssl_options(self, value):
        """Deserialize and apply the corresponding query string arg

        """
        opts = ast.literal_eval(value)
        if opts is None:
            if self.ssl_options is not None:
                raise ValueError(
                    'Specified ssl_options=None URI arg is inconsistent with '
                    'the specified amqps URI scheme.')
        else:
            # Older versions of Pika would take the opts dict and pass it
            # directly as kwargs to the deprecated ssl.wrap_socket method.
            # Here, we take the valid options and translate them into args
            # for various SSLContext methods.
            #
            # https://docs.python.org/3/library/ssl.html#ssl.wrap_socket
            #
            # SSLContext.load_verify_locations(cafile=None, capath=None, cadata=None)
            try:
                opt_protocol = ssl.PROTOCOL_TLS_CLIENT
            except AttributeError:
                opt_protocol = ssl.PROTOCOL_TLSv1_2
            if 'protocol' in opts:
                opt_protocol = opts['protocol']

            cxt = ssl.SSLContext(protocol=opt_protocol)

            opt_cafile = opts.get('ca_certs') or opts.get('cafile')
            opt_capath = opts.get('ca_path') or opts.get('capath')
            opt_cadata = opts.get('ca_data') or opts.get('cadata')
            cxt.load_verify_locations(opt_cafile, opt_capath, opt_cadata)

            # SSLContext.load_cert_chain(certfile, keyfile=None, password=None)
            if 'certfile' in opts:
                opt_certfile = opts['certfile']
                opt_keyfile = opts.get('keyfile')
                opt_password = opts.get('password')
                cxt.load_cert_chain(opt_certfile, opt_keyfile, opt_password)

            if 'ciphers' in opts:
                opt_ciphers = opts['ciphers']
                cxt.set_ciphers(opt_ciphers)

            server_hostname = opts.get('server_hostname')
            self.ssl_options = pika.SSLOptions(
                context=cxt, server_hostname=server_hostname)

    def _set_url_tcp_options(self, value):
        """Deserialize and apply the corresponding query string arg"""
        self.tcp_options = ast.literal_eval(value)


class SSLOptions(object):
    """Class used to provide parameters for optional fine grained control of SSL
    socket wrapping.

    """

    # Protect against accidental assignment of an invalid attribute
    __slots__ = ('context', 'server_hostname')

    def __init__(self, context, server_hostname=None):
        """
        :param ssl.SSLContext context: SSLContext instance
        :param str|None server_hostname: SSLContext.wrap_socket, used to enable
            SNI
        """
        if not isinstance(context, ssl.SSLContext):
            raise TypeError(
                'context must be of ssl.SSLContext type, but got {!r}'.format(
                    context))

        self.context = context
        self.server_hostname = server_hostname


class Connection(pika.compat.AbstractBase):
    """This is the core class that implements communication with RabbitMQ. This
    class should not be invoked directly but rather through the use of an
    adapter such as SelectConnection or BlockingConnection.

    """

    # Disable pylint messages concerning "method could be a function"
    # pylint: disable=R0201

    ON_CONNECTION_CLOSED = '_on_connection_closed'
    ON_CONNECTION_ERROR = '_on_connection_error'
    ON_CONNECTION_OPEN_OK = '_on_connection_open_ok'
    CONNECTION_CLOSED = 0
    CONNECTION_INIT = 1
    CONNECTION_PROTOCOL = 2
    CONNECTION_START = 3
    CONNECTION_TUNE = 4
    CONNECTION_OPEN = 5
    CONNECTION_CLOSING = 6  # client-initiated close in progress

    _STATE_NAMES = {
        CONNECTION_CLOSED: 'CLOSED',
        CONNECTION_INIT: 'INIT',
        CONNECTION_PROTOCOL: 'PROTOCOL',
        CONNECTION_START: 'START',
        CONNECTION_TUNE: 'TUNE',
        CONNECTION_OPEN: 'OPEN',
        CONNECTION_CLOSING: 'CLOSING'
    }

    def __init__(self,
                 parameters=None,
                 on_open_callback=None,
                 on_open_error_callback=None,
                 on_close_callback=None,
                 internal_connection_workflow=True):
        """Connection initialization expects an object that has implemented the
         Parameters class and a callback function to notify when we have
         successfully connected to the AMQP Broker.

        Available Parameters classes are the ConnectionParameters class and
        URLParameters class.

        :param pika.connection.Parameters parameters: Read-only connection
            parameters.
        :param callable on_open_callback: Called when the connection is opened:
            on_open_callback(connection)
        :param None | method on_open_error_callback: Called if the connection
            can't be established or connection establishment is interrupted by
            `Connection.close()`: on_open_error_callback(Connection, exception).
        :param None | method on_close_callback: Called when a previously fully
            open connection is closed:
            `on_close_callback(Connection, exception)`, where `exception` is
            either an instance of `exceptions.ConnectionClosed` if closed by
            user or broker or exception of another type that describes the cause
            of connection failure.
        :param bool internal_connection_workflow: True for autonomous connection
            establishment which is default; False for externally-managed
            connection workflow via the `create_connection()` factory.

        """
        self.connection_state = self.CONNECTION_CLOSED

        # Determines whether we invoke the on_open_error_callback or
        # on_close_callback. So that we don't lose track when state transitions
        # to CONNECTION_CLOSING as the result of Connection.close() call during
        # opening.
        self._opened = False

        # Value to pass to on_open_error_callback or on_close_callback when
        # connection fails to be established or becomes closed
        self._error = None  # type: Exception

        # Used to hold timer if configured for Connection.Blocked timeout
        self._blocked_conn_timer = None

        self._heartbeat_checker = None

        # Set our configuration options
        if parameters is not None:
            # NOTE: Work around inability to copy ssl.SSLContext contained in
            # our SSLOptions; ssl.SSLContext fails to implement __getnewargs__
            saved_ssl_options = parameters.ssl_options
            parameters.ssl_options = None
            try:
                self.params = copy.deepcopy(parameters)
                self.params.ssl_options = saved_ssl_options
            finally:
                parameters.ssl_options = saved_ssl_options
        else:
            self.params = ConnectionParameters()

        self._internal_connection_workflow = internal_connection_workflow

        # Define our callback dictionary
        self.callbacks = pika.callback.CallbackManager()

        # Attributes that will be properly initialized by _init_connection_state
        # and/or during connection handshake.
        self.server_capabilities = None
        self.server_properties = None
        self._body_max_length = None
        self.known_hosts = None
        self._frame_buffer = None
        self._channels = None

        self._init_connection_state()

        # Add the on connection error callback
        self.callbacks.add(
            0, self.ON_CONNECTION_ERROR, on_open_error_callback or
            self._default_on_connection_error, False)

        # On connection callback
        if on_open_callback:
            self.add_on_open_callback(on_open_callback)

        # On connection callback
        if on_close_callback:
            self.add_on_close_callback(on_close_callback)

        self._set_connection_state(self.CONNECTION_INIT)

        if self._internal_connection_workflow:
            # Kick off full-stack connection establishment. It will complete
            # asynchronously.
            self._adapter_connect_stream()
        else:
            # Externally-managed connection workflow will proceed asynchronously
            # using adapter-specific mechanism
            LOGGER.debug('Using external connection workflow.')

    def _init_connection_state(self):
        """Initialize or reset all of the internal state variables for a given
        connection. On disconnect or reconnect all of the state needs to
        be wiped.

        """
        # TODO: probably don't need the state recovery logic since we don't
        #       test re-connection sufficiently (if at all), and users should
        #       just create a new instance of Connection when needed.
        # So, just merge the pertinent logic into the constructor.

        # Connection state
        self._set_connection_state(self.CONNECTION_CLOSED)

        # Negotiated server properties
        self.server_properties = None

        # Inbound buffer for decoding frames
        self._frame_buffer = bytes()

        # Dict of open channels
        self._channels = dict()

        # Data used for Heartbeat checking and back-pressure detection
        self.bytes_sent = 0
        self.bytes_received = 0
        self.frames_sent = 0
        self.frames_received = 0
        self._heartbeat_checker = None

        # When closing, holds reason why
        self._error = None

        # Our starting point once connected, first frame received
        self._add_connection_start_callback()

        # Add a callback handler for the Broker telling us to disconnect.
        # NOTE: As of RabbitMQ 3.6.0, RabbitMQ broker may send Connection.Close
        # to signal error during connection setup (and wait a longish time
        # before closing the TCP/IP stream). Earlier RabbitMQ versions
        # simply closed the TCP/IP stream.
        self.callbacks.add(0, spec.Connection.Close,
                           self._on_connection_close_from_broker)

        if self.params.blocked_connection_timeout is not None:
            if self._blocked_conn_timer is not None:
                # Blocked connection timer was active when teardown was
                # initiated
                self._adapter_remove_timeout(self._blocked_conn_timer)
                self._blocked_conn_timer = None

            self.add_on_connection_blocked_callback(self._on_connection_blocked)
            self.add_on_connection_unblocked_callback(
                self._on_connection_unblocked)

    def add_on_close_callback(self, callback):
        """Add a callback notification when the connection has closed. The
        callback will be passed the connection and an exception instance. The
        exception will either be an instance of `exceptions.ConnectionClosed` if
        a fully-open connection was closed by user or broker or exception of
        another type that describes the cause of connection closure/failure.

        :param callable callback: Callback to call on close, having the signature:
            callback(pika.connection.Connection, exception)

        """
        validators.require_callback(callback)
        self.callbacks.add(0, self.ON_CONNECTION_CLOSED, callback, False)

    def add_on_connection_blocked_callback(self, callback):
        """RabbitMQ AMQP extension - Add a callback to be notified when the
        connection gets blocked (`Connection.Blocked` received from RabbitMQ)
        due to the broker running low on resources (memory or disk). In this
        state RabbitMQ suspends processing incoming data until the connection
        is unblocked, so it's a good idea for publishers receiving this
        notification to suspend publishing until the connection becomes
        unblocked.

        See also `Connection.add_on_connection_unblocked_callback()`

        See also `ConnectionParameters.blocked_connection_timeout`.

        :param callable callback: Callback to call on `Connection.Blocked`,
            having the signature `callback(connection, pika.frame.Method)`,
            where the method frame's `method` member is of type
            `pika.spec.Connection.Blocked`

        """
        validators.require_callback(callback)
        self.callbacks.add(
            0,
            spec.Connection.Blocked,
            functools.partial(callback, self),
            one_shot=False)

    def add_on_connection_unblocked_callback(self, callback):
        """RabbitMQ AMQP extension - Add a callback to be notified when the
        connection gets unblocked (`Connection.Unblocked` frame is received from
        RabbitMQ) letting publishers know it's ok to start publishing again.

        :param callable callback: Callback to call on
            `Connection.Unblocked`, having the signature
            `callback(connection, pika.frame.Method)`, where the method frame's
            `method` member is of type `pika.spec.Connection.Unblocked`

        """
        validators.require_callback(callback)
        self.callbacks.add(
            0,
            spec.Connection.Unblocked,
            functools.partial(callback, self),
            one_shot=False)

    def add_on_open_callback(self, callback):
        """Add a callback notification when the connection has opened. The
        callback will be passed the connection instance as its only arg.

        :param callable callback: Callback to call when open

        """
        validators.require_callback(callback)
        self.callbacks.add(0, self.ON_CONNECTION_OPEN_OK, callback, False)

    def add_on_open_error_callback(self, callback, remove_default=True):
        """Add a callback notification when the connection can not be opened.

        The callback method should accept the connection instance that could not
        connect, and either a string or an exception as its second arg.

        :param callable callback: Callback to call when can't connect, having
            the signature _(Connection, Exception)
        :param bool remove_default: Remove default exception raising callback

        """
        validators.require_callback(callback)
        if remove_default:
            self.callbacks.remove(0, self.ON_CONNECTION_ERROR,
                                  self._default_on_connection_error)
        self.callbacks.add(0, self.ON_CONNECTION_ERROR, callback, False)

    def channel(self, channel_number=None, on_open_callback=None):
        """Create a new channel with the next available channel number or pass
        in a channel number to use. Must be non-zero if you would like to
        specify but it is recommended that you let Pika manage the channel
        numbers.

        :param int channel_number: The channel number to use, defaults to the
                                   next available.
        :param callable on_open_callback: The callback when the channel is
            opened.  The callback will be invoked with the `Channel` instance
            as its only argument.
        :rtype: pika.channel.Channel

        """
        if not self.is_open:
            raise exceptions.ConnectionWrongStateError(
                'Channel allocation requires an open connection: %s' % self)

        validators.rpc_completion_callback(on_open_callback)

        if not channel_number:
            channel_number = self._next_channel_number()

        self._channels[channel_number] = self._create_channel(
            channel_number, on_open_callback)
        self._add_channel_callbacks(channel_number)
        self._channels[channel_number].open()
        return self._channels[channel_number]

    def update_secret(self, new_secret, reason, callback=None):
        """RabbitMQ AMQP extension - This method updates the secret used to authenticate this connection. 
        It is used when secrets have an expiration date and need to be renewed, like OAuth 2 tokens.
        Pass a callback to be notified of the response from the server.

        :param string new_secret: The new secret
        :param string reason: The reason for the secret update
        :param callable callback: Callback to call on
            `Connection.UpdateSecretOk`, having the signature
            `callback(pika.frame.Method)`, where the method frame's
            `method` member is of type `pika.spec.Connection.UpdateSecretOk`

        :raises pika.exceptions.ConnectionWrongStateError: if connection is
            not open.
        """
        if not self.is_open:
            raise exceptions.ConnectionWrongStateError(
                'Secret update requires an open connection: %s' % self)

        validators.rpc_completion_callback(callback)
        self._rpc(0, spec.Connection.UpdateSecret(new_secret, reason),
                  callback, [spec.Connection.UpdateSecretOk])

    def close(self, reply_code=200, reply_text='Normal shutdown'):
        """Disconnect from RabbitMQ. If there are any open channels, it will
        attempt to close them prior to fully disconnecting. Channels which
        have active consumers will attempt to send a Basic.Cancel to RabbitMQ
        to cleanly stop the delivery of messages prior to closing the channel.

        :param int reply_code: The code number for the close
        :param str reply_text: The text reason for the close

        :raises pika.exceptions.ConnectionWrongStateError: if connection is
            closed or closing.
        """
        if self.is_closing or self.is_closed:
            msg = ('Illegal close({}, {!r}) request on {} because it '
                   'was called while connection state={}.'.format(
                       reply_code, reply_text, self,
                       self._STATE_NAMES[self.connection_state]))
            LOGGER.error(msg)
            raise exceptions.ConnectionWrongStateError(msg)

        # NOTE The connection is either in opening or open state

        # Initiate graceful closing of channels that are OPEN or OPENING
        if self._channels:
            self._close_channels(reply_code, reply_text)

        prev_state = self.connection_state

        # Transition to closing
        self._set_connection_state(self.CONNECTION_CLOSING)
        LOGGER.info("Closing connection (%s): %r", reply_code, reply_text)

        if not self._opened:
            # It was opening, but not fully open yet, so we won't attempt
            # graceful AMQP Connection.Close.
            LOGGER.info('Connection.close() is terminating stream and '
                        'bypassing graceful AMQP close, since AMQP is still '
                        'opening.')

            error = exceptions.ConnectionOpenAborted(
                'Connection.close() called before connection '
                'finished opening: prev_state={} ({}): {!r}'.format(
                    self._STATE_NAMES[prev_state], reply_code, reply_text))
            self._terminate_stream(error)

        else:
            self._error = exceptions.ConnectionClosedByClient(
                reply_code, reply_text)

            # If there are channels that haven't finished closing yet, then
            # _on_close_ready will finally be called from _on_channel_cleanup once
            # all channels have been closed
            if not self._channels:
                # We can initiate graceful closing of the connection right away,
                # since no more channels remain
                self._on_close_ready()
            else:
                LOGGER.info(
                    'Connection.close is waiting for %d channels to close: %s',
                    len(self._channels), self)

    #
    # Connection state properties
    #

    @property
    def is_closed(self):
        """
        Returns a boolean reporting the current connection state.
        """
        return self.connection_state == self.CONNECTION_CLOSED

    @property
    def is_closing(self):
        """
        Returns True if connection is in the process of closing due to
        client-initiated `close` request, but closing is not yet complete.
        """
        return self.connection_state == self.CONNECTION_CLOSING

    @property
    def is_open(self):
        """
        Returns a boolean reporting the current connection state.
        """
        return self.connection_state == self.CONNECTION_OPEN

    #
    # Properties that reflect server capabilities for the current connection
    #

    @property
    def basic_nack(self):
        """Specifies if the server supports basic.nack on the active connection.

        :rtype: bool

        """
        return self.server_capabilities.get('basic.nack', False)

    @property
    def consumer_cancel_notify(self):
        """Specifies if the server supports consumer cancel notification on the
        active connection.

        :rtype: bool

        """
        return self.server_capabilities.get('consumer_cancel_notify', False)

    @property
    def exchange_exchange_bindings(self):
        """Specifies if the active connection supports exchange to exchange
        bindings.

        :rtype: bool

        """
        return self.server_capabilities.get('exchange_exchange_bindings', False)

    @property
    def publisher_confirms(self):
        """Specifies if the active connection can use publisher confirmations.

        :rtype: bool

        """
        return self.server_capabilities.get('publisher_confirms', False)

    @abc.abstractmethod
    def _adapter_call_later(self, delay, callback):
        """Adapters should override to call the callback after the
        specified number of seconds have elapsed, using a timer, or a
        thread, or similar.

        :param float|int delay: The number of seconds to wait to call callback
        :param callable callback: The callback will be called without args.
        :returns: Handle that can be passed to `_adapter_remove_timeout()` to
            cancel the callback.
        :rtype: object

        """
        raise NotImplementedError

    @abc.abstractmethod
    def _adapter_remove_timeout(self, timeout_id):
        """Adapters should override: Remove a timeout

        :param opaque timeout_id: The timeout handle to remove

        """
        raise NotImplementedError

    @abc.abstractmethod
    def _adapter_add_callback_threadsafe(self, callback):
        """Requests a call to the given function as soon as possible in the
        context of this connection's IOLoop thread.

        NOTE: This is the only thread-safe method offered by the connection. All
         other manipulations of the connection must be performed from the
         connection's thread.

        :param callable callback: The callback method; must be callable.

        """
        raise NotImplementedError

    #
    # Internal methods for managing the communication process
    #
    @abc.abstractmethod
    def _adapter_connect_stream(self):
        """Subclasses should override to initiate stream connection
        workflow asynchronously. Upon failed or aborted completion, they must
        invoke `Connection._on_stream_terminated()`.

        NOTE: On success, the stack will be up already, so there is no
              corresponding callback.

        """
        raise NotImplementedError

    @abc.abstractmethod
    def _adapter_disconnect_stream(self):
        """Asynchronously bring down the streaming transport layer and invoke
        `Connection._on_stream_terminated()` asynchronously when complete.

        :raises: NotImplementedError

        """
        raise NotImplementedError

    @abc.abstractmethod
    def _adapter_emit_data(self, data):
        """Take ownership of data and send it to AMQP server as soon as
        possible.

        Subclasses must override this

        :param bytes data:

        """
        raise NotImplementedError

    def _add_channel_callbacks(self, channel_number):
        """Add the appropriate callbacks for the specified channel number.

        :param int channel_number: The channel number for the callbacks

        """
        # pylint: disable=W0212

        # This permits us to garbage-collect our reference to the channel
        # regardless of whether it was closed by client or broker, and do so
        # after all channel-close callbacks.
        self._channels[channel_number]._add_on_cleanup_callback(
            self._on_channel_cleanup)

    def _add_connection_start_callback(self):
        """Add a callback for when a Connection.Start frame is received from
        the broker.

        """
        self.callbacks.add(0, spec.Connection.Start, self._on_connection_start)

    def _add_connection_tune_callback(self):
        """Add a callback for when a Connection.Tune frame is received."""
        self.callbacks.add(0, spec.Connection.Tune, self._on_connection_tune)

    def _check_for_protocol_mismatch(self, value):
        """Invoked when starting a connection to make sure it's a supported
        protocol.

        :param pika.frame.Method value: The frame to check
        :raises: ProtocolVersionMismatch

        """
        if ((value.method.version_major, value.method.version_minor) !=
                spec.PROTOCOL_VERSION[0:2]):
            raise exceptions.ProtocolVersionMismatch(frame.ProtocolHeader(),
                                                     value)

    @property
    def _client_properties(self):
        """Return the client properties dictionary.

        :rtype: dict

        """
        properties = {
            'product': PRODUCT,
            'platform': 'Python %s' % platform.python_version(),
            'capabilities': {
                'authentication_failure_close': True,
                'basic.nack': True,
                'connection.blocked': True,
                'consumer_cancel_notify': True,
                'publisher_confirms': True
            },
            'information': 'See http://pika.rtfd.org',
            'version': pika.__version__
        }

        if self.params.client_properties:
            properties.update(self.params.client_properties)

        return properties

    def _close_channels(self, reply_code, reply_text):
        """Initiate graceful closing of channels that are in OPEN or OPENING
        states, passing reply_code and reply_text.

        :param int reply_code: The code for why the channels are being closed
        :param str reply_text: The text reason for why the channels are closing

        """
        assert self.is_open, str(self)

        for channel_number in dictkeys(self._channels):
            chan = self._channels[channel_number]
            if not (chan.is_closing or chan.is_closed):
                chan.close(reply_code, reply_text)

    def _create_channel(self, channel_number, on_open_callback):
        """Create a new channel using the specified channel number and calling
        back the method specified by on_open_callback

        :param int channel_number: The channel number to use
        :param callable on_open_callback: The callback when the channel is
            opened.  The callback will be invoked with the `Channel` instance
            as its only argument.

        """
        LOGGER.debug('Creating channel %s', channel_number)
        return pika.channel.Channel(self, channel_number, on_open_callback)

    def _create_heartbeat_checker(self):
        """Create a heartbeat checker instance if there is a heartbeat interval
        set.

        :rtype: pika.heartbeat.Heartbeat|None

        """
        if self.params.heartbeat is not None and self.params.heartbeat > 0:
            LOGGER.debug('Creating a HeartbeatChecker: %r',
                         self.params.heartbeat)
            return pika.heartbeat.HeartbeatChecker(self, self.params.heartbeat)

        return None

    def _remove_heartbeat(self):
        """Stop the heartbeat checker if it exists

        """
        if self._heartbeat_checker:
            self._heartbeat_checker.stop()
            self._heartbeat_checker = None

    def _deliver_frame_to_channel(self, value):
        """Deliver the frame to the channel specified in the frame.

        :param pika.frame.Method value: The frame to deliver

        """
        if not value.channel_number in self._channels:
            # This should never happen and would constitute breach of the
            # protocol
            LOGGER.critical(
                'Received %s frame for unregistered channel %i on %s',
                value.NAME, value.channel_number, self)
            return

        # pylint: disable=W0212
        self._channels[value.channel_number]._handle_content_frame(value)

    def _ensure_closed(self):
        """If the connection is not closed, close it."""
        if self.is_open:
            self.close()

    def _get_body_frame_max_length(self):
        """Calculate the maximum amount of bytes that can be in a body frame.

        :rtype: int

        """
        return (self.params.frame_max - spec.FRAME_HEADER_SIZE -
                spec.FRAME_END_SIZE)

    def _get_credentials(self, method_frame):
        """Get credentials for authentication.

        :param pika.frame.MethodFrame method_frame: The Connection.Start frame
        :rtype: tuple(str, str)

        """
        (auth_type,
         response) = self.params.credentials.response_for(method_frame.method)
        if not auth_type:
            raise exceptions.AuthenticationError(self.params.credentials.TYPE)
        self.params.credentials.erase_credentials()
        return auth_type, response

    def _has_pending_callbacks(self, value):
        """Return true if there are any callbacks pending for the specified
        frame.

        :param pika.frame.Method value: The frame to check
        :rtype: bool

        """
        return self.callbacks.pending(value.channel_number, value.method)

    def _is_method_frame(self, value):
        """Returns true if the frame is a method frame.

        :param pika.frame.Frame value: The frame to evaluate
        :rtype: bool

        """
        return isinstance(value, frame.Method)

    def _is_protocol_header_frame(self, value):
        """Returns True if it's a protocol header frame.

        :rtype: bool

        """
        return isinstance(value, frame.ProtocolHeader)

    def _next_channel_number(self):
        """Return the next available channel number or raise an exception.

        :rtype: int

        """
        limit = self.params.channel_max or pika.channel.MAX_CHANNELS
        if len(self._channels) >= limit:
            raise exceptions.NoFreeChannels()

        for num in xrange(1, len(self._channels) + 1):
            if num not in self._channels:
                return num
        return len(self._channels) + 1

    def _on_channel_cleanup(self, channel):
        """Remove the channel from the dict of channels when Channel.CloseOk is
        sent. If connection is closing and no more channels remain, proceed to
        `_on_close_ready`.

        :param pika.channel.Channel channel: channel instance

        """
        try:
            del self._channels[channel.channel_number]
            LOGGER.debug('Removed channel %s', channel.channel_number)
        except KeyError:
            LOGGER.error('Channel %r not in channels', channel.channel_number)
        if self.is_closing:
            if not self._channels:
                # Initiate graceful closing of the connection
                self._on_close_ready()
            else:
                # Once Connection enters CLOSING state, all remaining channels
                # should also be in CLOSING state. Deviation from this would
                # prevent Connection from completing its closing procedure.
                channels_not_in_closing_state = [
                    chan for chan in dict_itervalues(self._channels)
                    if not chan.is_closing
                ]
                if channels_not_in_closing_state:
                    LOGGER.critical(
                        'Connection in CLOSING state has non-CLOSING '
                        'channels: %r', channels_not_in_closing_state)

    def _on_close_ready(self):
        """Called when the Connection is in a state that it can close after
        a close has been requested by client. This happens after all of the
        channels are closed that were open when the close request was made.

        """
        if self.is_closed:
            LOGGER.warning('_on_close_ready invoked when already closed')
            return

        # NOTE: Assuming self._error is instance of exceptions.ConnectionClosed
        self._send_connection_close(self._error.reply_code,
                                    self._error.reply_text)

    def _on_stream_connected(self):
        """Invoked when the socket is connected and it's time to start speaking
        AMQP with the broker.

        """
        self._set_connection_state(self.CONNECTION_PROTOCOL)

        # Start the communication with the RabbitMQ Broker
        self._send_frame(frame.ProtocolHeader())

    def _on_blocked_connection_timeout(self):
        """ Called when the "connection blocked timeout" expires. When this
        happens, we tear down the connection

        """
        self._blocked_conn_timer = None
        self._terminate_stream(
            exceptions.ConnectionBlockedTimeout(
                'Blocked connection timeout expired.'))

    def _on_connection_blocked(self, _connection, method_frame):
        """Handle Connection.Blocked notification from RabbitMQ broker

        :param pika.frame.Method method_frame: method frame having `method`
            member of type `pika.spec.Connection.Blocked`
        """
        LOGGER.warning('Received %s from broker', method_frame)

        if self._blocked_conn_timer is not None:
            # RabbitMQ is not supposed to repeat Connection.Blocked, but it
            # doesn't hurt to be careful
            LOGGER.warning(
                '_blocked_conn_timer %s already set when '
                '_on_connection_blocked is called', self._blocked_conn_timer)
        else:
            self._blocked_conn_timer = self._adapter_call_later(
                self.params.blocked_connection_timeout,
                self._on_blocked_connection_timeout)

    def _on_connection_unblocked(self, _connection, method_frame):
        """Handle Connection.Unblocked notification from RabbitMQ broker

        :param pika.frame.Method method_frame: method frame having `method`
            member of type `pika.spec.Connection.Blocked`
        """
        LOGGER.info('Received %s from broker', method_frame)

        if self._blocked_conn_timer is None:
            # RabbitMQ is supposed to pair Connection.Blocked/Unblocked, but it
            # doesn't hurt to be careful
            LOGGER.warning('_blocked_conn_timer was not active when '
                           '_on_connection_unblocked called')
        else:
            self._adapter_remove_timeout(self._blocked_conn_timer)
            self._blocked_conn_timer = None

    def _on_connection_close_from_broker(self, method_frame):
        """Called when the connection is closed remotely via Connection.Close
        frame from broker.

        :param pika.frame.Method method_frame: The Connection.Close frame

        """
        LOGGER.debug('_on_connection_close_from_broker: frame=%s', method_frame)

        self._terminate_stream(
            exceptions.ConnectionClosedByBroker(method_frame.method.reply_code,
                                                method_frame.method.reply_text))

    def _on_connection_close_ok(self, method_frame):
        """Called when Connection.CloseOk is received from remote.

        :param pika.frame.Method method_frame: The Connection.CloseOk frame

        """
        LOGGER.debug('_on_connection_close_ok: frame=%s', method_frame)

        self._terminate_stream(None)

    def _default_on_connection_error(self, _connection_unused, error):
        """Default behavior when the connecting connection cannot connect and
        user didn't supply own `on_connection_error` callback.

        :raises: the given error

        """
        raise error

    def _on_connection_open_ok(self, method_frame):
        """
        This is called once we have tuned the connection with the server and
        called the Connection.Open on the server and it has replied with
        Connection.Ok.
        """
        self._opened = True

        self.known_hosts = method_frame.method.known_hosts

        # We're now connected at the AMQP level
        self._set_connection_state(self.CONNECTION_OPEN)

        # Call our initial callback that we're open
        self.callbacks.process(0, self.ON_CONNECTION_OPEN_OK, self, self)

    def _on_connection_start(self, method_frame):
        """This is called as a callback once we have received a Connection.Start
        from the server.

        :param pika.frame.Method method_frame: The frame received
        :raises: UnexpectedFrameError

        """
        self._set_connection_state(self.CONNECTION_START)

        try:
            if self._is_protocol_header_frame(method_frame):
                raise exceptions.UnexpectedFrameError(method_frame)
            self._check_for_protocol_mismatch(method_frame)
            self._set_server_information(method_frame)
            self._add_connection_tune_callback()
            self._send_connection_start_ok(*self._get_credentials(method_frame))
        except Exception as error:  # pylint: disable=W0703
            LOGGER.exception('Error processing Connection.Start.')
            self._terminate_stream(error)

    @staticmethod
    def _negotiate_integer_value(client_value, server_value):
        """Negotiates two values. If either of them is 0 or None,
        returns the other one. If both are positive integers, returns the
        smallest one.

        :param int client_value: The client value
        :param int server_value: The server value
        :rtype: int

        """
        if client_value is None:
            client_value = 0
        if server_value is None:
            server_value = 0

        # this is consistent with how Java client and Bunny
        # perform negotiation, see pika/pika#874
        if client_value == 0 or server_value == 0:
            val = max(client_value, server_value)
        else:
            val = min(client_value, server_value)

        return val

    @staticmethod
    def _tune_heartbeat_timeout(client_value, server_value):
        """ Determine heartbeat timeout per AMQP 0-9-1 rules

        Per https://www.rabbitmq.com/resources/specs/amqp0-9-1.pdf,

        > Both peers negotiate the limits to the lowest agreed value as follows:
        > - The server MUST tell the client what limits it proposes.
        > - The client responds and **MAY reduce those limits** for its
            connection

        If the client specifies a value, it always takes precedence.

        :param client_value: None to accept server_value; otherwise, an integral
            number in seconds; 0 (zero) to disable heartbeat.
        :param server_value: integral value of the heartbeat timeout proposed by
            broker; 0 (zero) to disable heartbeat.

        :returns: the value of the heartbeat timeout to use and return to broker
        :rtype: int
        """
        if client_value is None:
            # Accept server's limit
            timeout = server_value
        else:
            timeout = client_value

        return timeout

    def _on_connection_tune(self, method_frame):
        """Once the Broker sends back a Connection.Tune, we will set our tuning
        variables that have been returned to us and kick off the Heartbeat
        monitor if required, send our TuneOk and then the Connection. Open rpc
        call on channel 0.

        :param pika.frame.Method method_frame: The frame received

        """
        self._set_connection_state(self.CONNECTION_TUNE)

        # Get our max channels, frames and heartbeat interval
        self.params.channel_max = Connection._negotiate_integer_value(
            self.params.channel_max, method_frame.method.channel_max)
        self.params.frame_max = Connection._negotiate_integer_value(
            self.params.frame_max, method_frame.method.frame_max)

        if callable(self.params.heartbeat):
            ret_heartbeat = self.params.heartbeat(self,
                                                  method_frame.method.heartbeat)
            if ret_heartbeat is None or callable(ret_heartbeat):
                # Enforce callback-specific restrictions on callback's return value
                raise TypeError('heartbeat callback must not return None '
                                'or callable, but got %r' % (ret_heartbeat,))

            # Leave it to hearbeat setter deal with the rest of the validation
            self.params.heartbeat = ret_heartbeat

        # Negotiate heatbeat timeout
        self.params.heartbeat = self._tune_heartbeat_timeout(
            client_value=self.params.heartbeat,
            server_value=method_frame.method.heartbeat)

        # Calculate the maximum pieces for body frames
        self._body_max_length = self._get_body_frame_max_length()

        # Create a new heartbeat checker if needed
        self._heartbeat_checker = self._create_heartbeat_checker()

        # Send the TuneOk response with what we've agreed upon
        self._send_connection_tune_ok()

        # Send the Connection.Open RPC call for the vhost
        self._send_connection_open()

    def _on_data_available(self, data_in):
        """This is called by our Adapter, passing in the data from the socket.
        As long as we have buffer try and map out frame data.

        :param str data_in: The data that is available to read

        """
        self._frame_buffer += data_in

        while self._frame_buffer:
            consumed_count, frame_value = self._read_frame()
            if not frame_value:
                return
            self._trim_frame_buffer(consumed_count)
            self._process_frame(frame_value)

    def _terminate_stream(self, error):
        """Deactivate heartbeat instance if activated already, and initiate
        termination of the stream (TCP) connection asynchronously.

        When connection terminates, the appropriate user callback will be
        invoked with the given error: "on open error" or "on connection closed".

        :param Exception | None error: exception instance describing the reason
            for termination; None for normal closing, such as upon receipt of
            Connection.CloseOk.

        """
        assert isinstance(error, (type(None), Exception)), \
            'error arg is neither None nor instance of Exception: {!r}.'.format(
                error)

        if error is not None:
            # Save the exception for user callback once the stream closes
            self._error = error
        else:
            assert self._error is not None, (
                '_terminate_stream() expected self._error to be set when '
                'passed None error arg.')

        # So it won't mess with the stack
        self._remove_heartbeat()

        # Begin disconnection of stream or termination of connection workflow
        self._adapter_disconnect_stream()

    def _on_stream_terminated(self, error):
        """Handle termination of stack (including TCP layer) or failure to
        establish the stack. Notify registered ON_CONNECTION_ERROR or
        ON_CONNECTION_CLOSED callbacks, depending on whether the connection
        was opening or open.

        :param Exception | None error: None means that the transport was aborted
            internally and exception in `self._error` represents the cause.
            Otherwise it's an exception object that describes the unexpected
            loss of connection.

        """
        LOGGER.info(
            'AMQP stack terminated, failed to connect, or aborted: '
            'opened=%r, error-arg=%r; pending-error=%r',
            self._opened, error, self._error)

        if error is not None:
            if self._error is not None:
                LOGGER.debug(
                    '_on_stream_terminated(): overriding '
                    'pending-error=%r with %r', self._error, error)
            self._error = error
        else:
            assert self._error is not None, (
                '_on_stream_terminated() expected self._error to be populated '
                'with reason for terminating stack.')

        # Stop the heartbeat checker if it exists
        self._remove_heartbeat()

        # Remove connection management callbacks
        self._remove_callbacks(0,
                               [spec.Connection.Close, spec.Connection.Start])

        if self.params.blocked_connection_timeout is not None:
            self._remove_callbacks(0,
                    [spec.Connection.Blocked, spec.Connection.Unblocked])

        if not self._opened and isinstance(self._error,
                (exceptions.StreamLostError, exceptions.ConnectionClosedByBroker)):
            # Heuristically deduce error based on connection state
            if self.connection_state == self.CONNECTION_PROTOCOL:
                LOGGER.error('Probably incompatible Protocol Versions')
                self._error = exceptions.IncompatibleProtocolError(
                    repr(self._error))
            elif self.connection_state == self.CONNECTION_START:
                LOGGER.error(
                    'Connection closed while authenticating indicating a '
                    'probable authentication error')
                self._error = exceptions.ProbableAuthenticationError(
                    repr(self._error))
            elif self.connection_state == self.CONNECTION_TUNE:
                LOGGER.error('Connection closed while tuning the connection '
                             'indicating a probable permission error when '
                             'accessing a virtual host')
                self._error = exceptions.ProbableAccessDeniedError(
                    repr(self._error))
            elif self.connection_state not in [
                    self.CONNECTION_OPEN, self.CONNECTION_CLOSED,
                    self.CONNECTION_CLOSING
            ]:
                LOGGER.warning('Unexpected connection state on disconnect: %i',
                               self.connection_state)

        # Transition to closed state
        self._set_connection_state(self.CONNECTION_CLOSED)

        # Inform our channel proxies, if any are still around
        for channel in dictkeys(self._channels):
            if channel not in self._channels:
                continue
            # pylint: disable=W0212
            self._channels[channel]._on_close_meta(self._error)

        # Inform interested parties
        if not self._opened:
            LOGGER.info('Connection setup terminated due to %r', self._error)
            self.callbacks.process(0, self.ON_CONNECTION_ERROR, self, self,
                                   self._error)
        else:
            LOGGER.info('Stack terminated due to %r', self._error)
            self.callbacks.process(0, self.ON_CONNECTION_CLOSED, self, self,
                                   self._error)

        # Reset connection properties
        self._init_connection_state()

    def _process_callbacks(self, frame_value):
        """Process the callbacks for the frame if the frame is a method frame
        and if it has any callbacks pending.

        :param pika.frame.Method frame_value: The frame to process
        :rtype: bool

        """
        if (self._is_method_frame(frame_value) and
                self._has_pending_callbacks(frame_value)):
            self.callbacks.process(
                frame_value.channel_number,  # Prefix
                frame_value.method,  # Key
                self,  # Caller
                frame_value)  # Args
            return True
        return False

    def _process_frame(self, frame_value):
        """Process an inbound frame from the socket.

        :param pika.frame.Frame|pika.frame.Method frame_value: The frame to
            process

        """
        # Will receive a frame type of -1 if protocol version mismatch
        if frame_value.frame_type < 0:
            return

        # Keep track of how many frames have been read
        self.frames_received += 1

        # Process any callbacks, if True, exit method
        if self._process_callbacks(frame_value):
            return

        # If a heartbeat is received, update the checker
        if isinstance(frame_value, frame.Heartbeat):
            if self._heartbeat_checker:
                self._heartbeat_checker.received()
            else:
                LOGGER.warning('Received heartbeat frame without a heartbeat '
                               'checker')

        # If the frame has a channel number beyond the base channel, deliver it
        elif frame_value.channel_number > 0:
            self._deliver_frame_to_channel(frame_value)

    def _read_frame(self):
        """Try and read from the frame buffer and decode a frame.

        :rtype tuple: (int, pika.frame.Frame)

        """
        return frame.decode_frame(self._frame_buffer)

    def _remove_callbacks(self, channel_number, method_classes):
        """Remove the callbacks for the specified channel number and list of
        method frames.

        :param int channel_number: The channel number to remove the callback on
        :param sequence method_classes: The method classes (derived from
            `pika.amqp_object.Method`) for the callbacks

        """
        for method_cls in method_classes:
            self.callbacks.remove(str(channel_number), method_cls)

    def _rpc(self,
             channel_number,
             method,
             callback=None,
             acceptable_replies=None):
        """Make an RPC call for the given callback, channel number and method.
        acceptable_replies lists out what responses we'll process from the
        server with the specified callback.

        :param int channel_number: The channel number for the RPC call
        :param pika.amqp_object.Method method: The method frame to call
        :param callable callback: The callback for the RPC response
        :param list acceptable_replies: The replies this RPC call expects

        """
        # Validate that acceptable_replies is a list or None
        if acceptable_replies and not isinstance(acceptable_replies, list):
            raise TypeError('acceptable_replies should be list or None')

        # Validate the callback is callable
        if callback is not None:
            validators.require_callback(callback)
            for reply in acceptable_replies:
                self.callbacks.add(channel_number, reply, callback)

        # Send the rpc call to RabbitMQ
        self._send_method(channel_number, method)

    def _send_connection_close(self, reply_code, reply_text):
        """Send a Connection.Close method frame.

        :param int reply_code: The reason for the close
        :param str reply_text: The text reason for the close

        """
        self._rpc(0, spec.Connection.Close(reply_code, reply_text, 0, 0),
                  self._on_connection_close_ok, [spec.Connection.CloseOk])

    def _send_connection_open(self):
        """Send a Connection.Open frame"""
        self._rpc(0, spec.Connection.Open(
            self.params.virtual_host, insist=True), self._on_connection_open_ok,
                  [spec.Connection.OpenOk])

    def _send_connection_start_ok(self, authentication_type, response):
        """Send a Connection.StartOk frame

        :param str authentication_type: The auth type value
        :param str response: The encoded value to send

        """
        self._send_method(
            0,
            spec.Connection.StartOk(self._client_properties,
                                    authentication_type, response,
                                    self.params.locale))

    def _send_connection_tune_ok(self):
        """Send a Connection.TuneOk frame"""
        self._send_method(
            0,
            spec.Connection.TuneOk(self.params.channel_max,
                                   self.params.frame_max,
                                   self.params.heartbeat))

    def _send_frame(self, frame_value):
        """This appends the fully generated frame to send to the broker to the
        output buffer which will be then sent via the connection adapter.

        :param pika.frame.Frame|pika.frame.ProtocolHeader frame_value: The
            frame to write
        :raises: exceptions.ConnectionClosed

        """
        if self.is_closed:
            LOGGER.error('Attempted to send frame when closed')
            raise exceptions.ConnectionWrongStateError(
                'Attempted to send a frame on closed connection.')

        marshaled_frame = frame_value.marshal()
        self._output_marshaled_frames([marshaled_frame])

    def _send_method(self, channel_number, method, content=None):
        """Constructs a RPC method frame and then sends it to the broker.

        :param int channel_number: The channel number for the frame
        :param pika.amqp_object.Method method: The method to send
        :param tuple content: If set, is a content frame, is tuple of
                              properties and body.

        """
        if content:
            self._send_message(channel_number, method, content)
        else:
            self._send_frame(frame.Method(channel_number, method))

    def _send_message(self, channel_number, method_frame, content):
        """Publish a message.

        :param int channel_number: The channel number for the frame
        :param pika.object.Method method_frame: The method frame to send
        :param tuple content: A content frame, which is tuple of properties and
                              body.

        """
        length = len(content[1])
        marshaled_body_frames = []

        # Note: we construct the Method, Header and Content objects, marshal them
        # *then* output in case the marshaling operation throws an exception
        frame_method = frame.Method(channel_number, method_frame)
        frame_header = frame.Header(channel_number, length, content[0])
        marshaled_body_frames.append(frame_method.marshal())
        marshaled_body_frames.append(frame_header.marshal())

        if content[1]:
            chunks = int(math.ceil(float(length) / self._body_max_length))
            for chunk in xrange(0, chunks):
                start = chunk * self._body_max_length
                end = start + self._body_max_length
                if end > length:
                    end = length
                frame_body = frame.Body(channel_number, content[1][start:end])
                marshaled_body_frames.append(frame_body.marshal())

        self._output_marshaled_frames(marshaled_body_frames)

    def _set_connection_state(self, connection_state):
        """Set the connection state.

        :param int connection_state: The connection state to set

        """
        LOGGER.debug('New Connection state: %s (prev=%s)',
                     self._STATE_NAMES[connection_state],
                     self._STATE_NAMES[self.connection_state])

        self.connection_state = connection_state

    def _set_server_information(self, method_frame):
        """Set the server properties and capabilities

        :param spec.connection.Start method_frame: The Connection.Start frame

        """
        self.server_properties = method_frame.method.server_properties
        self.server_capabilities = self.server_properties.get(
            'capabilities', dict())
        if hasattr(self.server_properties, 'capabilities'):
            del self.server_properties['capabilities']

    def _trim_frame_buffer(self, byte_count):
        """Trim the leading N bytes off the frame buffer and increment the
        counter that keeps track of how many bytes have been read/used from the
        socket.

        :param int byte_count: The number of bytes consumed

        """
        self._frame_buffer = self._frame_buffer[byte_count:]
        self.bytes_received += byte_count

    def _output_marshaled_frames(self, marshaled_frames):
        """Output list of marshaled frames to buffer and update stats

        :param list marshaled_frames: A list of frames marshaled to bytes

        """
        for marshaled_frame in marshaled_frames:
            self.bytes_sent += len(marshaled_frame)
            self.frames_sent += 1
            self._adapter_emit_data(marshaled_frame)
