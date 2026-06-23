"""
Integration test for the backtesting engine driving a real directional strategy
(bollinger_v1). The Binance HTTP endpoints the engine touches — ``/fapi/v1/exchangeInfo``
(trading rules) and ``/fapi/v1/klines`` (historical candles) — are mocked with
``aioresponses`` so the real connector and candle-feed code paths run, but the test is
deterministic and offline (live Binance returns HTTP 451 from restricted CI regions).
"""
import math
import re
import time
import unittest

from aioresponses import CallbackResult, aioresponses

from hummingbot.core.web_assistant.connections.connections_factory import ConnectionsFactory
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase

EXCHANGE_INFO_URL = re.compile(r"^https://fapi\.binance\.com/fapi/v1/exchangeInfo.*$")
KLINES_URL = re.compile(r"^https://fapi\.binance\.com/fapi/v1/klines.*$")
SERVER_TIME_URL = re.compile(r"^https://fapi\.binance\.com/fapi/v1/time.*$")


def _price_at(ts: float) -> float:
    """Deterministic price as a pure function of timestamp.

    Being a function of absolute time keeps prices consistent across the candle feed's
    paginated requests. The superposition of incommensurate sine waves produces local
    trends that move beyond ±2σ, so Bollinger %B crosses the controller's thresholds in
    both directions and the engine actually opens long and short positions.
    """
    return (
        2000.0
        + 150.0 * math.sin(2 * math.pi * ts / 21600)
        + 80.0 * math.sin(2 * math.pi * ts / 9000)
        + 120.0 * math.sin(2 * math.pi * ts / 47000)
    )


def _exchange_info_payload() -> dict:
    """Minimal binance_perpetual exchangeInfo for ETH-USDT (shape mirrors the connector tests)."""
    return {
        "symbols": [
            {
                "symbol": "ETHUSDT",
                "pair": "ETHUSDT",
                "contractType": "PERPETUAL",
                "baseAsset": "ETH",
                "quoteAsset": "USDT",
                "marginAsset": "USDT",
                "status": "TRADING",
                "filters": [
                    {"filterType": "PRICE_FILTER", "maxPrice": "300000", "minPrice": "0.01", "tickSize": "0.01"},
                    {"filterType": "LOT_SIZE", "maxQty": "10000000", "minQty": "0.001", "stepSize": "0.001"},
                    {"filterType": "MIN_NOTIONAL", "notional": "5"},
                ],
            }
        ],
    }


def _klines_callback(url, **kwargs) -> CallbackResult:
    """Generate Binance kline rows for the requested window/interval on the fly."""
    q = url.query
    interval_seconds = CandlesBase.interval_to_seconds[q["interval"]]
    limit = int(q["limit"])
    end_s = int(q["endTime"]) // 1000 if "endTime" in q else int(time.time())
    if "startTime" in q:
        start_s = int(q["startTime"]) // 1000
    else:
        start_s = end_s - interval_seconds * limit

    first = (start_s // interval_seconds) * interval_seconds
    last = (end_s // interval_seconds) * interval_seconds
    rows = []
    t = first
    while t <= last and len(rows) < limit:
        o = _price_at(t)
        c = _price_at(t + interval_seconds)
        high = max(o, c) + 1.0
        low = min(o, c) - 1.0
        rows.append([
            t * 1000,                              # open time (ms)
            f"{o:.2f}", f"{high:.2f}", f"{low:.2f}", f"{c:.2f}",
            "10",                                  # volume
            (t + interval_seconds) * 1000 - 1,     # close time (ms)
            f"{10 * c:.2f}",                       # quote asset volume
            100,                                   # number of trades
            "5",                                   # taker buy base volume
            f"{5 * c:.2f}",                        # taker buy quote volume
            "0",                                   # ignore
        ])
        t += interval_seconds
    return CallbackResult(status=200, payload=rows)


class TestBacktestingEngineDirectional(unittest.IsolatedAsyncioTestCase):
    CONNECTOR = "binance_perpetual"
    TRADING_PAIR = "ETH-USDT"
    BACKTEST_DAYS = 3
    BACKTESTING_RESOLUTION = "1m"

    async def asyncSetUp(self):
        # ConnectionsFactory is a process-wide singleton whose aiohttp session is bound to the
        # loop that first created it. IsolatedAsyncioTestCase gives each test its own loop, so a
        # session leaked by an earlier test points at a closed loop. Drop it so a fresh session
        # is created on this loop and intercepted cleanly by aioresponses.
        factory = ConnectionsFactory()
        factory._shared_client = None
        factory._ws_independent_session = None

    async def asyncTearDown(self):
        await ConnectionsFactory().close()

    @classmethod
    def _build_config(cls, time_limit=2700):
        config_data = {
            "id": "test_bollinger",
            "controller_name": "bollinger_v1",
            "controller_type": "directional_trading",
            "connector_name": cls.CONNECTOR,
            "trading_pair": cls.TRADING_PAIR,
            "candles_connector": cls.CONNECTOR,
            "candles_trading_pair": cls.TRADING_PAIR,
            "total_amount_quote": 1000,
            "stop_loss": "0.03",
            "take_profit": "0.02",
            "time_limit": time_limit,
            "leverage": 1,
            "max_executors_per_side": 1,
            "cooldown_time": 300,
            "bb_length": 100,
            "bb_std": 2.0,
            "bb_long_threshold": 0.0,
            "bb_short_threshold": 1.0,
            "interval": "3m",
        }
        return BacktestingEngineBase.get_controller_config_instance_from_dict(
            config_data, controllers_module="controllers"
        )

    async def test_backtest_directional(self):
        """Backtest bollinger_v1 with and without time_limit against mocked Binance HTTP."""
        end_ts = int(time.time())
        start_ts = end_ts - self.BACKTEST_DAYS * 24 * 3600

        engine = BacktestingEngineBase()

        with aioresponses() as mocked:
            mocked.get(SERVER_TIME_URL, payload={"serverTime": end_ts * 1000}, repeat=True)
            mocked.get(EXCHANGE_INFO_URL, payload=_exchange_info_payload(), repeat=True)
            mocked.get(KLINES_URL, callback=_klines_callback, repeat=True)

            # --- With time_limit (executor slices bounded) ---
            config_tl = self._build_config(time_limit=2700)

            t0 = time.perf_counter()
            result_tl = await engine.run_backtesting(
                config_tl, start_ts, end_ts,
                backtesting_resolution=self.BACKTESTING_RESOLUTION,
                trade_cost=0.0002,
            )
            elapsed_tl = time.perf_counter() - t0
            self._print_results("bollinger_v1 (time_limit=2700s)", result_tl, elapsed_tl)
            self._assert_result_structure(result_tl)

            # --- Without time_limit (full remaining DF, old behavior) ---
            # Reuse the same engine so cached connectors/trading rules stay on this event loop
            config_no_tl = self._build_config(time_limit=None)

            t0 = time.perf_counter()
            result_no_tl = await engine.run_backtesting(
                config_no_tl, start_ts, end_ts,
                backtesting_resolution=self.BACKTESTING_RESOLUTION,
                trade_cost=0.0002,
            )
            elapsed_no_tl = time.perf_counter() - t0
            self._print_results("bollinger_v1 (no time_limit)", result_no_tl, elapsed_no_tl)
            self._assert_result_structure(result_no_tl)

        # Print timing comparison
        print(f"\n{'=' * 60}")
        print("  Timing comparison")
        print(f"{'=' * 60}")
        print(f"  With time_limit:   {elapsed_tl:.2f}s")
        print(f"  No time_limit:     {elapsed_no_tl:.2f}s")

    def _assert_result_structure(self, result):
        self.assertIn("executors", result)
        self.assertIn("results", result)
        self.assertIn("processed_data", result)
        self.assertIn("position_holds", result)

        r = result["results"]
        expected_keys = [
            "net_pnl", "net_pnl_quote", "total_executors",
            "total_executors_with_position", "total_volume",
            "total_long", "total_short", "close_types",
            "accuracy_long", "accuracy_short", "total_positions",
            "accuracy", "max_drawdown_usd", "max_drawdown_pct",
            "sharpe_ratio", "profit_factor", "win_signals", "loss_signals",
            "unrealized_pnl_quote",
        ]
        for key in expected_keys:
            self.assertIn(key, r, f"Missing key: {key}")

        self.assertGreaterEqual(r["total_executors"], 0)
        self.assertIsInstance(r["net_pnl_quote"], float)

    @staticmethod
    def _print_results(label, result, elapsed):
        r = result["results"]
        print(f"\n{'=' * 60}")
        print(f"  {label}")
        print(f"{'=' * 60}")
        print(f"  Duration:          {elapsed:.2f}s")
        print(f"  Total executors:   {r['total_executors']}")
        print(f"  With position:     {r['total_executors_with_position']}")
        print(f"  Net PnL:           {r['net_pnl_quote']:.4f} USDT ({r['net_pnl']:.4%})")
        print(f"  Accuracy:          {r['accuracy']:.2%}")
        print(f"  Sharpe ratio:      {r['sharpe_ratio']:.4f}")
        print(f"  Max drawdown:      {r['max_drawdown_pct']:.4%}")
        print(f"  Profit factor:     {r['profit_factor']:.4f}")
        print(f"  Close types:       {r['close_types']}")


if __name__ == "__main__":
    unittest.main()
