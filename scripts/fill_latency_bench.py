"""Replay a checked-in fill sample and print count, p50, and p99.

This is not a trading script. It does not connect to an exchange.
"""

import sys
from pathlib import Path

from hummingbot.strategy_v2.backtesting.fill_latency import main

_SAMPLE = Path(__file__).resolve().parent / "fixtures" / "fill_latency_sample.csv"


if __name__ == "__main__":
    sys.stdout.write(main(_SAMPLE) + "\n")
