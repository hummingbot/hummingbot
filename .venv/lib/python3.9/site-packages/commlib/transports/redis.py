import functools
import logging
import time
from typing import Any, Callable, Dict, Optional, Tuple

import redis

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
from commlib.exceptions import RPCRequestError
from commlib.msg import PubSubMessage, RPCMessage
from commlib.pubsub import BasePublisher, BaseSubscriber
from commlib.rpc import (
    BaseRPCClient,
    BaseRPCService,
    CommRPCHeader,
    CommRPCMessage,
)
from commlib.serializer import JSONSerializer, Serializer
from commlib.transports.base_transport import BaseTransport
from commlib.utils import gen_timestamp

from rich import console, pretty

pretty.install()
console = console.Console()

redis_logger = None


class ConnectionParameters(BaseConnectionParameters):
    host: str = "localhost"
    port: int = 6379
    unix_socket: str = ""
    db: int = 0
    username: str = ""
    password: str = ""


class RedisConnection(redis.Redis):
    """RedisConnection."""

    def __init__(self, *args, **kwargs):
        """__init__.

        Args:
            args:
            kwargs:
        """
        super(RedisConnection, self).__init__(*args, **kwargs)


class RedisTransport(BaseTransport):
    @classmethod
    def logger(cls) -> logging.Logger:
        global redis_logger
        if redis_logger is None:
            redis_logger = logging.getLogger(__name__)
        return redis_logger

    def __init__(
        self,
        compression: CompressionType = CompressionType.DEFAULT_COMPRESSION,
        serializer: Serializer = JSONSerializer(),
        *args,
        **kwargs,
    ):
        """__init__.

        Args:
            serializer (Serializer): serializer
            compression (CompressionType): compression
        """
        super().__init__(*args, **kwargs)
        self._serializer = serializer
        self._compression = compression
        self.connect()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def log(self) -> logging.Logger:
        return self.logger()

    def connect(self) -> None:
        if self._conn_params.unix_socket not in ("", None):
            self._redis = RedisConnection(
                unix_socket_path=self._conn_params.unix_socket,
                username=self._conn_params.username,
                password=self._conn_params.password,
                db=self._conn_params.db,
                decode_responses=True,
            )
        else:
            self._redis = RedisConnection(
                host=self._conn_params.host,
                port=self._conn_params.port,
                username=self._conn_params.username,
                password=self._conn_params.password,
                db=self._conn_params.db,
                decode_responses=False,
            )

        self._rsub = self._redis.pubsub()
        self._connected = True

    def start(self) -> None:
        if not self.is_connected:
            self.connect()

    def stop(self) -> None:
        if self.is_connected:
            self._redis.connection_pool.disconnect()
            self._redis.close()
            self._connected = False

    def delete_queue(self, queue_name: str) -> bool:
        # self.log.debug('Removing message queue: <{}>'.format(queue_name))
        return True if self._redis.delete(queue_name) else False

    def queue_exists(self, queue_name: str) -> bool:
        return True if self._redis.exists(queue_name) else False

    def push_msg_to_queue(self, queue_name: str, data: Dict[str, Any]):
        payload = self._serializer.serialize(data)
        if self._compression != CompressionType.NO_COMPRESSION:
            payload = inflate_str(payload)
        self._redis.rpush(queue_name, payload)

    def publish(self, queue_name: str, data: Dict[str, Any]):
        payload = self._serializer.serialize(data)
        if self._compression != CompressionType.NO_COMPRESSION:
            payload = inflate_str(payload)
        self._redis.publish(queue_name, payload)

    def subscribe(self, topic: str, callback: Callable):
        _clb = functools.partial(self._on_msg_internal, callback)
        self._sub = self._rsub.psubscribe(**{topic: _clb})
        self._rsub.get_message()
        t = self._rsub.run_in_thread(0.001, daemon=True)
        return t

    def _on_msg_internal(self, callback: Callable, data: Any):
        if self._compression != CompressionType.NO_COMPRESSION:
            # _topic = data['channel']
            data["data"] = deflate(data["data"])
        callback(data)

    def wait_for_msg(self, queue_name: str, timeout=10):
        try:
            msgq, payload = self._redis.blpop(queue_name, timeout=timeout)
            if self._compression != CompressionType.NO_COMPRESSION:
                payload = deflate(payload)
        except Exception:
            self.log.error(f"Timeout after {timeout} seconds waiting for message")
            msgq = ""
            payload = None
        return msgq, payload


class RPCService(BaseRPCService):
    """RPCService.
    Redis RPC Service class
    """

    def __init__(self, *args, **kwargs):
        """__init__.

        Args:
            args: See BaseRPCService class
            kwargs: See BaseRPCService class
        """
        super(RPCService, self).__init__(*args, **kwargs)
        self._transport = RedisTransport(
            conn_params=self._conn_params,
            serializer=self._serializer,
            compression=self._compression,
        )

    def _send_response(self, data: Dict[str, Any], reply_to: str):
        self._comm_obj.header.timestamp = gen_timestamp()  # pylint: disable=E0237
        self._comm_obj.data = data
        _resp = self._comm_obj.dict()
        self._transport.push_msg_to_queue(reply_to, _resp)

    def _on_request_handle(self, data: Dict[str, Any], header: Dict[str, Any]):
        self._executor.submit(self._on_request_internal, data, header)

    def _on_request_internal(self, data: Dict[str, Any], header: Dict[str, Any]):
        if "reply_to" not in header:
            return
        try:
            _req_msg = CommRPCMessage(
                header=CommRPCHeader(reply_to=header["reply_to"]), data=data
            )
            if not self._validate_rpc_req_msg(_req_msg):
                raise RPCRequestError("Request Message is invalid!")
            if self._msg_type is None:
                resp = self.on_request(data)
            else:
                resp = self.on_request(self._msg_type.Request(**data))
                # RPCMessage.Response object here
                resp = resp.dict()
        except RPCRequestError:
            self.log.error(str(exc), exc_info=False)
            return
        except Exception as exc:
            self.log.error(str(exc), exc_info=False)
            resp = {}
        self._send_response(resp, _req_msg.header.reply_to)

    def run_forever(self):
        if self._transport.queue_exists(self._rpc_name):
            self._transport.delete_queue(self._rpc_name)
        while True:
            msgq, payload = self._transport.wait_for_msg(self._rpc_name, timeout=0)

            self._detach_request_handler(payload)
            if self._t_stop_event is not None:
                if self._t_stop_event.is_set():
                    self.log.debug("Stop event caught in thread")
                    self._transport.delete_queue(self._rpc_name)
                    break
            time.sleep(0.001)

    def _detach_request_handler(self, payload: str):
        data, header = self._unpack_comm_msg(payload)
        self.log.info(f"RPC Request <{self._rpc_name}>")
        self._on_request_handle(data, header)

    def _unpack_comm_msg(self, payload: str) -> Tuple:
        _payload = self._serializer.deserialize(payload)
        _data = _payload["data"]
        _header = _payload["header"]
        return _data, _header


class RPCClient(BaseRPCClient):
    """RPCClient."""

    def __init__(self, *args, **kwargs):
        """__init__.

        Args:
            args:
            kwargs:
        """
        super(RPCClient, self).__init__(*args, **kwargs)
        self._transport = RedisTransport(
            conn_params=self._conn_params,
            serializer=self._serializer,
            compression=self._compression,
        )

    def _gen_queue_name(self):
        return f"rpc-{self._gen_random_id()}"

    def _prepare_request(self, data: Dict[str, Any]):
        self._comm_obj.header.timestamp = gen_timestamp()  # pylint: disable=E0237
        self._comm_obj.header.reply_to = self._gen_queue_name()
        self._comm_obj.data = data
        return self._comm_obj.dict()

    def call(self, msg: RPCMessage.Request, timeout: float = 30) -> RPCMessage.Response:
        # TODO: Evaluate msg type passed here.
        if self._msg_type is None:
            data = msg
        else:
            data = msg.dict()

        _msg = self._prepare_request(data)
        _reply_to = _msg["header"]["reply_to"]
        self._transport.push_msg_to_queue(self._rpc_name, _msg)
        _, _msg = self._transport.wait_for_msg(_reply_to, timeout=timeout)
        self._transport.delete_queue(_reply_to)
        if _msg is None:
            return None
        data, header = self._unpack_comm_msg(_msg)
        # TODO: Evaluate response type and raise exception if necessary
        if self._msg_type is None:
            return data
        else:
            return self._msg_type.Response(**data)

    def _unpack_comm_msg(self, payload: str) -> Tuple:
        _payload = self._serializer.deserialize(payload)
        _data = _payload["data"]
        _header = _payload["header"]
        return _data, _header


class Publisher(BasePublisher):
    """Publisher.
    MQTT Publisher (Single Topic).
    """

    def __init__(self, queue_size: int = 10, *args, **kwargs):
        """__init__.

        Args:
            queue_size (int): queue_size
            args:
            kwargs:
        """
        self._queue_size = queue_size
        self._msg_seq = 0

        super(Publisher, self).__init__(*args, **kwargs)

        self._transport = RedisTransport(
            conn_params=self._conn_params,
            serializer=self._serializer,
            compression=self._compression,
        )

    def publish(self, msg: PubSubMessage) -> None:
        """publish.
        Publish message

        Args:
            msg (PubSubMessage): msg

        Returns:
            None:
        """
        if self._msg_type is not None and not isinstance(msg, PubSubMessage):
            raise ValueError('Argument "msg" must be of type PubSubMessage')
        elif isinstance(msg, dict):
            data = msg
        elif isinstance(msg, PubSubMessage):
            data = msg.dict()
        self.log.debug(f"Publishing Message to topic <{self._topic}>")
        self._transport.publish(self._topic, data)
        self._msg_seq += 1


class MPublisher(Publisher):
    """MPublisher.
    Multi-Topic Redis Publisher
    """

    def __init__(self, *args, **kwargs):
        """__init__.

        Args:
            args: See Publisher class
            kwargs: See Publisher class
        """
        super(MPublisher, self).__init__(topic="*", *args, **kwargs)

    def publish(self, msg: PubSubMessage, topic: str) -> None:
        """publish.

        Args:
            msg (PubSubMessage): Message to publish
            topic (str): Topic (URI) to send the message

        Returns:
            None:
        """
        if self._msg_type is not None and not isinstance(msg, PubSubMessage):
            raise ValueError('Argument "msg" must be of type PubSubMessage')
        elif isinstance(msg, dict):
            data = msg
        elif isinstance(msg, PubSubMessage):
            data = msg.dict()
        self.log.debug(f"Publishing Message: <{topic}>:{data}")
        self._transport.publish(topic, data)
        self._msg_seq += 1


class Subscriber(BaseSubscriber):
    """Subscriber.
    Redis Subscriber
    """

    def __init__(self, queue_size: Optional[int] = 1, *args, **kwargs):
        """__init__.

        Args:
            queue_size (int): queue_size
            args:
            kwargs:
        """
        self._subscriber_thread = None
        self._queue_size = queue_size
        super(Subscriber, self).__init__(*args, **kwargs)

        self._transport = RedisTransport(
            conn_params=self._conn_params,
            serializer=self._serializer,
            compression=self._compression,
        )

    def run(self):
        self._subscriber_thread = self._transport.subscribe(
            self._topic, self._on_message
        )
        self.log.debug(f"Started Subscriber: <{self._topic}>")

    def stop(self):
        """Stop background thread that handle subscribed topic messages"""
        if self._subscriber_thread is not None:
            self._subscriber_thread.stop()
        super().stop()

    def run_forever(self):
        self.run()
        while True:
            time.sleep(0.001)

    def _on_message(self, payload: Dict[str, Any]):
        try:
            data, uri = self._unpack_comm_msg(payload)
            if self.onmessage is not None:
                if self._msg_type is None:
                    _clb = functools.partial(self.onmessage, data)
                else:
                    _clb = functools.partial(self.onmessage, self._msg_type(**data))
                _clb()
        except Exception:
            self.log.error("Exception caught in _on_message", exc_info=True)

    def _unpack_comm_msg(self, msg: Dict[str, Any]) -> Tuple:
        _uri = msg["channel"]
        _data = self._serializer.deserialize(msg["data"])
        return _data, _uri


class PSubscriber(Subscriber):
    """PSubscriber.
    Redis Pattern-based Subscriber.
    """

    def _on_message(self, payload: Dict[str, Any]) -> None:
        try:
            data, topic = self._unpack_comm_msg(payload)
            if self.onmessage is not None:
                if self._msg_type is None:
                    _clb = functools.partial(self.onmessage, data, topic)
                else:
                    _clb = functools.partial(
                        self.onmessage, self._msg_type(**data), topic
                    )
                _clb()
        except Exception:
            self.log.error("Exception caught in _on_message", exc_info=True)


class ActionService(BaseActionService):
    """ActionService.
    Redis Action Server class
    """

    def __init__(self, *args, **kwargs):
        """__init__.

        Args:
            args: See BaseActionService class.
            kwargs:
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
    """ActionClient.
    Redis Action Client class
    """

    def __init__(self, *args, **kwargs):
        """__init__.

        Args:
            args: See BaseActionClient class
            kwargs: See BaseActionClient class
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
        self._feedback_sub = Subscriber(
            msg_type=_ActionFeedbackMessage,
            conn_params=self._conn_params,
            topic=self._feedback_topic,
            on_message=self._on_feedback,
        )
