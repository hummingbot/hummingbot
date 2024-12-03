import asyncio
from datetime import datetime
from typing import Any, Generator, Protocol

from hummingbot.core.web_assistant.rest_assistant import RESTAssistant

from .candle_data import CandleData
from .constants import INTERVALS
from .protocols import ProtocolForRestOperations, ProtocolMixinRestOperations
from .utils import adjust_start_end_to_interval, merge_sanitized_collections, sanitize_data, yield_candle_data_from_dict


class _ProtocolRestOperationsWithMixin(
    ProtocolForRestOperations,
    ProtocolMixinRestOperations,
    Protocol,
):
    ...


class MixinRestOperations:
    class _SelfMixinRestOperations(
        _ProtocolRestOperationsWithMixin,
        Protocol,
    ):
        def _catsc_parse_rest_candles_data(
                self: ProtocolForRestOperations,
                data: dict[str, Any],
                end_time: int | None = None,
        ) -> Generator[CandleData, None, None]:
            ...

    def _get_rest_candles_params(
            self: _ProtocolRestOperationsWithMixin,
            start_time: int | None = None,
            end_time: int | None = None,
            limit: int | None = None,
    ) -> dict[str, Any]:
        params = {
            "granularity": INTERVALS[self.interval],
            "start": self.ensure_timestamp_in_seconds(start_time) if start_time else None,
        }
        if end_time:
            params["end"] = self.ensure_timestamp_in_seconds(end_time)
        self.logger().debug(f"REST candles params: {params}")
        return params

    async def _catsc_listen_to_fetch(self: _ProtocolRestOperationsWithMixin):
        """
        Repeatedly calls fetch_candles on interval.
        """
        self.logger().debug("_listen_to_fetch() started...")
        candles: tuple[CandleData, ...] = await self._fetch_candles(end_time=int(datetime.now().timestamp()))
        await self._update_deque_set_historical(candles)

        while True:
            try:
                start_time: int = self._get_last_candle_timestamp()
                end_time: int = int(datetime.now().timestamp())
                candles = await self._fetch_candles(end_time=end_time, start_time=start_time)
                await self._update_deque_set_historical(candles)
                await self._sleep(self.get_seconds_from_interval(self.interval))

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(
                    "Unexpected error occurred when listening to public REST candle call. Retrying in 1 "
                    "seconds...",
                )
                await self._sleep(1.0)

    async def _catsc_fill_historical_candles(
            self: _ProtocolRestOperationsWithMixin,
            event: asyncio.Event,
    ):
        """
        This method fills the historical candles in the _candles deque until it reaches the maximum length.
        """
        while not self.ready:
            await event.wait()
            try:
                end_time: int | None = self._get_first_candle_timestamp()
                missing_records: int = self._get_missing_timestamps()
                candles: tuple[CandleData, ...] = await self._fetch_candles(end_time=end_time, limit=missing_records)
                await self._update_deque_set_historical(candles, extend_left=True)
            except asyncio.CancelledError:
                raise
            except ValueError:
                raise
            except Exception as e:
                self.logger().exception(
                    f"Unexpected error occurred when getting historical klines. Retrying in 1 seconds... ({e})",
                )
                await self._sleep(1.0)

    def _catsc_parse_rest_candles_data(
            self: ProtocolForRestOperations,
            data: dict[str, Any],
            end_time: int | None = None,
    ) -> Generator[CandleData, None, None]:
        for candle in yield_candle_data_from_dict(data, self.ensure_timestamp_in_seconds):
            if end_time is None or candle.timestamp < end_time:
                yield candle

    async def _fetch_candles(
            self: _SelfMixinRestOperations,
            start_time: int | None = None,
            end_time: int | None = None,
            limit: int | None = None,
            *,
            _offset: int | None = None,
    ) -> tuple[CandleData, ...]:
        """Fetch all candles between start and end time.

        Makes multiple API calls if needed, respecting both the exchange's
        maximum results per request limit and the candle interval.

        :param start_time: Start timestamp in seconds
        :param end_time: End timestamp in seconds
        :param limit: Maximum number of candles to fetch
        :returns: Tuple of candle data
        :rtype: tuple[CandleData, ...]
        :raises NetworkError: If API calls fail
        """
        rest_assistant: RESTAssistant = await self._api_factory.get_rest_assistant()
        all_candles: list[CandleData] = []

        current_start: int = start_time
        current_end: int = end_time
        candles_offset: int | None = _offset

        request_count: int = 0
        while request_count < 100:
            request_count += 1

            # Reset API query bound to respect
            #   - MAX request limit and adjust
            #   - Start/End times to the interval and the implicit offset=0 for the first batch
            #   - Offset for the subsequent batches
            current_start, current_end = adjust_start_end_to_interval(
                current_end,
                self.interval_in_seconds,
                start_time=current_start,
                limit=self.candles_max_result_per_rest_request,
                offset=candles_offset,
            )

            params: dict[str, Any] = self._get_rest_candles_params(
                start_time=current_start,
                end_time=current_end,
                limit=limit or self.candles_max_result_per_rest_request,
            )

            try:
                response: dict[str, Any] = await rest_assistant.execute_request(
                    url=self.candles_url,
                    throttler_limit_id=self._rest_throttler_limit_id,
                    params=params,
                )
            except Exception as e:
                self.logger().error(f"Error fetching candles: {e}")
                raise

            batch_candles: tuple[CandleData, ...] = tuple(self._catsc_parse_rest_candles_data(response, current_end))

            if not batch_candles:
                break

            # We can only know the offset after the first batch and at least 2 candles
            if len(batch_candles) > 1:
                candles_offset: int = batch_candles[-1].timestamp % self.interval_in_seconds
            self.logger().debug(f"Received {len(batch_candles)} candles from {current_start} to {current_end}")

            # Sanitize the candles: extracts longest valid sequence
            sanitized_batch: tuple[CandleData, ...] = sanitize_data(
                batch_candles,
                self.interval_in_seconds,
                (current_start, current_end),
                self.logger(),
            )

            if not sanitized_batch:
                break

            self.logger().debug(f"Received {len(sanitized_batch)} candles from {current_start} to {current_end}")
            all_candles = merge_sanitized_collections(
                all_candles,
                sanitized_batch,
                self.interval_in_seconds,
            )

            if not all_candles:
                break

            got_start = (
                start_time is None or
                0 <= all_candles[0].timestamp - start_time < self.interval_in_seconds or
                0 <= all_candles[-1].timestamp - start_time < self.interval_in_seconds
            )
            got_end = (0 <= end_time - all_candles[-1].timestamp < self.interval_in_seconds)

            if not got_start:
                current_start = start_time
                current_end = all_candles[0].timestamp - self.interval_in_seconds
                continue

            if not got_end:
                current_start = all_candles[-1].timestamp + self.interval_in_seconds
                current_end = end_time
                continue

            break

        return tuple(all_candles)
