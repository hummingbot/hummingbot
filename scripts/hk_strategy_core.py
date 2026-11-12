"""Shared point in time inputs for the paper strategy examples.

Consume the API's nearest pair without estimating or grading a wall. A receipt
time is when a caller could first know a response, not its snapshot time.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
import json
import math
from pathlib import Path
from threading import RLock
from typing import Callable

RECEIPT_TTL_SEC = 900
EXTRA_SNAPSHOT_AGE_SEC = 1800
PUBLICATION_PROXY = "historical_public_wall_proxy"


def positive(value) -> float:
    if isinstance(value, bool):
        raise ValueError("Expected a positive finite number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("Expected a positive finite number") from None
    if not math.isfinite(number) or number <= 0:
        raise ValueError("Expected a positive finite number")
    return number


@dataclass(frozen=True)
class LongPlan:
    stop: float
    target: float
    available_at: float

    def tag(self) -> str:
        return f"hk:{self.stop:.8f}:{self.target:.8f}:{self.available_at:.6f}"

    @classmethod
    def from_tag(cls, tag: str):
        try:
            prefix, stop, target, available = str(tag).split(":")
            plan = cls(positive(stop), positive(target), positive(available))
            return plan if prefix == "hk" and plan.stop < plan.target else None
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True)
class Snapshot:
    symbol: str
    available_at: float
    as_of: float | None
    delay_sec: int | None
    tier: str
    mark: float
    below: float | None
    above: float | None
    payload: dict

    def usable_at(self, decision_at: float) -> bool:
        if self.tier == PUBLICATION_PROXY:
            return self.available_at <= decision_at <= self.available_at + RECEIPT_TTL_SEC
        return (self.available_at <= decision_at <= self.available_at + RECEIPT_TTL_SEC
                and self.as_of + self.delay_sec <= decision_at + 1
                and decision_at - self.as_of <= self.delay_sec + EXTRA_SNAPSHOT_AGE_SEC)

    def long_plan(self, price: float, decision_at: float) -> LongPlan | None:
        price = positive(price)
        if (not self.usable_at(decision_at) or self.below is None or self.above is None
                or not self.below < price < self.above):
            return None
        risk, reward = price - self.below, self.above - price
        # A fixed teaching rule. No optimization or historical outcome lookup.
        if reward < risk or risk / price > 0.15:
            return None
        return LongPlan(self.below, self.above, self.available_at)


def _pair(nearest, mark):
    if not isinstance(nearest, dict):
        raise ValueError("Missing nearest pair")

    def wall(key):
        cell = nearest.get(key)
        if cell is None:
            return None
        if not isinstance(cell, dict):
            raise ValueError("Malformed nearest wall")
        price = positive(cell.get("price"))
        positive(cell.get("usd"))
        expected_side = "long" if key == "below" else "short"
        if cell.get("side") != expected_side or (price < mark) != (key == "below") or price == mark:
            raise ValueError("Nearest wall is on the wrong side")
        return price

    return wall("below"), wall("above")


def parse_snapshot(payload: dict, received_at: float, symbol: str) -> Snapshot:
    """Fail closed on absent times, malformed pairs, or a false delay label."""
    received_at = positive(received_at)
    if (not isinstance(payload, dict) or payload.get("ok") is not True
            or payload.get("symbol") != symbol):
        raise ValueError("Unexpected levels response")
    as_of = positive(payload.get("as_of"))
    delay = payload.get("delay_sec")
    tier = payload.get("tier")
    if (isinstance(delay, bool) or not isinstance(delay, int) or delay < 0
            or tier not in {"live", "delayed"}
            or (tier == "live" and delay != 0)
            or (tier == "delayed" and delay < 7200)
            or as_of + delay > received_at + 1):
        raise ValueError("Unusable snapshot time or delay")
    mark = positive((payload.get("mark") or {}).get("price"))
    below, above = _pair(payload.get("nearest"), mark)
    return Snapshot(symbol, received_at, as_of, delay, tier, mark,
                    below, above, json.loads(json.dumps(payload, allow_nan=False)))


def parse_publication_proxy(row: dict, symbol: str) -> Snapshot:
    """Explicit historical format. Unknown snapshot age never becomes an API time."""
    if (row.get("kind") != PUBLICATION_PROXY or row.get("symbol") != symbol
            or row.get("snapshot_as_of") is not None or row.get("delay_sec") is not None
            or row.get("source", {}).get("viewer") != "free"):
        raise ValueError("Unexpected public publication proxy")
    available_at, mark = positive(row["received_at"]), positive(row["mark"])
    below, above = _pair(row.get("nearest"), mark)
    return Snapshot(symbol, available_at, None, None, PUBLICATION_PROXY,
                    mark, below, above, json.loads(json.dumps(row, allow_nan=False)))


class Timeline:
    """Backward lookup only. An error receipt interrupts the previous success."""

    def __init__(self):
        self._lock = RLock()
        self.times: list[float] = []
        self.samples: list[Snapshot | None] = []

    def append(self, received_at: float, sample: Snapshot | None):
        received_at = positive(received_at)
        with self._lock:
            if self.times and received_at <= self.times[-1]:
                raise ValueError("Receipts must be strictly chronological")
            if sample is not None and sample.available_at != received_at:
                raise ValueError("Receipt time mismatch")
            self.times.append(received_at)
            self.samples.append(sample)

    def at(self, decision_at: float) -> Snapshot | None:
        with self._lock:
            index = bisect_right(self.times, decision_at) - 1
            sample = self.samples[index] if index >= 0 else None
            return sample if sample and sample.usable_at(decision_at) else None

    def trim(self, count):
        with self._lock:
            self.times = self.times[-count:]
            self.samples = self.samples[-count:]

    def clear(self):
        with self._lock:
            self.times.clear()
            self.samples.clear()

    @classmethod
    def read(cls, path: str | Path, symbol="BTCUSDT", *, allow_publication_proxy=False):
        timeline = cls()
        with Path(path).open() as stream:
            for line in stream:
                if not line.strip():
                    continue
                receipt = json.loads(line)
                received_at = positive(receipt["received_at"])
                if receipt.get("kind") == PUBLICATION_PROXY and not allow_publication_proxy:
                    raise ValueError("Historical public-wall proxy requires explicit opt in")
                if "error" in receipt:
                    timeline.append(received_at, None)
                elif receipt.get("kind") == PUBLICATION_PROXY:
                    timeline.append(received_at, parse_publication_proxy(receipt, symbol))
                else:
                    timeline.append(received_at, parse_snapshot(receipt["payload"], received_at, symbol))
        return timeline


class LevelsFeed:
    """At most one request per minute, with no key discovery or payment fallback."""

    def __init__(self, symbol="BTCUSDT", *, key=None, probe=False,
                 fetch: Callable | None = None, clock: Callable | None = None):
        import time
        self.symbol, self.key, self.probe = symbol, key, probe
        self.fetch, self.clock = fetch, clock or time.time
        self.timeline = Timeline()
        self.next_poll = 0.0
        self.last_error: str | None = None

    def poll(self, now: float):
        if now < self.next_poll:
            return
        self.next_poll = now + 60
        try:
            if self.fetch is None:
                from hunterkiller_langchain import get_levels
                fetch = get_levels
            else:
                fetch = self.fetch
            payload = fetch(self.symbol, key=self.key, probe=self.probe)
            # Network completion, never the start of the request, is availability.
            received_at = self.clock()
            sample = parse_snapshot(payload, received_at, self.symbol)
            self.timeline.append(received_at, sample)
            self.last_error = None
        except Exception as exc:
            received_at = self.clock()
            if not self.timeline.times or received_at > self.timeline.times[-1]:
                self.timeline.append(received_at, None)
            else:
                self.timeline.clear()
            status = getattr(exc, "status", None)
            self.last_error = f"HTTP {status}" if isinstance(status, int) else type(exc).__name__
        # Keep a bounded point in time cache, including failed receipts.
        self.timeline.trim(240)


def grid_quotes(plan: LongPlan, mid: float, inventory: float, *, quote_budget=100.0, levels=2):
    """Long spot grid within the frozen wall pair. Sells cannot exceed inventory."""
    mid, quote_budget = positive(mid), positive(quote_budget)
    if levels not in (1, 2, 3) or not math.isfinite(inventory) or inventory < 0:
        raise ValueError("Invalid grid size or inventory")
    if not plan.stop < mid < plan.target:
        return []
    bids = [("buy", mid - i * (mid - plan.stop) / (levels + 1)) for i in range(1, levels + 1)]
    asks = [("sell", mid + i * (plan.target - mid) / (levels + 1)) for i in range(1, levels + 1)]
    remaining = max(0.0, quote_budget - inventory * mid)
    return ([(side, price, remaining / levels / price) for side, price in bids if remaining > 0]
            + [(side, price, inventory / levels) for side, price in asks if inventory > 0])
