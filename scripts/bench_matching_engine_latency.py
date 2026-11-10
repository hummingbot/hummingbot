#!/usr/bin/env python3
"""
scripts/bench_matching_engine_latency.py

Benchmarking harness for matching engine fill latency and throughput.
Allows makers and algorithmic traders to benchmark order matching latency,
order book crossing performance, and trade replay fill times before deploying
capital on live or paper connectors.

Usage:
    python scripts/bench_matching_engine_latency.py
    python scripts/bench_matching_engine_latency.py --orders 2000 --depth 100 --order-size 5.0 --json results.json
"""

import argparse
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Ensure hummingbot package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow


@dataclass
class LatencyStats:
    total_orders: int
    total_fills: int
    avg_levels_walked: float
    elapsed_time_s: float
    throughput_ops_sec: float
    min_us: float
    mean_us: float
    std_us: float
    p50_us: float
    p90_us: float
    p95_us: float
    p99_us: float
    p99_9_us: float
    max_us: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MatchingEngineBenchmark:
    """
    High-performance matching engine benchmarking harness.
    Evaluates order book fill latency and replay throughput under configurable order flow.
    """

    def __init__(
        self,
        initial_mid: float = 100.0,
        spread_bps: float = 10.0,
        depth_levels: int = 50,
        dex_mode: bool = False,
    ):
        if not math.isfinite(initial_mid) or initial_mid <= 0:
            raise ValueError(f"initial_mid must be a positive finite number, got {initial_mid}")
        if not math.isfinite(spread_bps) or spread_bps < 0:
            raise ValueError(f"spread_bps must be non-negative and finite, got {spread_bps}")
        if not isinstance(depth_levels, int) or depth_levels < 1:
            raise ValueError(f"depth_levels must be an integer >= 1, got {depth_levels}")

        self.initial_mid = initial_mid
        self.spread_bps = spread_bps
        self.depth_levels = depth_levels
        self.dex_mode = dex_mode
        self.order_book: Optional[OrderBook] = None
        self.reset_order_book()

    def reset_order_book(self):
        """Initializes a synthetic order book with configurable depth and spread."""
        self.order_book = OrderBook(dex=self.dex_mode)
        half_spread = (self.initial_mid * (self.spread_bps / 10000.0)) / 2.0
        best_bid = self.initial_mid - half_spread
        best_ask = self.initial_mid + half_spread

        bids = []
        asks = []
        for i in range(self.depth_levels):
            # 0.1% tick step per level
            bid_price = best_bid * (1.0 - (i * 0.001))
            ask_price = best_ask * (1.0 + (i * 0.001))
            size = 1.0 + (i * 0.1)
            bids.append([bid_price, size, i + 1])
            asks.append([ask_price, size, i + 1])

        bids_array = np.array(bids, dtype=np.float64)
        asks_array = np.array(asks, dtype=np.float64)
        self.order_book.apply_numpy_snapshot(bids_array, asks_array)

    def run_benchmark(
        self,
        num_orders: int = 1000,
        order_size: float = 5.0,
        randomize_sizes: bool = True,
        seed: int = 42,
    ) -> Tuple[LatencyStats, List[float]]:
        """
        Executes order matching simulation across buy and sell flows,
        recording per-operation latency in nanoseconds.
        Simulate methods are non-mutating, so no mid-run order book rebuilds are performed.
        """
        if not isinstance(num_orders, int) or num_orders < 1:
            raise ValueError(f"num_orders must be an integer >= 1, got {num_orders}")
        if not math.isfinite(order_size) or order_size <= 0:
            raise ValueError(f"order_size must be a positive finite number, got {order_size}")

        np.random.seed(seed)
        latencies_ns: List[int] = []
        fills_count = 0
        total_levels_walked = 0

        # Pre-generate sides and sizes for consistent benchmarking
        is_buys = np.random.choice([True, False], size=num_orders)
        if randomize_sizes:
            sizes = np.random.uniform(max(0.1, order_size * 0.2), order_size * 1.8, size=num_orders)
        else:
            sizes = np.full(num_orders, order_size, dtype=np.float64)

        t_start = time.perf_counter()

        for i in range(num_orders):
            is_buy = is_buys[i]
            sz = float(sizes[i])

            # Measure core matching engine execution time
            t0 = time.perf_counter_ns()
            if is_buy:
                rows: List[OrderBookRow] = self.order_book.simulate_buy(sz)
            else:
                rows: List[OrderBookRow] = self.order_book.simulate_sell(sz)
            t1 = time.perf_counter_ns()

            latencies_ns.append(t1 - t0)
            if rows:
                fills_count += 1
                total_levels_walked += len(rows)

        total_elapsed = time.perf_counter() - t_start
        avg_levels = (total_levels_walked / fills_count) if fills_count > 0 else 0.0
        stats = self.calculate_stats(latencies_ns, fills_count, avg_levels, total_elapsed)
        latencies_us = [ns / 1000.0 for ns in latencies_ns]
        return stats, latencies_us

    @staticmethod
    def calculate_stats(
        latencies_ns: List[int],
        total_fills: int,
        avg_levels_walked: float,
        total_elapsed_s: float,
    ) -> LatencyStats:
        """Calculates latency summary percentiles and throughput in microseconds."""
        if not latencies_ns:
            return LatencyStats(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        latencies_us = np.array(latencies_ns, dtype=np.float64) / 1000.0
        n = len(latencies_us)

        return LatencyStats(
            total_orders=n,
            total_fills=total_fills,
            avg_levels_walked=float(avg_levels_walked),
            elapsed_time_s=float(total_elapsed_s),
            throughput_ops_sec=float(n / max(total_elapsed_s, 1e-9)),
            min_us=float(np.min(latencies_us)),
            mean_us=float(np.mean(latencies_us)),
            std_us=float(np.std(latencies_us)),
            p50_us=float(np.percentile(latencies_us, 50)),
            p90_us=float(np.percentile(latencies_us, 90)),
            p95_us=float(np.percentile(latencies_us, 95)),
            p99_us=float(np.percentile(latencies_us, 99)),
            p99_9_us=float(np.percentile(latencies_us, 99.9)),
            max_us=float(np.max(latencies_us)),
        )

    @staticmethod
    def format_table(stats: LatencyStats) -> str:
        """Renders an ASCII summary table for terminal logging."""
        lines = [
            "=" * 56,
            "     HUMMINGBOT MATCHING ENGINE LATENCY BENCHMARK       ",
            "=" * 56,
            f" Total Orders Evaluated : {stats.total_orders:,}",
            f" Total Successful Fills : {stats.total_fills:,}",
            f" Avg Book Levels Walked : {stats.avg_levels_walked:.2f} levels/order",
            f" Total Wall Time        : {stats.elapsed_time_s:.4f} s",
            f" Throughput             : {stats.throughput_ops_sec:,.1f} fills/sec",
            "-" * 56,
            " LATENCY PERCENTILES (Microseconds / µs)",
            "-" * 56,
            f" Min Latency            : {stats.min_us:8.2f} µs",
            f" Mean Latency           : {stats.mean_us:8.2f} µs (± {stats.std_us:.2f} µs)",
            f" p50 (Median)           : {stats.p50_us:8.2f} µs",
            f" p90                    : {stats.p90_us:8.2f} µs",
            f" p95                    : {stats.p95_us:8.2f} µs",
            f" p99                    : {stats.p99_us:8.2f} µs",
            f" p99.9                  : {stats.p99_9_us:8.2f} µs",
            f" Max Latency            : {stats.max_us:8.2f} µs",
            "=" * 56,
        ]
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Hummingbot matching engine fill latency benchmark harness."
    )
    parser.add_argument("--orders", type=int, default=1000, help="Number of simulated orders to evaluate (default: 1000)")
    parser.add_argument("--order-size", type=float, default=5.0, help="Order size to evaluate book walking depth (default: 5.0)")
    parser.add_argument("--depth", type=int, default=50, help="Number of price levels per side (default: 50)")
    parser.add_argument("--mid-price", type=float, default=100.0, help="Initial mid market price (default: 100.0)")
    parser.add_argument("--spread-bps", type=float, default=10.0, help="Spread in basis points (default: 10.0)")
    parser.add_argument("--dex", action="store_true", help="Enable DEX order book mode")
    parser.add_argument("--json", type=str, default="", help="Path to write JSON summary output")
    parser.add_argument("--csv", type=str, default="", help="Path to write raw latencies CSV")

    args = parser.parse_args()

    # CLI input validation
    if args.orders < 1:
        parser.error(f"--orders must be an integer >= 1, got {args.orders}")
    if not math.isfinite(args.order_size) or args.order_size <= 0:
        parser.error(f"--order-size must be a positive finite number, got {args.order_size}")
    if args.depth < 1:
        parser.error(f"--depth must be an integer >= 1, got {args.depth}")
    if not math.isfinite(args.mid_price) or args.mid_price <= 0:
        parser.error(f"--mid-price must be a positive finite number, got {args.mid_price}")
    if not math.isfinite(args.spread_bps) or args.spread_bps < 0:
        parser.error(f"--spread-bps must be non-negative and finite, got {args.spread_bps}")

    bench = MatchingEngineBenchmark(
        initial_mid=args.mid_price,
        spread_bps=args.spread_bps,
        depth_levels=args.depth,
        dex_mode=args.dex,
    )

    stats, raw_latencies = bench.run_benchmark(num_orders=args.orders, order_size=args.order_size)
    print(bench.format_table(stats))

    if args.json:
        with open(args.json, "w") as f:
            json.dump(stats.to_dict(), f, indent=2)
        print(f"\n[+] Results saved to JSON: {args.json}")

    if args.csv:
        with open(args.csv, "w") as f:
            f.write("order_index,latency_us\n")
            for idx, lat in enumerate(raw_latencies):
                f.write(f"{idx},{lat:.3f}\n")
        print(f"[+] Raw latencies saved to CSV: {args.csv}")


if __name__ == "__main__":
    main()
