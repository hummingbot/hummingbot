"""Offline fill-latency summary. Timestamps come from a sample file, not an exchange."""

import csv
import math
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


class FillLatencyError(ValueError):
    """A sample is empty or a latency is negative."""


def latencies_ms(samples: Sequence[Tuple[int, int]]) -> List[int]:
    """Return ack minus send, in milliseconds, for each pair."""
    delays: List[int] = []
    for send_ms, ack_ms in samples:
        delay = int(ack_ms) - int(send_ms)
        if delay < 0:
            raise FillLatencyError(f"negative latency: send_ms={send_ms} ack_ms={ack_ms}")
        delays.append(delay)
    return delays


def _nearest_rank(values: Sequence[int], percentile: float) -> int:
    ordered = sorted(values)
    rank = math.ceil(percentile / 100.0 * len(ordered))
    rank = min(len(ordered), max(1, rank))
    return ordered[rank - 1]


def summarize(latencies: Sequence[int]) -> Dict[str, int]:
    """Count plus nearest-rank p50 and p99, in milliseconds."""
    if len(latencies) == 0:
        raise FillLatencyError("no latencies")
    for value in latencies:
        if int(value) < 0:
            raise FillLatencyError(f"negative latency: {value}")
    cleaned = [int(value) for value in latencies]
    return {
        "count": len(cleaned),
        "p50_ms": _nearest_rank(cleaned, 50),
        "p99_ms": _nearest_rank(cleaned, 99),
    }


def read_samples(path: Path) -> List[Tuple[int, int]]:
    """Read send_ms,ack_ms rows from a CSV file."""
    pairs: List[Tuple[int, int]] = []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            pairs.append((int(row["send_ms"]), int(row["ack_ms"])))
    return pairs


def format_summary(summary: Dict[str, int]) -> str:
    return f"count={summary['count']}\np50={summary['p50_ms']}\np99={summary['p99_ms']}"


def main(sample_path: Path) -> str:
    return format_summary(summarize(latencies_ms(read_samples(sample_path))))
