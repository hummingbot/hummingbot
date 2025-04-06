# Copyright (c) 2012-2019 Roger Light and others
#
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Eclipse Public License v2.0
# and Eclipse Distribution License v1.0 which accompany this distribution.
#
# The Eclipse Public License is available at
#    http://www.eclipse.org/legal/epl-v10.html
# and the Eclipse Distribution License is available at
#   http://www.eclipse.org/org/documents/edl-v10.php.
#
# Contributors:
#    Roger Light - initial API and implementation
#    Ian Craggs - MQTT V5 support

import base64
import hashlib
import logging
import string
import struct
import sys
import threading
import time
import uuid

from .matcher import MQTTMatcher
from .properties import Properties
from .reasoncodes import ReasonCodes
from .subscribeoptions import SubscribeOptions

"""
This is an MQTT client module. MQTT is a lightweight pub/sub messaging
protocol that is easy to implement and suitable for low powered devices.
"""
import collections
import errno
import os
import platform
import select
import socket

ssl = None
try:
    import ssl
except ImportError:
    pass

socks = None
try:
    import socks
except ImportError:
    pass

try:
    # Python 3
    from urllib import parse as urllib_dot_parse
    from urllib import request as urllib_dot_request
except ImportError:
    # Python 2
    import urllib as urllib_dot_request

    import urlparse as urllib_dot_parse


try:
    # Use monotonic clock if available
    time_func = time.monotonic
except AttributeError:
    time_func = time.time

try:
    import dns.resolver
except ImportError:
    HAVE_DNS = False
else:
    HAVE_DNS = True


if platform.system() == 'Windows':
    EAGAIN = errno.WSAEWOULDBLOCK
else:
    EAGAIN = errno.EAGAIN

# Python 2.7 does not have BlockingIOError.  Fall back to IOError
try:
    BlockingIOError
except NameError:
    BlockingIOError  = IOError

MQTTv31 = 3
MQTTv311 = 4
MQTTv5 = 5

if sys.version_info[0] >= 3:
    # define some alias for python2 compatibility
    unicode = str
    basestring = str

# Message types
CONNECT = 0x10
CONNACK = 0x20
PUBLISH = 0x30
PUBACK = 0x40
PUBREC = 0x50
PUBREL = 0x60
PUBCOMP = 0x70
SUBSCRIBE = 0x80
SUBACK = 0x90
UNSUBSCRIBE = 0xA0
UNSUBACK = 0xB0
PINGREQ = 0xC0
PINGRESP = 0xD0
DISCONNECT = 0xE0
AUTH = 0xF0

# Log levels
MQTT_LOG_INFO = 0x01
MQTT_LOG_NOTICE = 0x02
MQTT_LOG_WARNING = 0x04
MQTT_LOG_ERR = 0x08
MQTT_LOG_DEBUG = 0x10
LOGGING_LEVEL = {
    MQTT_LOG_DEBUG: logging.DEBUG,
    MQTT_LOG_INFO: logging.INFO,
    MQTT_LOG_NOTICE: logging.INFO,  # This has no direct equivalent level
    MQTT_LOG_WARNING: logging.WARNING,
    MQTT_LOG_ERR: logging.ERROR,
}

# CONNACK codes
CONNACK_ACCEPTED = 0
CONNACK_REFUSED_PROTOCOL_VERSION = 1
CONNACK_REFUSED_IDENTIFIER_REJECTED = 2
CONNACK_REFUSED_SERVER_UNAVAILABLE = 3
CONNACK_REFUSED_BAD_USERNAME_PASSWORD = 4
CONNACK_REFUSED_NOT_AUTHORIZED = 5

# Connection state
mqtt_cs_new = 0
mqtt_cs_connected = 1
mqtt_cs_disconnecting = 2
mqtt_cs_connect_async = 3

# Message state
mqtt_ms_invalid = 0
mqtt_ms_publish = 1
mqtt_ms_wait_for_puback = 2
mqtt_ms_wait_for_pubrec = 3
mqtt_ms_resend_pubrel = 4
mqtt_ms_wait_for_pubrel = 5
mqtt_ms_resend_pubcomp = 6
mqtt_ms_wait_for_pubcomp = 7
mqtt_ms_send_pubrec = 8
mqtt_ms_queued = 9

# Error values
MQTT_ERR_AGAIN = -1
MQTT_ERR_SUCCESS = 0
MQTT_ERR_NOMEM = 1
MQTT_ERR_PROTOCOL = 2
MQTT_ERR_INVAL = 3
MQTT_ERR_NO_CONN = 4
MQTT_ERR_CONN_REFUSED = 5
MQTT_ERR_NOT_FOUND = 6
MQTT_ERR_CONN_LOST = 7
MQTT_ERR_TLS = 8
MQTT_ERR_PAYLOAD_SIZE = 9
MQTT_ERR_NOT_SUPPORTED = 10
MQTT_ERR_AUTH = 11
MQTT_ERR_ACL_DENIED = 12
MQTT_ERR_UNKNOWN = 13
MQTT_ERR_ERRNO = 14
MQTT_ERR_QUEUE_SIZE = 15
MQTT_ERR_KEEPALIVE = 16

MQTT_CLIENT = 0
MQTT_BRIDGE = 1

# For MQTT V5, use the clean start flag only on the first successful connect
MQTT_CLEAN_START_FIRST_ONLY = 3

sockpair_data = b"0"


class WebsocketConnectionError(ValueError):
    pass


def error_string(mqtt_errno):
    """Return the error string associated with an mqtt error number."""
    if mqtt_errno == MQTT_ERR_SUCCESS:
        return "No error."
    elif mqtt_errno == MQTT_ERR_NOMEM:
        return "Out of memory."
    elif mqtt_errno == MQTT_ERR_PROTOCOL:
        return "A network protocol error occurred when communicating with the broker."
    elif mqtt_errno == MQTT_ERR_INVAL:
        return "Invalid function arguments provided."
    elif mqtt_errno == MQTT_ERR_NO_CONN:
        return "The client is not currently connected."
    elif mqtt_errno == MQTT_ERR_CONN_REFUSED:
        return "The connection was refused."
    elif mqtt_errno == MQTT_ERR_NOT_FOUND:
        return "Message not found (internal error)."
    elif mqtt_errno == MQTT_ERR_CONN_LOST:
        return "The connection was lost."
    elif mqtt_errno == MQTT_ERR_TLS:
        return "A TLS error occurred."
    elif mqtt_errno == MQTT_ERR_PAYLOAD_SIZE:
        return "Payload too large."
    elif mqtt_errno == MQTT_ERR_NOT_SUPPORTED:
        return "This feature is not supported."
    elif mqtt_errno == MQTT_ERR_AUTH:
        return "Authorisation failed."
    elif mqtt_errno == MQTT_ERR_ACL_DENIED:
        return "Access denied by ACL."
    elif mqtt_errno == MQTT_ERR_UNKNOWN:
        return "Unknown error."
    elif mqtt_errno == MQTT_ERR_ERRNO:
        return "Error defined by errno."
    elif mqtt_errno == MQTT_ERR_QUEUE_SIZE:
        return "Message queue full."
    elif mqtt_errno == MQTT_ERR_KEEPALIVE:
        return "Client or broker did not communicate in the keepalive interval."
    else:
        return "Unknown error."


def connack_string(connack_code):
    """Return the string associated with a CONNACK result."""
    if connack_code == CONNACK_ACCEPTED:
        return "Connection Accepted."
    elif connack_code == CONNACK_REFUSED_PROTOCOL_VERSION:
        return "Connection Refused: unacceptable protocol version."
    elif connack_code == CONNACK_REFUSED_IDENTIFIER_REJECTED:
        return "Connection Refused: identifier rejected."
    elif connack_code == CONNACK_REFUSED_SERVER_UNAVAILABLE:
        return "Connection Refused: broker unavailable."
    elif connack_code == CONNACK_REFUSED_BAD_USERNAME_PASSWORD:
        return "Connection Refused: bad user name or password."
    elif connack_code == CONNACK_REFUSED_NOT_AUTHORIZED:
        return "Connection Refused: not authorised."
    else:
        return "Connection Refused: unknown reason."


def base62(num, base=string.digits + string.ascii_letters, padding=1):
    """Convert a number to base-62 representation."""
    assert num >= 0
    digits = []
    while num:
        num, rest = divmod(num, 62)
        digits.append(base[rest])
    digits.extend(base[0] for _ in range(len(digits), padding))
    return ''.join(reversed(digits))


def topic_matches_sub(sub, topic):
    """Check whether a topic matches a subscription.

    For example:

    foo/bar would match the subscription foo/# or +/bar
    non/matching would not match the subscription non/+/+
    """
    matcher = MQTTMatcher()
    matcher[sub] = True
    try:
        next(matcher.iter_match(topic))
        return True
    except StopIteration:
        return False


def _socketpair_compat():
    """TCP/IP socketpair including Windows support"""
    listensock = socket.socket(
        socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_IP)
    listensock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listensock.bind(("127.0.0.1", 0))
    listensock.listen(1)

    iface, port = listensock.getsockname()
    sock1 = socket.socket(
        socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_IP)
    sock1.setblocking(0)
    try:
        sock1.connect(("127.0.0.1", port))
    except BlockingIOError:
        pass
    sock2, address = listensock.accept()
    sock2.setblocking(0)
    listensock.close()
    return (sock1, sock2)


class MQTTMessageInfo(object):
    """This is a class returned from Client.publish() and can be used to find
    out the mid of the message that was published, and to determine whether the
    message has been published, and/or wait until it is published.
    """

    __slots__ = 'mid', '_published', '_condition', 'rc', '_iterpos'

    def __init__(self, mid):
        self.mid = mid
        self._published = False
        self._condition = threading.Condition()
        self.rc = 0
        self._iterpos = 0

    def __str__(self):
        return str((self.rc, self.mid))

    def __iter__(self):
        self._iterpos = 0
        return self

    def __next__(self):
        return self.next()

    def next(self):
        if self._iterpos == 0:
            self._iterpos = 1
            return self.rc
        elif self._iterpos == 1:
            self._iterpos = 2
            return self.mid
        else:
            raise StopIteration

    def __getitem__(self, index):
        if index == 0:
            return self.rc
        elif index == 1:
            return self.mid
        else:
            raise IndexError("index out of range")

    def _set_as_published(self):
        with self._condition:
            self._published = True
            self._condition.notify()

    def wait_for_publish(self, timeout=None):
        """Block until the message associated with this object is published, or
        until the timeout occurs. If timeout is None, this will never time out.
        Set timeout to a positive number of seconds, e.g. 1.2, to enable the
        timeout.

        Raises ValueError if the message was not queued due to the outgoing
        queue being full.

        Raises RuntimeError if the message was not published for another
        reason.
        """
        if self.rc == MQTT_ERR_QUEUE_SIZE:
            raise ValueError('Message is not queued due to ERR_QUEUE_SIZE')
        elif self.rc == MQTT_ERR_AGAIN:
            pass
        elif self.rc > 0:
            raise RuntimeError('Message publish failed: %s' % (error_string(self.rc)))

        timeout_time = None if timeout is None else time.time() + timeout
        timeout_tenth = None if timeout is None else timeout / 10.
        def timed_out():
            return False if timeout is None else time.time() > timeout_time

        with self._condition:
            while not self._published and not timed_out():
                self._condition.wait(timeout_tenth)

    def is_published(self):
        """Returns True if the message associated with this object has been
        published, else returns False."""
        if self.rc == MQTT_ERR_QUEUE_SIZE:
            raise ValueError('Message is not queued due to ERR_QUEUE_SIZE')
        elif self.rc == MQTT_ERR_AGAIN:
            pass
        elif self.rc > 0:
            raise RuntimeError('Message publish failed: %s' % (error_string(self.rc)))

        with self._condition:
            return self._published


class MQTTMessage(object):
    """ This is a class that describes an incoming or outgoing message. It is
    passed to the on_message callback as the message parameter.

    Members:

    topic : String. topic that the message was published on.
    payload : Bytes/Byte array. the message payload.
    qos : Integer. The message Quality of Service 0, 1 or 2.
    retain : Boolean. If true, the message is a retained message and not fresh.
    mid : Integer. The message id.
    properties: Properties class. In MQTT v5.0, the properties associated with the message.
    """

    __slots__ = 'timestamp', 'state', 'dup', 'mid', '_topic', 'payload', 'qos', 'retain', 'info', 'properties'

    def __init__(self, mid=0, topic=b""):
        self.timestamp = 0
        self.state = mqtt_ms_invalid
        self.dup = False
        self.mid = mid
        self._topic = topic
        self.payload = b""
        self.qos = 0
        self.retain = False
        self.info = MQTTMessageInfo(mid)

    def __eq__(self, other):
        """Override the default Equals behavior"""
        if isinstance(other, self.__class__):
            return self.mid == other.mid
        return False

    def __ne__(self, other):
        """Define a non-equality test"""
        return not self.__eq__(other)

    @property
    def topic(self):
        return self._topic.decode('utf-8')

    @topic.setter
    def topic(self, value):
        self._topic = value


class Client(object):
    """MQTT version 3.1/3.1.1/5.0 client class.

    This is the main class for use communicating with an MQTT broker.

    General usage flow:

    * Use connect()/connect_async() to connect to a broker
    * Call loop() frequently to maintain network traffic flow with the broker
    * Or use loop_start() to set a thread running to call loop() for you.
    * Or use loop_forever() to handle calling loop() for you in a blocking
    * function.
    * Use subscribe() to subscribe to a topic and receive messages
    * Use publish() to send messages
    * Use disconnect() to disconnect from the broker

    Data returned from the broker is made available with the use of callback
    functions as described below.

    Callbacks
    =========

    A number of callback functions are available to receive data back from the
    broker. To use a callback, define a function and then assign it to the
    client:

    def on_connect(client, userdata, flags, rc):
        print("Connection returned " + str(rc))

    client.on_connect = on_connect

    Callbacks can also be attached using decorators:

    client = paho.mqtt.Client()

    @client.connect_callback()
    def on_connect(client, userdata, flags, rc):
        print("Connection returned " + str(rc))


    **IMPORTANT** the required function signature for a callback can differ
    depending on whether you are using MQTT v5 or MQTT v3.1.1/v3.1. See the
    documentation for each callback.

    All of the callbacks as described below have a "client" and an "userdata"
    argument. "client" is the Client instance that is calling the callback.
    "userdata" is user data of any type and can be set when creating a new client
    instance or with user_data_set(userdata).

    If you wish to suppress exceptions within a callback, you should set
    `client.suppress_exceptions = True`

    The callbacks are listed below, documentation for each of them can be found
    at the same function name:

    on_connect, on_connect_fail, on_disconnect, on_message, on_publish,
    on_subscribe, on_unsubscribe, on_log, on_socket_open, on_socket_close,
    on_socket_register_write, on_socket_unregister_write
    """

    def __init__(self, client_id="", clean_session=None, userdata=None,
                 protocol=MQTTv311, transport="tcp", reconnect_on_failure=True):
        """client_id is the unique client id string used when connecting to the
        broker. If client_id is zero length or None, then the behaviour is
        defined by which protocol version is in use. If using MQTT v3.1.1, then
        a zero length client id will be sent to the broker and the broker will
        generate a random for the client. If using MQTT v3.1 then an id will be
        randomly generated. In both cases, clean_session must be True. If this
        is not the case a ValueError will be raised.

        clean_session is a boolean that determines the client type. If True,
        the broker will remove all information about this client when it
        disconnects. If False, the client is a persistent client and
        subscription information and queued messages will be retained when the
        client disconnects.
        Note that a client will never discard its own outgoing messages on
        disconnect. Calling connect() or reconnect() will cause the messages to
        be resent.  Use reinitialise() to reset a client to its original state.
        The clean_session argument only applies to MQTT versions v3.1.1 and v3.1.
        It is not accepted if the MQTT version is v5.0 - use the clean_start
        argument on connect() instead.

        userdata is user defined data of any type that is passed as the "userdata"
        parameter to callbacks. It may be updated at a later point with the
        user_data_set() function.

        The protocol argument allows explicit setting of the MQTT version to
        use for this client. Can be paho.mqtt.client.MQTTv311 (v3.1.1),
        paho.mqtt.client.MQTTv31 (v3.1) or paho.mqtt.client.MQTTv5 (v5.0),
        with the default being v3.1.1.

        Set transport to "websockets" to use WebSockets as the transport
        mechanism. Set to "tcp" to use raw TCP, which is the default.
        """

        if transport.lower() not in ('websockets', 'tcp'):
            raise ValueError(
                'transport must be "websockets" or "tcp", not %s' % transport)
        self._transport = transport.lower()
        self._protocol = protocol
        self._userdata = userdata
        self._sock = None
        self._sockpairR, self._sockpairW = (None, None,)
        self._keepalive = 60
        self._connect_timeout = 5.0
        self._client_mode = MQTT_CLIENT

        if protocol == MQTTv5:
            if clean_session is not None:
                raise ValueError('Clean session is not used for MQTT 5.0')
        else:
            if clean_session is None:
                clean_session = True
            if not clean_session and (client_id == "" or client_id is None):
                raise ValueError(
                    'A client id must be provided if clean session is False.')
            self._clean_session = clean_session

        # [MQTT-3.1.3-4] Client Id must be UTF-8 encoded string.
        if client_id == "" or client_id is None:
            if protocol == MQTTv31:
                self._client_id = base62(uuid.uuid4().int, padding=22)
            else:
                self._client_id = b""
        else:
            self._client_id = client_id
        if isinstance(self._client_id, unicode):
            self._client_id = self._client_id.encode('utf-8')

        self._username = None
        self._password = None
        self._in_packet = {
            "command": 0,
            "have_remaining": 0,
            "remaining_count": [],
            "remaining_mult": 1,
            "remaining_length": 0,
            "packet": bytearray(b""),
            "to_process": 0,
            "pos": 0}
        self._out_packet = collections.deque()
        self._last_msg_in = time_func()
        self._last_msg_out = time_func()
        self._reconnect_min_delay = 1
        self._reconnect_max_delay = 120
        self._reconnect_delay = None
        self._reconnect_on_failure = reconnect_on_failure
        self._ping_t = 0
        self._last_mid = 0
        self._state = mqtt_cs_new
        self._out_messages = collections.OrderedDict()
        self._in_messages = collections.OrderedDict()
        self._max_inflight_messages = 20
        self._inflight_messages = 0
        self._max_queued_messages = 0
        self._connect_properties = None
        self._will_properties = None
        self._will = False
        self._will_topic = b""
        self._will_payload = b""
        self._will_qos = 0
        self._will_retain = False
        self._on_message_filtered = MQTTMatcher()
        self._host = ""
        self._port = 1883
        self._bind_address = ""
        self._bind_port = 0
        self._proxy = {}
        self._in_callback_mutex = threading.Lock()
        self._callback_mutex = threading.RLock()
        self._msgtime_mutex = threading.Lock()
        self._out_message_mutex = threading.RLock()
        self._in_message_mutex = threading.Lock()
        self._reconnect_delay_mutex = threading.Lock()
        self._mid_generate_mutex = threading.Lock()
        self._thread = None
        self._thread_terminate = False
        self._ssl = False
        self._ssl_context = None
        # Only used when SSL context does not have check_hostname attribute
        self._tls_insecure = False
        self._logger = None
        self._registered_write = False
        # No default callbacks
        self._on_log = None
        self._on_connect = None
        self._on_connect_fail = None
        self._on_subscribe = None
        self._on_message = None
        self._on_publish = None
        self._on_unsubscribe = None
        self._on_disconnect = None
        self._on_socket_open = None
        self._on_socket_close = None
        self._on_socket_register_write = None
        self._on_socket_unregister_write = None
        self._websocket_path = "/mqtt"
        self._websocket_extra_headers = None
        # for clean_start == MQTT_CLEAN_START_FIRST_ONLY
        self._mqttv5_first_connect = True
        self.suppress_exceptions = False # For callbacks

    def __del__(self):
        self._reset_sockets()

    def _sock_recv(self, bufsize):
        try:
            return self._sock.recv(bufsize)
        except ssl.SSLWantReadError:
            raise BlockingIOError
        except ssl.SSLWantWriteError:
            self._call_socket_register_write()
            raise BlockingIOError

    def _sock_send(self, buf):
        try:
            return self._sock.send(buf)
        except ssl.SSLWantReadError:
            raise BlockingIOError
        except ssl.SSLWantWriteError:
            self._call_socket_register_write()
            raise BlockingIOError
        except BlockingIOError:
            self._call_socket_register_write()
            raise BlockingIOError

    def _sock_close(self):
        """Close the connection to the server."""
        if not self._sock:
            return

        try:
            sock = self._sock
            self._sock = None
            self._call_socket_unregister_write(sock)
            self._call_socket_close(sock)
        finally:
            # In case a callback fails, still close the socket to avoid leaking the file descriptor.
            sock.close()

    def _reset_sockets(self, sockpair_only=False):
        if sockpair_only == False:
            self._sock_close()

        if self._sockpairR:
            self._sockpairR.close()
            self._sockpairR = None
        if self._sockpairW:
            self._sockpairW.close()
            self._sockpairW = None

    def reinitialise(self, client_id="", clean_session=True, userdata=None):
        self._reset_sockets()

        self.__init__(client_id, clean_session, userdata)

    def ws_set_options(self, path="/mqtt", headers=None):
        """ Set the path and headers for a websocket connection

        path is a string starting with / which should be the endpoint of the
        mqtt connection on the remote server

        headers can be either a dict or a callable object. If it is a dict then
        the extra items in the dict are added to the websocket headers. If it is
        a callable, then the default websocket headers are passed into this
        function and the result is used as the new headers.
        """
        self._websocket_path = path

        if headers is not None:
            if isinstance(headers, dict) or callable(headers):
                self._websocket_extra_headers = headers
            else:
                raise ValueError(
                    "'headers' option to ws_set_options has to be either a dictionary or callable")

    def tls_set_context(self, context=None):
        """Configure network encryption and authentication context. Enables SSL/TLS support.

        context : an ssl.SSLContext object. By default this is given by
        `ssl.create_default_context()`, if available.

        Must be called before connect() or connect_async()."""
        if self._ssl_context is not None:
            raise ValueError('SSL/TLS has already been configured.')

        # Assume that have SSL support, or at least that context input behaves like ssl.SSLContext
        # in current versions of Python

        if context is None:
            if hasattr(ssl, 'create_default_context'):
                context = ssl.create_default_context()
            else:
                raise ValueError('SSL/TLS context must be specified')

        self._ssl = True
        self._ssl_context = context

        # Ensure _tls_insecure is consistent with check_hostname attribute
        if hasattr(context, 'check_hostname'):
            self._tls_insecure = not context.check_hostname

    def tls_set(self, ca_certs=None, certfile=None, keyfile=None, cert_reqs=None, tls_version=None, ciphers=None, keyfile_password=None):
        """Configure network encryption and authentication options. Enables SSL/TLS support.

        ca_certs : a string path to the Certificate Authority certificate files
        that are to be treated as trusted by this client. If this is the only
        option given then the client will operate in a similar manner to a web
        browser. That is to say it will require the broker to have a
        certificate signed by the Certificate Authorities in ca_certs and will
        communicate using TLS v1,2, but will not attempt any form of
        authentication. This provides basic network encryption but may not be
        sufficient depending on how the broker is configured.
        By default, on Python 2.7.9+ or 3.4+, the default certification
        authority of the system is used. On older Python version this parameter
        is mandatory.

        certfile and keyfile are strings pointing to the PEM encoded client
        certificate and private keys respectively. If these arguments are not
        None then they will be used as client information for TLS based
        authentication.  Support for this feature is broker dependent. Note
        that if either of these files in encrypted and needs a password to
        decrypt it, then this can be passed using the keyfile_password
        argument - you should take precautions to ensure that your password is
        not hard coded into your program by loading the password from a file
        for example. If you do not provide keyfile_password, the password will
        be requested to be typed in at a terminal window.

        cert_reqs allows the certificate requirements that the client imposes
        on the broker to be changed. By default this is ssl.CERT_REQUIRED,
        which means that the broker must provide a certificate. See the ssl
        pydoc for more information on this parameter.

        tls_version allows the version of the SSL/TLS protocol used to be
        specified. By default TLS v1.2 is used. Previous versions are allowed
        but not recommended due to possible security problems.

        ciphers is a string specifying which encryption ciphers are allowable
        for this connection, or None to use the defaults. See the ssl pydoc for
        more information.

        Must be called before connect() or connect_async()."""
        if ssl is None:
            raise ValueError('This platform has no SSL/TLS.')

        if not hasattr(ssl, 'SSLContext'):
            # Require Python version that has SSL context support in standard library
            raise ValueError(
                'Python 2.7.9 and 3.2 are the minimum supported versions for TLS.')

        if ca_certs is None and not hasattr(ssl.SSLContext, 'load_default_certs'):
            raise ValueError('ca_certs must not be None.')

        # Create SSLContext object
        if tls_version is None:
            tls_version = ssl.PROTOCOL_TLSv1_2
            # If the python version supports it, use highest TLS version automatically
            if hasattr(ssl, "PROTOCOL_TLS"):
                tls_version = ssl.PROTOCOL_TLS
        context = ssl.SSLContext(tls_version)

        # Configure context
        if certfile is not None:
            context.load_cert_chain(certfile, keyfile, keyfile_password)

        if cert_reqs == ssl.CERT_NONE and hasattr(context, 'check_hostname'):
            context.check_hostname = False

        context.verify_mode = ssl.CERT_REQUIRED if cert_reqs is None else cert_reqs

        if ca_certs is not None:
            context.load_verify_locations(ca_certs)
        else:
            context.load_default_certs()

        if ciphers is not None:
            context.set_ciphers(ciphers)

        self.tls_set_context(context)

        if cert_reqs != ssl.CERT_NONE:
            # Default to secure, sets context.check_hostname attribute
            # if available
            self.tls_insecure_set(False)
        else:
            # But with ssl.CERT_NONE, we can not check_hostname
            self.tls_insecure_set(True)

    def tls_insecure_set(self, value):
        """Configure verification of the server hostname in the server certificate.

        If value is set to true, it is impossible to guarantee that the host
        you are connecting to is not impersonating your server. This can be
        useful in initial server testing, but makes it possible for a malicious
        third party to impersonate your server through DNS spoofing, for
        example.

        Do not use this function in a real system. Setting value to true means
        there is no point using encryption.

        Must be called before connect() and after either tls_set() or
        tls_set_context()."""

        if self._ssl_context is None:
            raise ValueError(
                'Must configure SSL context before using tls_insecure_set.')

        self._tls_insecure = value

        # Ensure check_hostname is consistent with _tls_insecure attribute
        if hasattr(self._ssl_context, 'check_hostname'):
            # Rely on SSLContext to check host name
            # If verify_mode is CERT_NONE then the host name will never be checked
            self._ssl_context.check_hostname = not value

    def proxy_set(self, **proxy_args):
        """Configure proxying of MQTT connection. Enables support for SOCKS or
        HTTP proxies.

        Proxying is done through the PySocks library. Brief descriptions of the
        proxy_args parameters are below; see the PySocks docs for more info.

        (Required)
        proxy_type: One of {socks.HTTP, socks.SOCKS4, or socks.SOCKS5}
        proxy_addr: IP address or DNS name of proxy server

        (Optional)
        proxy_rdns: boolean indicating whether proxy lookup should be performed
            remotely (True, default) or locally (False)
        proxy_username: username for SOCKS5 proxy, or userid for SOCKS4 proxy
        proxy_password: password for SOCKS5 proxy

        Must be called before connect() or connect_async()."""
        if socks is None:
            raise ValueError("PySocks must be installed for proxy support.")
        elif not self._proxy_is_valid(proxy_args):
            raise ValueError("proxy_type and/or proxy_addr are invalid.")
        else:
            self._proxy = proxy_args

    def enable_logger(self, logger=None):
        """ Enables a logger to send log messages to """
        if logger is None:
            if self._logger is not None:
                # Do not replace existing logger
                return
            logger = logging.getLogger(__name__)
        self._logger = logger

    def disable_logger(self):
        self._logger = None

    def connect(self, host, port=1883, keepalive=60, bind_address="", bind_port=0,
                clean_start=MQTT_CLEAN_START_FIRST_ONLY, properties=None):
        """Connect to a remote broker.

        host is the hostname or IP address of the remote broker.
        port is the network port of the server host to connect to. Defaults to
        1883. Note that the default port for MQTT over SSL/TLS is 8883 so if you
        are using tls_set() the port may need providing.
        keepalive: Maximum period in seconds between communications with the
        broker. If no other messages are being exchanged, this controls the
        rate at which the client will send ping messages to the broker.
        clean_start: (MQTT v5.0 only) True, False or MQTT_CLEAN_START_FIRST_ONLY.
        Sets the MQTT v5.0 clean_start flag always, never or on the first successful connect only,
        respectively.  MQTT session data (such as outstanding messages and subscriptions)
        is cleared on successful connect when the clean_start flag is set.
        properties: (MQTT v5.0 only) the MQTT v5.0 properties to be sent in the
        MQTT connect packet.
        """

        if self._protocol == MQTTv5:
            self._mqttv5_first_connect = True
        else:
            if clean_start != MQTT_CLEAN_START_FIRST_ONLY:
                raise ValueError("Clean start only applies to MQTT V5")
            if properties != None:
                raise ValueError("Properties only apply to MQTT V5")

        self.connect_async(host, port, keepalive,
                           bind_address, bind_port, clean_start, properties)
        return self.reconnect()

    def connect_srv(self, domain=None, keepalive=60, bind_address="",
                    clean_start=MQTT_CLEAN_START_FIRST_ONLY, properties=None):
        """Connect to a remote broker.

        domain is the DNS domain to search for SRV records; if None,
        try to determine local domain name.
        keepalive, bind_address, clean_start and properties are as for connect()
        """

        if HAVE_DNS is False:
            raise ValueError(
                'No DNS resolver library found, try "pip install dnspython" or "pip3 install dnspython3".')

        if domain is None:
            domain = socket.getfqdn()
            domain = domain[domain.find('.') + 1:]

        try:
            rr = '_mqtt._tcp.%s' % domain
            if self._ssl:
                # IANA specifies secure-mqtt (not mqtts) for port 8883
                rr = '_secure-mqtt._tcp.%s' % domain
            answers = []
            for answer in dns.resolver.query(rr, dns.rdatatype.SRV):
                addr = answer.target.to_text()[:-1]
                answers.append(
                    (addr, answer.port, answer.priority, answer.weight))
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            raise ValueError("No answer/NXDOMAIN for SRV in %s" % (domain))

        # FIXME: doesn't account for weight
        for answer in answers:
            host, port, prio, weight = answer

            try:
                return self.connect(host, port, keepalive, bind_address, clean_start, properties)
            except Exception:
                pass

        raise ValueError("No SRV hosts responded")

    def connect_async(self, host, port=1883, keepalive=60, bind_address="", bind_port=0,
                      clean_start=MQTT_CLEAN_START_FIRST_ONLY, properties=None):
        """Connect to a remote broker asynchronously. This is a non-blocking
        connect call that can be used with loop_start() to provide very quick
        start.

        host is the hostname or IP address of the remote broker.
        port is the network port of the server host to connect to. Defaults to
        1883. Note that the default port for MQTT over SSL/TLS is 8883 so if you
        are using tls_set() the port may need providing.
        keepalive: Maximum period in seconds between communications with the
        broker. If no other messages are being exchanged, this controls the
        rate at which the client will send ping messages to the broker.
        clean_start: (MQTT v5.0 only) True, False or MQTT_CLEAN_START_FIRST_ONLY.
        Sets the MQTT v5.0 clean_start flag always, never or on the first successful connect only,
        respectively.  MQTT session data (such as outstanding messages and subscriptions)
        is cleared on successful connect when the clean_start flag is set.
        properties: (MQTT v5.0 only) the MQTT v5.0 properties to be sent in the
        MQTT connect packet.  Use the Properties class.
        """
        if host is None or len(host) == 0:
            raise ValueError('Invalid host.')
        if port <= 0:
            raise ValueError('Invalid port number.')
        if keepalive < 0:
            raise ValueError('Keepalive must be >=0.')
        if bind_address != "" and bind_address is not None:
            if sys.version_info < (2, 7) or (3, 0) < sys.version_info < (3, 2):
                raise ValueError('bind_address requires Python 2.7 or 3.2.')
        if bind_port < 0:
            raise ValueError('Invalid bind port number.')

        self._host = host
        self._port = port
        self._keepalive = keepalive
        self._bind_address = bind_address
        self._bind_port = bind_port
        self._clean_start = clean_start
        self._connect_properties = properties
        self._state = mqtt_cs_connect_async


    def reconnect_delay_set(self, min_delay=1, max_delay=120):
        """ Configure the exponential reconnect delay

            When connection is lost, wait initially min_delay seconds and
            double this time every attempt. The wait is capped at max_delay.
            Once the client is fully connected (e.g. not only TCP socket, but
            received a success CONNACK), the wait timer is reset to min_delay.
        """
        with self._reconnect_delay_mutex:
            self._reconnect_min_delay = min_delay
            self._reconnect_max_delay = max_delay
            self._reconnect_delay = None

    def reconnect(self):
        """Reconnect the client after a disconnect. Can only be called after
        connect()/connect_async()."""
        if len(self._host) == 0:
            raise ValueError('Invalid host.')
        if self._port <= 0:
            raise ValueError('Invalid port number.')

        self._in_packet = {
            "command": 0,
            "have_remaining": 0,
            "remaining_count": [],
            "remaining_mult": 1,
            "remaining_length": 0,
            "packet": bytearray(b""),
            "to_process": 0,
            "pos": 0}

        self._out_packet = collections.deque()

        with self._msgtime_mutex:
            self._last_msg_in = time_func()
            self._last_msg_out = time_func()

        self._ping_t = 0
        self._state = mqtt_cs_new

        self._sock_close()

        # Put messages in progress in a valid state.
        self._messages_reconnect_reset()

        sock = self._create_socket_connection()

        if self._ssl:
            # SSL is only supported when SSLContext is available (implies Python >= 2.7.9 or >= 3.2)

            verify_host = not self._tls_insecure
            try:
                # Try with server_hostname, even it's not supported in certain scenarios
                sock = self._ssl_context.wrap_socket(
                    sock,
                    server_hostname=self._host,
                    do_handshake_on_connect=False,
                )
            except ssl.CertificateError:
                # CertificateError is derived from ValueError
                raise
            except ValueError:
                # Python version requires SNI in order to handle server_hostname, but SNI is not available
                sock = self._ssl_context.wrap_socket(
                    sock,
                    do_handshake_on_connect=False,
                )
            else:
                # If SSL context has already checked hostname, then don't need to do it again
                if (hasattr(self._ssl_context, 'check_hostname') and
                        self._ssl_context.check_hostname):
                    verify_host = False

            sock.settimeout(self._keepalive)
            sock.do_handshake()

            if verify_host:
                ssl.match_hostname(sock.getpeercert(), self._host)

        if self._transport == "websockets":
            sock.settimeout(self._keepalive)
            sock = WebsocketWrapper(sock, self._host, self._port, self._ssl,
                                    self._websocket_path, self._websocket_extra_headers)

        self._sock = sock
        self._sock.setblocking(0)
        self._registered_write = False
        self._call_socket_open()

        return self._send_connect(self._keepalive)

    def loop(self, timeout=1.0, max_packets=1):
        """Process network events.

        It is strongly recommended that you use loop_start(), or
        loop_forever(), or if you are using an external event loop using
        loop_read(), loop_write(), and loop_misc(). Using loop() on it's own is
        no longer recommended.

        This function must be called regularly to ensure communication with the
        broker is carried out. It calls select() on the network socket to wait
        for network events. If incoming data is present it will then be
        processed. Outgoing commands, from e.g. publish(), are normally sent
        immediately that their function is called, but this is not always
        possible. loop() will also attempt to send any remaining outgoing
        messages, which also includes commands that are part of the flow for
        messages with QoS>0.

        timeout: The time in seconds to wait for incoming/outgoing network
            traffic before timing out and returning.
        max_packets: Not currently used.

        Returns MQTT_ERR_SUCCESS on success.
        Returns >0 on error.

        A ValueError will be raised if timeout < 0"""

        if self._sockpairR is None or self._sockpairW is None:
            self._reset_sockets(sockpair_only=True)
            self._sockpairR, self._sockpairW = _socketpair_compat()

        return self._loop(timeout)

    def _loop(self, timeout=1.0):
        if timeout < 0.0:
            raise ValueError('Invalid timeout.')

        try:
            packet = self._out_packet.popleft()
            self._out_packet.appendleft(packet)
            wlist = [self._sock]
        except IndexError:
            wlist = []

        # used to check if there are any bytes left in the (SSL) socket
        pending_bytes = 0
        if hasattr(self._sock, 'pending'):
            pending_bytes = self._sock.pending()

        # if bytes are pending do not wait in select
        if pending_bytes > 0:
            timeout = 0.0

        # sockpairR is used to break out of select() before the timeout, on a
        # call to publish() etc.
        if self._sockpairR is None:
            rlist = [self._sock]
        else:
            rlist = [self._sock, self._sockpairR]

        try:
            socklist = select.select(rlist, wlist, [], timeout)
        except TypeError:
            # Socket isn't correct type, in likelihood connection is lost
            return MQTT_ERR_CONN_LOST
        except ValueError:
            # Can occur if we just reconnected but rlist/wlist contain a -1 for
            # some reason.
            return MQTT_ERR_CONN_LOST
        except Exception:
            # Note that KeyboardInterrupt, etc. can still terminate since they
            # are not derived from Exception
            return MQTT_ERR_UNKNOWN

        if self._sock in socklist[0] or pending_bytes > 0:
            rc = self.loop_read()
            if rc or self._sock is None:
                return rc

        if self._sockpairR and self._sockpairR in socklist[0]:
            # Stimulate output write even though we didn't ask for it, because
            # at that point the publish or other command wasn't present.
            socklist[1].insert(0, self._sock)
            # Clear sockpairR - only ever a single byte written.
            try:
                # Read many bytes at once - this allows up to 10000 calls to
                # publish() inbetween calls to loop().
                self._sockpairR.recv(10000)
            except BlockingIOError:
                pass

        if self._sock in socklist[1]:
            rc = self.loop_write()
            if rc or self._sock is None:
                return rc

        return self.loop_misc()

    def publish(self, topic, payload=None, qos=0, retain=False, properties=None):
        """Publish a message on a topic.

        This causes a message to be sent to the broker and subsequently from
        the broker to any clients subscribing to matching topics.

        topic: The topic that the message should be published on.
        payload: The actual message to send. If not given, or set to None a
        zero length message will be used. Passing an int or float will result
        in the payload being converted to a string representing that number. If
        you wish to send a true int/float, use struct.pack() to create the
        payload you require.
        qos: The quality of service level to use.
        retain: If set to true, the message will be set as the "last known
        good"/retained message for the topic.
        properties: (MQTT v5.0 only) the MQTT v5.0 properties to be included.
        Use the Properties class.

        Returns a MQTTMessageInfo class, which can be used to determine whether
        the message has been delivered (using info.is_published()) or to block
        waiting for the message to be delivered (info.wait_for_publish()). The
        message ID and return code of the publish() call can be found at
        info.mid and info.rc.

        For backwards compatibility, the MQTTMessageInfo class is iterable so
        the old construct of (rc, mid) = client.publish(...) is still valid.

        rc is MQTT_ERR_SUCCESS to indicate success or MQTT_ERR_NO_CONN if the
        client is not currently connected.  mid is the message ID for the
        publish request. The mid value can be used to track the publish request
        by checking against the mid argument in the on_publish() callback if it
        is defined.

        A ValueError will be raised if topic is None, has zero length or is
        invalid (contains a wildcard), except if the MQTT version used is v5.0.
        For v5.0, a zero length topic can be used when a Topic Alias has been set.

        A ValueError will be raised if qos is not one of 0, 1 or 2, or if
        the length of the payload is greater than 268435455 bytes."""
        if self._protocol != MQTTv5:
            if topic is None or len(topic) == 0:
                raise ValueError('Invalid topic.')

        topic = topic.encode('utf-8')

        if self._topic_wildcard_len_check(topic) != MQTT_ERR_SUCCESS:
            raise ValueError('Publish topic cannot contain wildcards.')

        if qos < 0 or qos > 2:
            raise ValueError('Invalid QoS level.')

        if isinstance(payload, unicode):
            local_payload = payload.encode('utf-8')
        elif isinstance(payload, (bytes, bytearray)):
            local_payload = payload
        elif isinstance(payload, (int, float)):
            local_payload = str(payload).encode('ascii')
        elif payload is None:
            local_payload = b''
        else:
            raise TypeError(
                'payload must be a string, bytearray, int, float or None.')

        if len(local_payload) > 268435455:
            raise ValueError('Payload too large.')

        local_mid = self._mid_generate()

        if qos == 0:
            info = MQTTMessageInfo(local_mid)
            rc = self._send_publish(
                local_mid, topic, local_payload, qos, retain, False, info, properties)
            info.rc = rc
            return info
        else:
            message = MQTTMessage(local_mid, topic)
            message.timestamp = time_func()
            message.payload = local_payload
            message.qos = qos
            message.retain = retain
            message.dup = False
            message.properties = properties

            with self._out_message_mutex:
                if self._max_queued_messages > 0 and len(self._out_messages) >= self._max_queued_messages:
                    message.info.rc = MQTT_ERR_QUEUE_SIZE
                    return message.info

                if local_mid in self._out_messages:
                    message.info.rc = MQTT_ERR_QUEUE_SIZE
                    return message.info

                self._out_messages[message.mid] = message
                if self._max_inflight_messages == 0 or self._inflight_messages < self._max_inflight_messages:
                    self._inflight_messages += 1
                    if qos == 1:
                        message.state = mqtt_ms_wait_for_puback
                    elif qos == 2:
                        message.state = mqtt_ms_wait_for_pubrec

                    rc = self._send_publish(message.mid, topic, message.payload, message.qos, message.retain,
                                            message.dup, message.info, message.properties)

                    # remove from inflight messages so it will be send after a connection is made
                    if rc is MQTT_ERR_NO_CONN:
                        self._inflight_messages -= 1
                        message.state = mqtt_ms_publish

                    message.info.rc = rc
                    return message.info
                else:
                    message.state = mqtt_ms_queued
                    message.info.rc = MQTT_ERR_SUCCESS
                    return message.info

    def username_pw_set(self, username, password=None):
        """Set a username and optionally a password for broker authentication.

        Must be called before connect() to have any effect.
        Requires a broker that supports MQTT v3.1.

        username: The username to authenticate with. Need have no relationship to the client id. Must be unicode
            [MQTT-3.1.3-11].
            Set to None to reset client back to not using username/password for broker authentication.
        password: The password to authenticate with. Optional, set to None if not required. If it is unicode, then it
            will be encoded as UTF-8.
        """

        # [MQTT-3.1.3-11] User name must be UTF-8 encoded string
        self._username = None if username is None else username.encode('utf-8')
        self._password = password
        if isinstance(self._password, unicode):
            self._password = self._password.encode('utf-8')

    def enable_bridge_mode(self):
        """Sets the client in a bridge mode instead of client mode.

        Must be called before connect() to have any effect.
        Requires brokers that support bridge mode.

        Under bridge mode, the broker will identify the client as a bridge and
        not send it's own messages back to it. Hence a subsciption of # is
        possible without message loops. This feature also correctly propagates
        the retain flag on the messages.

        Currently Mosquitto and RSMB support this feature. This feature can
        be used to create a bridge between multiple broker.
        """
        self._client_mode = MQTT_BRIDGE

    def is_connected(self):
        """Returns the current status of the connection

        True if connection exists
        False if connection is closed
        """
        return self._state == mqtt_cs_connected

    def disconnect(self, reasoncode=None, properties=None):
        """Disconnect a connected client from the broker.
        reasoncode: (MQTT v5.0 only) a ReasonCodes instance setting the MQTT v5.0
        reasoncode to be sent with the disconnect.  It is optional, the receiver
        then assuming that 0 (success) is the value.
        properties: (MQTT v5.0 only) a Properties instance setting the MQTT v5.0 properties
        to be included. Optional - if not set, no properties are sent.
        """
        self._state = mqtt_cs_disconnecting

        if self._sock is None:
            return MQTT_ERR_NO_CONN

        return self._send_disconnect(reasoncode, properties)

    def subscribe(self, topic, qos=0, options=None, properties=None):
        """Subscribe the client to one or more topics.

        This function may be called in three different ways (and a further three for MQTT v5.0):

        Simple string and integer
        -------------------------
        e.g. subscribe("my/topic", 2)

        topic: A string specifying the subscription topic to subscribe to.
        qos: The desired quality of service level for the subscription.
             Defaults to 0.
        options and properties: Not used.

        Simple string and subscribe options (MQTT v5.0 only)
        ----------------------------------------------------
        e.g. subscribe("my/topic", options=SubscribeOptions(qos=2))

        topic: A string specifying the subscription topic to subscribe to.
        qos: Not used.
        options: The MQTT v5.0 subscribe options.
        properties: a Properties instance setting the MQTT v5.0 properties
        to be included. Optional - if not set, no properties are sent.

        String and integer tuple
        ------------------------
        e.g. subscribe(("my/topic", 1))

        topic: A tuple of (topic, qos). Both topic and qos must be present in
               the tuple.
        qos and options: Not used.
        properties: Only used for MQTT v5.0.  A Properties instance setting the
        MQTT v5.0 properties. Optional - if not set, no properties are sent.

        String and subscribe options tuple (MQTT v5.0 only)
        ---------------------------------------------------
        e.g. subscribe(("my/topic", SubscribeOptions(qos=1)))

        topic: A tuple of (topic, SubscribeOptions). Both topic and subscribe
                options must be present in the tuple.
        qos and options: Not used.
        properties: a Properties instance setting the MQTT v5.0 properties
        to be included. Optional - if not set, no properties are sent.

        List of string and integer tuples
        ---------------------------------
        e.g. subscribe([("my/topic", 0), ("another/topic", 2)])

        This allows multiple topic subscriptions in a single SUBSCRIPTION
        command, which is more efficient than using multiple calls to
        subscribe().

        topic: A list of tuple of format (topic, qos). Both topic and qos must
               be present in all of the tuples.
        qos, options and properties: Not used.

        List of string and subscribe option tuples (MQTT v5.0 only)
        -----------------------------------------------------------
        e.g. subscribe([("my/topic", SubscribeOptions(qos=0), ("another/topic", SubscribeOptions(qos=2)])

        This allows multiple topic subscriptions in a single SUBSCRIPTION
        command, which is more efficient than using multiple calls to
        subscribe().

        topic: A list of tuple of format (topic, SubscribeOptions). Both topic and subscribe
                options must be present in all of the tuples.
        qos and options: Not used.
        properties: a Properties instance setting the MQTT v5.0 properties
        to be included. Optional - if not set, no properties are sent.

        The function returns a tuple (result, mid), where result is
        MQTT_ERR_SUCCESS to indicate success or (MQTT_ERR_NO_CONN, None) if the
        client is not currently connected.  mid is the message ID for the
        subscribe request. The mid value can be used to track the subscribe
        request by checking against the mid argument in the on_subscribe()
        callback if it is defined.

        Raises a ValueError if qos is not 0, 1 or 2, or if topic is None or has
        zero string length, or if topic is not a string, tuple or list.
        """
        topic_qos_list = None

        if isinstance(topic, tuple):
            if self._protocol == MQTTv5:
                topic, options = topic
                if not isinstance(options, SubscribeOptions):
                    raise ValueError(
                        'Subscribe options must be instance of SubscribeOptions class.')
            else:
                topic, qos = topic

        if isinstance(topic, basestring):
            if qos < 0 or qos > 2:
                raise ValueError('Invalid QoS level.')
            if self._protocol == MQTTv5:
                if options is None:
                    # if no options are provided, use the QoS passed instead
                    options = SubscribeOptions(qos=qos)
                elif qos != 0:
                    raise ValueError(
                        'Subscribe options and qos parameters cannot be combined.')
                if not isinstance(options, SubscribeOptions):
                    raise ValueError(
                        'Subscribe options must be instance of SubscribeOptions class.')
                topic_qos_list = [(topic.encode('utf-8'), options)]
            else:
                if topic is None or len(topic) == 0:
                    raise ValueError('Invalid topic.')
                topic_qos_list = [(topic.encode('utf-8'), qos)]
        elif isinstance(topic, list):
            topic_qos_list = []
            if self._protocol == MQTTv5:
                for t, o in topic:
                    if not isinstance(o, SubscribeOptions):
                        # then the second value should be QoS
                        if o < 0 or o > 2:
                            raise ValueError('Invalid QoS level.')
                        o = SubscribeOptions(qos=o)
                    topic_qos_list.append((t.encode('utf-8'), o))
            else:
                for t, q in topic:
                    if q < 0 or q > 2:
                        raise ValueError('Invalid QoS level.')
                    if t is None or len(t) == 0 or not isinstance(t, basestring):
                        raise ValueError('Invalid topic.')
                    topic_qos_list.append((t.encode('utf-8'), q))

        if topic_qos_list is None:
            raise ValueError("No topic specified, or incorrect topic type.")

        if any(self._filter_wildcard_len_check(topic) != MQTT_ERR_SUCCESS for topic, _ in topic_qos_list):
            raise ValueError('Invalid subscription filter.')

        if self._sock is None:
            return (MQTT_ERR_NO_CONN, None)

        return self._send_subscribe(False, topic_qos_list, properties)

    def unsubscribe(self, topic, properties=None):
        """Unsubscribe the client from one or more topics.

        topic: A single string, or list of strings that are the subscription
               topics to unsubscribe from.
        properties: (MQTT v5.0 only) a Properties instance setting the MQTT v5.0 properties
        to be included. Optional - if not set, no properties are sent.

        Returns a tuple (result, mid), where result is MQTT_ERR_SUCCESS
        to indicate success or (MQTT_ERR_NO_CONN, None) if the client is not
        currently connected.
        mid is the message ID for the unsubscribe request. The mid value can be
        used to track the unsubscribe request by checking against the mid
        argument in the on_unsubscribe() callback if it is defined.

        Raises a ValueError if topic is None or has zero string length, or is
        not a string or list.
        """
        topic_list = None
        if topic is None:
            raise ValueError('Invalid topic.')
        if isinstance(topic, basestring):
            if len(topic) == 0:
                raise ValueError('Invalid topic.')
            topic_list = [topic.encode('utf-8')]
        elif isinstance(topic, list):
            topic_list = []
            for t in topic:
                if len(t) == 0 or not isinstance(t, basestring):
                    raise ValueError('Invalid topic.')
                topic_list.append(t.encode('utf-8'))

        if topic_list is None:
            raise ValueError("No topic specified, or incorrect topic type.")

        if self._sock is None:
            return (MQTT_ERR_NO_CONN, None)

        return self._send_unsubscribe(False, topic_list, properties)

    def loop_read(self, max_packets=1):
        """Process read network events. Use in place of calling loop() if you
        wish to handle your client reads as part of your own application.

        Use socket() to obtain the client socket to call select() or equivalent
        on.

        Do not use if you are using the threaded interface loop_start()."""
        if self._sock is None:
            return MQTT_ERR_NO_CONN

        max_packets = len(self._out_messages) + len(self._in_messages)
        if max_packets < 1:
            max_packets = 1

        for _ in range(0, max_packets):
            if self._sock is None:
                return MQTT_ERR_NO_CONN
            rc = self._packet_read()
            if rc > 0:
                return self._loop_rc_handle(rc)
            elif rc == MQTT_ERR_AGAIN:
                return MQTT_ERR_SUCCESS
        return MQTT_ERR_SUCCESS

    def loop_write(self, max_packets=1):
        """Process write network events. Use in place of calling loop() if you
        wish to handle your client writes as part of your own application.

        Use socket() to obtain the client socket to call select() or equivalent
        on.

        Use want_write() to determine if there is data waiting to be written.

        Do not use if you are using the threaded interface loop_start()."""
        if self._sock is None:
            return MQTT_ERR_NO_CONN

        try:
            rc = self._packet_write()
            if rc == MQTT_ERR_AGAIN:
                return MQTT_ERR_SUCCESS
            elif rc > 0:
                return self._loop_rc_handle(rc)
            else:
                return MQTT_ERR_SUCCESS
        finally:
            if self.want_write():
                self._call_socket_register_write()
            else:
                self._call_socket_unregister_write()

    def want_write(self):
        """Call to determine if there is network data waiting to be written.
        Useful if you are calling select() yourself rather than using loop().
        """
        try:
            packet = self._out_packet.popleft()
            self._out_packet.appendleft(packet)
            return True
        except IndexError:
            return False

    def loop_misc(self):
        """Process miscellaneous network events. Use in place of calling loop() if you
        wish to call select() or equivalent on.

        Do not use if you are using the threaded interface loop_start()."""
        if self._sock is None:
            return MQTT_ERR_NO_CONN

        now = time_func()
        self._check_keepalive()

        if self._ping_t > 0 and now - self._ping_t >= self._keepalive:
            # client->ping_t != 0 means we are waiting for a pingresp.
            # This hasn't happened in the keepalive time so we should disconnect.
            self._sock_close()

            if self._state == mqtt_cs_disconnecting:
                rc = MQTT_ERR_SUCCESS
            else:
                rc = MQTT_ERR_KEEPALIVE

            self._do_on_disconnect(rc)

            return MQTT_ERR_CONN_LOST

        return MQTT_ERR_SUCCESS

    def max_inflight_messages_set(self, inflight):
        """Set the maximum number of messages with QoS>0 that can be part way
        through their network flow at once. Defaults to 20."""
        if inflight < 0:
            raise ValueError('Invalid inflight.')
        self._max_inflight_messages = inflight

    def max_queued_messages_set(self, queue_size):
        """Set the maximum number of messages in the outgoing message queue.
        0 means unlimited."""
        if queue_size < 0:
            raise ValueError('Invalid queue size.')
        if not isinstance(queue_size, int):
            raise ValueError('Invalid type of queue size.')
        self._max_queued_messages = queue_size
        return self

    def message_retry_set(self, retry):
        """No longer used, remove in version 2.0"""
        pass

    def user_data_set(self, userdata):
        """Set the user data variable passed to callbacks. May be any data type."""
        self._userdata = userdata

    def will_set(self, topic, payload=None, qos=0, retain=False, properties=None):
        """Set a Will to be sent by the broker in case the client disconnects unexpectedly.

        This must be called before connect() to have any effect.

        topic: The topic that the will message should be published on.
        payload: The message to send as a will. If not given, or set to None a
        zero length message will be used as the will. Passing an int or float
        will result in the payload being converted to a string representing
        that number. If you wish to send a true int/float, use struct.pack() to
        create the payload you require.
        qos: The quality of service level to use for the will.
        retain: If set to true, the will message will be set as the "last known
        good"/retained message for the topic.
        properties: (MQTT v5.0 only) a Properties instance setting the MQTT v5.0 properties
        to be included with the will message. Optional - if not set, no properties are sent.

        Raises a ValueError if qos is not 0, 1 or 2, or if topic is None or has
        zero string length.
        """
        if topic is None or len(topic) == 0:
            raise ValueError('Invalid topic.')

        if qos < 0 or qos > 2:
            raise ValueError('Invalid QoS level.')

        if properties != None and not isinstance(properties, Properties):
            raise ValueError(
                "The properties argument must be an instance of the Properties class.")

        if isinstance(payload, unicode):
            self._will_payload = payload.encode('utf-8')
        elif isinstance(payload, (bytes, bytearray)):
            self._will_payload = payload
        elif isinstance(payload, (int, float)):
            self._will_payload = str(payload).encode('ascii')
        elif payload is None:
            self._will_payload = b""
        else:
            raise TypeError(
                'payload must be a string, bytearray, int, float or None.')

        self._will = True
        self._will_topic = topic.encode('utf-8')
        self._will_qos = qos
        self._will_retain = retain
        self._will_properties = properties

    def will_clear(self):
        """ Removes a will that was previously configured with will_set().

        Must be called before connect() to have any effect."""
        self._will = False
        self._will_topic = b""
        self._will_payload = b""
        self._will_qos = 0
        self._will_retain = False

    def socket(self):
        """Return the socket or ssl object for this client."""
        return self._sock

    def loop_forever(self, timeout=1.0, max_packets=1, retry_first_connection=False):
        """This function calls the network loop functions for you in an
        infinite blocking loop. It is useful for the case where you only want
        to run the MQTT client loop in your program.

        loop_forever() will handle reconnecting for you if reconnect_on_failure is
        true (this is the default behavior). If you call disconnect() in a callback
        it will return.


        timeout: The time in seconds to wait for incoming/outgoing network
          traffic before timing out and returning.
        max_packets: Not currently used.
        retry_first_connection: Should the first connection attempt be retried on failure.
          This is independent of the reconnect_on_failure setting.

        Raises OSError/WebsocketConnectionError on first connection failures unless retry_first_connection=True
        """

        run = True

        while run:
            if self._thread_terminate is True:
                break

            if self._state == mqtt_cs_connect_async:
                try:
                    self.reconnect()
                except (OSError, WebsocketConnectionError):
                    self._handle_on_connect_fail()
                    if not retry_first_connection:
                        raise
                    self._easy_log(
                        MQTT_LOG_DEBUG, "Connection failed, retrying")
                    self._reconnect_wait()
            else:
                break

        while run:
            rc = MQTT_ERR_SUCCESS
            while rc == MQTT_ERR_SUCCESS:
                rc = self._loop(timeout)
                # We don't need to worry about locking here, because we've
                # either called loop_forever() when in single threaded mode, or
                # in multi threaded mode when loop_stop() has been called and
                # so no other threads can access _out_packet or _messages.
                if (self._thread_terminate is True
                    and len(self._out_packet) == 0
                        and len(self._out_messages) == 0):
                    rc = 1
                    run = False

            def should_exit():
                return self._state == mqtt_cs_disconnecting or run is False or self._thread_terminate is True

            if should_exit() or not self._reconnect_on_failure:
                run = False
            else:
                self._reconnect_wait()

                if should_exit():
                    run = False
                else:
                    try:
                        self.reconnect()
                    except (OSError, WebsocketConnectionError):
                        self._handle_on_connect_fail()
                        self._easy_log(
                            MQTT_LOG_DEBUG, "Connection failed, retrying")

        return rc

    def loop_start(self):
        """This is part of the threaded client interface. Call this once to
        start a new thread to process network traffic. This provides an
        alternative to repeatedly calling loop() yourself.
        """
        if self._thread is not None:
            return MQTT_ERR_INVAL

        self._sockpairR, self._sockpairW = _socketpair_compat()
        self._thread_terminate = False
        self._thread = threading.Thread(target=self._thread_main)
        self._thread.daemon = True
        self._thread.start()

    def loop_stop(self, force=False):
        """This is part of the threaded client interface. Call this once to
        stop the network thread previously created with loop_start(). This call
        will block until the network thread finishes.

        The force parameter is currently ignored.
        """
        if self._thread is None:
            return MQTT_ERR_INVAL

        self._thread_terminate = True
        if threading.current_thread() != self._thread:
            self._thread.join()
            self._thread = None

    @property
    def on_log(self):
        """If implemented, called when the client has log information.
        Defined to allow debugging."""
        return self._on_log

    @on_log.setter
    def on_log(self, func):
        """ Define the logging callback implementation.

        Expected signature is:
            log_callback(client, userdata, level, buf)

        client:     the client instance for this callback
        userdata:   the private user data as set in Client() or userdata_set()
        level:      gives the severity of the message and will be one of
                    MQTT_LOG_INFO, MQTT_LOG_NOTICE, MQTT_LOG_WARNING,
                    MQTT_LOG_ERR, and MQTT_LOG_DEBUG.
        buf:        the message itself

        Decorator: @client.log_callback() (```client``` is the name of the
            instance which this callback is being attached to)
        """
        self._on_log = func

    def log_callback(self):
        def decorator(func):
            self.on_log = func
            return func
        return decorator

    @property
    def on_connect(self):
        """If implemented, called when the broker responds to our connection
        request."""
        return self._on_connect

    @on_connect.setter
    def on_connect(self, func):
        """ Define the connect callback implementation.

        Expected signature for MQTT v3.1 and v3.1.1 is:
            connect_callback(client, userdata, flags, rc)

        and for MQTT v5.0:
            connect_callback(client, userdata, flags, reasonCode, properties)

        client:     the client instance for this callback
        userdata:   the private user data as set in Client() or userdata_set()
        flags:      response flags sent by the broker
        rc:         the connection result
        reasonCode: the MQTT v5.0 reason code: an instance of the ReasonCode class.
                    ReasonCode may be compared to integer.
        properties: the MQTT v5.0 properties returned from the broker.  An instance
                    of the Properties class.
                    For MQTT v3.1 and v3.1.1 properties is not provided but for compatibility
                    with MQTT v5.0, we recommend adding properties=None.

        flags is a dict that contains response flags from the broker:
            flags['session present'] - this flag is useful for clients that are
                using clean session set to 0 only. If a client with clean
                session=0, that reconnects to a broker that it has previously
                connected to, this flag indicates whether the broker still has the
                session information for the client. If 1, the session still exists.

        The value of rc indicates success or not:
            0: Connection successful
            1: Connection refused - incorrect protocol version
            2: Connection refused - invalid client identifier
            3: Connection refused - server unavailable
            4: Connection refused - bad username or password
            5: Connection refused - not authorised
            6-255: Currently unused.

        Decorator: @client.connect_callback() (```client``` is the name of the
            instance which this callback is being attached to)

        """
        with self._callback_mutex:
            self._on_connect = func

    def connect_callback(self):
        def decorator(func):
            self.on_connect = func
            return func
        return decorator

    @property
    def on_connect_fail(self):
        """If implemented, called when the client failed to connect
        to the broker."""
        return self._on_connect_fail

    @on_connect_fail.setter
    def on_connect_fail(self, func):
        """ Define the connection failure callback implementation

        Expected signature is:
            on_connect_fail(client, userdata)

        client:     the client instance for this callback
        userdata:   the private user data as set in Client() or userdata_set()

        Decorator: @client.connect_fail_callback() (```client``` is the name of the
            instance which this callback is being attached to)

        """
        with self._callback_mutex:
            self._on_connect_fail = func

    def connect_fail_callback(self):
        def decorator(func):
            self.on_connect_fail = func
            return func
        return decorator

    @property
    def on_subscribe(self):
        """If implemented, called when the broker responds to a subscribe
        request."""
        return self._on_subscribe

    @on_subscribe.setter
    def on_subscribe(self, func):
        """ Define the subscribe callback implementation.

        Expected signature for MQTT v3.1.1 and v3.1 is:
            subscribe_callback(client, userdata, mid, granted_qos)

        and for MQTT v5.0:
            subscribe_callback(client, userdata, mid, reasonCodes, properties)

        client:         the client instance for this callback
        userdata:       the private user data as set in Client() or userdata_set()
        mid:            matches the mid variable returned from the corresponding
                        subscribe() call.
        granted_qos:    list of integers that give the QoS level the broker has
                        granted for each of the different subscription requests.
        reasonCodes:    the MQTT v5.0 reason codes received from the broker for each
                        subscription.  A list of ReasonCodes instances.
        properties:     the MQTT v5.0 properties received from the broker.  A
                        list of Properties class instances.

        Decorator: @client.subscribe_callback() (```client``` is the name of the
            instance which this callback is being attached to)
        """
        with self._callback_mutex:
            self._on_subscribe = func

    def subscribe_callback(self):
        def decorator(func):
            self.on_subscribe = func
            return func
        return decorator

    @property
    def on_message(self):
        """If implemented, called when a message has been received on a topic
        that the client subscribes to.

        This callback will be called for every message received. Use
        message_callback_add() to define multiple callbacks that will be called
        for specific topic filters."""
        return self._on_message

    @on_message.setter
    def on_message(self, func):
        """ Define the message received callback implementation.

        Expected signature is:
            on_message_callback(client, userdata, message)

        client:     the client instance for this callback
        userdata:   the private user data as set in Client() or userdata_set()
        message:    an instance of MQTTMessage.
                    This is a class with members topic, payload, qos, retain.

        Decorator: @client.message_callback() (```client``` is the name of the
            instance which this callback is being attached to)

        """
        with self._callback_mutex:
            self._on_message = func

    def message_callback(self):
        def decorator(func):
            self.on_message = func
            return func
        return decorator

    @property
    def on_publish(self):
        """If implemented, called when a message that was to be sent using the
        publish() call has completed transmission to the broker.

        For messages with QoS levels 1 and 2, this means that the appropriate
        handshakes have completed. For QoS 0, this simply means that the message
        has left the client.
        This callback is important because even if the publish() call returns
        success, it does not always mean that the message has been sent."""
        return self._on_publish

    @on_publish.setter
    def on_publish(self, func):
        """ Define the published message callback implementation.

        Expected signature is:
            on_publish_callback(client, userdata, mid)

        client:     the client instance for this callback
        userdata:   the private user data as set in Client() or userdata_set()
        mid:        matches the mid variable returned from the corresponding
                    publish() call, to allow outgoing messages to be tracked.

        Decorator: @client.publish_callback() (```client``` is the name of the
            instance which this callback is being attached to)

        """
        with self._callback_mutex:
            self._on_publish = func

    def publish_callback(self):
        def decorator(func):
            self.on_publish = func
            return func
        return decorator

    @property
    def on_unsubscribe(self):
        """If implemented, called when the broker responds to an unsubscribe
        request."""
        return self._on_unsubscribe

    @on_unsubscribe.setter
    def on_unsubscribe(self, func):
        """ Define the unsubscribe callback implementation.

        Expected signature for MQTT v3.1.1 and v3.1 is:
            unsubscribe_callback(client, userdata, mid)

        and for MQTT v5.0:
            unsubscribe_callback(client, userdata, mid, properties, reasonCodes)

        client:         the client instance for this callback
        userdata:       the private user data as set in Client() or userdata_set()
        mid:            matches the mid variable returned from the corresponding
                        unsubscribe() call.
        properties:     the MQTT v5.0 properties received from the broker.  A
                        list of Properties class instances.
        reasonCodes:    the MQTT v5.0 reason codes received from the broker for each
                        unsubscribe topic.  A list of ReasonCodes instances

        Decorator: @client.unsubscribe_callback() (```client``` is the name of the
            instance which this callback is being attached to)
        """
        with self._callback_mutex:
            self._on_unsubscribe = func

    def unsubscribe_callback(self):
        def decorator(func):
            self.on_unsubscribe = func
            return func
        return decorator

    @property
    def on_disconnect(self):
        """If implemented, called when the client disconnects from the broker.
        """
        return self._on_disconnect

    @on_disconnect.setter
    def on_disconnect(self, func):
        """ Define the disconnect callback implementation.

        Expected signature for MQTT v3.1.1 and v3.1 is:
            disconnect_callback(client, userdata, rc)

        and for MQTT v5.0:
            disconnect_callback(client, userdata, reasonCode, properties)

        client:     the client instance for this callback
        userdata:   the private user data as set in Client() or userdata_set()
        rc:         the disconnection result
                    The rc parameter indicates the disconnection state. If
                    MQTT_ERR_SUCCESS (0), the callback was called in response to
                    a disconnect() call. If any other value the disconnection
                    was unexpected, such as might be caused by a network error.

        Decorator: @client.disconnect_callback() (```client``` is the name of the
            instance which this callback is being attached to)

        """
        with self._callback_mutex:
            self._on_disconnect = func

    def disconnect_callback(self):
        def decorator(func):
            self.on_disconnect = func
            return func
        return decorator

    @property
    def on_socket_open(self):
        """If implemented, called just after the socket was opend."""
        return self._on_socket_open

    @on_socket_open.setter
    def on_socket_open(self, func):
        """Define the socket_open callback implementation.

        This should be used to register the socket to an external event loop for reading.

        Expected signature is:
            socket_open_callback(client, userdata, socket)

        client:     the client instance for this callback
        userdata:   the private user data as set in Client() or userdata_set()
        sock:       the socket which was just opened.

        Decorator: @client.socket_open_callback() (```client``` is the name of the
            instance which this callback is being attached to)
        """
        with self._callback_mutex:
            self._on_socket_open = func

    def socket_open_callback(self):
        def decorator(func):
            self.on_socket_open = func
            return func
        return decorator

    def _call_socket_open(self):
        """Call the socket_open callback with the just-opened socket"""
        with self._callback_mutex:
            on_socket_open = self.on_socket_open

        if on_socket_open:
            with self._in_callback_mutex:
                try:
                    on_socket_open(self, self._userdata, self._sock)
                except Exception as err:
                    self._easy_log(
                        MQTT_LOG_ERR, 'Caught exception in on_socket_open: %s', err)
                    if not self.suppress_exceptions:
                        raise

    @property
    def on_socket_close(self):
        """If implemented, called just before the socket is closed."""
        return self._on_socket_close

    @on_socket_close.setter
    def on_socket_close(self, func):
        """Define the socket_close callback implementation.

        This should be used to unregister the socket from an external event loop for reading.

        Expected signature is:
            socket_close_callback(client, userdata, socket)

        client:     the client instance for this callback
        userdata:   the private user data as set in Client() or userdata_set()
        sock:       the socket which is about to be closed.

        Decorator: @client.socket_close_callback() (```client``` is the name of the
            instance which this callback is being attached to)
        """
        with self._callback_mutex:
            self._on_socket_close = func

    def socket_close_callback(self):
        def decorator(func):
            self.on_socket_close = func
            return func
        return decorator

    def _call_socket_close(self, sock):
        """Call the socket_close callback with the about-to-be-closed socket"""
        with self._callback_mutex:
            on_socket_close = self.on_socket_close

        if on_socket_close:
            with self._in_callback_mutex:
                try:
                    on_socket_close(self, self._userdata, sock)
                except Exception as err:
                    self._easy_log(
                        MQTT_LOG_ERR, 'Caught exception in on_socket_close: %s', err)
                    if not self.suppress_exceptions:
                        raise

    @property
    def on_socket_register_write(self):
        """If implemented, called when the socket needs writing but can't."""
        return self._on_socket_register_write

    @on_socket_register_write.setter
    def on_socket_register_write(self, func):
        """Define the socket_register_write callback implementation.

        This should be used to register the socket with an external event loop for writing.

        Expected signature is:
            socket_register_write_callback(client, userdata, socket)

        client:     the client instance for this callback
        userdata:   the private user data as set in Client() or userdata_set()
        sock:       the socket which should be registered for writing

        Decorator: @client.socket_register_write_callback() (```client``` is the name of the
            instance which this callback is being attached to)
        """
        with self._callback_mutex:
            self._on_socket_register_write = func

    def socket_register_write_callback(self):
        def decorator(func):
            self._on_socket_register_write = func
            return func
        return decorator

    def _call_socket_register_write(self):
        """Call the socket_register_write callback with the unwritable socket"""
        if not self._sock or self._registered_write:
            return
        self._registered_write = True
        with self._callback_mutex:
            on_socket_register_write = self.on_socket_register_write

        if on_socket_register_write:
            try:
                on_socket_register_write(
                    self, self._userdata, self._sock)
            except Exception as err:
                self._easy_log(
                    MQTT_LOG_ERR, 'Caught exception in on_socket_register_write: %s', err)
                if not self.suppress_exceptions:
                    raise

    @property
    def on_socket_unregister_write(self):
        """If implemented, called when the socket doesn't need writing anymore."""
        return self._on_socket_unregister_write

    @on_socket_unregister_write.setter
    def on_socket_unregister_write(self, func):
        """Define the socket_unregister_write callback implementation.

        This should be used to unregister the socket from an external event loop for writing.

        Expected signature is:
            socket_unregister_write_callback(client, userdata, socket)

        client:     the client instance for this callback
        userdata:   the private user data as set in Client() or userdata_set()
        sock:       the socket which should be unregistered for writing

        Decorator: @client.socket_unregister_write_callback() (```client``` is the name of the
            instance which this callback is being attached to)
        """
        with self._callback_mutex:
            self._on_socket_unregister_write = func

    def socket_unregister_write_callback(self):
        def decorator(func):
            self._on_socket_unregister_write = func
            return func
        return decorator

    def _call_socket_unregister_write(self, sock=None):
        """Call the socket_unregister_write callback with the writable socket"""
        sock = sock or self._sock
        if not sock or not self._registered_write:
            return
        self._registered_write = False

        with self._callback_mutex:
            on_socket_unregister_write = self.on_socket_unregister_write

        if on_socket_unregister_write:
            try:
                on_socket_unregister_write(self, self._userdata, sock)
            except Exception as err:
                self._easy_log(
                    MQTT_LOG_ERR, 'Caught exception in on_socket_unregister_write: %s', err)
                if not self.suppress_exceptions:
                    raise

    def message_callback_add(self, sub, callback):
        """Register a message callback for a specific topic.
        Messages that match 'sub' will be passed to 'callback'. Any
        non-matching messages will be passed to the default on_message
        callback.

        Call multiple times with different 'sub' to define multiple topic
        specific callbacks.

        Topic specific callbacks may be removed with
        message_callback_remove()."""
        if callback is None or sub is None:
            raise ValueError("sub and callback must both be defined.")

        with self._callback_mutex:
            self._on_message_filtered[sub] = callback

    def topic_callback(self, sub):
        def decorator(func):
            self.message_callback_add(sub, func)
            return func
        return decorator

    def message_callback_remove(self, sub):
        """Remove a message callback previously registered with
        message_callback_add()."""
        if sub is None:
            raise ValueError("sub must defined.")

        with self._callback_mutex:
            try:
                del self._on_message_filtered[sub]
            except KeyError:  # no such subscription
                pass

    # ============================================================
    # Private functions
    # ============================================================

    def _loop_rc_handle(self, rc, properties=None):
        if rc:
            self._sock_close()

            if self._state == mqtt_cs_disconnecting:
                rc = MQTT_ERR_SUCCESS

            self._do_on_disconnect(rc, properties)

        return rc

    def _packet_read(self):
        # This gets called if pselect() indicates that there is network data
        # available - ie. at least one byte.  What we do depends on what data we
        # already have.
        # If we've not got a command, attempt to read one and save it. This should
        # always work because it's only a single byte.
        # Then try to read the remaining length. This may fail because it is may
        # be more than one byte - will need to save data pending next read if it
        # does fail.
        # Then try to read the remaining payload, where 'payload' here means the
        # combined variable header and actual payload. This is the most likely to
        # fail due to longer length, so save current data and current position.
        # After all data is read, send to _mqtt_handle_packet() to deal with.
        # Finally, free the memory and reset everything to starting conditions.
        if self._in_packet['command'] == 0:
            try:
                command = self._sock_recv(1)
            except BlockingIOError:
                return MQTT_ERR_AGAIN
            except ConnectionError as err:
                self._easy_log(
                    MQTT_LOG_ERR, 'failed to receive on socket: %s', err)
                return MQTT_ERR_CONN_LOST
            else:
                if len(command) == 0:
                    return MQTT_ERR_CONN_LOST
                command, = struct.unpack("!B", command)
                self._in_packet['command'] = command

        if self._in_packet['have_remaining'] == 0:
            # Read remaining
            # Algorithm for decoding taken from pseudo code at
            # http://publib.boulder.ibm.com/infocenter/wmbhelp/v6r0m0/topic/com.ibm.etools.mft.doc/ac10870_.htm
            while True:
                try:
                    byte = self._sock_recv(1)
                except BlockingIOError:
                    return MQTT_ERR_AGAIN
                except ConnectionError as err:
                    self._easy_log(
                        MQTT_LOG_ERR, 'failed to receive on socket: %s', err)
                    return MQTT_ERR_CONN_LOST
                else:
                    if len(byte) == 0:
                        return MQTT_ERR_CONN_LOST
                    byte, = struct.unpack("!B", byte)
                    self._in_packet['remaining_count'].append(byte)
                    # Max 4 bytes length for remaining length as defined by protocol.
                    # Anything more likely means a broken/malicious client.
                    if len(self._in_packet['remaining_count']) > 4:
                        return MQTT_ERR_PROTOCOL

                    self._in_packet['remaining_length'] += (
                        byte & 127) * self._in_packet['remaining_mult']
                    self._in_packet['remaining_mult'] = self._in_packet['remaining_mult'] * 128

                if (byte & 128) == 0:
                    break

            self._in_packet['have_remaining'] = 1
            self._in_packet['to_process'] = self._in_packet['remaining_length']

        count = 100 # Don't get stuck in this loop if we have a huge message.
        while self._in_packet['to_process'] > 0:
            try:
                data = self._sock_recv(self._in_packet['to_process'])
            except BlockingIOError:
                return MQTT_ERR_AGAIN
            except ConnectionError as err:
                self._easy_log(
                    MQTT_LOG_ERR, 'failed to receive on socket: %s', err)
                return MQTT_ERR_CONN_LOST
            else:
                if len(data) == 0:
                    return MQTT_ERR_CONN_LOST
                self._in_packet['to_process'] -= len(data)
                self._in_packet['packet'] += data
            count -= 1
            if count == 0:
                with self._msgtime_mutex:
                    self._last_msg_in = time_func()
                return MQTT_ERR_AGAIN

        # All data for this packet is read.
        self._in_packet['pos'] = 0
        rc = self._packet_handle()

        # Free data and reset values
        self._in_packet = {
            'command': 0,
            'have_remaining': 0,
            'remaining_count': [],
            'remaining_mult': 1,
            'remaining_length': 0,
            'packet': bytearray(b""),
            'to_process': 0,
            'pos': 0}

        with self._msgtime_mutex:
            self._last_msg_in = time_func()
        return rc

    def _packet_write(self):
        while True:
            try:
                packet = self._out_packet.popleft()
            except IndexError:
                return MQTT_ERR_SUCCESS

            try:
                write_length = self._sock_send(
                    packet['packet'][packet['pos']:])
            except (AttributeError, ValueError):
                self._out_packet.appendleft(packet)
                return MQTT_ERR_SUCCESS
            except BlockingIOError:
                self._out_packet.appendleft(packet)
                return MQTT_ERR_AGAIN
            except ConnectionError as err:
                self._out_packet.appendleft(packet)
                self._easy_log(
                    MQTT_LOG_ERR, 'failed to receive on socket: %s', err)
                return MQTT_ERR_CONN_LOST

            if write_length > 0:
                packet['to_process'] -= write_length
                packet['pos'] += write_length

                if packet['to_process'] == 0:
                    if (packet['command'] & 0xF0) == PUBLISH and packet['qos'] == 0:
                        with self._callback_mutex:
                            on_publish = self.on_publish

                        if on_publish:
                            with self._in_callback_mutex:
                                try:
                                    on_publish(
                                        self, self._userdata, packet['mid'])
                                except Exception as err:
                                    self._easy_log(
                                        MQTT_LOG_ERR, 'Caught exception in on_publish: %s', err)
                                    if not self.suppress_exceptions:
                                        raise

                        packet['info']._set_as_published()

                    if (packet['command'] & 0xF0) == DISCONNECT:
                        with self._msgtime_mutex:
                            self._last_msg_out = time_func()

                        self._do_on_disconnect(MQTT_ERR_SUCCESS)
                        self._sock_close()
                        return MQTT_ERR_SUCCESS

                else:
                    # We haven't finished with this packet
                    self._out_packet.appendleft(packet)
            else:
                break

        with self._msgtime_mutex:
            self._last_msg_out = time_func()

        return MQTT_ERR_SUCCESS

    def _easy_log(self, level, fmt, *args):
        if self.on_log is not None:
            buf = fmt % args
            try:
                self.on_log(self, self._userdata, level, buf)
            except Exception:
                # Can't _easy_log this, as we'll recurse until we break
                pass  # self._logger will pick this up, so we're fine
        if self._logger is not None:
            level_std = LOGGING_LEVEL[level]
            self._logger.log(level_std, fmt, *args)

    def _check_keepalive(self):
        if self._keepalive == 0:
            return MQTT_ERR_SUCCESS

        now = time_func()

        with self._msgtime_mutex:
            last_msg_out = self._last_msg_out
            last_msg_in = self._last_msg_in

        if self._sock is not None and (now - last_msg_out >= self._keepalive or now - last_msg_in >= self._keepalive):
            if self._state == mqtt_cs_connected and self._ping_t == 0:
                try:
                    self._send_pingreq()
                except Exception:
                    self._sock_close()
                    self._do_on_disconnect(MQTT_ERR_CONN_LOST)
                else:
                    with self._msgtime_mutex:
                        self._last_msg_out = now
                        self._last_msg_in = now
            else:
                self._sock_close()

                if self._state == mqtt_cs_disconnecting:
                    rc = MQTT_ERR_SUCCESS
                else:
                    rc = MQTT_ERR_KEEPALIVE

                self._do_on_disconnect(rc)

    def _mid_generate(self):
        with self._mid_generate_mutex:
            self._last_mid += 1
            if self._last_mid == 65536:
                self._last_mid = 1
            return self._last_mid

    @staticmethod
    def _topic_wildcard_len_check(topic):
        # Search for + or # in a topic. Return MQTT_ERR_INVAL if found.
        # Also returns MQTT_ERR_INVAL if the topic string is too long.
        # Returns MQTT_ERR_SUCCESS if everything is fine.
        if b'+' in topic or b'#' in topic or len(topic) > 65535:
            return MQTT_ERR_INVAL
        else:
            return MQTT_ERR_SUCCESS

    @staticmethod
    def _filter_wildcard_len_check(sub):
        if (len(sub) == 0 or len(sub) > 65535
            or any(b'+' in p or b'#' in p for p in sub.split(b'/') if len(p) > 1)
                or b'#/' in sub):
            return MQTT_ERR_INVAL
        else:
            return MQTT_ERR_SUCCESS

    def _send_pingreq(self):
        self._easy_log(MQTT_LOG_DEBUG, "Sending PINGREQ")
        rc = self._send_simple_command(PINGREQ)
        if rc == MQTT_ERR_SUCCESS:
            self._ping_t = time_func()
        return rc

    def _send_pingresp(self):
        self._easy_log(MQTT_LOG_DEBUG, "Sending PINGRESP")
        return self._send_simple_command(PINGRESP)

    def _send_puback(self, mid):
        self._easy_log(MQTT_LOG_DEBUG, "Sending PUBACK (Mid: %d)", mid)
        return self._send_command_with_mid(PUBACK, mid, False)

    def _send_pubcomp(self, mid):
        self._easy_log(MQTT_LOG_DEBUG, "Sending PUBCOMP (Mid: %d)", mid)
        return self._send_command_with_mid(PUBCOMP, mid, False)

    def _pack_remaining_length(self, packet, remaining_length):
        remaining_bytes = []
        while True:
            byte = remaining_length % 128
            remaining_length = remaining_length // 128
            # If there are more digits to encode, set the top bit of this digit
            if remaining_length > 0:
                byte |= 0x80

            remaining_bytes.append(byte)
            packet.append(byte)
            if remaining_length == 0:
                # FIXME - this doesn't deal with incorrectly large payloads
                return packet

    def _pack_str16(self, packet, data):
        if isinstance(data, unicode):
            data = data.encode('utf-8')
        packet.extend(struct.pack("!H", len(data)))
        packet.extend(data)

    def _send_publish(self, mid, topic, payload=b'', qos=0, retain=False, dup=False, info=None, properties=None):
        # we assume that topic and payload are already properly encoded
        assert not isinstance(topic, unicode) and not isinstance(
            payload, unicode) and payload is not None

        if self._sock is None:
            return MQTT_ERR_NO_CONN

        command = PUBLISH | ((dup & 0x1) << 3) | (qos << 1) | retain
        packet = bytearray()
        packet.append(command)

        payloadlen = len(payload)
        remaining_length = 2 + len(topic) + payloadlen

        if payloadlen == 0:
            if self._protocol == MQTTv5:
                self._easy_log(
                    MQTT_LOG_DEBUG,
                    "Sending PUBLISH (d%d, q%d, r%d, m%d), '%s', properties=%s (NULL payload)",
                    dup, qos, retain, mid, topic, properties
                )
            else:
                self._easy_log(
                    MQTT_LOG_DEBUG,
                    "Sending PUBLISH (d%d, q%d, r%d, m%d), '%s' (NULL payload)",
                    dup, qos, retain, mid, topic
                )
        else:
            if self._protocol == MQTTv5:
                self._easy_log(
                    MQTT_LOG_DEBUG,
                    "Sending PUBLISH (d%d, q%d, r%d, m%d), '%s', properties=%s, ... (%d bytes)",
                    dup, qos, retain, mid, topic, properties, payloadlen
                )
            else:
                self._easy_log(
                    MQTT_LOG_DEBUG,
                    "Sending PUBLISH (d%d, q%d, r%d, m%d), '%s', ... (%d bytes)",
                    dup, qos, retain, mid, topic, payloadlen
                )

        if qos > 0:
            # For message id
            remaining_length += 2

        if self._protocol == MQTTv5:
            if properties is None:
                packed_properties = b'\x00'
            else:
                packed_properties = properties.pack()
            remaining_length += len(packed_properties)

        self._pack_remaining_length(packet, remaining_length)
        self._pack_str16(packet, topic)

        if qos > 0:
            # For message id
            packet.extend(struct.pack("!H", mid))

        if self._protocol == MQTTv5:
            packet.extend(packed_properties)

        packet.extend(payload)

        return self._packet_queue(PUBLISH, packet, mid, qos, info)

    def _send_pubrec(self, mid):
        self._easy_log(MQTT_LOG_DEBUG, "Sending PUBREC (Mid: %d)", mid)
        return self._send_command_with_mid(PUBREC, mid, False)

    def _send_pubrel(self, mid):
        self._easy_log(MQTT_LOG_DEBUG, "Sending PUBREL (Mid: %d)", mid)
        return self._send_command_with_mid(PUBREL | 2, mid, False)

    def _send_command_with_mid(self, command, mid, dup):
        # For PUBACK, PUBCOMP, PUBREC, and PUBREL
        if dup:
            command |= 0x8

        remaining_length = 2
        packet = struct.pack('!BBH', command, remaining_length, mid)
        return self._packet_queue(command, packet, mid, 1)

    def _send_simple_command(self, command):
        # For DISCONNECT, PINGREQ and PINGRESP
        remaining_length = 0
        packet = struct.pack('!BB', command, remaining_length)
        return self._packet_queue(command, packet, 0, 0)

    def _send_connect(self, keepalive):
        proto_ver = self._protocol
        # hard-coded UTF-8 encoded string
        protocol = b"MQTT" if proto_ver >= MQTTv311 else b"MQIsdp"

        remaining_length = 2 + len(protocol) + 1 + \
            1 + 2 + 2 + len(self._client_id)

        connect_flags = 0
        if self._protocol == MQTTv5:
            if self._clean_start == True:
                connect_flags |= 0x02
            elif self._clean_start == MQTT_CLEAN_START_FIRST_ONLY and self._mqttv5_first_connect:
                connect_flags |= 0x02
        elif self._clean_session:
            connect_flags |= 0x02

        if self._will:
            remaining_length += 2 + \
                len(self._will_topic) + 2 + len(self._will_payload)
            connect_flags |= 0x04 | ((self._will_qos & 0x03) << 3) | (
                (self._will_retain & 0x01) << 5)

        if self._username is not None:
            remaining_length += 2 + len(self._username)
            connect_flags |= 0x80
            if self._password is not None:
                connect_flags |= 0x40
                remaining_length += 2 + len(self._password)

        if self._protocol == MQTTv5:
            if self._connect_properties is None:
                packed_connect_properties = b'\x00'
            else:
                packed_connect_properties = self._connect_properties.pack()
            remaining_length += len(packed_connect_properties)
            if self._will:
                if self._will_properties is None:
                    packed_will_properties = b'\x00'
                else:
                    packed_will_properties = self._will_properties.pack()
                remaining_length += len(packed_will_properties)

        command = CONNECT
        packet = bytearray()
        packet.append(command)

        # as per the mosquitto broker, if the MSB of this version is set
        # to 1, then it treats the connection as a bridge
        if self._client_mode == MQTT_BRIDGE:
            proto_ver |= 0x80

        self._pack_remaining_length(packet, remaining_length)
        packet.extend(struct.pack("!H" + str(len(protocol)) + "sBBH", len(protocol), protocol, proto_ver, connect_flags,
                                  keepalive))

        if self._protocol == MQTTv5:
            packet += packed_connect_properties

        self._pack_str16(packet, self._client_id)

        if self._will:
            if self._protocol == MQTTv5:
                packet += packed_will_properties
            self._pack_str16(packet, self._will_topic)
            self._pack_str16(packet, self._will_payload)

        if self._username is not None:
            self._pack_str16(packet, self._username)

            if self._password is not None:
                self._pack_str16(packet, self._password)

        self._keepalive = keepalive
        if self._protocol == MQTTv5:
            self._easy_log(
                MQTT_LOG_DEBUG,
                "Sending CONNECT (u%d, p%d, wr%d, wq%d, wf%d, c%d, k%d) client_id=%s properties=%s",
                (connect_flags & 0x80) >> 7,
                (connect_flags & 0x40) >> 6,
                (connect_flags & 0x20) >> 5,
                (connect_flags & 0x18) >> 3,
                (connect_flags & 0x4) >> 2,
                (connect_flags & 0x2) >> 1,
                keepalive,
                self._client_id,
                self._connect_properties
            )
        else:
            self._easy_log(
                MQTT_LOG_DEBUG,
                "Sending CONNECT (u%d, p%d, wr%d, wq%d, wf%d, c%d, k%d) client_id=%s",
                (connect_flags & 0x80) >> 7,
                (connect_flags & 0x40) >> 6,
                (connect_flags & 0x20) >> 5,
                (connect_flags & 0x18) >> 3,
                (connect_flags & 0x4) >> 2,
                (connect_flags & 0x2) >> 1,
                keepalive,
                self._client_id
            )
        return self._packet_queue(command, packet, 0, 0)

    def _send_disconnect(self, reasoncode=None, properties=None):
        if self._protocol == MQTTv5:
            self._easy_log(MQTT_LOG_DEBUG, "Sending DISCONNECT reasonCode=%s properties=%s",
                           reasoncode,
                           properties
                           )
        else:
            self._easy_log(MQTT_LOG_DEBUG, "Sending DISCONNECT")

        remaining_length = 0

        command = DISCONNECT
        packet = bytearray()
        packet.append(command)

        if self._protocol == MQTTv5:
            if properties is not None or reasoncode is not None:
                if reasoncode is None:
                    reasoncode = ReasonCodes(DISCONNECT >> 4, identifier=0)
                remaining_length += 1
                if properties is not None:
                    packed_props = properties.pack()
                    remaining_length += len(packed_props)

        self._pack_remaining_length(packet, remaining_length)

        if self._protocol == MQTTv5:
            if reasoncode != None:
                packet += reasoncode.pack()
                if properties != None:
                    packet += packed_props

        return self._packet_queue(command, packet, 0, 0)

    def _send_subscribe(self, dup, topics, properties=None):
        remaining_length = 2
        if self._protocol == MQTTv5:
            if properties is None:
                packed_subscribe_properties = b'\x00'
            else:
                packed_subscribe_properties = properties.pack()
            remaining_length += len(packed_subscribe_properties)
        for t, _ in topics:
            remaining_length += 2 + len(t) + 1

        command = SUBSCRIBE | (dup << 3) | 0x2
        packet = bytearray()
        packet.append(command)
        self._pack_remaining_length(packet, remaining_length)
        local_mid = self._mid_generate()
        packet.extend(struct.pack("!H", local_mid))

        if self._protocol == MQTTv5:
            packet += packed_subscribe_properties

        for t, q in topics:
            self._pack_str16(packet, t)
            if self._protocol == MQTTv5:
                packet += q.pack()
            else:
                packet.append(q)

        self._easy_log(
            MQTT_LOG_DEBUG,
            "Sending SUBSCRIBE (d%d, m%d) %s",
            dup,
            local_mid,
            topics,
        )
        return (self._packet_queue(command, packet, local_mid, 1), local_mid)

    def _send_unsubscribe(self, dup, topics, properties=None):
        remaining_length = 2
        if self._protocol == MQTTv5:
            if properties is None:
                packed_unsubscribe_properties = b'\x00'
            else:
                packed_unsubscribe_properties = properties.pack()
            remaining_length += len(packed_unsubscribe_properties)
        for t in topics:
            remaining_length += 2 + len(t)

        command = UNSUBSCRIBE | (dup << 3) | 0x2
        packet = bytearray()
        packet.append(command)
        self._pack_remaining_length(packet, remaining_length)
        local_mid = self._mid_generate()
        packet.extend(struct.pack("!H", local_mid))

        if self._protocol == MQTTv5:
            packet += packed_unsubscribe_properties

        for t in topics:
            self._pack_str16(packet, t)

        # topics_repr = ", ".join("'"+topic.decode('utf8')+"'" for topic in topics)
        if self._protocol == MQTTv5:
            self._easy_log(
                MQTT_LOG_DEBUG,
                "Sending UNSUBSCRIBE (d%d, m%d) %s %s",
                dup,
                local_mid,
                properties,
                topics,
            )
        else:
            self._easy_log(
                MQTT_LOG_DEBUG,
                "Sending UNSUBSCRIBE (d%d, m%d) %s",
                dup,
                local_mid,
                topics,
            )
        return (self._packet_queue(command, packet, local_mid, 1), local_mid)

    def _check_clean_session(self):
        if self._protocol == MQTTv5:
            if self._clean_start == MQTT_CLEAN_START_FIRST_ONLY:
                return self._mqttv5_first_connect
            else:
                return self._clean_start
        else:
            return self._clean_session

    def _messages_reconnect_reset_out(self):
        with self._out_message_mutex:
            self._inflight_messages = 0
            for m in self._out_messages.values():
                m.timestamp = 0
                if self._max_inflight_messages == 0 or self._inflight_messages < self._max_inflight_messages:
                    if m.qos == 0:
                        m.state = mqtt_ms_publish
                    elif m.qos == 1:
                        # self._inflight_messages = self._inflight_messages + 1
                        if m.state == mqtt_ms_wait_for_puback:
                            m.dup = True
                        m.state = mqtt_ms_publish
                    elif m.qos == 2:
                        # self._inflight_messages = self._inflight_messages + 1
                        if self._check_clean_session():
                            if m.state != mqtt_ms_publish:
                                m.dup = True
                            m.state = mqtt_ms_publish
                        else:
                            if m.state == mqtt_ms_wait_for_pubcomp:
                                m.state = mqtt_ms_resend_pubrel
                            else:
                                if m.state == mqtt_ms_wait_for_pubrec:
                                    m.dup = True
                                m.state = mqtt_ms_publish
                else:
                    m.state = mqtt_ms_queued

    def _messages_reconnect_reset_in(self):
        with self._in_message_mutex:
            if self._check_clean_session():
                self._in_messages = collections.OrderedDict()
                return
            for m in self._in_messages.values():
                m.timestamp = 0
                if m.qos != 2:
                    self._in_messages.pop(m.mid)
                else:
                    # Preserve current state
                    pass

    def _messages_reconnect_reset(self):
        self._messages_reconnect_reset_out()
        self._messages_reconnect_reset_in()

    def _packet_queue(self, command, packet, mid, qos, info=None):
        mpkt = {
            'command': command,
            'mid': mid,
            'qos': qos,
            'pos': 0,
            'to_process': len(packet),
            'packet': packet,
            'info': info}

        self._out_packet.append(mpkt)

        # Write a single byte to sockpairW (connected to sockpairR) to break
        # out of select() if in threaded mode.
        if self._sockpairW is not None:
            try:
                self._sockpairW.send(sockpair_data)
            except BlockingIOError:
                pass

        # If we have an external event loop registered, use that instead
        # of calling loop_write() directly.
        if self._thread is None and self._on_socket_register_write is None:
            if self._in_callback_mutex.acquire(False):
                self._in_callback_mutex.release()
                return self.loop_write()

        self._call_socket_register_write()

        return MQTT_ERR_SUCCESS

    def _packet_handle(self):
        cmd = self._in_packet['command'] & 0xF0
        if cmd == PINGREQ:
            return self._handle_pingreq()
        elif cmd == PINGRESP:
            return self._handle_pingresp()
        elif cmd == PUBACK:
            return self._handle_pubackcomp("PUBACK")
        elif cmd == PUBCOMP:
            return self._handle_pubackcomp("PUBCOMP")
        elif cmd == PUBLISH:
            return self._handle_publish()
        elif cmd == PUBREC:
            return self._handle_pubrec()
        elif cmd == PUBREL:
            return self._handle_pubrel()
        elif cmd == CONNACK:
            return self._handle_connack()
        elif cmd == SUBACK:
            return self._handle_suback()
        elif cmd == UNSUBACK:
            return self._handle_unsuback()
        elif cmd == DISCONNECT and self._protocol == MQTTv5:  # only allowed in MQTT 5.0
            return self._handle_disconnect()
        else:
            # If we don't recognise the command, return an error straight away.
            self._easy_log(MQTT_LOG_ERR, "Error: Unrecognised command %s", cmd)
            return MQTT_ERR_PROTOCOL

    def _handle_pingreq(self):
        if self._in_packet['remaining_length'] != 0:
            return MQTT_ERR_PROTOCOL

        self._easy_log(MQTT_LOG_DEBUG, "Received PINGREQ")
        return self._send_pingresp()

    def _handle_pingresp(self):
        if self._in_packet['remaining_length'] != 0:
            return MQTT_ERR_PROTOCOL

        # No longer waiting for a PINGRESP.
        self._ping_t = 0
        self._easy_log(MQTT_LOG_DEBUG, "Received PINGRESP")
        return MQTT_ERR_SUCCESS

    def _handle_connack(self):
        if self._protocol == MQTTv5:
            if self._in_packet['remaining_length'] < 2:
                return MQTT_ERR_PROTOCOL
        elif self._in_packet['remaining_length'] != 2:
            return MQTT_ERR_PROTOCOL

        if self._protocol == MQTTv5:
            (flags, result) = struct.unpack(
                "!BB", self._in_packet['packet'][:2])
            if result == 1:
                # This is probably a failure from a broker that doesn't support
                # MQTT v5.
                reason = 132 # Unsupported protocol version
                properties = None
            else:
                reason = ReasonCodes(CONNACK >> 4, identifier=result)
                properties = Properties(CONNACK >> 4)
                properties.unpack(self._in_packet['packet'][2:])
        else:
            (flags, result) = struct.unpack("!BB", self._in_packet['packet'])
        if self._protocol == MQTTv311:
            if result == CONNACK_REFUSED_PROTOCOL_VERSION:
                if not self._reconnect_on_failure:
                    return MQTT_ERR_PROTOCOL
                self._easy_log(
                    MQTT_LOG_DEBUG,
                    "Received CONNACK (%s, %s), attempting downgrade to MQTT v3.1.",
                    flags, result
                )
                # Downgrade to MQTT v3.1
                self._protocol = MQTTv31
                return self.reconnect()
            elif (result == CONNACK_REFUSED_IDENTIFIER_REJECTED
                    and self._client_id == b''):
                if not self._reconnect_on_failure:
                    return MQTT_ERR_PROTOCOL
                self._easy_log(
                    MQTT_LOG_DEBUG,
                    "Received CONNACK (%s, %s), attempting to use non-empty CID",
                    flags, result,
                )
                self._client_id = base62(uuid.uuid4().int, padding=22)
                return self.reconnect()

        if result == 0:
            self._state = mqtt_cs_connected
            self._reconnect_delay = None

        if self._protocol == MQTTv5:
            self._easy_log(
                MQTT_LOG_DEBUG, "Received CONNACK (%s, %s) properties=%s", flags, reason, properties)
        else:
            self._easy_log(
                MQTT_LOG_DEBUG, "Received CONNACK (%s, %s)", flags, result)

        # it won't be the first successful connect any more
        self._mqttv5_first_connect = False

        with self._callback_mutex:
            on_connect = self.on_connect

        if on_connect:
            flags_dict = {}
            flags_dict['session present'] = flags & 0x01
            with self._in_callback_mutex:
                try:
                    if self._protocol == MQTTv5:
                        on_connect(self, self._userdata,
                                        flags_dict, reason, properties)
                    else:
                        on_connect(
                            self, self._userdata, flags_dict, result)
                except Exception as err:
                    self._easy_log(
                        MQTT_LOG_ERR, 'Caught exception in on_connect: %s', err)
                    if not self.suppress_exceptions:
                        raise

        if result == 0:
            rc = 0
            with self._out_message_mutex:
                for m in self._out_messages.values():
                    m.timestamp = time_func()
                    if m.state == mqtt_ms_queued:
                        self.loop_write()  # Process outgoing messages that have just been queued up
                        return MQTT_ERR_SUCCESS

                    if m.qos == 0:
                        with self._in_callback_mutex:  # Don't call loop_write after _send_publish()
                            rc = self._send_publish(
                                m.mid,
                                m.topic.encode('utf-8'),
                                m.payload,
                                m.qos,
                                m.retain,
                                m.dup,
                                properties=m.properties
                            )
                        if rc != 0:
                            return rc
                    elif m.qos == 1:
                        if m.state == mqtt_ms_publish:
                            self._inflight_messages += 1
                            m.state = mqtt_ms_wait_for_puback
                            with self._in_callback_mutex:  # Don't call loop_write after _send_publish()
                                rc = self._send_publish(
                                    m.mid,
                                    m.topic.encode('utf-8'),
                                    m.payload,
                                    m.qos,
                                    m.retain,
                                    m.dup,
                                    properties=m.properties
                                )
                            if rc != 0:
                                return rc
                    elif m.qos == 2:
                        if m.state == mqtt_ms_publish:
                            self._inflight_messages += 1
                            m.state = mqtt_ms_wait_for_pubrec
                            with self._in_callback_mutex:  # Don't call loop_write after _send_publish()
                                rc = self._send_publish(
                                    m.mid,
                                    m.topic.encode('utf-8'),
                                    m.payload,
                                    m.qos,
                                    m.retain,
                                    m.dup,
                                    properties=m.properties
                                )
                            if rc != 0:
                                return rc
                        elif m.state == mqtt_ms_resend_pubrel:
                            self._inflight_messages += 1
                            m.state = mqtt_ms_wait_for_pubcomp
                            with self._in_callback_mutex:  # Don't call loop_write after _send_publish()
                                rc = self._send_pubrel(m.mid)
                            if rc != 0:
                                return rc
                    self.loop_write()  # Process outgoing messages that have just been queued up

            return rc
        elif result > 0 and result < 6:
            return MQTT_ERR_CONN_REFUSED
        else:
            return MQTT_ERR_PROTOCOL

    def _handle_disconnect(self):
        packet_type = DISCONNECT >> 4
        reasonCode = properties = None
        if self._in_packet['remaining_length'] > 2:
            reasonCode = ReasonCodes(packet_type)
            reasonCode.unpack(self._in_packet['packet'])
            if self._in_packet['remaining_length'] > 3:
                properties = Properties(packet_type)
                props, props_len = properties.unpack(
                    self._in_packet['packet'][1:])
        self._easy_log(MQTT_LOG_DEBUG, "Received DISCONNECT %s %s",
                       reasonCode,
                       properties
                       )

        self._loop_rc_handle(reasonCode, properties)

        return MQTT_ERR_SUCCESS

    def _handle_suback(self):
        self._easy_log(MQTT_LOG_DEBUG, "Received SUBACK")
        pack_format = "!H" + str(len(self._in_packet['packet']) - 2) + 's'
        (mid, packet) = struct.unpack(pack_format, self._in_packet['packet'])

        if self._protocol == MQTTv5:
            properties = Properties(SUBACK >> 4)
            props, props_len = properties.unpack(packet)
            reasoncodes = []
            for c in packet[props_len:]:
                if sys.version_info[0] < 3:
                    c = ord(c)
                reasoncodes.append(ReasonCodes(SUBACK >> 4, identifier=c))
        else:
            pack_format = "!" + "B" * len(packet)
            granted_qos = struct.unpack(pack_format, packet)

        with self._callback_mutex:
            on_subscribe = self.on_subscribe

        if on_subscribe:
            with self._in_callback_mutex:  # Don't call loop_write after _send_publish()
                try:
                    if self._protocol == MQTTv5:
                        on_subscribe(
                            self, self._userdata, mid, reasoncodes, properties)
                    else:
                        on_subscribe(
                            self, self._userdata, mid, granted_qos)
                except Exception as err:
                    self._easy_log(
                        MQTT_LOG_ERR, 'Caught exception in on_subscribe: %s', err)
                    if not self.suppress_exceptions:
                        raise

        return MQTT_ERR_SUCCESS

    def _handle_publish(self):
        rc = 0

        header = self._in_packet['command']
        message = MQTTMessage()
        message.dup = (header & 0x08) >> 3
        message.qos = (header & 0x06) >> 1
        message.retain = (header & 0x01)

        pack_format = "!H" + str(len(self._in_packet['packet']) - 2) + 's'
        (slen, packet) = struct.unpack(pack_format, self._in_packet['packet'])
        pack_format = '!' + str(slen) + 's' + str(len(packet) - slen) + 's'
        (topic, packet) = struct.unpack(pack_format, packet)

        if self._protocol != MQTTv5 and len(topic) == 0:
            return MQTT_ERR_PROTOCOL

        # Handle topics with invalid UTF-8
        # This replaces an invalid topic with a message and the hex
        # representation of the topic for logging. When the user attempts to
        # access message.topic in the callback, an exception will be raised.
        try:
            print_topic = topic.decode('utf-8')
        except UnicodeDecodeError:
            print_topic = "TOPIC WITH INVALID UTF-8: " + str(topic)

        message.topic = topic

        if message.qos > 0:
            pack_format = "!H" + str(len(packet) - 2) + 's'
            (message.mid, packet) = struct.unpack(pack_format, packet)

        if self._protocol == MQTTv5:
            message.properties = Properties(PUBLISH >> 4)
            props, props_len = message.properties.unpack(packet)
            packet = packet[props_len:]

        message.payload = packet

        if self._protocol == MQTTv5:
            self._easy_log(
                MQTT_LOG_DEBUG,
                "Received PUBLISH (d%d, q%d, r%d, m%d), '%s', properties=%s, ...  (%d bytes)",
                message.dup, message.qos, message.retain, message.mid,
                print_topic, message.properties, len(message.payload)
            )
        else:
            self._easy_log(
                MQTT_LOG_DEBUG,
                "Received PUBLISH (d%d, q%d, r%d, m%d), '%s', ...  (%d bytes)",
                message.dup, message.qos, message.retain, message.mid,
                print_topic, len(message.payload)
            )

        message.timestamp = time_func()
        if message.qos == 0:
            self._handle_on_message(message)
            return MQTT_ERR_SUCCESS
        elif message.qos == 1:
            self._handle_on_message(message)
            return self._send_puback(message.mid)
        elif message.qos == 2:
            rc = self._send_pubrec(message.mid)
            message.state = mqtt_ms_wait_for_pubrel
            with self._in_message_mutex:
                self._in_messages[message.mid] = message
            return rc
        else:
            return MQTT_ERR_PROTOCOL

    def _handle_pubrel(self):
        if self._protocol == MQTTv5:
            if self._in_packet['remaining_length'] < 2:
                return MQTT_ERR_PROTOCOL
        elif self._in_packet['remaining_length'] != 2:
            return MQTT_ERR_PROTOCOL

        mid, = struct.unpack("!H", self._in_packet['packet'])
        self._easy_log(MQTT_LOG_DEBUG, "Received PUBREL (Mid: %d)", mid)

        with self._in_message_mutex:
            if mid in self._in_messages:
                # Only pass the message on if we have removed it from the queue - this
                # prevents multiple callbacks for the same message.
                message = self._in_messages.pop(mid)
                self._handle_on_message(message)
                self._inflight_messages -= 1
                if self._max_inflight_messages > 0:
                    with self._out_message_mutex:
                        rc = self._update_inflight()
                    if rc != MQTT_ERR_SUCCESS:
                        return rc

        # FIXME: this should only be done if the message is known
        # If unknown it's a protocol error and we should close the connection.
        # But since we don't have (on disk) persistence for the session, it
        # is possible that we must known about this message.
        # Choose to acknwoledge this messsage (and thus losing a message) but
        # avoid hanging. See #284.
        return self._send_pubcomp(mid)

    def _update_inflight(self):
        # Dont lock message_mutex here
        for m in self._out_messages.values():
            if self._inflight_messages < self._max_inflight_messages:
                if m.qos > 0 and m.state == mqtt_ms_queued:
                    self._inflight_messages += 1
                    if m.qos == 1:
                        m.state = mqtt_ms_wait_for_puback
                    elif m.qos == 2:
                        m.state = mqtt_ms_wait_for_pubrec
                    rc = self._send_publish(
                        m.mid,
                        m.topic.encode('utf-8'),
                        m.payload,
                        m.qos,
                        m.retain,
                        m.dup,
                        properties=m.properties,
                    )
                    if rc != 0:
                        return rc
            else:
                return MQTT_ERR_SUCCESS
        return MQTT_ERR_SUCCESS

    def _handle_pubrec(self):
        if self._protocol == MQTTv5:
            if self._in_packet['remaining_length'] < 2:
                return MQTT_ERR_PROTOCOL
        elif self._in_packet['remaining_length'] != 2:
            return MQTT_ERR_PROTOCOL

        mid, = struct.unpack("!H", self._in_packet['packet'][:2])
        if self._protocol == MQTTv5:
            if self._in_packet['remaining_length'] > 2:
                reasonCode = ReasonCodes(PUBREC >> 4)
                reasonCode.unpack(self._in_packet['packet'][2:])
                if self._in_packet['remaining_length'] > 3:
                    properties = Properties(PUBREC >> 4)
                    props, props_len = properties.unpack(
                        self._in_packet['packet'][3:])
        self._easy_log(MQTT_LOG_DEBUG, "Received PUBREC (Mid: %d)", mid)

        with self._out_message_mutex:
            if mid in self._out_messages:
                msg = self._out_messages[mid]
                msg.state = mqtt_ms_wait_for_pubcomp
                msg.timestamp = time_func()
                return self._send_pubrel(mid)

        return MQTT_ERR_SUCCESS

    def _handle_unsuback(self):
        if self._protocol == MQTTv5:
            if self._in_packet['remaining_length'] < 4:
                return MQTT_ERR_PROTOCOL
        elif self._in_packet['remaining_length'] != 2:
            return MQTT_ERR_PROTOCOL

        mid, = struct.unpack("!H", self._in_packet['packet'][:2])
        if self._protocol == MQTTv5:
            packet = self._in_packet['packet'][2:]
            properties = Properties(UNSUBACK >> 4)
            props, props_len = properties.unpack(packet)
            reasoncodes = []
            for c in packet[props_len:]:
                if sys.version_info[0] < 3:
                    c = ord(c)
                reasoncodes.append(ReasonCodes(UNSUBACK >> 4, identifier=c))
            if len(reasoncodes) == 1:
                reasoncodes = reasoncodes[0]

        self._easy_log(MQTT_LOG_DEBUG, "Received UNSUBACK (Mid: %d)", mid)
        with self._callback_mutex:
            on_unsubscribe = self.on_unsubscribe

        if on_unsubscribe:
            with self._in_callback_mutex:
                try:
                    if self._protocol == MQTTv5:
                        on_unsubscribe(
                            self, self._userdata, mid, properties, reasoncodes)
                    else:
                        on_unsubscribe(self, self._userdata, mid)
                except Exception as err:
                    self._easy_log(
                        MQTT_LOG_ERR, 'Caught exception in on_unsubscribe: %s', err)
                    if not self.suppress_exceptions:
                        raise

        return MQTT_ERR_SUCCESS

    def _do_on_disconnect(self, rc, properties=None):
        with self._callback_mutex:
            on_disconnect = self.on_disconnect

        if on_disconnect:
            with self._in_callback_mutex:
                try:
                    if self._protocol == MQTTv5:
                        on_disconnect(
                            self, self._userdata, rc, properties)
                    else:
                        on_disconnect(self, self._userdata, rc)
                except Exception as err:
                    self._easy_log(
                        MQTT_LOG_ERR, 'Caught exception in on_disconnect: %s', err)
                    if not self.suppress_exceptions:
                        raise

    def _do_on_publish(self, mid):
        with self._callback_mutex:
            on_publish = self.on_publish

        if on_publish:
            with self._in_callback_mutex:
                try:
                    on_publish(self, self._userdata, mid)
                except Exception as err:
                    self._easy_log(
                        MQTT_LOG_ERR, 'Caught exception in on_publish: %s', err)
                    if not self.suppress_exceptions:
                        raise

        msg = self._out_messages.pop(mid)
        msg.info._set_as_published()
        if msg.qos > 0:
            self._inflight_messages -= 1
            if self._max_inflight_messages > 0:
                rc = self._update_inflight()
                if rc != MQTT_ERR_SUCCESS:
                    return rc
        return MQTT_ERR_SUCCESS

    def _handle_pubackcomp(self, cmd):
        if self._protocol == MQTTv5:
            if self._in_packet['remaining_length'] < 2:
                return MQTT_ERR_PROTOCOL
        elif self._in_packet['remaining_length'] != 2:
            return MQTT_ERR_PROTOCOL

        packet_type = PUBACK if cmd == "PUBACK" else PUBCOMP
        packet_type = packet_type >> 4
        mid, = struct.unpack("!H", self._in_packet['packet'][:2])
        if self._protocol == MQTTv5:
            if self._in_packet['remaining_length'] > 2:
                reasonCode = ReasonCodes(packet_type)
                reasonCode.unpack(self._in_packet['packet'][2:])
                if self._in_packet['remaining_length'] > 3:
                    properties = Properties(packet_type)
                    props, props_len = properties.unpack(
                        self._in_packet['packet'][3:])
        self._easy_log(MQTT_LOG_DEBUG, "Received %s (Mid: %d)", cmd, mid)

        with self._out_message_mutex:
            if mid in self._out_messages:
                # Only inform the client the message has been sent once.
                rc = self._do_on_publish(mid)
                return rc

        return MQTT_ERR_SUCCESS

    def _handle_on_message(self, message):
        matched = False

        try:
            topic = message.topic
        except UnicodeDecodeError:
            topic = None

        on_message_callbacks = []
        with self._callback_mutex:
            if topic is not None:
                for callback in self._on_message_filtered.iter_match(message.topic):
                    on_message_callbacks.append(callback)

            if len(on_message_callbacks) == 0:
                on_message = self.on_message
            else:
                on_message = None

        for callback in on_message_callbacks:
            with self._in_callback_mutex:
                try:
                    callback(self, self._userdata, message)
                except Exception as err:
                    self._easy_log(
                        MQTT_LOG_ERR,
                        'Caught exception in user defined callback function %s: %s',
                        callback.__name__,
                        err
                    )
                    if not self.suppress_exceptions:
                        raise

        if on_message:
            with self._in_callback_mutex:
                try:
                    on_message(self, self._userdata, message)
                except Exception as err:
                    self._easy_log(
                        MQTT_LOG_ERR, 'Caught exception in on_message: %s', err)
                    if not self.suppress_exceptions:
                        raise


    def _handle_on_connect_fail(self):
        with self._callback_mutex:
            on_connect_fail = self.on_connect_fail

        if on_connect_fail:
            with self._in_callback_mutex:
                try:
                    on_connect_fail(self, self._userdata)
                except Exception as err:
                    self._easy_log(
                        MQTT_LOG_ERR, 'Caught exception in on_connect_fail: %s', err)

    def _thread_main(self):
        self.loop_forever(retry_first_connection=True)

    def _reconnect_wait(self):
        # See reconnect_delay_set for details
        now = time_func()
        with self._reconnect_delay_mutex:
            if self._reconnect_delay is None:
                self._reconnect_delay = self._reconnect_min_delay
            else:
                self._reconnect_delay = min(
                    self._reconnect_delay * 2,
                    self._reconnect_max_delay,
                )

            target_time = now + self._reconnect_delay

        remaining = target_time - now
        while (self._state != mqtt_cs_disconnecting
                and not self._thread_terminate
                and remaining > 0):

            time.sleep(min(remaining, 1))
            remaining = target_time - time_func()

    @staticmethod
    def _proxy_is_valid(p):
        def check(t, a):
            return (socks is not None and
                    t in set([socks.HTTP, socks.SOCKS4, socks.SOCKS5]) and a)

        if isinstance(p, dict):
            return check(p.get("proxy_type"), p.get("proxy_addr"))
        elif isinstance(p, (list, tuple)):
            return len(p) == 6 and check(p[0], p[1])
        else:
            return False

    def _get_proxy(self):
        if socks is None:
            return None

        # First, check if the user explicitly passed us a proxy to use
        if self._proxy_is_valid(self._proxy):
            return self._proxy

        # Next, check for an mqtt_proxy environment variable as long as the host
        # we're trying to connect to isn't listed under the no_proxy environment
        # variable (matches built-in module urllib's behavior)
        if not (hasattr(urllib_dot_request, "proxy_bypass") and
                urllib_dot_request.proxy_bypass(self._host)):
            env_proxies = urllib_dot_request.getproxies()
            if "mqtt" in env_proxies:
                parts = urllib_dot_parse.urlparse(env_proxies["mqtt"])
                if parts.scheme == "http":
                    proxy = {
                        "proxy_type": socks.HTTP,
                        "proxy_addr": parts.hostname,
                        "proxy_port": parts.port
                    }
                    return proxy
                elif parts.scheme == "socks":
                    proxy = {
                        "proxy_type": socks.SOCKS5,
                        "proxy_addr": parts.hostname,
                        "proxy_port": parts.port
                    }
                    return proxy

        # Finally, check if the user has monkeypatched the PySocks library with
        # a default proxy
        socks_default = socks.get_default_proxy()
        if self._proxy_is_valid(socks_default):
            proxy_keys = ("proxy_type", "proxy_addr", "proxy_port",
                          "proxy_rdns", "proxy_username", "proxy_password")
            return dict(zip(proxy_keys, socks_default))

        # If we didn't find a proxy through any of the above methods, return
        # None to indicate that the connection should be handled normally
        return None

    def _create_socket_connection(self):
        proxy = self._get_proxy()
        addr = (self._host, self._port)
        source = (self._bind_address, self._bind_port)


        if sys.version_info < (2, 7) or (3, 0) < sys.version_info < (3, 2):
            # Have to short-circuit here because of unsupported source_address
            # param in earlier Python versions.
            return socket.create_connection(addr, timeout=self._connect_timeout)

        if proxy:
            return socks.create_connection(addr, timeout=self._connect_timeout, source_address=source, **proxy)
        else:
            return socket.create_connection(addr, timeout=self._connect_timeout, source_address=source)


class WebsocketWrapper(object):
    OPCODE_CONTINUATION = 0x0
    OPCODE_TEXT = 0x1
    OPCODE_BINARY = 0x2
    OPCODE_CONNCLOSE = 0x8
    OPCODE_PING = 0x9
    OPCODE_PONG = 0xa

    def __init__(self, socket, host, port, is_ssl, path, extra_headers):

        self.connected = False

        self._ssl = is_ssl
        self._host = host
        self._port = port
        self._socket = socket
        self._path = path

        self._sendbuffer = bytearray()
        self._readbuffer = bytearray()

        self._requested_size = 0
        self._payload_head = 0
        self._readbuffer_head = 0

        self._do_handshake(extra_headers)

    def __del__(self):

        self._sendbuffer = None
        self._readbuffer = None

    def _do_handshake(self, extra_headers):

        sec_websocket_key = uuid.uuid4().bytes
        sec_websocket_key = base64.b64encode(sec_websocket_key)

        websocket_headers = {
            "Host": "{self._host:s}:{self._port:d}".format(self=self),
            "Upgrade": "websocket",
            "Connection": "Upgrade",
            "Origin": "https://{self._host:s}:{self._port:d}".format(self=self),
            "Sec-WebSocket-Key": sec_websocket_key.decode("utf8"),
            "Sec-Websocket-Version": "13",
            "Sec-Websocket-Protocol": "mqtt",
        }

        # This is checked in ws_set_options so it will either be None, a
        # dictionary, or a callable
        if isinstance(extra_headers, dict):
            websocket_headers.update(extra_headers)
        elif callable(extra_headers):
            websocket_headers = extra_headers(websocket_headers)

        header = "\r\n".join([
            "GET {self._path} HTTP/1.1".format(self=self),
            "\r\n".join("{}: {}".format(i, j)
                        for i, j in websocket_headers.items()),
            "\r\n",
        ]).encode("utf8")

        self._socket.send(header)

        has_secret = False
        has_upgrade = False

        while True:
            # read HTTP response header as lines
            byte = self._socket.recv(1)

            self._readbuffer.extend(byte)

            # line end
            if byte == b"\n":
                if len(self._readbuffer) > 2:
                    # check upgrade
                    if b"connection" in str(self._readbuffer).lower().encode('utf-8'):
                        if b"upgrade" not in str(self._readbuffer).lower().encode('utf-8'):
                            raise WebsocketConnectionError(
                                "WebSocket handshake error, connection not upgraded")
                        else:
                            has_upgrade = True

                    # check key hash
                    if b"sec-websocket-accept" in str(self._readbuffer).lower().encode('utf-8'):
                        GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

                        server_hash = self._readbuffer.decode(
                            'utf-8').split(": ", 1)[1]
                        server_hash = server_hash.strip().encode('utf-8')

                        client_hash = sec_websocket_key.decode('utf-8') + GUID
                        client_hash = hashlib.sha1(client_hash.encode('utf-8'))
                        client_hash = base64.b64encode(client_hash.digest())

                        if server_hash != client_hash:
                            raise WebsocketConnectionError(
                                "WebSocket handshake error, invalid secret key")
                        else:
                            has_secret = True
                else:
                    # ending linebreak
                    break

                # reset linebuffer
                self._readbuffer = bytearray()

            # connection reset
            elif not byte:
                raise WebsocketConnectionError("WebSocket handshake error")

        if not has_upgrade or not has_secret:
            raise WebsocketConnectionError("WebSocket handshake error")

        self._readbuffer = bytearray()
        self.connected = True

    def _create_frame(self, opcode, data, do_masking=1):

        header = bytearray()
        length = len(data)

        mask_key = bytearray(os.urandom(4))
        mask_flag = do_masking

        # 1 << 7 is the final flag, we don't send continuated data
        header.append(1 << 7 | opcode)

        if length < 126:
            header.append(mask_flag << 7 | length)

        elif length < 65536:
            header.append(mask_flag << 7 | 126)
            header += struct.pack("!H", length)

        elif length < 0x8000000000000001:
            header.append(mask_flag << 7 | 127)
            header += struct.pack("!Q", length)

        else:
            raise ValueError("Maximum payload size is 2^63")

        if mask_flag == 1:
            for index in range(length):
                data[index] ^= mask_key[index % 4]
            data = mask_key + data

        return header + data

    def _buffered_read(self, length):

        # try to recv and store needed bytes
        wanted_bytes = length - (len(self._readbuffer) - self._readbuffer_head)
        if wanted_bytes > 0:

            data = self._socket.recv(wanted_bytes)

            if not data:
                raise ConnectionAbortedError
            else:
                self._readbuffer.extend(data)

            if len(data) < wanted_bytes:
                raise BlockingIOError

        self._readbuffer_head += length
        return self._readbuffer[self._readbuffer_head - length:self._readbuffer_head]

    def _recv_impl(self, length):

        # try to decode websocket payload part from data
        try:

            self._readbuffer_head = 0

            result = None

            chunk_startindex = self._payload_head
            chunk_endindex = self._payload_head + length

            header1 = self._buffered_read(1)
            header2 = self._buffered_read(1)

            opcode = (header1[0] & 0x0f)
            maskbit = (header2[0] & 0x80) == 0x80
            lengthbits = (header2[0] & 0x7f)
            payload_length = lengthbits
            mask_key = None

            # read length
            if lengthbits == 0x7e:

                value = self._buffered_read(2)
                payload_length, = struct.unpack("!H", value)

            elif lengthbits == 0x7f:

                value = self._buffered_read(8)
                payload_length, = struct.unpack("!Q", value)

            # read mask
            if maskbit:
                mask_key = self._buffered_read(4)

            # if frame payload is shorter than the requested data, read only the possible part
            readindex = chunk_endindex
            if payload_length < readindex:
                readindex = payload_length

            if readindex > 0:
                # get payload chunk
                payload = self._buffered_read(readindex)

                # unmask only the needed part
                if maskbit:
                    for index in range(chunk_startindex, readindex):
                        payload[index] ^= mask_key[index % 4]

                result = payload[chunk_startindex:readindex]
                self._payload_head = readindex
            else:
                payload = bytearray()

            # check if full frame arrived and reset readbuffer and payloadhead if needed
            if readindex == payload_length:
                self._readbuffer = bytearray()
                self._payload_head = 0

                # respond to non-binary opcodes, their arrival is not guaranteed beacause of non-blocking sockets
                if opcode == WebsocketWrapper.OPCODE_CONNCLOSE:
                    frame = self._create_frame(
                        WebsocketWrapper.OPCODE_CONNCLOSE, payload, 0)
                    self._socket.send(frame)

                if opcode == WebsocketWrapper.OPCODE_PING:
                    frame = self._create_frame(
                        WebsocketWrapper.OPCODE_PONG, payload, 0)
                    self._socket.send(frame)

            # This isn't *proper* handling of continuation frames, but given
            # that we only support binary frames, it is *probably* good enough.
            if (opcode == WebsocketWrapper.OPCODE_BINARY or opcode == WebsocketWrapper.OPCODE_CONTINUATION) \
                    and payload_length > 0:
                return result
            else:
                raise BlockingIOError

        except ConnectionError:
            self.connected = False
            return b''

    def _send_impl(self, data):

        # if previous frame was sent successfully
        if len(self._sendbuffer) == 0:
            # create websocket frame
            frame = self._create_frame(
                WebsocketWrapper.OPCODE_BINARY, bytearray(data))
            self._sendbuffer.extend(frame)
            self._requested_size = len(data)

        # try to write out as much as possible
        length = self._socket.send(self._sendbuffer)

        self._sendbuffer = self._sendbuffer[length:]

        if len(self._sendbuffer) == 0:
            # buffer sent out completely, return with payload's size
            return self._requested_size
        else:
            # couldn't send whole data, request the same data again with 0 as sent length
            return 0

    def recv(self, length):
        return self._recv_impl(length)

    def read(self, length):
        return self._recv_impl(length)

    def send(self, data):
        return self._send_impl(data)

    def write(self, data):
        return self._send_impl(data)

    def close(self):
        self._socket.close()

    def fileno(self):
        return self._socket.fileno()

    def pending(self):
        # Fix for bug #131: a SSL socket may still have data available
        # for reading without select() being aware of it.
        if self._ssl:
            return self._socket.pending()
        else:
            # normal socket rely only on select()
            return 0

    def setblocking(self, flag):
        self._socket.setblocking(flag)
