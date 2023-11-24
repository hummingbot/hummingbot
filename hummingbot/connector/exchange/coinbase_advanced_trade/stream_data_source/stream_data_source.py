import asyncio
import functools
import logging
import time
from typing import Any, Awaitable, Callable, Coroutine, Generic, Tuple, TypeVar

from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.logger import HummingbotLogger

from ..connecting_functions.call_or_await import CallOrAwait
from ..connecting_functions.exception_log_manager import log_exception

# This '.' not recommended, however, it helps reduce the length of the import, as well as avoid
# mis-ordering with other more general hummingbot packages
from ..fittings.auto_stream_pipe_fitting import AutoStreamPipeFitting
from ..task_manager import TaskState
from .enums import StreamAction, StreamState
from .errors import CoinbaseAdvancedTradeWSSubscriptionError, StreamDataSourceError
from .protocols import SubscriptionBuilderT, WSAssistantPtl, WSResponsePtl

T = TypeVar("T")


class StreamDataSource(AutoStreamPipeFitting[WSResponsePtl, T], Generic[T]):
    """
    UserStreamTrackerDataSource implementation for Coinbase Advanced Trade API.
    """
    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger | logging.Logger:
        if cls._logger is None:
            name: str = HummingbotLogger.logger_name_for_class(cls)
            cls._logger = logging.getLogger(name)
        return cls._logger

    __slots__ = (
        "_channel",
        "_pair",
        "_ws_factory",
        "_ws_url",
        "_pair_to_symbol",
        "_subscription_builder",
        "_on_failed_subscription",
        "_heartbeat_channel",
        "_subscription_lock",
        "_ws_assistant",
        "_ws_assistant_ready",
        "_last_recv_time_s",
        "_stream_state",
        "_task_state",
    )

    def __init__(
            self,
            *,
            channel: str,
            pair: str,
            ws_factory: Callable[[], Coroutine[Any, Any, WSAssistantPtl]],
            ws_url: str,
            pair_to_symbol: Callable[[str], Awaitable[str]],
            subscription_builder: SubscriptionBuilderT,
            on_failed_subscription: Callable[[WSResponsePtl], None] | None = None,
            heartbeat_channel: str | None = None,
    ) -> None:
        """
        Initialize a StreamDataSource.

        :param channel: The channel to subscribe to.
        :param pair: The pair to subscribe to.
        :param ws_factory: The method for creating the WSAssistant.
        :param pair_to_symbol: The method for converting a pair to a symbol.
        :param subscription_builder: The method for building a subscription payload.
        :param heartbeat_channel: The channel to subscribe to for heartbeats.
        """
        self._channel: str = channel
        self._pair: str = pair
        self._ws_factory: Callable[[], Coroutine[Any, Any, WSAssistantPtl]] = ws_factory
        self._ws_url: str = ws_url
        self._heartbeat_channel: str | None = heartbeat_channel

        self._ws_assistant: WSAssistantPtl | None = None
        self._ws_assistant_ready: asyncio.Event = asyncio.Event()

        # Construct the subscription builder
        self._subscription_builder: functools.partial[SubscriptionBuilderT] = functools.partial(
            subscription_builder,
            pair=self._pair,
            pair_to_symbol=pair_to_symbol,
        )
        self._on_failed_subscription: Callable[[WSResponsePtl], WSResponsePtl] | None = on_failed_subscription
        self._subscription_lock: asyncio.Lock = asyncio.Lock()

        self._last_recv_time_s: float = 0.0
        self._stream_state: StreamState = StreamState.CLOSED

        super().__init__(source=self.get_ws_assistant,
                         handler=self._filter_empty_data,
                         connect=self._connect,
                         disconnect=self.close_connection)

        self._task_state: TaskState = TaskState.STOPPED

    async def _filter_empty_data(self, response: WSResponsePtl) -> T:
        """
        Filters out empty data from the response.

        :param response: The response to filter.
        :return: The filtered response.
        """
        try:
            response = self._on_failed_subscription(response)

        except CoinbaseAdvancedTradeWSSubscriptionError:
            self.logger().error(f"Failed to subscribe to {self._channel} for {self._pair}.")
            await asyncio.sleep(0.25)
            await self.subscribe()
            return

        except asyncio.CancelledError:
            raise

        except Exception as e:
            self.logger().error(f"Unexpected message: {response}.")
            raise e

        self.logger().debug(f"Validated subscription to {self._channel} for {self._pair}.")
        self._last_recv_time_s: float = self._time()
        return response.data

    @property
    def state(self) -> Tuple[StreamState, TaskState]:
        """Returns the state of the stream"""
        return self._stream_state, self._task_state

    @property
    def stream_state(self) -> StreamState:
        """Returns the state of the stream"""
        return self._stream_state

    @property
    def task_state(self) -> TaskState:
        """Returns the state of the stream"""
        return self._task_state

    @property
    def channel(self) -> str:
        """Returns the channel of the stream"""
        return self._channel

    @property
    def pair(self) -> str:
        """Returns the pair of the stream"""
        return self._pair

    @property
    def last_recv_time(self) -> float:
        """Returns the time of the last received message"""
        return self._last_recv_time_s

    async def get_ws_assistant(self) -> WSAssistantPtl:
        """Returns the WS Assistant, when it is available (created by a call to open_connection)"""
        # self.logger().debug("Waiting for WS Assistant to be ready...")
        await self._ws_assistant_ready.wait()
        # self.logger().debug("'-> Send WS Assistant Ready to Stream task")
        return self._ws_assistant

    async def start_stream(self) -> None:
        """Starts the Streaming operation."""
        await self.start_task()
        await self.open_connection()

    async def stop_stream(self) -> None:
        """Starts the Streaming operation."""
        await self.close_connection()
        await self.stop_task()

    async def start_task(self) -> None:
        """Starts the TaskManager transferring messages to Pipeline."""
        if not super(AutoStreamPipeFitting, self).is_running():
            await super(AutoStreamPipeFitting, self).start_task()
            if super(AutoStreamPipeFitting, self).is_running():
                self._task_state = TaskState.STARTED

    async def stop_task(self) -> None:
        """Stops the TaskManager transferring messages to Pipeline."""
        if self._stream_state != StreamState.CLOSED:
            self.logger().error(f"Attempting to stop Task of an unclosed {self._channel}/{self._pair} stream.")
            return
        await super(AutoStreamPipeFitting, self).stop_task()

        if not super(AutoStreamPipeFitting, self).is_running():
            self._task_state = TaskState.STOPPED
        else:
            self.logger().error(f"Failed to stop the TaskManager for {self._channel}/{self._pair} stream.")

    async def open_connection(self) -> None:
        """Initializes the websocket connection and subscribe to the heartbeats channel."""
        if self._stream_state == StreamState.CLOSED:
            # Create the websocket assistant
            self._ws_assistant = await self._ws_factory()
            self.logger().debug(f"_ws_assistant {self._ws_assistant}")

            self.logger().debug(f"_ws_assistant CONNECT {self._ws_url}")
            await self._ws_assistant.connect(ws_url=self._ws_url, ping_timeout=30)
            self.logger().debug(" '-> CONNECTED")

            # Signal that the WS Assistant is ready when connected
            self._ws_assistant_ready.set()
            self._stream_state = StreamState.OPENED

            # Immediately subscribing to heartbeats channel if configured
            if self._heartbeat_channel is not None:
                await self.subscribe(channel=self._heartbeat_channel, set_state=False)

            # Flush out any messages left-over (in particular the SENTINEL)
            self.logger().debug("Restarting the destination")
            await self.destination.start()

        else:
            self.logger().debug(
                f"Attempting to open unclosed {self._channel}/{self._pair} stream. "
                f"State {self._stream_state} left unchanged")

    async def close_connection(self) -> None:
        """Closes websocket operations"""
        if self._ws_assistant is not None:
            try:
                await self.unsubscribe()
            except Exception as e:
                log_exception(e, self.logger(), "ERROR", f"Failed to unsubscribe from channels: {str(e)}")

            # Disconnect from the websocket
            await self._ws_assistant.disconnect()
            self._ws_assistant_ready.clear()
            self._ws_assistant = None

        self._stream_state = StreamState.CLOSED

        # Initiate snapshot downstream
        await self.destination.stop()

    async def subscribe(self, *, channel: str | None = None, set_state: bool = True) -> None:
        """
        Subscribes to the stream with a subscription data.
        When no data is provided, the default subscription data

        :param channel: Channel to subscribe to
        :param set_state: Whether to set the stream state to SUBSCRIBED/STREAMING.
        """
        channel: str = channel or self._channel

        if self._stream_state == StreamState.SUBSCRIBED:
            # self.logger().warning(f"Attempted to subscribe to {channel}/{self._pair} stream while already
            # subscribed.")
            return

        if self._task_state != TaskState.STARTED and channel != "heartbeats":
            self.logger().warning(f"Subscribing to {channel}/{self._pair} stream the TaskManager is NOT "
                                  f"started: Message loss is likely to occur.")

        if self._stream_state != StreamState.OPENED:
            self.logger().warning(f"Subscribing to {channel}/{self._pair} stream while not opened. "
                                  f"Attempting to open the stream...")
            await self.open_connection()

        subscription_builder = functools.partial(
            self._subscription_builder,
            action=StreamAction.SUBSCRIBE,
            channel=channel,
        )
        while True:
            try:
                await self._send_to_stream(subscription_builder=subscription_builder)
                break
            except ConnectionResetError:
                self.logger().debug("Connection reset error occurred")
                await self.close_connection()
                await asyncio.sleep(0.1)
                await self.open_connection()
            except Exception as e:
                raise e

        if set_state:
            self._stream_state = StreamState.SUBSCRIBED
        # self.logger().debug(f"Request sent to {channel} for {self._pair}.")

        self.logger().info(f"Subscribed to {channel} for {self._pair}...")

    async def unsubscribe(self, *, channel: str | None = None, set_state: bool = True) -> None:
        """
        Unsubscribes to the stream with an unsubscribe data.
        When no data is provided, the default subscription data

        :param channel: Channel to unsubscribe from.
        :param set_state: Whether to set the stream state to UNSUBSCRIBED.
        """
        channel: str = channel or self._channel

        if self._stream_state != StreamState.SUBSCRIBED:
            # self.logger().warning(f"Attempted to unsubscribe from {channel}/{self._pair} stream while not
            # subscribed.")
            return

        subscription_builder = functools.partial(
            self._subscription_builder,
            action=StreamAction.UNSUBSCRIBE,
            channel=channel,
        )

        try:
            await self._send_to_stream(subscription_builder=subscription_builder)
        except Exception as e:
            raise e

        if set_state:
            self._stream_state = StreamState.UNSUBSCRIBED
        self.logger().info(f"Unsubscribed from {channel} for {self._pair}.")

    async def _send_to_stream(self, *, subscription_builder: functools.partial[SubscriptionBuilderT]) -> None:
        """
        Sends a payload to the Stream.

        :param subscription_builder: The subscription builder to use
        :type subscription_builder: partial[SubscriptionBuilderT]
        :return: None
        """
        self.logger().debug("Awaiting lock")
        async with self._subscription_lock:
            try:
                payload = await CallOrAwait(subscription_builder).call(logger=self.logger())
                self.logger().debug(f"Awaiting send() with {payload}")
                await self._ws_assistant.send(
                    WSJSONRequest(
                        payload=payload,
                        is_auth_required=True))

            except asyncio.CancelledError as e:
                log_exception(e, self.logger(), "ERROR", f"Cancellation occurred sending sending {payload}")
                await self.close_connection()
                raise e

            except ConnectionResetError as e:
                log_exception(e, self.logger(), "ERROR", f"Connection reset error occurred sending {payload}")
                raise e

            except Exception as e:
                await self.close_connection()
                log_exception(e, self.logger(), "ERROR", f"Unexpected error occurred sending {payload}")
                raise e

    async def _connect(self) -> None:
        """
        Connects to the websocket and subscribes to the user events.
        This method is called by the AutoStreamPipeFitting.
        """
        self.logger().debug(f"_connect to {self._channel} for {self._pair}...")
        await self.open_connection()
        await self.subscribe()

        if self._stream_state != StreamState.SUBSCRIBED:
            raise StreamDataSourceError(f"Cannot listen in the current state {self._stream_state}")

    @staticmethod
    async def _sleep(delay: float) -> None:
        """
        Function added only to facilitate patching the sleep in unit tests without affecting the asyncio module

        :param delay: number of seconds to sleep
        """
        await asyncio.sleep(delay)

    @staticmethod
    def _time() -> float:
        """
        Function added only to facilitate patching the time
        """
        return time.time()
