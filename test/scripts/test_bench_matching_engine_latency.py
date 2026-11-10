#!/usr/bin/env python3
"""
Unit tests for MatchingEngineBenchmark harness (scripts/bench_matching_engine_latency.py).
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from scripts.bench_matching_engine_latency import LatencyStats, MatchingEngineBenchmark


class MatchingEngineBenchmarkTests(unittest.TestCase):

    def setUp(self):
        self.benchmark = MatchingEngineBenchmark(
            initial_mid=100.0,
            spread_bps=10.0,
            depth_levels=25,
            dex_mode=False,
        )

    def test_initialization(self):
        self.assertIsNotNone(self.benchmark.order_book)
        bids, asks = self.benchmark.order_book.snapshot
        self.assertEqual(25, len(bids))
        self.assertEqual(25, len(asks))
        best_bid = bids.iloc[0]["price"]
        best_ask = asks.iloc[0]["price"]
        self.assertLess(best_bid, best_ask)

    def test_run_benchmark(self):
        stats, raw_latencies = self.benchmark.run_benchmark(num_orders=150, order_size=0.2, seed=123)
        self.assertEqual(150, stats.total_orders)
        self.assertGreater(stats.total_fills, 0)
        self.assertEqual(150, len(raw_latencies))
        self.assertGreater(stats.throughput_ops_sec, 0)

        # Monotonicity check
        self.assertLessEqual(stats.min_us, stats.p50_us)
        self.assertLessEqual(stats.p50_us, stats.p90_us)
        self.assertLessEqual(stats.p90_us, stats.p95_us)
        self.assertLessEqual(stats.p95_us, stats.p99_us)
        self.assertLessEqual(stats.p99_us, stats.p99_9_us)
        self.assertLessEqual(stats.p99_9_us, stats.max_us)

    def test_calculate_stats_empty(self):
        stats = MatchingEngineBenchmark.calculate_stats([], 0, 0.0)
        self.assertEqual(0, stats.total_orders)
        self.assertEqual(0.0, stats.mean_us)

    def test_format_table(self):
        stats, _ = self.benchmark.run_benchmark(num_orders=50, seed=42)
        table = MatchingEngineBenchmark.format_table(stats)
        self.assertIn("HUMMINGBOT MATCHING ENGINE LATENCY BENCHMARK", table)
        self.assertIn("p50 (Median)", table)
        self.assertIn("p99", table)

    def test_cli_execution_with_json_and_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "bench_out.json")
            csv_path = os.path.join(tmpdir, "bench_out.csv")
            script_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "scripts", "bench_matching_engine_latency.py"
            )

            cmd = [
                sys.executable,
                script_path,
                "--orders", "100",
                "--depth", "20",
                "--json", json_path,
                "--csv", csv_path,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(0, res.returncode, f"CLI failed: {res.stderr}")
            self.assertIn("HUMMINGBOT MATCHING ENGINE LATENCY BENCHMARK", res.stdout)

            self.assertTrue(os.path.exists(json_path))
            with open(json_path) as f:
                data = json.load(f)
                self.assertEqual(100, data["total_orders"])
                self.assertIn("p50_us", data)
                self.assertIn("p99_us", data)

            self.assertTrue(os.path.exists(csv_path))
            with open(csv_path) as f:
                lines = f.readlines()
                self.assertEqual(101, len(lines))  # 1 header + 100 rows


if __name__ == "__main__":
    unittest.main()
