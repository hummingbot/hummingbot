import asyncio
import functools
import logging
from collections import defaultdict
from typing import Any, AsyncGenerator, Callable, Coroutine, Dict, List, Tuple, Type, TypeVar

from hummingbot.logger import HummingbotLogger
from hummingbot.logger.indenting_logger import indented_debug_decorator

from ..connecting_functions.call_or_await import CallOrAwait
from ..connecting_functions.exception_log_manager import log_exception
from ..fittings.pipe_pipe_fitting import PipePipeFitting
from ..fittings.pipes_pipe_fitting import PipesPipeFitting
from ..pipe.protocols import PipeGetPtl
from ..stream_data_source.protocols import WSAssistantPtl
from ..stream_data_source.stream_data_source import StreamDataSource, StreamState, SubscriptionBuilderT
from ..task_manager import TaskState
from .helper_functions import sequence_verifier

T = TypeVar("T")

CollectorT: Type = PipesPipeFitting[Dict[str, Any], T]


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

    @indented_debug_decorator(msg="MultiStream", bullet="|")
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

        #        def create_stream_data_sources() -> Generator[StreamDataSource, None, None]:
        #            for c in channels:
        #                for p in pairs:
        #                    yield StreamDataSource(
        #                        channel=c,
        #                        pair=p,
        #                        ws_factory=ws_factory,
        #                        ws_url=ws_url,
        #                        pair_to_symbol=pair_to_symbol,
        #                        subscription_builder=subscription_builder,
        #                        heartbeat_channel=heartbeat_channel,
        #                    )
        #
        #        def create_pipe_blocks(stream_data_source):
        #            cp = self._stream_key(channel=stream_data_source.channel, pair=stream_data_source.pair)
        #            yield PipePipeFitting[Dict[str, Any], Dict[str, Any]](
        #                stream_data_source.destination,
        #                functools.partial(
        #                    sequence_verifier,
        #                    sequence_reader=sequence_reader,
        #                    sequences=self._sequences,
        #                    key=cp,
        #                    logger=self.logger()
        #                )
        #            )
        #            for t in transformers:
        #                yield PipePipeFitting[Dict[str, Any], Dict[str, Any]](
        #                    self._transformers[cp][-1].destination,
        #                    t
        #                )

        self._streams: Dict[str, StreamDataSource] = {}
        self._transformers: Dict[str, List[PipePipeFitting]] = {}
        self._sequences: defaultdict[str, int] = defaultdict(int)
        self._stream_access_lock: asyncio.Lock = asyncio.Lock()

        #        self._streams = {
        #            self._stream_key(channel=stream_data_source.channel, pair=stream_data_source.pair): stream_data_source
        #            for stream_data_source in create_stream_data_sources()}
        #
        #        self._transformers = {
        #            channel_pair: list(create_pipe_blocks(stream_data_source))
        #            for channel_pair, stream_data_source in self._streams.items()}

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

                # Create the PipePipeFittings that transform the messages
                self._transformers[channel_pair]: List[PipePipeFitting] = []

                # Create the callable to pass as a handler to the PipePipeFitting
                verify_sequence = functools.partial(
                    sequence_verifier,
                    sequence_reader=sequence_reader,
                    sequences=self._sequences,
                    key=channel_pair,
                    logger=self.logger())

                # Create the PipePipeFittings that verify the sequence number and update it
                self._transformers[channel_pair].append(
                    PipePipeFitting[Dict[str, Any], Dict[str, Any]](
                        self._streams[channel_pair].destination,
                        handler=verify_sequence,
                        logger=self.logger(),
                    ),
                )

                for transformer in transformers:
                    self._transformers[channel_pair].append(
                        PipePipeFitting[Dict[str, Any], Dict[str, Any]](
                            self._transformers[channel_pair][-1].destination,
                            transformer,
                        ))

        self._collector: CollectorT = CollectorT(
            sources=tuple(self._transformers[t][-1].destination for t in self._transformers),
            handler=collector,
        )

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
        return min((self._streams[t].last_recv_time for t in self._streams), default=0)

    #    @indented_debug_decorator(bullet="o")
    #    async def _open_connections(self) -> None:
    #        """Open all the streams"""
    #        self.logger().debug(f"Opening {len(self._streams)} streams")
    #        done: Tuple[bool, ...] = await self._perform_on_all_streams(self._open_connection)
    #        await self._pop_unsuccessful_streams(done)
    #        self.logger().debug(f" '> Opened {len(self._streams)} streams")
    #
    #    async def _close_connections(self) -> None:
    #        """Close all the streams"""
    #        await self._perform_on_all_streams(self._close_connection)

    @indented_debug_decorator(bullet="s")
    async def subscribe(self) -> None:
        """Subscribe to all the streams"""
        self.logger().debug(f"Subscribing {len(self._streams)} streams")
        done: Tuple[bool, ...] = await self._perform_on_all_streams(self._subscribe)
        await self._pop_unsuccessful_streams(done)
        self.logger().debug(f" '> Subscribed {len(self._streams)} streams")

    async def unsubscribe(self) -> None:
        """Unsubscribe to all the streams"""
        await self._perform_on_all_streams(self._unsubscribe)

    async def start_streams(self) -> None:
        """Listen to all the streams and put the messages to the output queue."""
        # Open the streams connection, eliminate the ones that failed
        done: Tuple[bool, ...] = await self._perform_on_all_streams(self._open_connection)
        await self._pop_unsuccessful_streams(done)

        # Streams
        done: Tuple[bool, ...] = await self._perform_on_all_streams(self._start_task)
        await self._pop_unsuccessful_streams(done)

        # Collector
        self._collector.start_all_tasks()
        if not all(self._collector.are_running()):
            self.logger().warning("Collector failed to start all its upstream tasks.")
            await self._pop_unsuccessful_streams(self._collector.are_running())

        # Transformers for each stream in reverse order
        for key in self._streams:
            for transformer in reversed(self._transformers[key]):
                transformer.start_task()
                if not transformer.is_running:
                    self.logger().warning(f"A transformer {transformer} failed to start for stream {key}.")
                    await self._pop_unsuccessful_streams(success_list=(transformer.is_running(),))

    async def stop_streams(self) -> None:
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
                await CallOrAwait(action, (stream,)).call()
                return True
            except Exception as e:
                log_exception(
                    e,
                    self.logger(),
                    "ERROR",
                    f"An error occurred while performing action {action} on stream {stream.channel}:{stream.pair}: {e}")
                # self.logger().error(
                #    f"An error occurred while performing action on stream {stream.channel}:{stream.pair}: {e}")
                return False

        if not isinstance(action, Callable):
            self.logger().warning("The action provided is not callable.")
            return tuple((True for _ in self._streams.values()))

        if action is None:
            self.logger().warning("No action provided to perform on the streams.")
            return tuple((True for _ in self._streams.values()))

        return await asyncio.gather(*[apply_on_(stream) for stream in self._streams.values()])

    @indented_debug_decorator(bullet="c")
    async def _open_connection(self, stream: StreamDataSource) -> bool:
        """Open connection for a stream"""
        if stream.state[0] == StreamState.OPENED:
            return True

        await stream.open_connection()
        if stream.state[0] != StreamState.OPENED:
            self.logger().warning(f"Stream {stream.channel}:{stream.pair} failed to open.{stream.state[0]}")
            await stream.close_connection()
            return False
        return True

    async def _close_connection(self, stream: StreamDataSource) -> bool:
        """Close connection for a stream"""
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
        """Start the task for a stream"""
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
        """Unsubscribe a stream"""
        if stream.state[0] == StreamState.UNSUBSCRIBED:
            return True

        await stream.unsubscribe()
        if stream.state[0] != StreamState.UNSUBSCRIBED:
            self.logger().warning(f"Stream {stream.channel}:{stream.pair} failed to unsubscribe.")
            await stream.close_connection()
            return False
        return True
