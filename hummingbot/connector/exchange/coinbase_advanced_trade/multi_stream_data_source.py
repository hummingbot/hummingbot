import asyncio
import functools
import logging
from collections import defaultdict
from typing import Any, AsyncGenerator, Callable, Coroutine, Dict, Generator, List, Protocol, Tuple, Type, TypeVar

from hummingbot.core.web_assistant.connections.data_types import WSRequest, WSResponse
from hummingbot.logger import HummingbotLogger

from .coinbase_advanced_trade_web_utils import get_timestamp_from_exchange_time
from .pipe.protocols import PipeGetPtl
from .pipeline import PipeBlock, PipesCollector
from .stream_data_source import StreamDataSource, StreamState, SubscriptionBuilderT
from .task_manager import TaskState

T = TypeVar("T")

CollectorT: Type = PipesCollector[Dict[str, Any], T]


class WSAssistantPtl(Protocol):
    async def connect(
            self,
            ws_url: str,
            *,
            ping_timeout: float,
            message_timeout: float | None = None,
            ws_headers: Dict[str, Any] | None = None,
    ) -> None:
        ...

    async def disconnect(self) -> None:
        ...

    async def send(self, request: WSRequest) -> None:
        ...

    async def ping(self) -> None:
        ...

    async def receive(self) -> WSResponse | None:
        ...

    @property
    def last_recv_time(self) -> float:
        return ...

    async def iter_messages(self) -> AsyncGenerator[WSResponse | None, None]:
        yield ...


def _sequencer(
        sequence: int,
        channel: str,
        sequences: Dict[str, int],
        key: str,
        logger: HummingbotLogger | logging.Logger | None = None
) -> None:
    """
    Check the sequence number and increment it.
    """
    if sequence != sequences[key] + 1:
        if logger:
            logger.warning(
                f"Sequence number mismatch. Expected {sequences[key] + 1}, received {sequence} for {key}"
                f"\n      channel: {channel}")
        # This should never occur, it indicates a flaw in the code
        if sequence < sequences[key]:
            raise ValueError(
                f"Sequence number lower than expected {sequences[key] + 1}, received {sequence} for {key}")
    sequences[key] = sequence


def sequence_verifier(
        event_message: Dict[str, Any],
        *,
        sequence_reader: Callable[[Dict[str, Any]], int],
        sequences: Dict[str, int],
        key: str,
        logger: HummingbotLogger | logging.Logger | None = None
) -> Generator[T, None, None]:
    """
    Sequence verification and update method
    :param event_message: The message received from the exchange.
    :param sequence_reader: The method to read the sequence number from the message.
    :param sequences: The dictionary of sequence numbers.
    :param key: The key to the sequence number in the dictionary.
    :param logger: The logger to use.
    :return: Generator of unmodified messages received from the exchange.
    """
    sequence = sequence_reader(event_message)
    if sequence != sequences[key] + 1:
        if logger:
            logger.warning(f"Sequence number mismatch. Expected {sequences[key] + 1}, received {sequence} for {key}")
        # This should never occur, it indicates a flaw in the code
        if sequence < sequences[key]:
            raise ValueError(f"Sequence number lower than expected {sequences[key] + 1}, received {sequence} for {key}")
    sequences[key] = sequence

    yield event_message


def _timestamp_filter_sequence(
        event_message: Dict[str, Any],
        *,
        sequencer: Callable[[int, str], Any],
        logger: HummingbotLogger | logging.Logger | None = None,
) -> Generator[T, None, None]:
    """
    Reformat the timestamp to seconds.
    Filter out heartbeat and (subscriptions?) messages.
    Call the sequencer to track the sequence number.
    :param event_message: The message received from the exchange.
    """
    """
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels#user-channel
    {
      "channel": "user",
      "client_id": "",
      "timestamp": "2023-02-09T20:33:57.609931463Z",
      "sequence_num": 0,
      "events": [...]
    }
    """
    if logger:
        if event_message["channel"] == "user":
            logger.debug(f"Sequence handler {event_message['channel']}:{event_message['sequence_num']}:{event_message}")
        else:
            logger.debug(f"Sequence handler {event_message['channel']}:{event_message['sequence_num']}")
            logger.debug(f"{event_message}")

    # sequence_num = 0: subscriptions message for heartbeats
    # sequence_num = 1: user snapshot message
    # sequence_num = 2: subscriptions message for user
    sequencer(event_message["sequence_num"], event_message["channel"])

    if event_message["channel"] == "user":
        # logging.debug(f"      DEBUG: Filter {event_message}")
        if isinstance(event_message["timestamp"], str):
            event_message["timestamp"] = get_timestamp_from_exchange_time(event_message["timestamp"], "s")
        yield event_message
    # else:
    #     logging.debug(f"*** DEBUG: Filtering message {event_message} {event_message['channel']} not user")


class MultiStreamDataSource:
    """
    MultiStreamDataSource implementation for Coinbase Advanced Trade API.
    """
    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger | logging.Logger:
        if cls._logger is None:
            name: str = HummingbotLogger.logger_name_for_class(cls)
            cls._logger = logging.getLogger(name)
        return cls._logger

    __slots__ = (
        "_streams",
        "_sequences",
        "_transformers",
        "_collector",
        "_ws_factory",
        "_pair_to_symbol",
        "_last_recv_time",
        "_stream_state",
        "_stream_access_lock",
    )

    def __init__(self,
                 *,
                 channels: Tuple[str, ...],
                 pairs: Tuple[str, ...],
                 ws_factory: Callable[[], Coroutine[Any, Any, WSAssistantPtl]],
                 ws_url: str,
                 pair_to_symbol: Callable[[str], Coroutine[Any, Any, str]],
                 subscription_builder: SubscriptionBuilderT,
                 sequence_reader: Callable[[Dict[str, Any]], int],
                 transformers: List[Callable],
                 collector: Callable[..., AsyncGenerator[T, None]],
                 heartbeat_channel: str | None = None) -> None:
        """
        Initialize the CoinbaseAdvancedTradeAPIUserStreamDataSource.

        :param Tuple channels: Channel to subscribe to.
        :param Tuple pairs: symbol to subscribe to.
        :param ws_factory: The method for creating the WSAssistant.
        :param pair_to_symbol: Async function to convert the pair to symbol.
        """

        self._streams: Dict[str, StreamDataSource] = {}
        self._transformers: Dict[str, List[PipeBlock]] = {}
        self._sequences: defaultdict[str, int] = defaultdict(int)

        for channel in channels:
            for pair in pairs:
                channel_pair = self._stream_key(channel=channel, pair=pair)

                # Create the StreamDataSource, websocket to queue
                self._streams[channel_pair] = StreamDataSource(
                    channel=channel,
                    pair=pair,
                    ws_factory=ws_factory,
                    ws_url=ws_url,
                    pair_to_symbol=pair_to_symbol,
                    subscription_builder=subscription_builder,
                    heartbeat_channel=heartbeat_channel,
                )

                # Create the PipeBlocks that transform the messages
                self._transformers[channel_pair]: List[PipeBlock] = []

                # Create the callable to pass as a handler to the PipeBlock
                verify_sequence = functools.partial(
                    sequence_verifier,
                    sequence_reader=sequence_reader,
                    sequences=self._sequences,
                    key=channel_pair,
                    logger=self.logger())

                # Create the PipeBlocks that verify the sequence number and update it
                self._transformers[channel_pair].append(
                    PipeBlock[Dict[str, Any], Dict[str, Any]](
                        self._streams[channel_pair].destination,
                        verify_sequence))

                for transformer in transformers:
                    self._transformers[channel_pair].append(
                        PipeBlock[Dict[str, Any], Dict[str, Any]](
                            self._transformers[channel_pair][-1].destination,
                            transformer,
                        ))

        self._collector: CollectorT = CollectorT(
            sources=tuple(self._transformers[t][-1].destination for t in self._transformers),
            handler=collector,
        )
        self._stream_access_lock: asyncio.Lock = asyncio.Lock()

    @staticmethod
    def _stream_key(*, channel: str, pair: str) -> str:
        """Returns the channel/pair key for the stream"""
        return f"{channel}:{pair}"

    @property
    def queue(self) -> PipeGetPtl[T]:
        """Returns the output queue"""
        return self._collector.destination

    @property
    def states(self) -> List[Tuple[StreamState, TaskState]]:
        """Returns the states of all the streams"""
        return [self._streams[t].state for t in self._streams]

    @property
    def last_recv_time(self) -> float:
        """Returns the time of the last received message"""
        return min((self._streams[t].last_recv_time for t in self._streams))

    async def open(self) -> None:
        """Open all the streams"""
        self.logger().debug(f"Opening {len(self._streams)} streams")
        done: Tuple[bool, ...] = await self._perform_on_all_streams(self._open_connection)
        await self._pop_unsuccessful_streams(done)
        self.logger().debug(f" '> Opened {len(self._streams)} streams")

    async def close(self) -> None:
        """Close all the streams"""
        await self._perform_on_all_streams(self._close_connection)

    async def subscribe(self) -> None:
        """Subscribe to all the streams"""
        self.logger().debug(f"Subscribing {len(self._streams)} streams")
        done: Tuple[bool, ...] = await self._perform_on_all_streams(self._subscribe)
        await self._pop_unsuccessful_streams(done)
        self.logger().debug(f" '> Subscribed {len(self._streams)} streams")

    async def unsubscribe(self) -> None:
        """Unsubscribe to all the streams"""
        await self._perform_on_all_streams(self._unsubscribe)

    async def start_stream(self) -> None:
        """Listen to all the streams and put the messages to the output queue."""
        # Open the streams connection, eliminate the ones that failed
        done: Tuple[bool, ...] = await self._perform_on_all_streams(self._open_connection)
        await self._pop_unsuccessful_streams(done)

        # Streams
        done: Tuple[bool, ...] = await self._perform_on_all_streams(self._start_task)
        await self._pop_unsuccessful_streams(done)

        # Collector
        await self._collector.start_all_tasks()
        if not all(self._collector.are_running):
            self.logger().warning("Collector failed to start all its upstream tasks.")
            await self._pop_unsuccessful_streams(self._collector.are_running)

        # Transformers for each stream in reverse order
        for key in self._streams:
            for transformer in reversed(self._transformers[key]):
                await transformer.start_task()
                if not transformer.is_running:
                    self.logger().warning(f"A transformer {transformer} failed to start for stream {key}.")
                    await self._pop_unsuccessful_streams((transformer.is_running,))

    async def stop_stream(self) -> None:
        """Listen to all the streams and put the messages to the output queue."""
        await self._perform_on_all_streams(self._close_connection)
        await self._perform_on_all_streams(self._stop_task)
        await self._collector.stop_all_tasks()

    async def _pop_unsuccessful_streams(self, success_list: Tuple[bool, ...]) -> None:
        """Remove the streams that fails based on a list of success/failure"""
        for (k, v), s in zip(tuple(self._streams.items()), success_list):
            if not s:
                self.logger().warning(f"Stream {v.channel}:{v.pair} failed to open: Removing from the MultiStream")
                await self._cleanly_terminate_stream(k)
                await self._collector.remove_source(self._transformers[k][-1].destination)
                async with self._stream_access_lock:
                    self._remove_stream(k)

    async def _cleanly_terminate_stream(self, key: str) -> None:
        """Remove the streams that fails based on a list of success/failure"""
        if stream := self._streams.get(key, None):
            await self._unsubscribe(stream)
            await self._close_connection(stream)
            await self._stop_task(stream)

        if transformers := self._transformers.get(key, None):
            await asyncio.gather(*[t.stop_task() for t in transformers])
            await self._collector.stop_task(transformers[-1])

    def _remove_stream(self, key: str) -> None:
        """Remove the streams that fails based on a list of success/failure"""
        self._streams.pop(key)
        self._transformers.pop(key)

    async def _perform_on_all_streams(self, action: Callable[[StreamDataSource], Coroutine]) -> Tuple[bool, ...]:
        """Perform an action on all the streams."""

        async def apply_on_(stream: StreamDataSource) -> bool:
            try:
                await action(stream)
                return True
            except Exception as e:
                self.logger().error(
                    f"An error occurred while performing action on stream {stream.channel}:{stream.pair}: {e}")
                return False

        return await asyncio.gather(*[apply_on_(stream) for stream in self._streams.values()])

    async def _open_connection(self, stream: StreamDataSource) -> bool:
        """Initialize all the streams, subscribe to heartbeats channels"""
        if stream.state[0] == StreamState.OPENED:
            return True

        await stream.open_connection()
        if stream.state[0] != StreamState.OPENED:
            self.logger().warning(f"Stream {stream.channel}:{stream.pair} failed to open.")
            await stream.close_connection()
            return False
        return True

    async def _close_connection(self, stream: StreamDataSource) -> bool:
        """Initialize all the streams, subscribe to heartbeats channels"""
        if stream.state[0] == StreamState.CLOSED:
            return True

        await stream.close_connection()
        if stream.state[0] != StreamState.CLOSED:
            self.logger().warning(f"Stream {stream.channel}:{stream.pair} failed to close.")
            await stream.close_connection()
            return False
        return True

    async def _subscribe(self, stream: StreamDataSource) -> bool:
        """Subscribe to a stream"""
        if stream.state[0] == StreamState.SUBSCRIBED:
            return True

        await stream.subscribe()
        if stream.state[0] != StreamState.SUBSCRIBED:
            self.logger().warning(f"Stream {stream.channel}:{stream.pair} failed to subscribe.")
            await stream.close_connection()
            return False
        return True

    async def _start_task(self, stream: StreamDataSource) -> bool:
        """Subscribe to a stream"""
        if stream.state[1] == TaskState.STARTED:
            return True

        await stream.start_task()
        if stream.state[1] != TaskState.STARTED:
            self.logger().warning(f"Stream {stream.channel}:{stream.pair} failed to start the task.")
            return False
        return True

    async def _stop_task(self, stream: StreamDataSource) -> bool:
        """Stop the task for a stream"""
        if stream.state[1] == TaskState.STOPPED:
            return True

        await stream.stop_task()
        if stream.state[1] != TaskState.STOPPED:
            self.logger().warning(f"Stream {stream.channel}:{stream.pair} failed to stop the task.")
            return False
        return True

    async def _unsubscribe(self, stream: StreamDataSource) -> bool:
        """Unsubscribe to all the streams"""
        if stream.state[0] == StreamState.UNSUBSCRIBED:
            return True

        await stream.unsubscribe()
        if stream.state[0] != StreamState.UNSUBSCRIBED:
            self.logger().warning(f"Stream {stream.channel}:{stream.pair} failed to unsubscribe.")
            await stream.close_connection()
            return False
        return True
