import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel

from commlib.endpoints import BaseEndpoint, EndpointState
from commlib.msg import RPCMessage
from commlib.utils import gen_random_id, gen_timestamp

rpc_logger = None


class CommRPCHeader(BaseModel):
    reply_to: str = ""
    timestamp: Optional[int] = gen_timestamp()
    content_type: Optional[str] = "json"
    encoding: Optional[str] = "utf8"
    agent: Optional[str] = "commlib"


class CommRPCMessage(BaseModel):
    header: CommRPCHeader = CommRPCHeader()
    data: Dict[str, Any] = {}


class BaseRPCServer(BaseEndpoint):
    @classmethod
    def logger(cls) -> logging.Logger:
        global rpc_logger
        if rpc_logger is None:
            rpc_logger = logging.getLogger(__name__)
        return rpc_logger

    def __init__(
        self,
        base_uri: str = "",
        svc_map: dict = {},
        workers: int = 2,
        *args,
        **kwargs):
        """__init__.
        Initializes a BaseRPCService instance with the provided configuration.

        Args:
            base_uri (str): The base URI for the RPC service.
            svc_map (dict): A mapping of service names to their corresponding RPC service implementations.
            workers (int): The number of worker threads to use for the RPC service.

        Attributes:
            _base_uri (str): The base URI for the RPC service.
            _svc_map (dict): A mapping of service names to their corresponding RPC service implementations.
            _max_workers (int): The number of worker threads to use for the RPC service.
            _gen_random_id (Callable): A function to generate a random ID.
            _executor (ThreadPoolExecutor): A thread pool executor to handle RPC requests.
            _main_thread (threading.Thread): The main thread for the RPC service.
            _t_stop_event (threading.Event): An event to signal the RPC service to stop.
            _comm_obj (CommRPCMessage): An instance of the CommRPCMessage class.
        """

        super().__init__(*args, **kwargs)
        self._base_uri = base_uri
        self._svc_map = svc_map
        self._max_workers = workers
        self._gen_random_id = gen_random_id
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        self._main_thread = None
        self._t_stop_event = None
        self._comm_obj = CommRPCMessage()

    def run_forever(self):
        """run_forever.
        Run the RPC service in background and blocks the main thread.
        """
        raise NotImplementedError()

    def run(self):
        """run.
        Run the RPC service in background.
        """
        self._main_thread = threading.Thread(target=self.run_forever)
        self._main_thread.daemon = True
        self._t_stop_event = threading.Event()
        self._main_thread.start()

    def stop(self) -> None:
        self._transport.stop()


class BaseRPCService(BaseEndpoint):
    """ΒaseRPCService.
    Implements a base class for an RPC service that can be run in the background.

    The `BaseRPCService` class provides a foundation for implementing RPC services that can be run in the background. It includes functionality for managing worker threads, serializing and deserializing RPC messages, and handling incoming RPC requests.

    Subclasses of `BaseRPCService` must implement the `run_forever()` method, which is responsible for the main loop of the RPC service. The `run()` method starts the RPC service in a background thread, and the `stop()` method stops the RPC service.

    The `_serialize_data()`, `_serialize_response()`, and `_validate_rpc_req_msg()` methods are utility functions used by the RPC service implementation.
    """

    @classmethod
    def logger(cls) -> logging.Logger:
        global rpc_logger
        if rpc_logger is None:
            rpc_logger = logging.getLogger(__name__)
        return rpc_logger

    def __init__(
        self,
        rpc_name: str,
        msg_type: RPCMessage = None,
        on_request: Callable = None,
        workers: int = 5,
        *args,
        **kwargs):
        """__init__.
        Initializes a new instance of the `BaseRPCService` class.

        Args:
            rpc_name (str): The name of the RPC service.
            msg_type (RPCMessage, optional): The type of RPC message to use.
            on_request (Callable, optional): A callback function to handle incoming RPC requests.
            workers (int, optional): The maximum number of worker threads to use. Defaults to 5.
            *args: Additional positional arguments to pass to the base class constructor.
            **kwargs: Additional keyword arguments to pass to the base class constructor.

        Attributes:
            _rpc_name (str): The name of the RPC service.
            _msg_type (RPCMessage): The type of RPC message to use.
            on_request (Callable): A callback function to handle incoming RPC requests.
            _gen_random_id (Callable): A function to generate a random ID.
            _max_workers (int): The maximum number of worker threads to use.
            _executor (ThreadPoolExecutor): The thread pool executor used to handle RPC requests.
            _main_thread (threading.Thread): The main thread running the RPC service.
            _t_stop_event (threading.Event): An event used to signal the RPC service to stop.
            _comm_obj (CommRPCMessage): An instance of the `CommRPCMessage` class.
        """

        super().__init__(*args, **kwargs)
        self._rpc_name = rpc_name
        self._msg_type = msg_type
        self.on_request = on_request
        self._gen_random_id = gen_random_id
        self._max_workers = workers
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        self._main_thread = None
        self._t_stop_event = None
        self._comm_obj = CommRPCMessage()

    def _serialize_data(self, payload: Dict[str, Any]) -> str:
        """
        Serializes the given payload dictionary to a string using the configured serializer.

        Args:
            payload (Dict[str, Any]): The dictionary to serialize.

        Returns:
            str: The serialized payload.
        """

        return self._serializer.serialize(payload)

    def _serialize_response(self, message: RPCMessage.Response) -> str:
        """
        Serializes an RPC response message to a string.

        Args:
            message (RPCMessage.Response): The RPC response message to serialize.

        Returns:
            str: The serialized RPC response message.
        """

        return self._serialize_data(message.dict())

    def _validate_rpc_req_msg(self, msg: CommRPCMessage) -> bool:
        """_validate_rpc_req_msg.
        Validates the RPC request message by checking if the message header is present and the reply_to field is not empty or None.

        Args:
            msg (CommRPCMessage): The RPC request message to validate.

        Returns:
            bool: True if the RPC request message is valid, False otherwise.
        """

        if msg.header is None:
            return False
        elif msg.header.reply_to in ("", None):
            return False
        return True

    def run_forever(self):
        """run_forever.
        Run the RPC service in background and blocks the main thread.
        """
        raise NotImplementedError()

    def run(self) -> None:
        """
        Start the subscriber thread in the background without blocking
        the main thread.
        """
        if self._transport is None:
            raise RuntimeError(
                f"Transport not initialized - cannot run {self.__class__.__name__}")
        if not self._transport.is_connected and \
            self._state not in (EndpointState.CONNECTED,
                                EndpointState.CONNECTING):
            self._main_thread = threading.Thread(target=self.run_forever)
            self._main_thread.daemon = True
            self._t_stop_event = threading.Event()
            self._main_thread.start()
            self._state = EndpointState.CONNECTED
        else:
            self.logger().debug(
                f"Transport already connected - cannot run {self.__class__.__name__}")

    def stop(self):
        """
        Stop the RPC service and the main thread.

        This method sets the `_t_stop_event` flag, which is used to signal the main thread to stop running. It then calls the `stop()` method of the parent class to perform any additional cleanup or shutdown logic.
        """

        if self._t_stop_event is not None:
            self._t_stop_event.set()
        super().stop()


class BaseRPCClient(BaseEndpoint):
    """RPCClient Base class.
    Inherit to implement transport-specific RPCClient.
    """

    @classmethod
    def logger(cls) -> logging.Logger:
        global rpc_logger
        if rpc_logger is None:
            rpc_logger = logging.getLogger(__name__)
        return rpc_logger

    def __init__(
        self,
        rpc_name: str,
        msg_type: RPCMessage = None,
        workers: int = 5,
        *args,
        **kwargs):
        """
        Initializes a new instance of the `BaseRPCClient` class.

        Args:
            rpc_name (str): The name of the RPC service.
            msg_type (RPCMessage): The type of RPC message to use.
            workers (int): The number of worker threads to use for asynchronous RPC calls.
            *args: Additional arguments to pass to the parent class constructor.
            **kwargs: Additional keyword arguments to pass to the parent class constructor.

        Attributes:
            _rpc_name (str): The name of the RPC service.
            _msg_type (RPCMessage): The type of RPC message to use.
            _gen_random_id (callable): A function to generate a random ID for RPC messages.
            _max_workers (int): The maximum number of worker threads to use for asynchronous RPC calls.
            _executor (ThreadPoolExecutor): The thread pool executor used for asynchronous RPC calls.
            _comm_obj (CommRPCMessage): An instance of the `CommRPCMessage` class.
        """

        super().__init__(*args, **kwargs)
        self._rpc_name = rpc_name
        self._msg_type = msg_type
        self._gen_random_id = gen_random_id
        self._max_workers = workers
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        self._comm_obj = CommRPCMessage()

    def call(
        self, msg: RPCMessage.Request, timeout: float = 30.0) -> RPCMessage.Response:
        """call.
        Synchronous RPC Call.

        Args:
            msg (RPCMessage.Request): msg
            timeout (float): timeout

        Returns:
            RPCMessage.Response:
        """
        raise NotImplementedError()

    def call_async(
        self,
        msg: RPCMessage.Request,
        timeout: float = 30.0,
        on_response: callable = None) -> Future:
        """call_async.
        Asynchronously call an RPC method and return a Future object.

        Args:
            msg (RPCMessage.Request): The RPC request message.
            timeout (float): The timeout for the RPC call in seconds.
            on_response (callable): An optional callback function to be called when the RPC response is received.

        Returns:
            Future: A Future object representing the asynchronous RPC call.
        """

        _future = self._executor.submit(self.call, msg, timeout)
        if on_response is not None:
            _future.add_done_callback(partial(self._done_callback, on_response))
        return _future

    def _done_callback(self, on_response: callable, _future):
        """_done_callback.
        Handles the completion of an asynchronous RPC call.

        This function is used as a callback for the Future object returned by `call_async()`. It checks the status of the Future and, if successful, calls the provided `on_response` callback with the result.

        Args:
            on_response (callable): A callback function to be called with the RPC response.
            _future (Future): The Future object representing the asynchronous RPC call.
        """

        if _future.cancelled():
            pass
            # TODO: Implement Calcellation logic
        elif _future.done():
            error = _future.exception()
            if error:
                pass
                # TODO: Implement Exception logic
            else:
                result = _future.result()
                on_response(result)
                return result

    def _serialize_data(self, payload: Dict[str, Any]) -> str:
        """
        Serialize the provided payload dictionary into a string representation.

        Args:
            payload (Dict[str, Any]): The dictionary to be serialized.

        Returns:
            str: The serialized representation of the payload.
        """

        return self._serializer.serialize(payload)

    def _serialize_request(self, message: RPCMessage.Request) -> str:
        """
        Serialize the provided RPC request message into a string representation.

        Args:
            message (RPCMessage.Request): The RPC request message to be serialized.

        Returns:
            str: The serialized representation of the RPC request message.
        """

        return self._serialize_data(message.dict())
