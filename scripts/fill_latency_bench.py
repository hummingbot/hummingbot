"""Replay a checked-in fill sample and print count, p50, and p99.

This is not a trading script. It does not connect to an exchange.

Run from the repository root:

    python scripts/fill_latency_bench.py
"""

import os
import sys
from pathlib import Path

# Running this file puts scripts/ on the path, not the repository root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hummingbot.strategy_v2.backtesting.fill_latency import main  # noqa: E402

_SAMPLE = Path(__file__).resolve().parent / "fixtures" / "fill_latency_sample.csv"


if __name__ == "__main__":
    sys.stdout.write(main(_SAMPLE) + "\n")
