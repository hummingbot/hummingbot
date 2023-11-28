import asyncio
import logging
from collections import defaultdict
from functools import partial
from typing import Any, Awaitable, Callable, Coroutine, Dict, List, Tuple

from hummingbot.logger import HummingbotLogger

from ..connecting_functions.exception_log_manager import log_if_possible
from ..fittings.pipe_pipe_fitting import PipePipeFitting
from ..multi_stream_data_source.helper_functions import sequence_verifier
from ..pipe.protocols import PipeGetPtl
from ..stream_data_source.protocols import WSAssistantPtl, WSResponsePtl
from ..stream_data_source.stream_data_source import StreamDataSource, StreamState, SubscriptionBuilderT
from ..task_manager import TaskState


async def _open_connection(stream: StreamDataSource, logger: logging.Logger | None) -> bool:
    """Open connection for a stream"""
    if stream.state[0] != StreamState.CLOSED:
        return True

    await stream.open_connection()
    if stream.state[0] != StreamState.OPENED:
        log_if_possible(logger, "WARNING", f"Stream {stream.channel}:{','.join(stream.pairs)} failed to open.")
        return False
    return True


async def _close_connection(stream: StreamDataSource, logger: logging.Logger | None) -> bool:
    """Close connection for a stream"""
    if stream.state[0] == StreamState.CLOSED:
        return True

    if stream.state[0] == StreamState.SUBSCRIBED:
        await stream.unsubscribe()

    await stream.close_connection()
    if stream.state[0] != StreamState.CLOSED:
        log_if_possible(logger, "WARNING", f"Stream {stream.channel}:{','.join(stream.pairs)} failed to close.")
        return False
    return True


async def _subscribe(stream: StreamDataSource, logger: logging.Logger | None) -> bool:
    """Subscribe to a stream"""
    if stream.state[0] == StreamState.SUBSCRIBED:
        return True

    if stream.state[1] == TaskState.STOPPED:
        log_if_possible(
            logger,
            "WARNING",
            f"Stream {stream.channel}:{','.join(stream.pairs)} subscribing while its task is STOPPED.")

    await stream.subscribe()
    if stream.state[0] != StreamState.SUBSCRIBED:
        log_if_possible(logger, "WARNING", f"Stream {stream.channel}:{','.join(stream.pairs)} failed to subscribe.")
        return False
    return True


async def _unsubscribe(stream: StreamDataSource, logger: logging.Logger | None) -> bool:
    """Unsubscribe a stream"""
    if stream.state[0] == StreamState.UNSUBSCRIBED:
        return True

    await stream.unsubscribe()
    if stream.state[0] != StreamState.UNSUBSCRIBED:
        log_if_possible(logger, "WARNING", f"Stream {stream.channel}:{','.join(stream.pairs)} failed to unsubscribe.")
        return False
    return True


async def _start_task(stream: StreamDataSource, logger: logging.Logger | None) -> bool:
    """Start the task for a stream"""
    if stream.state[1] == TaskState.STARTED:
        return True

    await stream.start_task()
    if stream.state[1] != TaskState.STARTED:
        log_if_possible(logger, "WARNING", f"Stream {stream.channel}:{','.join(stream.pairs)} failed to start the task.")
        return False
    return True


async def _stop_task(stream: StreamDataSource, logger: logging.Logger | None) -> bool:
    """Stop the task for a stream"""
    if stream.state[1] == TaskState.STOPPED:
        return True

    if stream.state[0] == StreamState.SUBSCRIBED:
        log_if_possible(
            logger,
            "WARNING",
            f"Stream {stream.channel}:{','.join(stream.pairs)} stopping its task while SUBSCRIBED.")

    await stream.stop_task()
    if stream.state[1] != TaskState.STOPPED:
        log_if_possible(
            logger,
            "WARNING",
            f"Stream {stream.channel}:{','.join(stream.pairs)} failed to stop the task.")
        return False
    return True


def _stop_task_nowait(stream: StreamDataSource, logger: logging.Logger | None) -> bool:
    """Stop the task for a stream"""
    if stream.state[1] == TaskState.STOPPED:
        return True

    if stream.state[0] == StreamState.SUBSCRIBED:
        log_if_possible(
            logger,
            "WARNING",
            f"Stream {stream.channel}:{','.join(stream.pairs)} stopping its task while SUBSCRIBED.")

    stream.stop_task_nowait()
    if stream.state[1] != TaskState.STOPPED:
        log_if_possible(
            logger,
            "WARNING",
            f"Stream {stream.channel}:{','.join(stream.pairs)} failed to stop the task.")
        return False
    return True


class SingleStreamDataSource:
    """
    Single StreamDataSource implementation.
    """
    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger | logging.Logger:
        if cls._logger is None:
            name: str = HummingbotLogger.logger_name_for_class(cls)
            cls._logger = logging.getLogger(name)
        return cls._logger

    __slots__ = (
        "_stream",
        "_sequence",
        "_transformers",
        "_ws_factory",
        "_pair_to_symbol",
        "_last_recv_time",
        "_stream_state",
        "_stream_access_lock",
        # Methods
        "open_connection",
        "close_connection",
        "subscribe",
        "unsubscribe",
        "start_task",
        "stop_task",
        "stop_task_nowait",
    )

    def __init__(self,
                 *,
                 channel: str,
                 pairs: Tuple[str, ...],
                 ws_factory: Callable[[], Coroutine[Any, Any, WSAssistantPtl]],
                 ws_url: str,
                 pair_to_symbol: Callable[[str], Awaitable[str]],
                 subscription_builder: SubscriptionBuilderT,
                 sequence_reader: Callable[[Dict[str, Any]], int],
                 transformers: List[Callable],
                 on_failed_subscription: Callable[[WSResponsePtl], WSResponsePtl] | None = None,
                 heartbeat_channel: str | None = None) -> None:
        """
        Initialize the CoinbaseAdvancedTradeAPIUserStreamDataSource.

        :param Tuple channel: Channel to subscribe to.
        :param Tuple pairs: symbol to subscribe to.
        :param ws_factory: The method for creating the WSAssistant.
        :param pair_to_symbol: Async function to convert the pair to symbol.
        """

        self._transformers: List[PipePipeFitting] = []
        self._sequence: defaultdict[str, int] = defaultdict(int)
        self._stream_access_lock: asyncio.Lock = asyncio.Lock()

        channel_pair = ",".join(pairs)

        # Create the StreamDataSource, websocket to queue
        self._stream = StreamDataSource(
            channel=channel,
            pairs=pairs,
            ws_factory=ws_factory,
            ws_url=ws_url,
            pair_to_symbol=pair_to_symbol,
            subscription_builder=subscription_builder,
            on_failed_subscription=on_failed_subscription,
            heartbeat_channel=heartbeat_channel,
        )

        # Create the sequence verifier
        verify_sequence = partial(
            sequence_verifier,
            sequence_reader=sequence_reader,
            sequences=self._sequence,
            key=channel_pair,
            logger=self.logger())

        # Create the PipePipeFittings that verify the sequence number and update it
        self._transformers = [
            PipePipeFitting[Dict[str, Any], Dict[str, Any]](
                self._stream.destination,
                handler=verify_sequence,
                logger=self.logger(),
            ),
        ]

        self._transformers.extend(
            PipePipeFitting[Dict[str, Any], Dict[str, Any]](
                self._transformers[-1].destination,
                transformer,
            )
            for transformer in transformers
        )

        # Create the methods for the stream
        MethT = Callable[[], Coroutine[None, None, bool]]
        self.open_connection: MethT = partial(_open_connection, self._stream, logger=self.logger())
        self.close_connection: MethT = partial(_close_connection, self._stream, logger=self.logger())
        self.subscribe: MethT = partial(_subscribe, self._stream, logger=self.logger())
        self.unsubscribe: MethT = partial(_unsubscribe, self._stream, logger=self.logger())
        self.start_task: MethT = partial(_start_task, self._stream, logger=self.logger())
        self.stop_task: MethT = partial(_stop_task, self._stream, logger=self.logger())

        self.stop_task_nowait: Callable[[], bool] = partial(_stop_task_nowait, self._stream, logger=self.logger())

    @property
    def queue(self) -> PipeGetPtl[Dict[str, Any]]:
        """Returns the output queue"""
        return self._transformers[-1].destination

    @property
    def state(self) -> Tuple[StreamState, TaskState]:
        """Returns the states of all the streams"""
        return self._stream.state

    @property
    def last_recv_time(self) -> float:
        """Returns the time of the last received message"""
        return self._stream.last_recv_time

    async def start_stream(self) -> None:
        """Starts the stream"""
        # Transformers for each stream in reverse order
        self.logger().debug("Starting transformers for the stream")
        for transformer in reversed(self._transformers):
            await transformer.start_task()
            if not transformer.is_running:
                self.logger().error("A transformer task failed to start for the stream.")
                raise RuntimeError("A transformer task failed to start for the stream.")

        # Open the streams connection, eliminate the ones that failed
        self.logger().debug("Opening the connection")
        await self.open_connection()

        # Streams
        self.logger().debug("Starting stream task")
        await self.start_task()

    async def stop_stream(self) -> None:
        """Stops the stream."""
        await self.unsubscribe()
        await self.close_connection()
        for transformer in self._transformers:
            await transformer.stop_task()

        await self.stop_task()
