"""
AMQP Specification
==================
This module implements the constants and classes that comprise AMQP protocol
level constructs. It should rarely be directly referenced outside of Pika's
own internal use.
.. note:: Auto-generated code by codegen.py, do not edit directly. Pull
requests to this file without accompanying ``utils/codegen.py`` changes will be
rejected.

"""

import struct
from pika import amqp_object
from pika import data
from pika.compat import str_or_bytes, unicode_type
from pika.exchange_type import ExchangeType
from pika.delivery_mode import DeliveryMode

# Python 3 support for str object
str = bytes

PROTOCOL_VERSION = (0, 9, 1)
PORT = 5672

ACCESS_REFUSED = 403
CHANNEL_ERROR = 504
COMMAND_INVALID = 503
CONNECTION_FORCED = 320
CONTENT_TOO_LARGE = 311
FRAME_BODY = 3
FRAME_END = 206
FRAME_END_SIZE = 1
FRAME_ERROR = 501
FRAME_HEADER = 2
FRAME_HEADER_SIZE = 7
FRAME_HEARTBEAT = 8
FRAME_MAX_SIZE = 131072
FRAME_METHOD = 1
FRAME_MIN_SIZE = 4096
INTERNAL_ERROR = 541
INVALID_PATH = 402
NOT_ALLOWED = 530
NOT_FOUND = 404
NOT_IMPLEMENTED = 540
NO_CONSUMERS = 313
NO_ROUTE = 312
PERSISTENT_DELIVERY_MODE = 2
PRECONDITION_FAILED = 406
REPLY_SUCCESS = 200
RESOURCE_ERROR = 506
RESOURCE_LOCKED = 405
SYNTAX_ERROR = 502
TRANSIENT_DELIVERY_MODE = 1
UNEXPECTED_FRAME = 505


class Connection(amqp_object.Class):

    INDEX = 0x000A  # 10
    NAME = 'Connection'

    class Start(amqp_object.Method):

        INDEX = 0x000A000A  # 10, 10; 655370
        NAME = 'Connection.Start'

        def __init__(self, version_major=0, version_minor=9, server_properties=None, mechanisms='PLAIN', locales='en_US'):
            self.version_major = version_major
            self.version_minor = version_minor
            self.server_properties = server_properties
            self.mechanisms = mechanisms
            self.locales = locales

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.version_major = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.version_minor = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            (self.server_properties, offset) = data.decode_table(encoded, offset)
            length = struct.unpack_from('>I', encoded, offset)[0]
            offset += 4
            self.mechanisms = encoded[offset:offset + length]
            try:
                self.mechanisms = str(self.mechanisms)
            except UnicodeEncodeError:
                pass
            offset += length
            length = struct.unpack_from('>I', encoded, offset)[0]
            offset += 4
            self.locales = encoded[offset:offset + length]
            try:
                self.locales = str(self.locales)
            except UnicodeEncodeError:
                pass
            offset += length
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('B', self.version_major))
            pieces.append(struct.pack('B', self.version_minor))
            data.encode_table(pieces, self.server_properties)
            assert isinstance(self.mechanisms, str_or_bytes),\
                   'A non-string value was supplied for self.mechanisms'
            value = self.mechanisms.encode('utf-8') if isinstance(self.mechanisms, unicode_type) else self.mechanisms
            pieces.append(struct.pack('>I', len(value)))
            pieces.append(value)
            assert isinstance(self.locales, str_or_bytes),\
                   'A non-string value was supplied for self.locales'
            value = self.locales.encode('utf-8') if isinstance(self.locales, unicode_type) else self.locales
            pieces.append(struct.pack('>I', len(value)))
            pieces.append(value)
            return pieces

    class StartOk(amqp_object.Method):

        INDEX = 0x000A000B  # 10, 11; 655371
        NAME = 'Connection.StartOk'

        def __init__(self, client_properties=None, mechanism='PLAIN', response=None, locale='en_US'):
            self.client_properties = client_properties
            self.mechanism = mechanism
            self.response = response
            self.locale = locale

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            (self.client_properties, offset) = data.decode_table(encoded, offset)
            self.mechanism, offset = data.decode_short_string(encoded, offset)
            length = struct.unpack_from('>I', encoded, offset)[0]
            offset += 4
            self.response = encoded[offset:offset + length]
            try:
                self.response = str(self.response)
            except UnicodeEncodeError:
                pass
            offset += length
            self.locale, offset = data.decode_short_string(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            data.encode_table(pieces, self.client_properties)
            assert isinstance(self.mechanism, str_or_bytes),\
                   'A non-string value was supplied for self.mechanism'
            data.encode_short_string(pieces, self.mechanism)
            assert isinstance(self.response, str_or_bytes),\
                   'A non-string value was supplied for self.response'
            value = self.response.encode('utf-8') if isinstance(self.response, unicode_type) else self.response
            pieces.append(struct.pack('>I', len(value)))
            pieces.append(value)
            assert isinstance(self.locale, str_or_bytes),\
                   'A non-string value was supplied for self.locale'
            data.encode_short_string(pieces, self.locale)
            return pieces

    class Secure(amqp_object.Method):

        INDEX = 0x000A0014  # 10, 20; 655380
        NAME = 'Connection.Secure'

        def __init__(self, challenge=None):
            self.challenge = challenge

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            length = struct.unpack_from('>I', encoded, offset)[0]
            offset += 4
            self.challenge = encoded[offset:offset + length]
            try:
                self.challenge = str(self.challenge)
            except UnicodeEncodeError:
                pass
            offset += length
            return self

        def encode(self):
            pieces = list()
            assert isinstance(self.challenge, str_or_bytes),\
                   'A non-string value was supplied for self.challenge'
            value = self.challenge.encode('utf-8') if isinstance(self.challenge, unicode_type) else self.challenge
            pieces.append(struct.pack('>I', len(value)))
            pieces.append(value)
            return pieces

    class SecureOk(amqp_object.Method):

        INDEX = 0x000A0015  # 10, 21; 655381
        NAME = 'Connection.SecureOk'

        def __init__(self, response=None):
            self.response = response

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            length = struct.unpack_from('>I', encoded, offset)[0]
            offset += 4
            self.response = encoded[offset:offset + length]
            try:
                self.response = str(self.response)
            except UnicodeEncodeError:
                pass
            offset += length
            return self

        def encode(self):
            pieces = list()
            assert isinstance(self.response, str_or_bytes),\
                   'A non-string value was supplied for self.response'
            value = self.response.encode('utf-8') if isinstance(self.response, unicode_type) else self.response
            pieces.append(struct.pack('>I', len(value)))
            pieces.append(value)
            return pieces

    class Tune(amqp_object.Method):

        INDEX = 0x000A001E  # 10, 30; 655390
        NAME = 'Connection.Tune'

        def __init__(self, channel_max=0, frame_max=0, heartbeat=0):
            self.channel_max = channel_max
            self.frame_max = frame_max
            self.heartbeat = heartbeat

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.channel_max = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.frame_max = struct.unpack_from('>I', encoded, offset)[0]
            offset += 4
            self.heartbeat = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.channel_max))
            pieces.append(struct.pack('>I', self.frame_max))
            pieces.append(struct.pack('>H', self.heartbeat))
            return pieces

    class TuneOk(amqp_object.Method):

        INDEX = 0x000A001F  # 10, 31; 655391
        NAME = 'Connection.TuneOk'

        def __init__(self, channel_max=0, frame_max=0, heartbeat=0):
            self.channel_max = channel_max
            self.frame_max = frame_max
            self.heartbeat = heartbeat

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.channel_max = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.frame_max = struct.unpack_from('>I', encoded, offset)[0]
            offset += 4
            self.heartbeat = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.channel_max))
            pieces.append(struct.pack('>I', self.frame_max))
            pieces.append(struct.pack('>H', self.heartbeat))
            return pieces

    class Open(amqp_object.Method):

        INDEX = 0x000A0028  # 10, 40; 655400
        NAME = 'Connection.Open'

        def __init__(self, virtual_host='/', capabilities='', insist=False):
            self.virtual_host = virtual_host
            self.capabilities = capabilities
            self.insist = insist

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.virtual_host, offset = data.decode_short_string(encoded, offset)
            self.capabilities, offset = data.decode_short_string(encoded, offset)
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.insist = (bit_buffer & (1 << 0)) != 0
            return self

        def encode(self):
            pieces = list()
            assert isinstance(self.virtual_host, str_or_bytes),\
                   'A non-string value was supplied for self.virtual_host'
            data.encode_short_string(pieces, self.virtual_host)
            assert isinstance(self.capabilities, str_or_bytes),\
                   'A non-string value was supplied for self.capabilities'
            data.encode_short_string(pieces, self.capabilities)
            bit_buffer = 0
            if self.insist:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class OpenOk(amqp_object.Method):

        INDEX = 0x000A0029  # 10, 41; 655401
        NAME = 'Connection.OpenOk'

        def __init__(self, known_hosts=''):
            self.known_hosts = known_hosts

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.known_hosts, offset = data.decode_short_string(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            assert isinstance(self.known_hosts, str_or_bytes),\
                   'A non-string value was supplied for self.known_hosts'
            data.encode_short_string(pieces, self.known_hosts)
            return pieces

    class Close(amqp_object.Method):

        INDEX = 0x000A0032  # 10, 50; 655410
        NAME = 'Connection.Close'

        def __init__(self, reply_code=None, reply_text='', class_id=None, method_id=None):
            self.reply_code = reply_code
            self.reply_text = reply_text
            self.class_id = class_id
            self.method_id = method_id

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.reply_code = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.reply_text, offset = data.decode_short_string(encoded, offset)
            self.class_id = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.method_id = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.reply_code))
            assert isinstance(self.reply_text, str_or_bytes),\
                   'A non-string value was supplied for self.reply_text'
            data.encode_short_string(pieces, self.reply_text)
            pieces.append(struct.pack('>H', self.class_id))
            pieces.append(struct.pack('>H', self.method_id))
            return pieces

    class CloseOk(amqp_object.Method):

        INDEX = 0x000A0033  # 10, 51; 655411
        NAME = 'Connection.CloseOk'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces

    class Blocked(amqp_object.Method):

        INDEX = 0x000A003C  # 10, 60; 655420
        NAME = 'Connection.Blocked'

        def __init__(self, reason=''):
            self.reason = reason

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.reason, offset = data.decode_short_string(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            assert isinstance(self.reason, str_or_bytes),\
                   'A non-string value was supplied for self.reason'
            data.encode_short_string(pieces, self.reason)
            return pieces

    class Unblocked(amqp_object.Method):

        INDEX = 0x000A003D  # 10, 61; 655421
        NAME = 'Connection.Unblocked'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces

    class UpdateSecret(amqp_object.Method):

        INDEX = 0x000A0046  # 10, 70; 655430
        NAME = 'Connection.UpdateSecret'

        def __init__(self, new_secret, reason):
            self.new_secret = new_secret
            self.reason = reason

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            length = struct.unpack_from('>I', encoded, offset)[0]
            offset += 4
            self.mechanisms = encoded[offset:offset + length]
            try:
                self.mechanisms = str(self.mechanisms)
            except UnicodeEncodeError:
                pass
            offset += length
            self.reason, offset = data.decode_short_string(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            assert isinstance(self.new_secret, str_or_bytes),\
                'A non-string value was supplied for self.new_secret'
            value = self.new_secret.encode('utf-8') if isinstance(self.new_secret, unicode_type) else self.new_secret
            pieces.append(struct.pack('>I', len(value)))
            pieces.append(value)
            assert isinstance(self.reason, str_or_bytes),\
                'A non-string value was supplied for self.reason'
            data.encode_short_string(pieces, self.reason)
            return pieces

    class UpdateSecretOk(amqp_object.Method):

        INDEX = 0x000A0047  # 10, 71; 655431
        NAME = 'Connection.UpdateSecretOk'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces


class Channel(amqp_object.Class):

    INDEX = 0x0014  # 20
    NAME = 'Channel'

    class Open(amqp_object.Method):

        INDEX = 0x0014000A  # 20, 10; 1310730
        NAME = 'Channel.Open'

        def __init__(self, out_of_band=''):
            self.out_of_band = out_of_band

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.out_of_band, offset = data.decode_short_string(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            assert isinstance(self.out_of_band, str_or_bytes),\
                   'A non-string value was supplied for self.out_of_band'
            data.encode_short_string(pieces, self.out_of_band)
            return pieces

    class OpenOk(amqp_object.Method):

        INDEX = 0x0014000B  # 20, 11; 1310731
        NAME = 'Channel.OpenOk'

        def __init__(self, channel_id=''):
            self.channel_id = channel_id

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            length = struct.unpack_from('>I', encoded, offset)[0]
            offset += 4
            self.channel_id = encoded[offset:offset + length]
            try:
                self.channel_id = str(self.channel_id)
            except UnicodeEncodeError:
                pass
            offset += length
            return self

        def encode(self):
            pieces = list()
            assert isinstance(self.channel_id, str_or_bytes),\
                   'A non-string value was supplied for self.channel_id'
            value = self.channel_id.encode('utf-8') if isinstance(self.channel_id, unicode_type) else self.channel_id
            pieces.append(struct.pack('>I', len(value)))
            pieces.append(value)
            return pieces

    class Flow(amqp_object.Method):

        INDEX = 0x00140014  # 20, 20; 1310740
        NAME = 'Channel.Flow'

        def __init__(self, active=None):
            self.active = active

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.active = (bit_buffer & (1 << 0)) != 0
            return self

        def encode(self):
            pieces = list()
            bit_buffer = 0
            if self.active:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class FlowOk(amqp_object.Method):

        INDEX = 0x00140015  # 20, 21; 1310741
        NAME = 'Channel.FlowOk'

        def __init__(self, active=None):
            self.active = active

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.active = (bit_buffer & (1 << 0)) != 0
            return self

        def encode(self):
            pieces = list()
            bit_buffer = 0
            if self.active:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class Close(amqp_object.Method):

        INDEX = 0x00140028  # 20, 40; 1310760
        NAME = 'Channel.Close'

        def __init__(self, reply_code=None, reply_text='', class_id=None, method_id=None):
            self.reply_code = reply_code
            self.reply_text = reply_text
            self.class_id = class_id
            self.method_id = method_id

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.reply_code = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.reply_text, offset = data.decode_short_string(encoded, offset)
            self.class_id = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.method_id = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.reply_code))
            assert isinstance(self.reply_text, str_or_bytes),\
                   'A non-string value was supplied for self.reply_text'
            data.encode_short_string(pieces, self.reply_text)
            pieces.append(struct.pack('>H', self.class_id))
            pieces.append(struct.pack('>H', self.method_id))
            return pieces

    class CloseOk(amqp_object.Method):

        INDEX = 0x00140029  # 20, 41; 1310761
        NAME = 'Channel.CloseOk'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces


class Access(amqp_object.Class):

    INDEX = 0x001E  # 30
    NAME = 'Access'

    class Request(amqp_object.Method):

        INDEX = 0x001E000A  # 30, 10; 1966090
        NAME = 'Access.Request'

        def __init__(self, realm='/data', exclusive=False, passive=True, active=True, write=True, read=True):
            self.realm = realm
            self.exclusive = exclusive
            self.passive = passive
            self.active = active
            self.write = write
            self.read = read

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.realm, offset = data.decode_short_string(encoded, offset)
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.exclusive = (bit_buffer & (1 << 0)) != 0
            self.passive = (bit_buffer & (1 << 1)) != 0
            self.active = (bit_buffer & (1 << 2)) != 0
            self.write = (bit_buffer & (1 << 3)) != 0
            self.read = (bit_buffer & (1 << 4)) != 0
            return self

        def encode(self):
            pieces = list()
            assert isinstance(self.realm, str_or_bytes),\
                   'A non-string value was supplied for self.realm'
            data.encode_short_string(pieces, self.realm)
            bit_buffer = 0
            if self.exclusive:
                bit_buffer |= 1 << 0
            if self.passive:
                bit_buffer |= 1 << 1
            if self.active:
                bit_buffer |= 1 << 2
            if self.write:
                bit_buffer |= 1 << 3
            if self.read:
                bit_buffer |= 1 << 4
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class RequestOk(amqp_object.Method):

        INDEX = 0x001E000B  # 30, 11; 1966091
        NAME = 'Access.RequestOk'

        def __init__(self, ticket=1):
            self.ticket = ticket

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.ticket = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.ticket))
            return pieces


class Exchange(amqp_object.Class):

    INDEX = 0x0028  # 40
    NAME = 'Exchange'

    class Declare(amqp_object.Method):

        INDEX = 0x0028000A  # 40, 10; 2621450
        NAME = 'Exchange.Declare'

        def __init__(self, ticket=0, exchange=None, type=ExchangeType.direct, passive=False, durable=False, auto_delete=False, internal=False, nowait=False, arguments=None):
            self.ticket = ticket
            self.exchange = exchange
            self.type = type
            self.passive = passive
            self.durable = durable
            self.auto_delete = auto_delete
            self.internal = internal
            self.nowait = nowait
            self.arguments = arguments

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.ticket = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.exchange, offset = data.decode_short_string(encoded, offset)
            self.type, offset = data.decode_short_string(encoded, offset)
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.passive = (bit_buffer & (1 << 0)) != 0
            self.durable = (bit_buffer & (1 << 1)) != 0
            self.auto_delete = (bit_buffer & (1 << 2)) != 0
            self.internal = (bit_buffer & (1 << 3)) != 0
            self.nowait = (bit_buffer & (1 << 4)) != 0
            (self.arguments, offset) = data.decode_table(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.ticket))
            assert isinstance(self.exchange, str_or_bytes),\
                   'A non-string value was supplied for self.exchange'
            data.encode_short_string(pieces, self.exchange)
            assert isinstance(self.type, str_or_bytes),\
                   'A non-string value was supplied for self.type'
            data.encode_short_string(pieces, self.type)
            bit_buffer = 0
            if self.passive:
                bit_buffer |= 1 << 0
            if self.durable:
                bit_buffer |= 1 << 1
            if self.auto_delete:
                bit_buffer |= 1 << 2
            if self.internal:
                bit_buffer |= 1 << 3
            if self.nowait:
                bit_buffer |= 1 << 4
            pieces.append(struct.pack('B', bit_buffer))
            data.encode_table(pieces, self.arguments)
            return pieces

    class DeclareOk(amqp_object.Method):

        INDEX = 0x0028000B  # 40, 11; 2621451
        NAME = 'Exchange.DeclareOk'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces

    class Delete(amqp_object.Method):

        INDEX = 0x00280014  # 40, 20; 2621460
        NAME = 'Exchange.Delete'

        def __init__(self, ticket=0, exchange=None, if_unused=False, nowait=False):
            self.ticket = ticket
            self.exchange = exchange
            self.if_unused = if_unused
            self.nowait = nowait

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.ticket = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.exchange, offset = data.decode_short_string(encoded, offset)
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.if_unused = (bit_buffer & (1 << 0)) != 0
            self.nowait = (bit_buffer & (1 << 1)) != 0
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.ticket))
            assert isinstance(self.exchange, str_or_bytes),\
                   'A non-string value was supplied for self.exchange'
            data.encode_short_string(pieces, self.exchange)
            bit_buffer = 0
            if self.if_unused:
                bit_buffer |= 1 << 0
            if self.nowait:
                bit_buffer |= 1 << 1
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class DeleteOk(amqp_object.Method):

        INDEX = 0x00280015  # 40, 21; 2621461
        NAME = 'Exchange.DeleteOk'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces

    class Bind(amqp_object.Method):

        INDEX = 0x0028001E  # 40, 30; 2621470
        NAME = 'Exchange.Bind'

        def __init__(self, ticket=0, destination=None, source=None, routing_key='', nowait=False, arguments=None):
            self.ticket = ticket
            self.destination = destination
            self.source = source
            self.routing_key = routing_key
            self.nowait = nowait
            self.arguments = arguments

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.ticket = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.destination, offset = data.decode_short_string(encoded, offset)
            self.source, offset = data.decode_short_string(encoded, offset)
            self.routing_key, offset = data.decode_short_string(encoded, offset)
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.nowait = (bit_buffer & (1 << 0)) != 0
            (self.arguments, offset) = data.decode_table(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.ticket))
            assert isinstance(self.destination, str_or_bytes),\
                   'A non-string value was supplied for self.destination'
            data.encode_short_string(pieces, self.destination)
            assert isinstance(self.source, str_or_bytes),\
                   'A non-string value was supplied for self.source'
            data.encode_short_string(pieces, self.source)
            assert isinstance(self.routing_key, str_or_bytes),\
                   'A non-string value was supplied for self.routing_key'
            data.encode_short_string(pieces, self.routing_key)
            bit_buffer = 0
            if self.nowait:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            data.encode_table(pieces, self.arguments)
            return pieces

    class BindOk(amqp_object.Method):

        INDEX = 0x0028001F  # 40, 31; 2621471
        NAME = 'Exchange.BindOk'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces

    class Unbind(amqp_object.Method):

        INDEX = 0x00280028  # 40, 40; 2621480
        NAME = 'Exchange.Unbind'

        def __init__(self, ticket=0, destination=None, source=None, routing_key='', nowait=False, arguments=None):
            self.ticket = ticket
            self.destination = destination
            self.source = source
            self.routing_key = routing_key
            self.nowait = nowait
            self.arguments = arguments

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.ticket = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.destination, offset = data.decode_short_string(encoded, offset)
            self.source, offset = data.decode_short_string(encoded, offset)
            self.routing_key, offset = data.decode_short_string(encoded, offset)
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.nowait = (bit_buffer & (1 << 0)) != 0
            (self.arguments, offset) = data.decode_table(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.ticket))
            assert isinstance(self.destination, str_or_bytes),\
                   'A non-string value was supplied for self.destination'
            data.encode_short_string(pieces, self.destination)
            assert isinstance(self.source, str_or_bytes),\
                   'A non-string value was supplied for self.source'
            data.encode_short_string(pieces, self.source)
            assert isinstance(self.routing_key, str_or_bytes),\
                   'A non-string value was supplied for self.routing_key'
            data.encode_short_string(pieces, self.routing_key)
            bit_buffer = 0
            if self.nowait:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            data.encode_table(pieces, self.arguments)
            return pieces

    class UnbindOk(amqp_object.Method):

        INDEX = 0x00280033  # 40, 51; 2621491
        NAME = 'Exchange.UnbindOk'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces


class Queue(amqp_object.Class):

    INDEX = 0x0032  # 50
    NAME = 'Queue'

    class Declare(amqp_object.Method):

        INDEX = 0x0032000A  # 50, 10; 3276810
        NAME = 'Queue.Declare'

        def __init__(self, ticket=0, queue='', passive=False, durable=False, exclusive=False, auto_delete=False, nowait=False, arguments=None):
            self.ticket = ticket
            self.queue = queue
            self.passive = passive
            self.durable = durable
            self.exclusive = exclusive
            self.auto_delete = auto_delete
            self.nowait = nowait
            self.arguments = arguments

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.ticket = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.queue, offset = data.decode_short_string(encoded, offset)
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.passive = (bit_buffer & (1 << 0)) != 0
            self.durable = (bit_buffer & (1 << 1)) != 0
            self.exclusive = (bit_buffer & (1 << 2)) != 0
            self.auto_delete = (bit_buffer & (1 << 3)) != 0
            self.nowait = (bit_buffer & (1 << 4)) != 0
            (self.arguments, offset) = data.decode_table(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.ticket))
            assert isinstance(self.queue, str_or_bytes),\
                   'A non-string value was supplied for self.queue'
            data.encode_short_string(pieces, self.queue)
            bit_buffer = 0
            if self.passive:
                bit_buffer |= 1 << 0
            if self.durable:
                bit_buffer |= 1 << 1
            if self.exclusive:
                bit_buffer |= 1 << 2
            if self.auto_delete:
                bit_buffer |= 1 << 3
            if self.nowait:
                bit_buffer |= 1 << 4
            pieces.append(struct.pack('B', bit_buffer))
            data.encode_table(pieces, self.arguments)
            return pieces

    class DeclareOk(amqp_object.Method):

        INDEX = 0x0032000B  # 50, 11; 3276811
        NAME = 'Queue.DeclareOk'

        def __init__(self, queue=None, message_count=None, consumer_count=None):
            self.queue = queue
            self.message_count = message_count
            self.consumer_count = consumer_count

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.queue, offset = data.decode_short_string(encoded, offset)
            self.message_count = struct.unpack_from('>I', encoded, offset)[0]
            offset += 4
            self.consumer_count = struct.unpack_from('>I', encoded, offset)[0]
            offset += 4
            return self

        def encode(self):
            pieces = list()
            assert isinstance(self.queue, str_or_bytes),\
                   'A non-string value was supplied for self.queue'
            data.encode_short_string(pieces, self.queue)
            pieces.append(struct.pack('>I', self.message_count))
            pieces.append(struct.pack('>I', self.consumer_count))
            return pieces

    class Bind(amqp_object.Method):

        INDEX = 0x00320014  # 50, 20; 3276820
        NAME = 'Queue.Bind'

        def __init__(self, ticket=0, queue='', exchange=None, routing_key='', nowait=False, arguments=None):
            self.ticket = ticket
            self.queue = queue
            self.exchange = exchange
            self.routing_key = routing_key
            self.nowait = nowait
            self.arguments = arguments

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.ticket = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.queue, offset = data.decode_short_string(encoded, offset)
            self.exchange, offset = data.decode_short_string(encoded, offset)
            self.routing_key, offset = data.decode_short_string(encoded, offset)
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.nowait = (bit_buffer & (1 << 0)) != 0
            (self.arguments, offset) = data.decode_table(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.ticket))
            assert isinstance(self.queue, str_or_bytes),\
                   'A non-string value was supplied for self.queue'
            data.encode_short_string(pieces, self.queue)
            assert isinstance(self.exchange, str_or_bytes),\
                   'A non-string value was supplied for self.exchange'
            data.encode_short_string(pieces, self.exchange)
            assert isinstance(self.routing_key, str_or_bytes),\
                   'A non-string value was supplied for self.routing_key'
            data.encode_short_string(pieces, self.routing_key)
            bit_buffer = 0
            if self.nowait:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            data.encode_table(pieces, self.arguments)
            return pieces

    class BindOk(amqp_object.Method):

        INDEX = 0x00320015  # 50, 21; 3276821
        NAME = 'Queue.BindOk'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces

    class Purge(amqp_object.Method):

        INDEX = 0x0032001E  # 50, 30; 3276830
        NAME = 'Queue.Purge'

        def __init__(self, ticket=0, queue='', nowait=False):
            self.ticket = ticket
            self.queue = queue
            self.nowait = nowait

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.ticket = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.queue, offset = data.decode_short_string(encoded, offset)
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.nowait = (bit_buffer & (1 << 0)) != 0
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.ticket))
            assert isinstance(self.queue, str_or_bytes),\
                   'A non-string value was supplied for self.queue'
            data.encode_short_string(pieces, self.queue)
            bit_buffer = 0
            if self.nowait:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class PurgeOk(amqp_object.Method):

        INDEX = 0x0032001F  # 50, 31; 3276831
        NAME = 'Queue.PurgeOk'

        def __init__(self, message_count=None):
            self.message_count = message_count

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.message_count = struct.unpack_from('>I', encoded, offset)[0]
            offset += 4
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>I', self.message_count))
            return pieces

    class Delete(amqp_object.Method):

        INDEX = 0x00320028  # 50, 40; 3276840
        NAME = 'Queue.Delete'

        def __init__(self, ticket=0, queue='', if_unused=False, if_empty=False, nowait=False):
            self.ticket = ticket
            self.queue = queue
            self.if_unused = if_unused
            self.if_empty = if_empty
            self.nowait = nowait

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.ticket = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.queue, offset = data.decode_short_string(encoded, offset)
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.if_unused = (bit_buffer & (1 << 0)) != 0
            self.if_empty = (bit_buffer & (1 << 1)) != 0
            self.nowait = (bit_buffer & (1 << 2)) != 0
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.ticket))
            assert isinstance(self.queue, str_or_bytes),\
                   'A non-string value was supplied for self.queue'
            data.encode_short_string(pieces, self.queue)
            bit_buffer = 0
            if self.if_unused:
                bit_buffer |= 1 << 0
            if self.if_empty:
                bit_buffer |= 1 << 1
            if self.nowait:
                bit_buffer |= 1 << 2
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class DeleteOk(amqp_object.Method):

        INDEX = 0x00320029  # 50, 41; 3276841
        NAME = 'Queue.DeleteOk'

        def __init__(self, message_count=None):
            self.message_count = message_count

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.message_count = struct.unpack_from('>I', encoded, offset)[0]
            offset += 4
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>I', self.message_count))
            return pieces

    class Unbind(amqp_object.Method):

        INDEX = 0x00320032  # 50, 50; 3276850
        NAME = 'Queue.Unbind'

        def __init__(self, ticket=0, queue='', exchange=None, routing_key='', arguments=None):
            self.ticket = ticket
            self.queue = queue
            self.exchange = exchange
            self.routing_key = routing_key
            self.arguments = arguments

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.ticket = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.queue, offset = data.decode_short_string(encoded, offset)
            self.exchange, offset = data.decode_short_string(encoded, offset)
            self.routing_key, offset = data.decode_short_string(encoded, offset)
            (self.arguments, offset) = data.decode_table(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.ticket))
            assert isinstance(self.queue, str_or_bytes),\
                   'A non-string value was supplied for self.queue'
            data.encode_short_string(pieces, self.queue)
            assert isinstance(self.exchange, str_or_bytes),\
                   'A non-string value was supplied for self.exchange'
            data.encode_short_string(pieces, self.exchange)
            assert isinstance(self.routing_key, str_or_bytes),\
                   'A non-string value was supplied for self.routing_key'
            data.encode_short_string(pieces, self.routing_key)
            data.encode_table(pieces, self.arguments)
            return pieces

    class UnbindOk(amqp_object.Method):

        INDEX = 0x00320033  # 50, 51; 3276851
        NAME = 'Queue.UnbindOk'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces


class Basic(amqp_object.Class):

    INDEX = 0x003C  # 60
    NAME = 'Basic'

    class Qos(amqp_object.Method):

        INDEX = 0x003C000A  # 60, 10; 3932170
        NAME = 'Basic.Qos'

        def __init__(self, prefetch_size=0, prefetch_count=0, global_qos=False):
            self.prefetch_size = prefetch_size
            self.prefetch_count = prefetch_count
            self.global_qos = global_qos

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.prefetch_size = struct.unpack_from('>I', encoded, offset)[0]
            offset += 4
            self.prefetch_count = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.global_qos = (bit_buffer & (1 << 0)) != 0
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>I', self.prefetch_size))
            pieces.append(struct.pack('>H', self.prefetch_count))
            bit_buffer = 0
            if self.global_qos:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class QosOk(amqp_object.Method):

        INDEX = 0x003C000B  # 60, 11; 3932171
        NAME = 'Basic.QosOk'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces

    class Consume(amqp_object.Method):

        INDEX = 0x003C0014  # 60, 20; 3932180
        NAME = 'Basic.Consume'

        def __init__(self, ticket=0, queue='', consumer_tag='', no_local=False, no_ack=False, exclusive=False, nowait=False, arguments=None):
            self.ticket = ticket
            self.queue = queue
            self.consumer_tag = consumer_tag
            self.no_local = no_local
            self.no_ack = no_ack
            self.exclusive = exclusive
            self.nowait = nowait
            self.arguments = arguments

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.ticket = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.queue, offset = data.decode_short_string(encoded, offset)
            self.consumer_tag, offset = data.decode_short_string(encoded, offset)
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.no_local = (bit_buffer & (1 << 0)) != 0
            self.no_ack = (bit_buffer & (1 << 1)) != 0
            self.exclusive = (bit_buffer & (1 << 2)) != 0
            self.nowait = (bit_buffer & (1 << 3)) != 0
            (self.arguments, offset) = data.decode_table(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.ticket))
            assert isinstance(self.queue, str_or_bytes),\
                   'A non-string value was supplied for self.queue'
            data.encode_short_string(pieces, self.queue)
            assert isinstance(self.consumer_tag, str_or_bytes),\
                   'A non-string value was supplied for self.consumer_tag'
            data.encode_short_string(pieces, self.consumer_tag)
            bit_buffer = 0
            if self.no_local:
                bit_buffer |= 1 << 0
            if self.no_ack:
                bit_buffer |= 1 << 1
            if self.exclusive:
                bit_buffer |= 1 << 2
            if self.nowait:
                bit_buffer |= 1 << 3
            pieces.append(struct.pack('B', bit_buffer))
            data.encode_table(pieces, self.arguments)
            return pieces

    class ConsumeOk(amqp_object.Method):

        INDEX = 0x003C0015  # 60, 21; 3932181
        NAME = 'Basic.ConsumeOk'

        def __init__(self, consumer_tag=None):
            self.consumer_tag = consumer_tag

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.consumer_tag, offset = data.decode_short_string(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            assert isinstance(self.consumer_tag, str_or_bytes),\
                   'A non-string value was supplied for self.consumer_tag'
            data.encode_short_string(pieces, self.consumer_tag)
            return pieces

    class Cancel(amqp_object.Method):

        INDEX = 0x003C001E  # 60, 30; 3932190
        NAME = 'Basic.Cancel'

        def __init__(self, consumer_tag=None, nowait=False):
            self.consumer_tag = consumer_tag
            self.nowait = nowait

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.consumer_tag, offset = data.decode_short_string(encoded, offset)
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.nowait = (bit_buffer & (1 << 0)) != 0
            return self

        def encode(self):
            pieces = list()
            assert isinstance(self.consumer_tag, str_or_bytes),\
                   'A non-string value was supplied for self.consumer_tag'
            data.encode_short_string(pieces, self.consumer_tag)
            bit_buffer = 0
            if self.nowait:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class CancelOk(amqp_object.Method):

        INDEX = 0x003C001F  # 60, 31; 3932191
        NAME = 'Basic.CancelOk'

        def __init__(self, consumer_tag=None):
            self.consumer_tag = consumer_tag

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.consumer_tag, offset = data.decode_short_string(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            assert isinstance(self.consumer_tag, str_or_bytes),\
                   'A non-string value was supplied for self.consumer_tag'
            data.encode_short_string(pieces, self.consumer_tag)
            return pieces

    class Publish(amqp_object.Method):

        INDEX = 0x003C0028  # 60, 40; 3932200
        NAME = 'Basic.Publish'

        def __init__(self, ticket=0, exchange='', routing_key='', mandatory=False, immediate=False):
            self.ticket = ticket
            self.exchange = exchange
            self.routing_key = routing_key
            self.mandatory = mandatory
            self.immediate = immediate

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.ticket = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.exchange, offset = data.decode_short_string(encoded, offset)
            self.routing_key, offset = data.decode_short_string(encoded, offset)
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.mandatory = (bit_buffer & (1 << 0)) != 0
            self.immediate = (bit_buffer & (1 << 1)) != 0
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.ticket))
            assert isinstance(self.exchange, str_or_bytes),\
                   'A non-string value was supplied for self.exchange'
            data.encode_short_string(pieces, self.exchange)
            assert isinstance(self.routing_key, str_or_bytes),\
                   'A non-string value was supplied for self.routing_key'
            data.encode_short_string(pieces, self.routing_key)
            bit_buffer = 0
            if self.mandatory:
                bit_buffer |= 1 << 0
            if self.immediate:
                bit_buffer |= 1 << 1
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class Return(amqp_object.Method):

        INDEX = 0x003C0032  # 60, 50; 3932210
        NAME = 'Basic.Return'

        def __init__(self, reply_code=None, reply_text='', exchange=None, routing_key=None):
            self.reply_code = reply_code
            self.reply_text = reply_text
            self.exchange = exchange
            self.routing_key = routing_key

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.reply_code = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.reply_text, offset = data.decode_short_string(encoded, offset)
            self.exchange, offset = data.decode_short_string(encoded, offset)
            self.routing_key, offset = data.decode_short_string(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.reply_code))
            assert isinstance(self.reply_text, str_or_bytes),\
                   'A non-string value was supplied for self.reply_text'
            data.encode_short_string(pieces, self.reply_text)
            assert isinstance(self.exchange, str_or_bytes),\
                   'A non-string value was supplied for self.exchange'
            data.encode_short_string(pieces, self.exchange)
            assert isinstance(self.routing_key, str_or_bytes),\
                   'A non-string value was supplied for self.routing_key'
            data.encode_short_string(pieces, self.routing_key)
            return pieces

    class Deliver(amqp_object.Method):

        INDEX = 0x003C003C  # 60, 60; 3932220
        NAME = 'Basic.Deliver'

        def __init__(self, consumer_tag=None, delivery_tag=None, redelivered=False, exchange=None, routing_key=None):
            self.consumer_tag = consumer_tag
            self.delivery_tag = delivery_tag
            self.redelivered = redelivered
            self.exchange = exchange
            self.routing_key = routing_key

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.consumer_tag, offset = data.decode_short_string(encoded, offset)
            self.delivery_tag = struct.unpack_from('>Q', encoded, offset)[0]
            offset += 8
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.redelivered = (bit_buffer & (1 << 0)) != 0
            self.exchange, offset = data.decode_short_string(encoded, offset)
            self.routing_key, offset = data.decode_short_string(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            assert isinstance(self.consumer_tag, str_or_bytes),\
                   'A non-string value was supplied for self.consumer_tag'
            data.encode_short_string(pieces, self.consumer_tag)
            pieces.append(struct.pack('>Q', self.delivery_tag))
            bit_buffer = 0
            if self.redelivered:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            assert isinstance(self.exchange, str_or_bytes),\
                   'A non-string value was supplied for self.exchange'
            data.encode_short_string(pieces, self.exchange)
            assert isinstance(self.routing_key, str_or_bytes),\
                   'A non-string value was supplied for self.routing_key'
            data.encode_short_string(pieces, self.routing_key)
            return pieces

    class Get(amqp_object.Method):

        INDEX = 0x003C0046  # 60, 70; 3932230
        NAME = 'Basic.Get'

        def __init__(self, ticket=0, queue='', no_ack=False):
            self.ticket = ticket
            self.queue = queue
            self.no_ack = no_ack

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            self.ticket = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            self.queue, offset = data.decode_short_string(encoded, offset)
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.no_ack = (bit_buffer & (1 << 0)) != 0
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>H', self.ticket))
            assert isinstance(self.queue, str_or_bytes),\
                   'A non-string value was supplied for self.queue'
            data.encode_short_string(pieces, self.queue)
            bit_buffer = 0
            if self.no_ack:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class GetOk(amqp_object.Method):

        INDEX = 0x003C0047  # 60, 71; 3932231
        NAME = 'Basic.GetOk'

        def __init__(self, delivery_tag=None, redelivered=False, exchange=None, routing_key=None, message_count=None):
            self.delivery_tag = delivery_tag
            self.redelivered = redelivered
            self.exchange = exchange
            self.routing_key = routing_key
            self.message_count = message_count

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.delivery_tag = struct.unpack_from('>Q', encoded, offset)[0]
            offset += 8
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.redelivered = (bit_buffer & (1 << 0)) != 0
            self.exchange, offset = data.decode_short_string(encoded, offset)
            self.routing_key, offset = data.decode_short_string(encoded, offset)
            self.message_count = struct.unpack_from('>I', encoded, offset)[0]
            offset += 4
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>Q', self.delivery_tag))
            bit_buffer = 0
            if self.redelivered:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            assert isinstance(self.exchange, str_or_bytes),\
                   'A non-string value was supplied for self.exchange'
            data.encode_short_string(pieces, self.exchange)
            assert isinstance(self.routing_key, str_or_bytes),\
                   'A non-string value was supplied for self.routing_key'
            data.encode_short_string(pieces, self.routing_key)
            pieces.append(struct.pack('>I', self.message_count))
            return pieces

    class GetEmpty(amqp_object.Method):

        INDEX = 0x003C0048  # 60, 72; 3932232
        NAME = 'Basic.GetEmpty'

        def __init__(self, cluster_id=''):
            self.cluster_id = cluster_id

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.cluster_id, offset = data.decode_short_string(encoded, offset)
            return self

        def encode(self):
            pieces = list()
            assert isinstance(self.cluster_id, str_or_bytes),\
                   'A non-string value was supplied for self.cluster_id'
            data.encode_short_string(pieces, self.cluster_id)
            return pieces

    class Ack(amqp_object.Method):

        INDEX = 0x003C0050  # 60, 80; 3932240
        NAME = 'Basic.Ack'

        def __init__(self, delivery_tag=0, multiple=False):
            self.delivery_tag = delivery_tag
            self.multiple = multiple

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.delivery_tag = struct.unpack_from('>Q', encoded, offset)[0]
            offset += 8
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.multiple = (bit_buffer & (1 << 0)) != 0
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>Q', self.delivery_tag))
            bit_buffer = 0
            if self.multiple:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class Reject(amqp_object.Method):

        INDEX = 0x003C005A  # 60, 90; 3932250
        NAME = 'Basic.Reject'

        def __init__(self, delivery_tag=None, requeue=True):
            self.delivery_tag = delivery_tag
            self.requeue = requeue

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.delivery_tag = struct.unpack_from('>Q', encoded, offset)[0]
            offset += 8
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.requeue = (bit_buffer & (1 << 0)) != 0
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>Q', self.delivery_tag))
            bit_buffer = 0
            if self.requeue:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class RecoverAsync(amqp_object.Method):

        INDEX = 0x003C0064  # 60, 100; 3932260
        NAME = 'Basic.RecoverAsync'

        def __init__(self, requeue=False):
            self.requeue = requeue

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.requeue = (bit_buffer & (1 << 0)) != 0
            return self

        def encode(self):
            pieces = list()
            bit_buffer = 0
            if self.requeue:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class Recover(amqp_object.Method):

        INDEX = 0x003C006E  # 60, 110; 3932270
        NAME = 'Basic.Recover'

        def __init__(self, requeue=False):
            self.requeue = requeue

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.requeue = (bit_buffer & (1 << 0)) != 0
            return self

        def encode(self):
            pieces = list()
            bit_buffer = 0
            if self.requeue:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class RecoverOk(amqp_object.Method):

        INDEX = 0x003C006F  # 60, 111; 3932271
        NAME = 'Basic.RecoverOk'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces

    class Nack(amqp_object.Method):

        INDEX = 0x003C0078  # 60, 120; 3932280
        NAME = 'Basic.Nack'

        def __init__(self, delivery_tag=0, multiple=False, requeue=True):
            self.delivery_tag = delivery_tag
            self.multiple = multiple
            self.requeue = requeue

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            self.delivery_tag = struct.unpack_from('>Q', encoded, offset)[0]
            offset += 8
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.multiple = (bit_buffer & (1 << 0)) != 0
            self.requeue = (bit_buffer & (1 << 1)) != 0
            return self

        def encode(self):
            pieces = list()
            pieces.append(struct.pack('>Q', self.delivery_tag))
            bit_buffer = 0
            if self.multiple:
                bit_buffer |= 1 << 0
            if self.requeue:
                bit_buffer |= 1 << 1
            pieces.append(struct.pack('B', bit_buffer))
            return pieces


class Tx(amqp_object.Class):

    INDEX = 0x005A  # 90
    NAME = 'Tx'

    class Select(amqp_object.Method):

        INDEX = 0x005A000A  # 90, 10; 5898250
        NAME = 'Tx.Select'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces

    class SelectOk(amqp_object.Method):

        INDEX = 0x005A000B  # 90, 11; 5898251
        NAME = 'Tx.SelectOk'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces

    class Commit(amqp_object.Method):

        INDEX = 0x005A0014  # 90, 20; 5898260
        NAME = 'Tx.Commit'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces

    class CommitOk(amqp_object.Method):

        INDEX = 0x005A0015  # 90, 21; 5898261
        NAME = 'Tx.CommitOk'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces

    class Rollback(amqp_object.Method):

        INDEX = 0x005A001E  # 90, 30; 5898270
        NAME = 'Tx.Rollback'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces

    class RollbackOk(amqp_object.Method):

        INDEX = 0x005A001F  # 90, 31; 5898271
        NAME = 'Tx.RollbackOk'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces


class Confirm(amqp_object.Class):

    INDEX = 0x0055  # 85
    NAME = 'Confirm'

    class Select(amqp_object.Method):

        INDEX = 0x0055000A  # 85, 10; 5570570
        NAME = 'Confirm.Select'

        def __init__(self, nowait=False):
            self.nowait = nowait

        @property
        def synchronous(self):
            return True

        def decode(self, encoded, offset=0):
            bit_buffer = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
            self.nowait = (bit_buffer & (1 << 0)) != 0
            return self

        def encode(self):
            pieces = list()
            bit_buffer = 0
            if self.nowait:
                bit_buffer |= 1 << 0
            pieces.append(struct.pack('B', bit_buffer))
            return pieces

    class SelectOk(amqp_object.Method):

        INDEX = 0x0055000B  # 85, 11; 5570571
        NAME = 'Confirm.SelectOk'

        def __init__(self):
            pass

        @property
        def synchronous(self):
            return False

        def decode(self, encoded, offset=0):
            return self

        def encode(self):
            pieces = list()
            return pieces


class BasicProperties(amqp_object.Properties):

    CLASS = Basic
    INDEX = 0x003C  # 60
    NAME = 'BasicProperties'

    FLAG_CONTENT_TYPE = (1 << 15)
    FLAG_CONTENT_ENCODING = (1 << 14)
    FLAG_HEADERS = (1 << 13)
    FLAG_DELIVERY_MODE = (1 << 12)
    FLAG_PRIORITY = (1 << 11)
    FLAG_CORRELATION_ID = (1 << 10)
    FLAG_REPLY_TO = (1 << 9)
    FLAG_EXPIRATION = (1 << 8)
    FLAG_MESSAGE_ID = (1 << 7)
    FLAG_TIMESTAMP = (1 << 6)
    FLAG_TYPE = (1 << 5)
    FLAG_USER_ID = (1 << 4)
    FLAG_APP_ID = (1 << 3)
    FLAG_CLUSTER_ID = (1 << 2)

    def __init__(self, content_type=None, content_encoding=None, headers=None, delivery_mode=None, priority=None, correlation_id=None, reply_to=None, expiration=None, message_id=None, timestamp=None, type=None, user_id=None, app_id=None, cluster_id=None):
        self.content_type = content_type
        self.content_encoding = content_encoding
        self.headers = headers
        if isinstance(delivery_mode, DeliveryMode):
            self.delivery_mode = delivery_mode.value
        else:
            self.delivery_mode = delivery_mode
        self.priority = priority
        self.correlation_id = correlation_id
        self.reply_to = reply_to
        self.expiration = expiration
        self.message_id = message_id
        self.timestamp = timestamp
        self.type = type
        self.user_id = user_id
        self.app_id = app_id
        self.cluster_id = cluster_id

    def decode(self, encoded, offset=0):
        flags = 0
        flagword_index = 0
        while True:
            partial_flags = struct.unpack_from('>H', encoded, offset)[0]
            offset += 2
            flags = flags | (partial_flags << (flagword_index * 16))
            if not (partial_flags & 1):
                break
            flagword_index += 1
        if flags & BasicProperties.FLAG_CONTENT_TYPE:
            self.content_type, offset = data.decode_short_string(encoded, offset)
        else:
            self.content_type = None
        if flags & BasicProperties.FLAG_CONTENT_ENCODING:
            self.content_encoding, offset = data.decode_short_string(encoded, offset)
        else:
            self.content_encoding = None
        if flags & BasicProperties.FLAG_HEADERS:
            (self.headers, offset) = data.decode_table(encoded, offset)
        else:
            self.headers = None
        if flags & BasicProperties.FLAG_DELIVERY_MODE:
            self.delivery_mode = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
        else:
            self.delivery_mode = None
        if flags & BasicProperties.FLAG_PRIORITY:
            self.priority = struct.unpack_from('B', encoded, offset)[0]
            offset += 1
        else:
            self.priority = None
        if flags & BasicProperties.FLAG_CORRELATION_ID:
            self.correlation_id, offset = data.decode_short_string(encoded, offset)
        else:
            self.correlation_id = None
        if flags & BasicProperties.FLAG_REPLY_TO:
            self.reply_to, offset = data.decode_short_string(encoded, offset)
        else:
            self.reply_to = None
        if flags & BasicProperties.FLAG_EXPIRATION:
            self.expiration, offset = data.decode_short_string(encoded, offset)
        else:
            self.expiration = None
        if flags & BasicProperties.FLAG_MESSAGE_ID:
            self.message_id, offset = data.decode_short_string(encoded, offset)
        else:
            self.message_id = None
        if flags & BasicProperties.FLAG_TIMESTAMP:
            self.timestamp = struct.unpack_from('>Q', encoded, offset)[0]
            offset += 8
        else:
            self.timestamp = None
        if flags & BasicProperties.FLAG_TYPE:
            self.type, offset = data.decode_short_string(encoded, offset)
        else:
            self.type = None
        if flags & BasicProperties.FLAG_USER_ID:
            self.user_id, offset = data.decode_short_string(encoded, offset)
        else:
            self.user_id = None
        if flags & BasicProperties.FLAG_APP_ID:
            self.app_id, offset = data.decode_short_string(encoded, offset)
        else:
            self.app_id = None
        if flags & BasicProperties.FLAG_CLUSTER_ID:
            self.cluster_id, offset = data.decode_short_string(encoded, offset)
        else:
            self.cluster_id = None
        return self

    def encode(self):
        pieces = list()
        flags = 0
        if self.content_type is not None:
            flags = flags | BasicProperties.FLAG_CONTENT_TYPE
            assert isinstance(self.content_type, str_or_bytes),\
                   'A non-string value was supplied for self.content_type'
            data.encode_short_string(pieces, self.content_type)
        if self.content_encoding is not None:
            flags = flags | BasicProperties.FLAG_CONTENT_ENCODING
            assert isinstance(self.content_encoding, str_or_bytes),\
                   'A non-string value was supplied for self.content_encoding'
            data.encode_short_string(pieces, self.content_encoding)
        if self.headers is not None:
            flags = flags | BasicProperties.FLAG_HEADERS
            data.encode_table(pieces, self.headers)
        if self.delivery_mode is not None:
            flags = flags | BasicProperties.FLAG_DELIVERY_MODE
            pieces.append(struct.pack('B', self.delivery_mode))
        if self.priority is not None:
            flags = flags | BasicProperties.FLAG_PRIORITY
            pieces.append(struct.pack('B', self.priority))
        if self.correlation_id is not None:
            flags = flags | BasicProperties.FLAG_CORRELATION_ID
            assert isinstance(self.correlation_id, str_or_bytes),\
                   'A non-string value was supplied for self.correlation_id'
            data.encode_short_string(pieces, self.correlation_id)
        if self.reply_to is not None:
            flags = flags | BasicProperties.FLAG_REPLY_TO
            assert isinstance(self.reply_to, str_or_bytes),\
                   'A non-string value was supplied for self.reply_to'
            data.encode_short_string(pieces, self.reply_to)
        if self.expiration is not None:
            flags = flags | BasicProperties.FLAG_EXPIRATION
            assert isinstance(self.expiration, str_or_bytes),\
                   'A non-string value was supplied for self.expiration'
            data.encode_short_string(pieces, self.expiration)
        if self.message_id is not None:
            flags = flags | BasicProperties.FLAG_MESSAGE_ID
            assert isinstance(self.message_id, str_or_bytes),\
                   'A non-string value was supplied for self.message_id'
            data.encode_short_string(pieces, self.message_id)
        if self.timestamp is not None:
            flags = flags | BasicProperties.FLAG_TIMESTAMP
            pieces.append(struct.pack('>Q', self.timestamp))
        if self.type is not None:
            flags = flags | BasicProperties.FLAG_TYPE
            assert isinstance(self.type, str_or_bytes),\
                   'A non-string value was supplied for self.type'
            data.encode_short_string(pieces, self.type)
        if self.user_id is not None:
            flags = flags | BasicProperties.FLAG_USER_ID
            assert isinstance(self.user_id, str_or_bytes),\
                   'A non-string value was supplied for self.user_id'
            data.encode_short_string(pieces, self.user_id)
        if self.app_id is not None:
            flags = flags | BasicProperties.FLAG_APP_ID
            assert isinstance(self.app_id, str_or_bytes),\
                   'A non-string value was supplied for self.app_id'
            data.encode_short_string(pieces, self.app_id)
        if self.cluster_id is not None:
            flags = flags | BasicProperties.FLAG_CLUSTER_ID
            assert isinstance(self.cluster_id, str_or_bytes),\
                   'A non-string value was supplied for self.cluster_id'
            data.encode_short_string(pieces, self.cluster_id)
        flag_pieces = list()
        while True:
            remainder = flags >> 16
            partial_flags = flags & 0xFFFE
            if remainder != 0:
                partial_flags |= 1
            flag_pieces.append(struct.pack('>H', partial_flags))
            flags = remainder
            if not flags:
                break
        return flag_pieces + pieces

methods = {
    0x000A000A: Connection.Start,
    0x000A000B: Connection.StartOk,
    0x000A0014: Connection.Secure,
    0x000A0015: Connection.SecureOk,
    0x000A001E: Connection.Tune,
    0x000A001F: Connection.TuneOk,
    0x000A0028: Connection.Open,
    0x000A0029: Connection.OpenOk,
    0x000A0032: Connection.Close,
    0x000A0033: Connection.CloseOk,
    0x000A003C: Connection.Blocked,
    0x000A003D: Connection.Unblocked,
    0x000A0046: Connection.UpdateSecret,
    0x000A0047: Connection.UpdateSecretOk,
    0x0014000A: Channel.Open,
    0x0014000B: Channel.OpenOk,
    0x00140014: Channel.Flow,
    0x00140015: Channel.FlowOk,
    0x00140028: Channel.Close,
    0x00140029: Channel.CloseOk,
    0x001E000A: Access.Request,
    0x001E000B: Access.RequestOk,
    0x0028000A: Exchange.Declare,
    0x0028000B: Exchange.DeclareOk,
    0x00280014: Exchange.Delete,
    0x00280015: Exchange.DeleteOk,
    0x0028001E: Exchange.Bind,
    0x0028001F: Exchange.BindOk,
    0x00280028: Exchange.Unbind,
    0x00280033: Exchange.UnbindOk,
    0x0032000A: Queue.Declare,
    0x0032000B: Queue.DeclareOk,
    0x00320014: Queue.Bind,
    0x00320015: Queue.BindOk,
    0x0032001E: Queue.Purge,
    0x0032001F: Queue.PurgeOk,
    0x00320028: Queue.Delete,
    0x00320029: Queue.DeleteOk,
    0x00320032: Queue.Unbind,
    0x00320033: Queue.UnbindOk,
    0x003C000A: Basic.Qos,
    0x003C000B: Basic.QosOk,
    0x003C0014: Basic.Consume,
    0x003C0015: Basic.ConsumeOk,
    0x003C001E: Basic.Cancel,
    0x003C001F: Basic.CancelOk,
    0x003C0028: Basic.Publish,
    0x003C0032: Basic.Return,
    0x003C003C: Basic.Deliver,
    0x003C0046: Basic.Get,
    0x003C0047: Basic.GetOk,
    0x003C0048: Basic.GetEmpty,
    0x003C0050: Basic.Ack,
    0x003C005A: Basic.Reject,
    0x003C0064: Basic.RecoverAsync,
    0x003C006E: Basic.Recover,
    0x003C006F: Basic.RecoverOk,
    0x003C0078: Basic.Nack,
    0x005A000A: Tx.Select,
    0x005A000B: Tx.SelectOk,
    0x005A0014: Tx.Commit,
    0x005A0015: Tx.CommitOk,
    0x005A001E: Tx.Rollback,
    0x005A001F: Tx.RollbackOk,
    0x0055000A: Confirm.Select,
    0x0055000B: Confirm.SelectOk
}

props = {
    0x003C: BasicProperties
}


def has_content(methodNumber):
    return methodNumber in (
        Basic.Publish.INDEX,
        Basic.Return.INDEX,
        Basic.Deliver.INDEX,
        Basic.GetOk.INDEX,
    )
