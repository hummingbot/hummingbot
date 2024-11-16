import logging
from collections import deque
from datetime import datetime
from typing import Any, Callable, Generator, Sequence, TypeAlias

import numpy as np
from numpy._typing import NDArray

from hummingbot.data_feed.candles_feed.coinbase_advanced_trade_spot_candles.candle_data import CandleData


def _t_to_i(
        timestamp: int,
        interval_in_s: int,
        *,
        offset: int | None = None,
        _next: bool = False,
) -> int:
    """Aligns a timestamp to the start of the interval accounting for the offset.
    WHen offset is None, returns the unmodified timestamp.

    :param timestamp: Timestamp to adjust
    :param interval_in_s: Interval in seconds
    :param _next: If True, adjust to the next interval
    :param offset: Offset in seconds
    :returns: Adjusted timestamp
    :rtype: int
    """
    if _next:
        timestamp += interval_in_s

    if offset is None:
        return timestamp

    offset_ts: int = timestamp - offset
    return timestamp - delta if (delta := offset_ts % interval_in_s) else timestamp


def adjust_start_end_to_interval(
        end_time: int | None,
        interval_in_s: int,
        *,
        start_time: int | None = None,
        limit: int | None = None,
        offset: int | None = None,
) -> tuple[int | None, int | None]:
    """Adjusts the start and end times to the nearest interval.

    :param start_time: Start timestamp
    :param end_time: End timestamp
    :param interval_in_s: Interval in seconds
    :param limit: Maximum number of intervals to look back
    :param offset: Server alignment in seconds
    :returns: Adjusted start and end times
    :rtype: tuple[int | None, int | None]
    """
    raw_end = end_time or int(datetime.now().timestamp())
    adjusted_end = _t_to_i(raw_end, interval_in_s, offset=offset)
    adjusted_start = 0

    # Set the offset for the start time
    if offset is None:
        offset = adjusted_end % interval_in_s

    if start_time is not None:
        aligned_start = _t_to_i(start_time, interval_in_s, offset=offset)
        adjusted_start = min(aligned_start, adjusted_end)

    if limit is None:
        return adjusted_start, adjusted_end

    adjusted_start = max(adjusted_start, adjusted_end - interval_in_s * (limit - 1))

    return adjusted_start, adjusted_end


def sanitize_data(
        candles: tuple[CandleData, ...],
        interval_in_s: int,
        inclusive_bounds: tuple[int | None, int | None] = (None, None),
        logger: logging.Logger | None = None,
) -> tuple[CandleData, ...]:
    """Sanitizes the data by finding the largest sequence of valid intervals.

    :param candles: Tuple of candle data to sanitize
    :param interval_in_s: Expected interval between candles in seconds
    :param inclusive_bounds: (start_time, end_time) tuple for trimming, (None, None)
         means no bounds
    :returns: Sanitized and trimmed candle data
    :rtype: tuple[CandleData, ...]
    """

    if not candles:
        return ()

    sorted_candles: list[CandleData] = sorted(candles, key=lambda x: x.timestamp, reverse=False)

    start_bound: int | None = inclusive_bounds[0]
    end_bound: int | None = inclusive_bounds[1]
    if start_bound is not None and start_bound > 0:
        sorted_candles = [c for c in sorted_candles if c.timestamp >= start_bound]
    if end_bound is not None and end_bound > 0:
        sorted_candles = [c for c in sorted_candles if c.timestamp <= end_bound]

    #
    if not sorted_candles:
        return ()

    if len(sorted_candles) == 1:
        return tuple(sorted_candles)

    # Find all valid sequences
    timestamps = [c.timestamp for c in sorted_candles]
    best_sequence = []
    current_sequence = []
    max_length = 0

    if logger:
        logger.debug(f"Sanitizing {len(sorted_candles)} candles with interval {interval_in_s}")

    for i in range(len(timestamps) - 1):
        if not current_sequence:
            current_sequence = [i]

        if timestamps[i + 1] - timestamps[i] == interval_in_s:
            current_sequence.append(i + 1)
        else:
            # Sequence broken, check if it's at least as long as the best
            if len(current_sequence) >= max_length:
                # Always update for equal length, getting most recent sequence
                best_sequence = current_sequence
                max_length = len(current_sequence)
            current_sequence = []

    # Check the last sequence
    if len(current_sequence) >= max_length:  # Update even for equal length
        best_sequence = current_sequence

    # If no valid sequences found (more than 2 TS matching the interval
    if len(best_sequence) == 1:
        return (sorted_candles[-1],)

    # Return the selected sequence
    start_idx = best_sequence[0]
    end_idx = best_sequence[-1] + 1
    return tuple(sorted_candles[start_idx:end_idx])


def merge_sanitized_collections(
        existing_candles: list[CandleData],
        new_candles: tuple[CandleData, ...],
        interval_in_s: int,
) -> list[CandleData]:
    """Merges new sanitized candles into existing sanitized collection.

    The existing collection is assumed to be a valid sequence from the end.
    New candles are only merged if they form a continuous sequence with
    the existing collection.

    :param existing_candles: Existing sanitized candles sequence
    :param new_candles: New sanitized candles to potentially merge
    :param interval_in_s: Expected interval between candles
    :returns: Merged collection maintaining continuous sequence from end
    """
    if not existing_candles:
        return list(new_candles)
    if not new_candles:
        return existing_candles

    # Check if new candles can be pre/post -pended
    if existing_candles[0].timestamp - new_candles[-1].timestamp == interval_in_s:
        return list(new_candles) + existing_candles
    if new_candles[0].timestamp - existing_candles[-1].timestamp == interval_in_s:
        return existing_candles + list(new_candles)

    return existing_candles


CandleArray: TypeAlias = NDArray[np.float64]


def update_deque_from_sequence(
        out_deque: deque[CandleArray],
        in_sequence: Sequence[Sequence[float] | CandleData],
        extend_left: bool = False,
):
    """ Updates a deque with new data from a sequence.

    :param out_deque: The deque to update
    :param in_sequence: The sequence to update from
    :param extend_left: If True, extend the deque to the left
    """
    if not in_sequence:
        return

    arrays = [
        np.array(x.to_float_array() if isinstance(x, CandleData) else x, dtype=np.float64)
        for x in in_sequence
    ]

    if len(out_deque) == 0:
        if len(arrays) > out_deque.maxlen:
            arrays = arrays[-out_deque.maxlen:]
        out_deque.extend(arrays)

    elif not extend_left:
        latest_timestamp = out_deque[-1][0]
        if arrays := [arr for arr in arrays if arr[0] > latest_timestamp]:
            out_deque.extend(arrays)

    else:
        earliest_timestamp = out_deque[0][0]
        arrays = [arr for arr in arrays if arr[0] < earliest_timestamp]
        available_space = out_deque.maxlen - len(out_deque)
        if available_space > 0 and arrays:
            if len(arrays) > available_space:
                arrays = arrays[-available_space:]
            out_deque.extendleft(reversed(arrays))


def yield_candle_data_from_dict(
        data: dict[str, Any],
        ensure_timestamp_in_seconds: Callable[[int | float | str | datetime], float] | None = None,
) -> Generator[CandleData, None, None]:
    """Yields CandleData objects from a dictionary containing 'candles' key.

    :param data: The dictionary to parse containing 'candles' key
    :param ensure_timestamp_in_seconds: Function to convert timestamps to seconds
    :returns: Generator of CandleData objects
    """
    for row in data.get('candles', []):
        if ensure_timestamp_in_seconds is None:
            start = row.get('start', 0)
        else:
            start = ensure_timestamp_in_seconds(row.get('start', 0))
        yield CandleData(
            timestamp_raw=start,
            open=row.get('open', 0),
            high=row.get('high', 0),
            low=row.get('low', 0),
            close=row.get('close', 0),
            volume=row.get('volume', 0),
        )
