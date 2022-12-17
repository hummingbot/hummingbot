import asyncio
import logging
import sys
from collections import deque
from contextlib import AsyncExitStack
from decimal import Decimal
from typing import Any, AsyncGenerator, AsyncIterable, Deque, Dict, List, Optional

from asyncstdlib import list as list_async
from tenacity import AsyncRetrying, before_sleep_log, retry_if_exception_type

from juno import time
from juno.connectors import Connector
from juno.itertools import generate_missing_spans
from juno.models import Candle, ConnectorException, Trade
from juno.storages import Storage
from juno.tenacity import stop_after_attempt_with_reset, wait_none_then_exponential

_log = logging.getLogger(__name__)

_CANDLE_KEY = Candle.__name__.lower()
_TRADE_KEY = Trade.__name__.lower()

_STORAGE_BATCH_SIZE = 1000


class Chandler:
    """
    A component responsible for providing candlestick info. Features:

    - Seamlessly merge together historical and future candles.
    - Construct candles from trades.
    - Store candles locally for quicker retrieval and to minimize communication with an exchange.
    """

    def __init__(
        self,
        storage: Storage,
        connectors: Dict[str, Connector],
    ) -> None:
        self._storage = storage
        self._connectors = connectors

    async def stream_candles(
        self,
        connector_name: str,
        trading_pair: str,
        interval: int,
        start: int,
        end: int = time.MAX_TIME,
    ) -> AsyncIterable[Candle]:
        """
        Tries to stream candles for the specified range from local storage. If candles don't exist, streams them from
        an exchange and stores to local storage.
        """
        start = time.floor_timestamp(start, interval)
        end = time.floor_timestamp(end, interval)

        if end <= start:
            return

        shard = _key(connector_name, trading_pair, interval)
        candle_msg = f"{connector_name} {trading_pair} {time.format_interval(interval)} candle(s)"

        _log.info(f"Checking for existing {candle_msg} in local storage.")
        existing_spans = await list_async(
            self._storage.stream_time_series_spans(
                shard=shard,
                key=_CANDLE_KEY,
                start=start,
                end=end,
            )
        )
        missing_spans = list(generate_missing_spans(start, end, existing_spans))

        spans = [(a, b, True) for a, b in existing_spans] + [(a, b, False) for a, b in missing_spans]
        spans.sort(key=lambda s: s[0])

        last_candle: Optional[Candle] = None
        for span_start, span_end, exist_locally in spans:
            period_msg = f"{time.format_span(span_start, span_end)}"
            if exist_locally:
                _log.info(f"Local {candle_msg} exist between {period_msg}.")
                stream = self._storage.stream_time_series(
                    shard=shard,
                    key=_CANDLE_KEY,
                    type_=Candle,
                    start=span_start,
                    end=span_end,
                )
            else:
                _log.info(f"Missing {candle_msg} between {period_msg}.")
                stream = self._stream_and_store_exchange_candles(
                    connector_name=connector_name,
                    trading_pair=trading_pair,
                    interval=interval,
                    start=span_start,
                    end=span_end,
                )
            try:
                async for candle in stream:
                    if last_candle:
                        time_diff = candle.time - last_candle.time
                        if time_diff >= interval * 2:
                            num_missed = time_diff // interval - 1
                            _log.warning(
                                f"Missed {num_missed} {candle_msg}; last closed candle {last_candle}. current candle "
                                f"{candle}."
                            )
                    else:
                        num_missed = (candle.time - start) // interval
                        if num_missed > 0:
                            _log.warning(
                                f"Missed {num_missed} {candle_msg} from the start {time.format_timestamp(start)}; "
                                f"current candle {candle}."
                            )

                    yield candle
                    last_candle = candle
            finally:
                if isinstance(stream, AsyncGenerator):
                    await stream.aclose()

        if last_candle:
            time_diff = end - last_candle.time
            if time_diff >= interval * 2:
                num_missed = time_diff // interval - 1
                _log.warning(
                    f"Missed {num_missed} {candle_msg} from the end {time.format_timestamp(end)}; current candle "
                    f"{last_candle}."
                )
        else:
            _log.warning(f"Missed all {candle_msg} between {time.format_span(start, end)}.")

    async def _stream_and_store_exchange_candles(
        self,
        connector_name: str,
        trading_pair: str,
        interval: int,
        start: int,
        end: int,
    ) -> AsyncGenerator[Candle, None]:
        shard = _key(connector_name, trading_pair, interval)
        # Note that we need to use a context manager based retrying because retry decorators do not work with async
        # generator functions.
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt_with_reset(8, 300),
            wait=wait_none_then_exponential(),
            retry=retry_if_exception_type(ConnectorException),
            before_sleep=before_sleep_log(_log, logging.WARNING),
        ):
            with attempt:
                # We use a swap batch in order to swap the batch right before storing. With a single batch, it may
                # happen that our program gets cancelled at an `await` point before we're able to clear the batch. This
                # can cause same data to be stored twice, raising an integrity error.
                batch = []
                swap_batch: List[Candle] = []
                current = time.floor_timestamp(time.now(), interval)

                try:
                    stream = self._stream_exchange_candles(
                        connector_name=connector_name,
                        trading_pair=trading_pair,
                        interval=interval,
                        start=start,
                        end=end,
                        current=current,
                    )
                    try:
                        async for candle in stream:
                            batch.append(candle)
                            if len(batch) == _STORAGE_BATCH_SIZE:
                                del swap_batch[:]
                                batch_start = start
                                batch_end = batch[-1].time + interval
                                start = batch_end
                                swap_batch, batch = batch, swap_batch
                                await self._storage.store_time_series_and_span(
                                    shard=shard,
                                    key=_CANDLE_KEY,
                                    items=swap_batch,
                                    start=batch_start,
                                    end=batch_end,
                                )
                            yield candle
                    finally:
                        await stream.aclose()
                except (asyncio.CancelledError, ConnectorException):
                    if len(batch) > 0:
                        batch_start = start
                        batch_end = batch[-1].time + interval
                        start = batch_end
                        await self._storage.store_time_series_and_span(
                            shard=shard,
                            key=_CANDLE_KEY,
                            items=batch,
                            start=batch_start,
                            end=batch_end,
                        )
                    raise
                else:
                    current = time.floor_timestamp(time.now(), interval)
                    await self._storage.store_time_series_and_span(
                        shard=shard,
                        key=_CANDLE_KEY,
                        items=batch,
                        start=start,
                        end=min(current, end),
                    )

    async def _stream_exchange_candles(
        self,
        connector_name: str,
        trading_pair: str,
        interval: int,
        start: int,
        end: int,
        current: int,
    ) -> AsyncGenerator[Candle, None]:
        exchange_instance = self._connectors[connector_name]
        intervals = exchange_instance.list_candle_intervals()
        is_candle_interval_supported = interval in intervals

        async def inner(stream: Optional[AsyncIterable[Candle]]) -> AsyncGenerator[Candle, None]:
            if start < current:  # Historical.
                historical_end = min(end, current)
                if exchange_instance.can_stream_historical_candles and is_candle_interval_supported:
                    historical_stream = exchange_instance.stream_historical_candles(
                        trading_pair=trading_pair,
                        interval=interval,
                        start=start,
                        end=historical_end,
                    )
                else:
                    historical_stream = self._stream_construct_candles(
                        connector_name, trading_pair, interval, start, historical_end
                    )
                try:
                    async for candle in historical_stream:
                        yield candle
                finally:
                    if isinstance(historical_stream, AsyncGenerator):
                        await historical_stream.aclose()
            if stream:  # Future.
                try:
                    async for candle in stream:
                        # If we start the websocket connection while candle is closing, we can also receive the same
                        # candle from here that we already got from historical. Ignore such candles.
                        if candle.time < current:
                            continue

                        if candle.time >= end:
                            break

                        yield candle

                        if candle.time == end - interval:
                            break
                finally:
                    if isinstance(stream, AsyncGenerator):
                        await stream.aclose()

        async with AsyncExitStack() as stack:
            stream = None
            if end > current:
                if exchange_instance.can_stream_candles and is_candle_interval_supported:
                    stream = await stack.enter_async_context(
                        exchange_instance.connect_stream_candles(trading_pair, interval)
                    )
                else:
                    stream = self._stream_construct_candles(connector_name, trading_pair, interval, current, end)

            last_candle_time = -1
            outer_stream = inner(stream)
            try:
                async for candle in outer_stream:
                    if interval < time.WEEK_MS and (candle.time % interval) != 0:
                        adjusted_time = time.floor_timestamp(candle.time, interval)
                        _log.warning(
                            f"Candle with bad time {candle} for interval {time.format_interval(interval)}; trying to "
                            f"adjust back in time to {time.format_timestamp(adjusted_time)} or skip if volume zero."
                        )
                        if last_candle_time == adjusted_time:
                            if candle.volume > 0:
                                raise RuntimeError(
                                    f"Received {trading_pair} {time.format_interval(interval)} candle {candle} with a "
                                    "time that does not fall into the interval. Cannot adjust back in time because "
                                    f"time coincides with last candle time {time.format_timestamp(last_candle_time)}. "
                                    "Cannot skip because volume not zero."
                                )
                            else:
                                continue
                        candle = Candle(
                            time=adjusted_time,
                            open=candle.open,
                            high=candle.high,
                            low=candle.low,
                            close=candle.close,
                            volume=candle.volume,
                        )

                    yield candle
                    last_candle_time = candle.time
            finally:
                await outer_stream.aclose()

    async def _stream_construct_candles(
        self,
        connector_name: str,
        trading_pair: str,
        interval: int,
        start: int,
        end: int,
    ) -> AsyncGenerator[Candle, None]:
        _log.info(f"Constructing {connector_name} {trading_pair} {interval} candles from trades.")

        current = start
        next_ = current + interval
        open_ = Decimal("0.0")
        high = Decimal("0.0")
        low = Decimal(f"{sys.maxsize}.0")
        close = Decimal("0.0")
        volume = Decimal("0.0")
        is_first = True
        async for trade in self.stream_trades(
            connector_name=connector_name,
            trading_pair=trading_pair,
            start=start,
            end=end,
        ):
            if trade.time >= next_:
                assert not is_first
                yield Candle(
                    time=current,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
                current = next_
                next_ = current + interval
                open_ = Decimal("0.0")
                high = Decimal("0.0")
                low = Decimal(f"{sys.maxsize}.0")
                close = Decimal("0.0")
                volume = Decimal("0.0")
                is_first = True

            if is_first:
                open_ = trade.price
                is_first = False
            high = max(high, trade.price)
            low = min(low, trade.price)
            close = trade.price
            volume += trade.size

        if not is_first:
            yield Candle(
                time=current,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
            )

    # Trades

    async def stream_trades(
        self,
        connector_name: str,
        trading_pair: str,
        start: int,
        end: int,
    ) -> AsyncIterable[Trade]:
        """
        Tries to stream trades for the specified range from local storage. If trades don't exist, streams them from an
        exchange and stores to local storage.
        """
        shard = _key(connector_name, trading_pair)
        trade_msg = f"{connector_name} {trading_pair} trades"

        _log.info(f"Checking for existing {trade_msg} in local storage.")
        existing_spans = await list_async(
            self._storage.stream_time_series_spans(
                shard=shard,
                key=_TRADE_KEY,
                start=start,
                end=end,
            )
        )
        missing_spans = list(generate_missing_spans(start, end, existing_spans))

        spans = [(a, b, True) for a, b in existing_spans] + [(a, b, False) for a, b in missing_spans]
        spans.sort(key=lambda s: s[0])

        for span_start, span_end, exist_locally in spans:
            period_msg = f"{time.format_span(span_start, span_end)}"
            if exist_locally:
                _log.info(f"Local {trade_msg} exist between {period_msg}.")
                stream = self._storage.stream_time_series(
                    shard=shard,
                    key=_TRADE_KEY,
                    type_=Trade,
                    start=span_start,
                    end=span_end,
                )
            else:
                _log.info(f"Missing {trade_msg} between {period_msg}.")
                stream = self._stream_and_store_exchange_trades(connector_name, trading_pair, span_start, span_end)
            async for trade in stream:
                yield trade

    async def _stream_and_store_exchange_trades(
        self,
        connector_name: str,
        trading_pair: str,
        start: int,
        end: int,
    ) -> AsyncIterable[Trade]:
        shard = _key(connector_name, trading_pair)
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt_with_reset(8, 300),
            wait=wait_none_then_exponential(),
            retry=retry_if_exception_type(ConnectorException),
            before_sleep=before_sleep_log(_log, logging.WARNING),
        ):
            with attempt:
                # We use a swap batch in order to swap the batch right before storing. With a single batch, it may
                # happen that our program gets cancelled at an `await` point before we're able to clear the batch. This
                # can cause same data to be stored twice, raising an integrity error. We also use swap to store trades
                # from previous batch in case we get multiple trades with a same time at the edge of the batch.
                batch = []
                swap_batch: List[Trade] = []
                current = time.now()

                try:
                    async for trade in self._stream_exchange_trades(
                        connector_name=connector_name, trading_pair=trading_pair, start=start, end=end, current=current
                    ):
                        batch.append(trade)
                        # We go over limit with +1 because we never take the last trade of the batch because multiple
                        # trades can happen at the same time. We need our time span to be correct.
                        if len(batch) == _STORAGE_BATCH_SIZE + 1:
                            del swap_batch[:]

                            last = batch[-1]
                            for i in range(len(batch) - 1, -1, -1):
                                if batch[i].time != last.time:
                                    break
                                # Note that we are inserting in front.
                                swap_batch.insert(0, batch[i])
                                del batch[i]

                            batch_start = start
                            batch_end = batch[-1].time + 1
                            swap_batch, batch = batch, swap_batch
                            start = batch_end
                            await self._storage.store_time_series_and_span(
                                shard=shard,
                                key=_TRADE_KEY,
                                items=swap_batch,
                                start=batch_start,
                                end=batch_end,
                            )
                        yield trade
                except (asyncio.CancelledError, ConnectorException):
                    if len(batch) > 0:
                        batch_start = start
                        batch_end = batch[-1].time + 1
                        start = batch_end
                        await self._storage.store_time_series_and_span(
                            shard=shard,
                            key=_TRADE_KEY,
                            items=batch,
                            start=batch_start,
                            end=batch_end,
                        )
                    raise
                else:
                    current = time.now()
                    await self._storage.store_time_series_and_span(
                        shard=shard,
                        key=_TRADE_KEY,
                        items=batch,
                        start=start,
                        end=min(current, end),
                    )

    async def _stream_exchange_trades(
        self,
        connector_name: str,
        trading_pair: str,
        start: int,
        end: int,
        current: int,
    ) -> AsyncIterable[Trade]:
        connector = self._connectors[connector_name]

        async def inner(stream: Optional[AsyncIterable[Trade]]) -> AsyncIterable[Trade]:
            last_trade_ids: Deque[int] = deque(maxlen=20)
            if start < current:  # Historical.
                async for trade in connector.stream_historical_trades(trading_pair, start, min(end, current)):
                    if trade.id > 0:
                        last_trade_ids.append(trade.id)
                    yield trade
            if stream:  # Future.
                skipping_existing = True
                async for trade in stream:
                    # TODO: Can we improve? We may potentially wait for a long time before a trade
                    # past the end time occurs.
                    if trade.time >= end:
                        break

                    # Skip if trade was already retrieved from historical. If we start the websocket connection during
                    # a trade, we can also receive the same trade from here that we already got from historical.
                    if skipping_existing and (trade.id > 0 and trade.id in last_trade_ids or trade.time < current):
                        continue
                    else:
                        skipping_existing = False

                    yield trade

        if end > current:
            async with connector.connect_stream_trades(trading_pair) as stream:
                async for trade in inner(stream):
                    yield trade
        else:
            async for trade in inner(None):
                yield trade


def _key(*items: Any) -> str:
    return "_".join(map(str.lower, map(str, items)))
