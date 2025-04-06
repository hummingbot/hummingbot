import functools
import json
import logging
import time
import uuid
from collections import deque
from threading import Event as ThreadEvent
from threading import Semaphore, Thread
from typing import Dict

import pika

from commlib.action import (
    BaseActionClient,
    BaseActionService,
    _ActionCancelMessage,
    _ActionFeedbackMessage,
    _ActionGoalMessage,
    _ActionResultMessage,
    _ActionStatusMessage,
)
from commlib.compression import CompressionType, deflate, inflate_str
from commlib.connection import BaseConnectionParameters
from commlib.exceptions import *
from commlib.msg import PubSubMessage, RPCMessage
from commlib.pubsub import BasePublisher, BaseSubscriber
from commlib.rpc import (
    BaseRPCClient,
    BaseRPCService,
    CommRPCHeader,
    CommRPCMessage,
)
from commlib.transports.base_transport import BaseTransport
from commlib.utils import gen_timestamp

# Reduce log level for pika internal logger
logging.getLogger("pika").setLevel(logging.WARN)

logger = logging.getLogger(__name__)


class MessageProperties(pika.BasicProperties):
    """Message Properties/Attribures used for sending and receiving messages.

    Args:
        content_type (str):
        content_encoding (str):
        timestamp (str):

    """

    def __init__(
        self,
        content_type: str = None,
        content_encoding: str = None,
        timestamp: float = None,
        correlation_id: str = None,
        reply_to: str = None,
        message_id: str = None,
        user_id: str = None,
        app_id: str = None,
    ):
        """__init__.

        Args:
            content_type (str): content_type
            content_encoding (str): content_encoding
            timestamp (float): timestamp
            correlation_id (str): correlation_id
            reply_to (str): reply_to
            message_id (str): message_id
            user_id (str): user_id
            app_id (str): app_id
        """
        if timestamp is None:
            timestamp = gen_timestamp()
        super(MessageProperties, self).__init__(
            content_type=content_type,
            content_encoding=content_encoding,
            timestamp=timestamp,
            correlation_id=correlation_id,
            reply_to=reply_to,
            message_id=str(message_id) if message_id is not None else None,
            user_id=str(user_id) if user_id is not None else None,
            app_id=str(app_id) if app_id is not None else None,
        )


class ConnectionParameters(BaseConnectionParameters):
    """AMQP Connection parameters.
    AMQP connection parameters class
    """

    host: str = "127.0.0.1"
    port: int = 5672
    vhost: str = "/"
    secure: bool = False
    reconnect_attempts: int = 10
    retry_delay: float = 5.0
    timeout: float = 120
    blocked_connection_timeout: float = None
    heartbeat_timeout: int = 60
    channel_max: int = 128
    username: str = "guest"
    password: str = "guest"

    def make_pika(self):
        return pika.ConnectionParameters(
            host=self.host,
            port=str(self.port),
            credentials=pika.PlainCredentials(
                username=self.username, password=self.password
            ),
            connection_attempts=self.reconnect_attempts,
            retry_delay=self.retry_delay,
            blocked_connection_timeout=self.blocked_connection_timeout,
            socket_timeout=self.timeout,
            virtual_host=self.vhost,
            heartbeat=self.heartbeat_timeout,
            channel_max=self.channel_max,
        )

    def __str__(self):
        _properties = {
            "host": self.host,
            "port": self.port,
            "vhost": self.vhost,
            "reconnect_attempts": self.reconnect_attempts,
            "retry_delay": self.retry_delay,
            "timeout": self.timeout,
            "blocked_connection_timeout": self.blocked_connection_timeout,
            "heartbeat_timeout": self.heartbeat_timeout,
            "channel_max": self.channel_max,
        }
        _str = json.dumps(_properties)
        return _str


class Connection(pika.BlockingConnection):
    """Connection. Thin wrapper around pika.BlockingConnection"""

    def __init__(self, conn_params: ConnectionParameters):
        """__init__.

        Args:
            conn_params (ConnectionParameters): conn_params
        """
        self._connection_params = conn_params
        self._pika_connection = None
        self._transport = None
        self._events_thread = None
        self._t_stop_event = None
        super(Connection, self).__init__(parameters=self._connection_params.make_pika())

    def stop_amqp_events_thread(self):
        """stop_amqp_events_thread.
        Stops the background thead that handles internal amqp events.
        """
        if self._t_stop_event is not None:
            self._t_stop_event.set()
            self._events_thread = None

    def detach_amqp_events_thread(self):
        """detach_amqp_events_thread.
        Starts a thread in background to handle with internal amqp events.
            Useful for use with producers in complex applications where
            the program might sleep for several seconds. In this case,
            if the amqp events thread is not started, the main thread
            will be blocked and messages will not leave to the wire at
            the expected time.
        """
        if self._events_thread is not None:
            if self._events_thread.is_alive():
                return
        self._events_thread = Thread(target=self._ensure_events_processed)
        self._events_thread.daemon = True
        self._t_stop_event = ThreadEvent()
        self._events_thread.start()

    def _ensure_events_processed(self):
        """_ensure_events_processed."""
        try:
            while True:
                self.sleep(1)
                if self._t_stop_event.is_set():
                    break
        except Exception as exc:
            print(f"Exception thrown while processing amqp events - {exc}")


class ExchangeType:
    """AMQP Exchange Types."""

    Topic = "topic"
    Direct = "direct"
    Fanout = "fanout"
    Default = ""


class AMQPTransport(BaseTransport):
    """AMQPT Transport implementation."""

    def __init__(self, connection: Connection = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._connection = connection
        self._channel = None
        self._closing = False

    @property
    def channel(self):
        return self._channel

    @property
    def connection(self):
        return self._connection

    def connect(self) -> bool:
        try:
            if self._connection is None:
                self._connection = Connection(self._conn_params)
            self.create_channel()
            return True
        except pika.exceptions.ProbableAuthenticationError as e:
            logger.error(f"Authentication Error: {str(e)}")
            return False
        except Exception as e:
            return False

    def _on_connect(self):
        ch = self._connection.channel()
        self._channel = ch

    def create_channel(self):
        """Creates a new channel."""
        try:
            # Create a new communication channel
            self._channel = self._connection.channel()
            self.log.debug(
                "Connected to AMQP broker <amqp://"
                + f"{self._conn_params.host}:{self._conn_params.port}, "
                + f"vhost={self._conn_params.vhost}>"
            )
        except pika.exceptions.ConnectionClosed:
            self.log.debug("Connection timed out. Reconnecting...")
            self.connect()
        except pika.exceptions.AuthenticationError:
            self.log.debug("Authentication Error. Reconnecting...")
        except pika.exceptions.AMQPConnectionError as e:
            self.log.debug(f"Connection Error ({e}). Reconnecting...")
            self.connect()
        self._connected = True

    def add_threadsafe_callback(self, cb, *args, **kwargs):
        self.connection.add_callback_threadsafe(functools.partial(cb, *args, **kwargs))

    def process_amqp_events(self, timeout=0):
        """Force process amqp events, such as heartbeat packages."""
        self.connection.process_data_events(timeout)
        # self.add_threadsafe_callback(self.connection.process_data_events)

    def detach_amqp_events_thread(self):
        self.connection.detach_amqp_events_thread()

    def _signal_handler(self, signum, frame):
        """TODO"""
        self.log.debug(f"Signal received: {signum}")
        self._graceful_shutdown()

    def _graceful_shutdown(self):
        if not self._connection:
            return
        if not self._channel:
            return
        if self._channel.is_closed:
            return
        self.log.debug("Invoking a graceful shutdown...")
        if self.channel.is_open:
            self.add_threadsafe_callback(self.channel.close)
        self.log.debug("Channel closed!")
        self._connected = False

    def exchange_exists(self, exchange_name):
        resp = self._channel.exchange_declare(
            exchange=exchange_name,
            passive=True,  # Perform a declare or just to see if it exists
        )
        self.log.debug(f"Exchange exists result: {resp}")
        return resp

    def create_exchange(
        self, exchange_name: str, exchange_type: ExchangeType, internal=None
    ):
        """
        Create a new exchange.

        @param exchange_name: The name of the exchange (e.g. com.logging).
        @type exchange_name: string

        @param exchange_type: The type of the exchange (e.g. 'topic').
        @type exchange_type: string
        """
        self._channel.exchange_declare(
            exchange=exchange_name,
            durable=True,  # Survive reboot
            passive=False,  # Perform a declare or just to see if it exists
            internal=internal,  # Can only be published to by other exchanges
            exchange_type=exchange_type,
        )

        self.log.debug(
            f"Created exchange: [name={exchange_name}, type={exchange_type}]"
        )

    def create_queue(
        self,
        queue_name: str = "",
        exclusive: str = True,
        queue_size: int = 10,
        message_ttl: int = 60000,
        overflow_behaviour: int = "drop-head",
        expires: int = 600000,
    ):
        """
        Create a new queue.

        @param queue_name: The name of the queue.
        @type queue_name: string

        @param exclusive: Only allow access by the current connection.
        @type exclusive: bool

        @param queue_size: The size of the queue
        @type queue_size: int

        @param message_ttl: Per-queue message time-to-live
            (https://www.rabbitmq.com/ttl.html#per-queue-message-ttl)
        @type message_ttl: int

        @param overflow_behaviour: Overflow behaviour - 'drop-head' ||
            'reject-publish'.
            https://www.rabbitmq.com/maxlength.html#overflow-behaviour
        @type overflow_behaviour: str

        @param expires: Queues will expire after a period of time only
            when they are not used (e.g. do not have consumers).
            This feature can be used together with the auto-delete
            queue property. The value is expressed in milliseconds (ms).
            Default value is 10 minutes.
            https://www.rabbitmq.com/ttl.html#queue-ttl
        """
        args = {
            "x-max-length": queue_size,
            "x-overflow": overflow_behaviour,
            "x-message-ttl": message_ttl,
            "x-expires": expires,
        }

        result = self._channel.queue_declare(
            exclusive=exclusive,
            queue=queue_name,
            durable=False,
            auto_delete=True,
            arguments=args,
        )
        queue_name = result.method.queue
        self.log.debug(
            f"Created queue [{queue_name}] [size={queue_size}, ttl={message_ttl}]"
        )
        return queue_name

    def delete_queue(self, queue_name):
        self._channel.queue_delete(queue=queue_name)

    def queue_exists(self, queue_name):
        """Check if a queue exists, given its name.

        Args:
            queue_name (str): The name of the queue.

        Returns:
            int: True if queue exists False otherwise.
        """
        # resp = self._channel.queue_declare(queue_name, passive=True,
        #                                    callback=self._queue_exists_clb)
        try:
            _ = self._channel.queue_declare(queue_name, passive=True)
        except pika.exceptions.ChannelClosedByBroker as exc:
            self.create_channel()
            if exc.reply_code == 404:  # Not Found
                return False
            else:
                self.log.warning(f"Queue exists <{queue_name}>")
                return True

    def bind_queue(self, exchange_name, queue_name, bind_key):
        """
        Bind a queue to and exchange using a bind-key.

        @param exchange_name: The name of the exchange (e.g. com.logging).
        @type exchange_name: string

        @param queue_name: The name of the queue.
        @type queue_name: string

        @param bind_key: The binding key name.
        @type bind_key: string
        """
        try:
            self._channel.queue_bind(
                exchange=exchange_name, queue=queue_name, routing_key=bind_key
            )
        except Exception:
            raise AMQPError("Error while trying to bind queue to exchange")

    def set_channel_qos(self, prefetch_count=1, global_qos=False):
        self._channel.basic_qos(prefetch_count=prefetch_count, global_qos=global_qos)

    def consume_from_queue(self, queue_name, callback):
        consumer_tag = self._channel.basic_consume(queue_name, callback)
        return consumer_tag

    def start_consuming(self):
        self.channel.start_consuming()

    def stop_consuming(self):
        try:
            self.channel.stop_consuming()
        except BaseException:
            pass

    def disconnect(self):
        self._graceful_shutdown()

    def start(self):
        self.connect()

    def stop(self):
        self.stop_consuming()
        self.disconnect()


class RPCService(BaseRPCService):
    """AMQP RPC Service class.
    Implements an AMQP RPC Service.

    Args:
        rpc_name (str): The name of the RPC.
        exchange (str): The exchange to bind the RPC.
            Defaults to (AMQT default).
        on_request (function): The on-request callback function to register.
    """

    def __init__(
        self, exchange: str = "", connection: Connection = None, *args, **kwargs
    ):
        """__init__.

        Args:
            exchange (str): exchange
            args:
            kwargs:
        """
        self._exchange = exchange
        self._closing = False
        self._rpc_queue = None
        super(RPCService, self).__init__(*args, **kwargs)

        self._transport = AMQPTransport(
            conn_params=self._conn_params, connection=connection, debug=self.debug
        )

    def run_forever(self, raise_if_exists: bool = False):
        """Run RPC Service in normal mode. Blocking operation."""
        status = self._transport.connect()
        if not status:
            raise ConnectionError("Failed to connect to AMQP broker")

        self._rpc_queue = self._transport.create_queue(self._rpc_name)
        self._transport.set_channel_qos(prefetch_count=self._max_workers)
        self._transport.consume_from_queue(self._rpc_queue, self._on_request_handle)
        try:
            self._transport.start_consuming()
        except pika.exceptions.ConnectionClosedByBroker as exc:
            self.log.error(exc, exc_info=True)
        except pika.exceptions.AMQPConnectionError as exc:
            self.log.error(exc, exc_info=True)
        except Exception as exc:
            self.log.error(exc, exc_info=True)
            raise AMQPError("Error while trying to consume from queue")

    def _rpc_exists(self):
        return self._transport.queue_exists(self._rpc_name)

    def _on_request_handle(self, ch, method, properties, body):
        self._executor.submit(
            self._on_request_callback, ch, method, properties, body
        )
        # TODO handle tasks

    def _on_request_callback(self, ch, method, properties, body):
        _data = {}
        _ctype = None
        _cencoding = None
        _ts_send = None
        _dmode = None
        _corr_id = None
        _reply_to = None
        _delivery_tag = None
        try:
            _reply_to = properties.reply_to
            _delivery_tag = method.delivery_tag
            _corr_id = properties.correlation_id
            _ctype = properties.content_type
            _cencoding = properties.content_encoding
            _dmode = properties.delivery_mode
            _ts_send = properties.timestamp
            _req_msg = CommRPCMessage(
                header=CommRPCHeader(reply_to=_reply_to), data=_data
            )
            if not self._validate_rpc_req_msg(_req_msg):
                raise RPCRequestError("Request Message is invalid!")
        except Exception:
            self.log.error("Exception Thrown in on_request_handle", exc_info=True)
        try:
            if self._compression != CompressionType.NO_COMPRESSION:
                body = deflate(body)
            _data = self._serializer.deserialize(body)
        except Exception:
            self.log.error("Could not deserialize data", exc_info=True)
            self._transport.add_threadsafe_callback(
                self._send_response, {}, ch, _corr_id, _reply_to, _delivery_tag
            )
            return
        try:
            resp = self._invoke_onrequest_callback(_data)
            self._transport.add_threadsafe_callback(
                self._send_response, resp, ch, _corr_id, _reply_to, _delivery_tag
            )
        except Exception:
            self.log.error("OnRequest Callback invocation failed", exc_info=True)

    def _invoke_onrequest_callback(self, data: dict):
        if self._msg_type is None:
            try:
                resp = self.on_request(data)
            except Exception as exc:
                self.log.error(str(exc), exc_info=False)
                resp = {}
        else:
            try:
                msg = self._msg_type.Request(**data)
                resp = self.on_request(msg)
            except Exception as exc:
                self.log.error(str(exc), exc_info=False)
                resp = self._msg_type.Response()
            resp = resp.dict()
        return resp

    def _send_response(
        self, data: dict, channel, correlation_id: str, reply_to: str, delivery_tag: str
    ):
        _payload = None
        _encoding = None
        _type = None
        try:
            _encoding = self._serializer.CONTENT_ENCODING
            _type = self._serializer.CONTENT_TYPE
            _payload = self._serializer.serialize(data)
            if self._compression != CompressionType.NO_COMPRESSION:
                _payload = inflate_str(_payload)
            else:
                _payload = _payload.encode(_encoding)
        except Exception as e:
            self.log.error("Could not deserialize data", exc_info=True)
            _payload = {"status": 501, "error": f"Internal server error: {e}"}

        _msg_props = MessageProperties(
            content_type=_type,
            content_encoding=_encoding,
            correlation_id=correlation_id,
        )

        channel.basic_publish(
            exchange=self._exchange,
            routing_key=reply_to,
            properties=_msg_props,
            body=_payload,
        )
        # Acknowledge receiving the message.
        channel.basic_ack(delivery_tag=delivery_tag)

    def close(self) -> bool:
        """Stop RPC Service.
        Safely close channel and connection to the broker.
        """
        if self._closing:
            return False
        self._closing = True
        if not self._transport.channel:
            return False
        if self._transport.channel.is_closed:
            self.log.warning("Channel was already closed!")
            return False
        self._transport.add_threadsafe_callback(
            self._transport.delete_queue, self._rpc_queue
        )
        super(RPCService, self).stop()
        return True

    def stop(self) -> bool:
        """Stop RPC Service.
        Safely close channel and connection to the broker.
        """
        return self.close()

    def __del__(self):
        self.close()

    def __exit__(self, exc_type, value, traceback):
        self.close()


class RPCClient(BaseRPCClient):
    """AMQP RPC Client class.

    Args:
        rpc_name (str): The name of the RPC.
        **kwargs: The Keyword arguments to pass to  the base class
            (BaseRPCClient).
    """

    def __init__(
        self,
        use_corr_id=False,
        connection: Connection = None,
        *args,
        **kwargs):
        self._use_corr_id = use_corr_id
        self._corr_id = None
        self._response = None
        self._exchange = ExchangeType.Default
        self._delay = 0

        super().__init__(*args, **kwargs)

        self._transport = AMQPTransport(
            conn_params=self._conn_params, connection=connection, debug=self.debug
        )
        self._transport.connect()

        # Register on_request cabblack handle
        self._transport.add_threadsafe_callback(
            self._transport.channel.basic_consume,
            "amq.rabbitmq.reply-to",
            self._on_response_handle,
            exclusive=True,
            consumer_tag=None,
            auto_ack=True,
        )

        if connection is None:
            self.run()

    @property
    def delay(self) -> float:
        """The last recorded delay of the communication.
        Internally calculated.
        """
        return self._delay

    def run(self):
        self._transport.detach_amqp_events_thread()

    def gen_corr_id(self) -> str:
        """Generate correlationID."""
        return str(uuid.uuid4())

    def call(self, msg: RPCMessage.Request, timeout: float = 10.0):
        """Call RPC.

        Args:
            timeout (float): Response timeout. Set this value carefully
                based on application criteria.
        """
        if self._msg_type is None:
            data = msg
        else:
            data = msg.dict()

        self._response = None
        if self._use_corr_id:
            self._corr_id = self.gen_corr_id()

        start_t = time.time()
        self._transport.add_threadsafe_callback(functools.partial(self._send_msg, data))
        resp = self._wait_for_response(timeout=timeout)
        if resp is None:
            return resp
        elapsed_t = time.time() - start_t
        self._delay = elapsed_t
        if self._msg_type is None:
            return resp
        else:
            return self._msg_type.Response(**resp)

    def _wait_for_response(self, timeout: float = 30.0):
        start_t = time.time()
        while self._response is None:
            elapsed_t = time.time() - start_t
            if elapsed_t >= timeout:
                return None
            time.sleep(0.001)
        return self._response

    def _on_response_handle(self, ch, method, properties, body):
        _ctype = None
        _cencoding = None
        _ts_send = None
        _dmode = None
        _data = None
        try:
            if self._use_corr_id:
                _corr_id = properties.correlation_id
                if self._corr_id != _corr_id:
                    return
            _ctype = properties.content_type
            _cencoding = properties.content_encoding
            _dmode = properties.delivery_mode
            _ts_send = properties.timestamp
        except Exception:
            self.log.error("Error parsing response from rpc server.", exc_info=True)

        try:
            if self._compression != CompressionType.NO_COMPRESSION:
                body = deflate(body)
            _data = self._serializer.deserialize(body)
        except Exception:
            self.log.error("Could not deserialize data", exc_info=True)
            _data = {}
        self._response = _data

    def _send_msg(self, data: Dict) -> None:
        _payload = None
        _encoding = None
        _type = None

        _encoding = self._serializer.CONTENT_ENCODING
        _type = self._serializer.CONTENT_TYPE
        _payload = self._serializer.serialize(data)
        if self._compression != CompressionType.NO_COMPRESSION:
            _payload = inflate_str(_payload)
        else:
            _payload = _payload.encode(_encoding)

        # Direct reply-to implementation
        _rpc_props = MessageProperties(
            content_type=_type,
            content_encoding=_encoding,
            correlation_id=self._corr_id,
            timestamp=gen_timestamp(),
            reply_to="amq.rabbitmq.reply-to",
        )

        self._transport.add_threadsafe_callback(
            self._transport.channel.basic_publish,
            exchange=self._exchange,
            routing_key=self._rpc_name,
            mandatory=False,
            properties=_rpc_props,
            body=_payload,
        )


class Publisher(BasePublisher):
    """Publisher class.

    Args:
        topic (str): The topic uri to publish data.
        exchange (str): The exchange to publish data.
        **kwargs: The keyword arguments to pass to the base class
            (BasePublisher).
    """

    def __init__(
        self,
        exchange: str = "amq.topic",
        connection: Connection = None,
        *args,
        **kwargs,
    ):
        """Constructor."""
        self._topic_exchange = exchange
        super().__init__(*args, **kwargs)

        self._transport = AMQPTransport(
            conn_params=self._conn_params, connection=connection, debug=self.debug
        )
        self._transport.connect()
        self._transport.create_exchange(self._topic_exchange, ExchangeType.Topic)
        if connection is None:
            self.run()

    def run(self) -> None:
        self._transport.detach_amqp_events_thread()

    def publish(self, msg: PubSubMessage) -> None:
        """Publish message once.

        Args:
            msg (PubSubMessage): Message to publish.
        """
        if self._msg_type is not None and not isinstance(msg, PubSubMessage):
            raise ValueError('Argument "msg" must be of type PubSubMessage')
        elif isinstance(msg, dict):
            data = msg
        elif isinstance(msg, PubSubMessage):
            data = msg.dict()
        # Thread Safe solution
        self._transport.add_threadsafe_callback(self._send_msg, data, self._topic)

    def _send_msg(self, msg: Dict, topic: str):
        _payload = None
        _encoding = None
        _type = None

        _encoding = self._serializer.CONTENT_ENCODING
        _type = self._serializer.CONTENT_TYPE
        _payload = self._serializer.serialize(msg)
        if self._compression != CompressionType.NO_COMPRESSION:
            _payload = inflate_str(_payload)
        else:
            _payload = _payload.encode(_encoding)

        msg_props = MessageProperties(
            content_type=_type,
            content_encoding=_encoding,
            message_id=0,
        )

        # In amqp '#' defines one or more words.
        topic = topic.replace("*", "#")

        self._transport._channel.basic_publish(
            exchange=self._topic_exchange,
            routing_key=topic,
            properties=msg_props,
            body=_payload,
        )


class MPublisher(Publisher):
    def __init__(self, *args, **kwargs):
        super().__init__(topic="*", *args, **kwargs)

    def publish(self, msg: PubSubMessage, topic: str) -> None:
        """Publish message once.

        Args:
            msg (PubSubMessage): Message to publish.
        """
        if self._msg_type is not None and not isinstance(msg, PubSubMessage):
            raise ValueError('Argument "msg" must be of type PubSubMessage')
        elif isinstance(msg, dict):
            data = msg
        elif isinstance(msg, PubSubMessage):
            data = msg.dict()
        # Thread Safe solution
        self._transport.add_threadsafe_callback(self._send_msg, data, topic)


class Subscriber(BaseSubscriber):
    """Subscriber class.
    Implements the Subscriber endpoint of the PubSub communication pattern.

    Args:
        topic (str): The topic uri.
        on_message (function): The callback function. This function
            is fired when messages arrive at the registered topic.
        exchange (str): The name of the exchange. Defaults to `amq.topic`
        queue_size (int): The maximum queue size of the topic.
        message_ttl (int): Message Time-to-Live as specified by AMQP.
        overflow (str): queue overflow behavior. Specified by AMQP Protocol.
            Defaults to `drop-head`.
        **kwargs: The keyword arguments to pass to the base class
            (BaseSubscriber).
    """

    FREQ_CALC_SAMPLES_MAX = 100

    def __init__(
        self,
        exchange: str = "amq.topic",
        queue_size: int = 10,
        message_ttl: int = 60000,
        overflow: str = "drop-head",
        connection: Connection = None,
        *args,
        **kwargs,
    ):
        """Constructor."""
        self._topic_exchange = exchange
        self._queue_size = queue_size
        self._message_ttl = message_ttl
        self._overflow = overflow
        self._queue_name = None
        self._closing = False
        self._transport = None

        super().__init__(*args, **kwargs)

        self._transport = AMQPTransport(
            conn_params=self._conn_params, connection=connection, debug=self.debug
        )

        self._last_msg_ts = None
        self._msg_freq_fifo = deque(maxlen=self.FREQ_CALC_SAMPLES_MAX)
        self._hz = 0
        self._sem = Semaphore()

    @property
    def hz(self) -> float:
        """Incoming message frequency."""
        return self._hz

    def run_forever(self) -> None:
        """Start Subscriber. Blocking method."""
        self._transport.connect()
        _exch_ex = self._transport.exchange_exists(self._topic_exchange)
        if _exch_ex.method.NAME != "Exchange.DeclareOk":
            self._transport.create_exchange(self._topic_exchange, ExchangeType.Topic)

        # Create a queue. Set default idle expiration time to 5 mins
        self._queue_name = self._transport.create_queue(
            queue_size=self._queue_size,
            message_ttl=self._message_ttl,
            overflow_behaviour=self._overflow,
            expires=300000,
        )

        # Bind queue to the Topic exchange
        self._transport.bind_queue(self._topic_exchange, self._queue_name, self._topic)
        self._consume()

    def close(self) -> None:
        if self._closing:
            return False
        elif not self._transport:
            return False
        elif not self._transport.channel:
            return False
        elif self._transport.channel.is_closed:
            self.log.warning("Channel was already closed!")
            return False
        self._closing = True
        self._transport.add_threadsafe_callback(
            self._transport.delete_queue, self._queue_name
        )

    def _consume(self, reliable: bool = False) -> None:
        """Start AMQP consumer."""
        self._transport._channel.basic_consume(
            self._queue_name,
            self._on_msg_callback_wrapper,
            exclusive=False,
            auto_ack=(not reliable),
        )
        try:
            self._transport.start_consuming()
        except KeyboardInterrupt as exc:
            # Log error with traceback
            self.log.error(exc, exc_info=False)
        except Exception as exc:
            self.log.error(exc, exc_info=False)
            raise AMQPError("Could not consume from message queue")

    def _on_msg_callback_wrapper(self, ch, method, properties, body):
        _data = {}
        _ctype = None
        _cencoding = None
        _ts_send = None
        _dmode = None

        try:
            _ctype = properties.content_type
            _cencoding = properties.content_encoding
            _dmode = properties.delivery_mode
            _ts_send = properties.timestamp
        except Exception:
            self.log.debug("Failed to read message properties", exc_info=True)
        try:
            if self._compression != CompressionType.NO_COMPRESSION:
                body = deflate(body)
            _data = self._serializer.deserialize(body)
        except Exception:
            self.log.error("Could not deserialize data", exc_info=True)
            # Return data as is. Let callback handle with encoding...
            _data = {}
        try:
            self._sem.acquire()
            self._sem.release()
        except Exception:
            self.log.warn("Could not calculate message rate", exc_info=True)

        try:
            if self.onmessage is not None:
                if self._msg_type is None:
                    _clb = functools.partial(self.onmessage, _data)
                else:
                    _clb = functools.partial(self.onmessage, self._msg_type(**_data))
                _clb()
        except Exception:
            self.log.error("Error in on_msg_callback", exc_info=True)

    def stop(self) -> None:
        self.close()

    def __del__(self):
        self.close()

    def __exit__(self, exc_type, value, traceback):
        self.close()


class PSubscriber(Subscriber):
    """PSubscriber."""

    def __init__(self, *args, **kwargs):
        """__init__.

        Args:
            args:
            kwargs:
        """
        kwargs["topic"] = kwargs["topic"].replace("*", "#")
        super(PSubscriber, self).__init__(*args, **kwargs)

    def _on_msg_callback_wrapper(self, ch, method, properties, body):
        _data = {}
        _ctype = None
        _cencoding = None
        _ts_send = None
        _dmode = None

        try:
            _ctype = properties.content_type
            _cencoding = properties.content_encoding
            _dmode = properties.delivery_mode
            _ts_send = properties.timestamp
        except Exception:
            self.log.debug("Error reading message properties", exc_info=True)

        try:
            if self._compression != CompressionType.NO_COMPRESSION:
                body = deflate(body)
            _data = self._serializer.deserialize(body)
        except Exception:
            self.log.error("Could not deserialize data", exc_info=True)
            # Return data as is. Let callback handle with encoding...
            _data = {}
        try:
            _topic = method.routing_key
            _topic = _topic.replace("#", "").replace("*", "")
        except Exception:
            self.log.error(
                "Routing key could not be retrieved for message", exc_info=True
            )
            return

        try:
            if self.onmessage is not None:
                if self._msg_type is None:
                    _clb = functools.partial(self.onmessage, _data, _topic)
                else:
                    _clb = functools.partial(
                        self.onmessage, self._msg_type(**_data), _topic
                    )
                _clb()
        except Exception:
            self.log.error("Error in on_msg_callback", exc_info=True)


class ActionService(BaseActionService):
    def __init__(self, *args, **kwargs):
        """__init__.

        Args:
            args: See BaseActionService parent class
            kwargs: See BaseActionService parent class
        """
        super(ActionService, self).__init__(*args, **kwargs)

        self._goal_rpc = RPCService(
            msg_type=_ActionGoalMessage,
            rpc_name=self._goal_rpc_uri,
            conn_params=self._conn_params,
            on_request=self._handle_send_goal,
            debug=self.debug,
        )
        self._cancel_rpc = RPCService(
            msg_type=_ActionCancelMessage,
            rpc_name=self._cancel_rpc_uri,
            conn_params=self._conn_params,
            on_request=self._handle_cancel_goal,
            debug=self.debug,
        )
        self._result_rpc = RPCService(
            msg_type=_ActionResultMessage,
            rpc_name=self._result_rpc_uri,
            conn_params=self._conn_params,
            on_request=self._handle_get_result,
            debug=self.debug,
        )
        self._feedback_pub = Publisher(
            msg_type=_ActionFeedbackMessage,
            topic=self._feedback_topic,
            conn_params=self._conn_params,
            debug=self.debug,
        )
        self._status_pub = Publisher(
            msg_type=_ActionStatusMessage,
            topic=self._status_topic,
            conn_params=self._conn_params,
            debug=self.debug,
        )


class ActionClient(BaseActionClient):
    def __init__(self, *args, **kwargs):
        """__init__.
        Action Client constructor.

        Args:
            args: See BaseActionClient parent class
            kwargs: See BaseActionClient parent class
        """
        super(ActionClient, self).__init__(*args, **kwargs)

        self._goal_client = RPCClient(
            msg_type=_ActionGoalMessage,
            rpc_name=self._goal_rpc_uri,
            conn_params=self._conn_params,
            debug=self.debug,
        )
        self._cancel_client = RPCClient(
            msg_type=_ActionCancelMessage,
            rpc_name=self._cancel_rpc_uri,
            conn_params=self._conn_params,
            debug=self.debug,
        )
        self._result_client = RPCClient(
            msg_type=_ActionResultMessage,
            rpc_name=self._result_rpc_uri,
            conn_params=self._conn_params,
            debug=self.debug,
        )
        self._status_sub = Subscriber(
            msg_type=_ActionStatusMessage,
            conn_params=self._conn_params,
            topic=self._status_topic,
            on_message=self._on_status,
        )
        self._status_sub = Subscriber(
            msg_type=_ActionStatusMessage,
            conn_params=self._conn_params,
            topic=self._status_topic,
            on_message=self._on_status,
        )
        self._feedback_sub = Subscriber(
            msg_type=_ActionFeedbackMessage,
            conn_params=self._conn_params,
            topic=self._feedback_topic,
            on_message=self._on_feedback,
        )
