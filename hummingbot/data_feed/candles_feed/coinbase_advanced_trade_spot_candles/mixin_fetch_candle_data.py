from typing import Any, Generator, Protocol

from hummingbot.core.web_assistant.rest_assistant import RESTAssistant

from .candle_data import CandleData
from .protocols import ProtocolForFetchCandleData, ProtocolMixinFetchCandleData
from .utils import (
    adjust_start_end_to_interval,
    merge_sanitized_collections,
    sanitize_data,
    update_deque_from_sequence,
    yield_candle_data_from_dict,
)


class _ProtocolFetchCandleDataWithMixin(
    ProtocolForFetchCandleData,
    ProtocolMixinFetchCandleData,
    Protocol,
):
    ...


class MixinFetchCandleData:
    class _SelfMixinFetchCandleData(
        _ProtocolFetchCandleDataWithMixin,
        Protocol,
    ):
        def _catsc_parse_rest_candles_data(
                self: ProtocolForFetchCandleData,
                data: dict[str, Any],
                end_time: int | None = None,
        ) -> Generator[CandleData, None, None]:
            ...

    def _catsc_parse_rest_candles_data(
            self: ProtocolForFetchCandleData,
            data: dict[str, Any],
            end_time: int | None = None,
    ) -> Generator[CandleData, None, None]:
        for candle in yield_candle_data_from_dict(data, self.ensure_timestamp_in_seconds):
            if end_time is None or candle.timestamp < end_time:
                yield candle

    async def _fetch_candles(
            self: _SelfMixinFetchCandleData,
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

    async def _initialize_deque_from_sequence(
            self: _ProtocolFetchCandleDataWithMixin,
            candles: tuple[CandleData, ...],
    ):
        call_history = len(self._candles) == 0
        update_deque_from_sequence(self._candles, candles)
        if call_history:
            self._ws_candle_available.set()
            await self._catsc_fill_historical_candles()
