from abc import (
    ABC,
    abstractmethod,
)
import asyncio
import logging
import signal
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)

from websockets import (
    ConnectionClosed,
    WebSocketException,
)

from web3._utils.batching import (
    BATCH_REQUEST_ID,
    sort_batch_response_by_response_ids,
)
from web3._utils.caching import (
    generate_cache_key,
)
from web3._utils.caching.caching_utils import (
    async_handle_recv_caching,
    async_handle_send_caching,
)
from web3._utils.validation import (
    validate_rpc_response_and_raise_if_error,
)
from web3.exceptions import (
    PersistentConnectionClosedOK,
    ProviderConnectionError,
    TaskNotRunning,
    TimeExhausted,
    Web3AttributeError,
)
from web3.providers.async_base import (
    AsyncJSONBaseProvider,
)
from web3.providers.persistent.request_processor import (
    RequestProcessor,
)
from web3.types import (
    RPCEndpoint,
    RPCId,
    RPCRequest,
    RPCResponse,
)

if TYPE_CHECKING:
    from web3 import AsyncWeb3  # noqa: F401
    from web3.middleware.base import MiddlewareOnion  # noqa: F401


DEFAULT_PERSISTENT_CONNECTION_TIMEOUT = 30.0


class PersistentConnectionProvider(AsyncJSONBaseProvider, ABC):
    logger = logging.getLogger("web3.providers.PersistentConnectionProvider")
    has_persistent_connection = True

    _send_func_cache: Tuple[
        Optional[int], Optional[Callable[..., Coroutine[Any, Any, RPCRequest]]]
    ] = (
        None,
        None,
    )
    _recv_func_cache: Tuple[
        Optional[int], Optional[Callable[..., Coroutine[Any, Any, RPCResponse]]]
    ] = (
        None,
        None,
    )

    def __init__(
        self,
        request_timeout: float = DEFAULT_PERSISTENT_CONNECTION_TIMEOUT,
        subscription_response_queue_size: int = 500,
        silence_listener_task_exceptions: bool = False,
        max_connection_retries: int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._request_processor = RequestProcessor(
            self,
            subscription_response_queue_size=subscription_response_queue_size,
        )
        self._message_listener_task: Optional["asyncio.Task[None]"] = None
        self._batch_request_counter: Optional[int] = None
        self._listen_event: asyncio.Event = asyncio.Event()
        self._max_connection_retries = max_connection_retries

        self.request_timeout = request_timeout
        self.silence_listener_task_exceptions = silence_listener_task_exceptions

    async def send_func(
        self, async_w3: "AsyncWeb3", middleware_onion: "MiddlewareOnion"
    ) -> Callable[..., Coroutine[Any, Any, RPCRequest]]:
        """
        Cache the middleware chain for `send`.
        """
        middleware = middleware_onion.as_tuple_of_middleware()
        cache_key = hash(tuple(id(mw) for mw in middleware))

        if cache_key != self._send_func_cache[0]:

            async def send_function(method: RPCEndpoint, params: Any) -> RPCRequest:
                for mw in middleware:
                    initialized = mw(async_w3)
                    method, params = await initialized.async_request_processor(
                        method, params
                    )

                return await self.send_request(method, params)

            self._send_func_cache = (cache_key, send_function)

        return self._send_func_cache[1]

    async def recv_func(
        self, async_w3: "AsyncWeb3", middleware_onion: "MiddlewareOnion"
    ) -> Any:
        """
        Cache and compose the middleware stack for `recv`.
        """
        middleware = middleware_onion.as_tuple_of_middleware()
        cache_key = hash(tuple(id(mw) for mw in middleware))

        if cache_key != self._recv_func_cache[0]:

            async def recv_function(rpc_request: RPCRequest) -> RPCResponse:
                # first, retrieve the response
                response = await self.recv_for_request(rpc_request)
                method = rpc_request["method"]
                for mw in reversed(middleware):
                    initialized = mw(async_w3)
                    response = await initialized.async_response_processor(
                        method, response
                    )
                return response

            self._recv_func_cache = (cache_key, recv_function)

        return self._recv_func_cache[1]

    def get_endpoint_uri_or_ipc_path(self) -> str:
        if hasattr(self, "endpoint_uri"):
            return str(self.endpoint_uri)
        elif hasattr(self, "ipc_path"):
            return str(self.ipc_path)
        else:
            raise Web3AttributeError(
                "`PersistentConnectionProvider` must have either `endpoint_uri` or "
                "`ipc_path` attribute."
            )

    async def connect(self) -> None:
        _connection_attempts = 0
        _backoff_rate_change = 1.75
        _backoff_time = 1.75

        while _connection_attempts != self._max_connection_retries:
            try:
                _connection_attempts += 1
                self.logger.info(
                    f"Connecting to: {self.get_endpoint_uri_or_ipc_path()}"
                )
                await self._provider_specific_connect()
                self._message_listener_task = asyncio.create_task(
                    self._message_listener()
                )
                self._message_listener_task.add_done_callback(
                    self._message_listener_callback
                )
                self.logger.info(
                    f"Successfully connected to: {self.get_endpoint_uri_or_ipc_path()}"
                )
                break
            except (WebSocketException, OSError) as e:
                if _connection_attempts == self._max_connection_retries:
                    raise ProviderConnectionError(
                        f"Could not connect to: {self.get_endpoint_uri_or_ipc_path()}. "
                        f"Retries exceeded max of {self._max_connection_retries}."
                    ) from e
                self.logger.info(
                    f"Could not connect to: {self.get_endpoint_uri_or_ipc_path()}. "
                    f"Retrying in {round(_backoff_time, 1)} seconds.",
                    exc_info=True,
                )
                await asyncio.sleep(_backoff_time)
                _backoff_time *= _backoff_rate_change

    async def disconnect(self) -> None:
        # this should remain idempotent
        try:
            if self._message_listener_task:
                self._message_listener_task.cancel()
                await self._message_listener_task
        except (asyncio.CancelledError, StopAsyncIteration, ConnectionClosed):
            pass
        finally:
            self._message_listener_task = None
            self.logger.info("Message listener background task successfully shut down.")

        await self._provider_specific_disconnect()
        self._request_processor.clear_caches()
        self.logger.info(
            f"Successfully disconnected from: {self.get_endpoint_uri_or_ipc_path()}"
        )

    @async_handle_send_caching
    async def send_request(self, method: RPCEndpoint, params: Any) -> RPCRequest:
        request_dict = self.form_request(method, params)
        await self.socket_send(self.encode_rpc_dict(request_dict))
        return request_dict

    @async_handle_recv_caching
    async def recv_for_request(self, rpc_request: RPCRequest) -> RPCResponse:
        return await self._get_response_for_request_id(rpc_request["id"])

    async def make_request(
        self,
        method: RPCEndpoint,
        params: Any,
    ) -> RPCResponse:
        rpc_request = await self.send_request(method, params)
        return await self.recv_for_request(rpc_request)

    async def make_batch_request(
        self, requests: List[Tuple[RPCEndpoint, Any]]
    ) -> List[RPCResponse]:
        request_data = self.encode_batch_rpc_request(requests)
        await self.socket_send(request_data)

        response = cast(
            List[RPCResponse], await self._get_response_for_request_id(BATCH_REQUEST_ID)
        )
        return response

    # -- abstract methods -- #

    @abstractmethod
    async def socket_send(self, request_data: bytes) -> None:
        """
        Send an encoded RPC request to the provider over the persistent connection.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    async def socket_recv(self) -> RPCResponse:
        """
        Receive, decode, and return an RPC response from the provider over the
        persistent connection.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    # -- private methods -- #

    async def _provider_specific_connect(self) -> None:
        raise NotImplementedError("Must be implemented by subclasses")

    async def _provider_specific_disconnect(self) -> None:
        # this method should be idempotent
        raise NotImplementedError("Must be implemented by subclasses")

    async def _provider_specific_socket_reader(self) -> RPCResponse:
        raise NotImplementedError("Must be implemented by subclasses")

    def _set_signal_handlers(self) -> None:
        def extended_handler(sig: int, frame: Any, existing_handler: Any) -> None:
            loop = asyncio.get_event_loop()

            # invoke the existing handler, if callable
            if callable(existing_handler):
                existing_handler(sig, frame)
            loop.create_task(self.disconnect())

        existing_sigint_handler = signal.getsignal(signal.SIGINT)
        existing_sigterm_handler = signal.getsignal(signal.SIGTERM)

        # extend the existing signal handlers to include the disconnect method
        signal.signal(
            signal.SIGINT,
            lambda sig, frame: extended_handler(sig, frame, existing_sigint_handler),
        )
        signal.signal(
            signal.SIGTERM,
            lambda sig, frame: extended_handler(sig, frame, existing_sigterm_handler),
        )

    def _message_listener_callback(
        self, message_listener_task: "asyncio.Task[None]"
    ) -> None:
        # Puts a `TaskNotRunning` in appropriate queues to signal the end of the
        # listener task to any listeners relying on the queues.
        self._request_processor._subscription_response_queue.put_nowait(
            TaskNotRunning(message_listener_task)
        )
        self._request_processor._handler_subscription_queue.put_nowait(
            TaskNotRunning(message_listener_task)
        )

    def _raise_stray_errors_from_cache(self) -> None:
        """
        Check the request response cache for any errors not tied to current requests
        and raise them if found.
        """
        if not self._is_batching:
            for (
                response
            ) in self._request_processor._request_response_cache._data.values():
                request = (
                    self._request_processor._request_information_cache.get_cache_entry(
                        generate_cache_key(response["id"])
                    )
                )
                if "error" in response and request is None:
                    # if we find an error response in the cache without a corresponding
                    # request, raise the error
                    validate_rpc_response_and_raise_if_error(
                        response, None, logger=self.logger
                    )

    async def _message_listener(self) -> None:
        self.logger.info(
            f"{self.__class__.__qualname__} listener background task started. Storing "
            "all messages in appropriate request processor queues / caches to be "
            "processed."
        )
        while True:
            # the use of sleep(0) seems to be the most efficient way to yield control
            # back to the event loop to share the loop with other tasks.
            await asyncio.sleep(0)

            try:
                response = await self._provider_specific_socket_reader()

                if isinstance(response, list):
                    response = sort_batch_response_by_response_ids(response)

                subscription = (
                    response.get("method") == "eth_subscription"
                    if not isinstance(response, list)
                    else False
                )
                await self._request_processor.cache_raw_response(
                    response, subscription=subscription
                )
                self._raise_stray_errors_from_cache()
            except PersistentConnectionClosedOK as e:
                self.logger.info(
                    "Message listener background task has ended gracefully: "
                    f"{e.user_message}"
                )
                # trigger a return to end the listener task and initiate the callback fn
                return
            except Exception as e:
                if not self.silence_listener_task_exceptions:
                    raise e
                else:
                    self._error_log_listener_task_exception(e)

    def _error_log_listener_task_exception(self, e: Exception) -> None:
        """
        When silencing listener task exceptions, this method is used to log the
        exception and keep the listener task alive. Override this method to fine-tune
        error logging behavior for the implementation class.
        """
        self.logger.error(
            "Exception caught in listener, error logging and keeping "
            "listener background task alive."
            f"\n    error={e.__class__.__name__}: {e}"
        )

    def _handle_listener_task_exceptions(self) -> None:
        """
        Should be called every time a `PersistentConnectionProvider` is polling for
        messages in the main loop. If the message listener task has completed and an
        exception was recorded, raise the exception in the main loop.
        """
        msg_listener_task = getattr(self, "_message_listener_task", None)
        if (
            msg_listener_task
            and msg_listener_task.done()
            and msg_listener_task.exception()
        ):
            raise msg_listener_task.exception()

    async def _get_response_for_request_id(
        self, request_id: Union[RPCId, List[RPCId]], timeout: Optional[float] = None
    ) -> RPCResponse:
        if timeout is None:
            timeout = self.request_timeout

        async def _match_response_id_to_request_id() -> RPCResponse:
            request_cache_key = generate_cache_key(request_id)

            while True:
                # check if an exception was recorded in the listener task and raise
                # it in the main loop if so
                self._handle_listener_task_exceptions()

                if request_cache_key in self._request_processor._request_response_cache:
                    self.logger.debug(
                        f"Popping response for id {request_id} from cache."
                    )
                    popped_response = await self._request_processor.pop_raw_response(
                        cache_key=request_cache_key,
                    )
                    return popped_response
                else:
                    await asyncio.sleep(0)

        try:
            # Add the request timeout around the while loop that checks the request
            # cache. If the request is not in the cache within the request_timeout,
            # raise ``TimeExhausted``.
            return await asyncio.wait_for(_match_response_id_to_request_id(), timeout)
        except asyncio.TimeoutError:
            raise TimeExhausted(
                f"Timed out waiting for response with request id `{request_id}` after "
                f"{self.request_timeout} second(s). This may be due to the provider "
                "not returning a response with the same id that was sent in the "
                "request or an exception raised during the request was caught and "
                "allowed to continue."
            )
