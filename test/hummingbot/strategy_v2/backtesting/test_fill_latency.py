import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from hummingbot.strategy_v2.backtesting.fill_latency import (
    FillLatencyError,
    format_summary,
    latencies_ms,
    main,
    read_samples,
    summarize,
)


class TestFillLatency(unittest.TestCase):
    def test_empty_summary_raises(self):
        with self.assertRaises(FillLatencyError):
            summarize([])

    def test_negative_latency_raises(self):
        with self.assertRaises(FillLatencyError):
            summarize([1, -1])
        with self.assertRaises(FillLatencyError):
            latencies_ms([(20, 10)])

    def test_single_sample(self):
        summary = summarize(latencies_ms([(1000, 1015)]))
        self.assertEqual({"count": 1, "p50_ms": 15, "p99_ms": 15}, summary)

    def test_nearest_rank_percentiles(self):
        summary = summarize([10, 40, 20, 30])
        self.assertEqual(4, summary["count"])
        self.assertEqual(20, summary["p50_ms"])
        self.assertEqual(40, summary["p99_ms"])

    def test_sample_file(self):
        sample = Path(__file__).resolve().parents[4] / "scripts" / "fixtures" / "fill_latency_sample.csv"
        text = main(sample)
        self.assertEqual("count=4\np50=20\np99=40", text)
        self.assertEqual(text, format_summary(summarize([10, 20, 30, 40])))

    def test_script_process_prints_summary(self):
        repo = Path(__file__).resolve().parents[4]
        script = repo / "scripts" / "fill_latency_bench.py"
        completed = subprocess.run(
            [sys.executable, str(script)],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual("count=4\np50=20\np99=40\n", completed.stdout)

    def test_read_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.csv"
            path.write_text("send_ms,ack_ms\n5,8\n", encoding="utf-8")
            self.assertEqual([(5, 8)], read_samples(path))
            self.assertEqual([3], latencies_ms(read_samples(path)))
