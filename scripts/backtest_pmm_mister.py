"""
Backtest pmm_mister with position hold support and optional chart output.

Usage:
    conda run -n hummingbot python scripts/backtest_pmm_mister.py
    conda run -n hummingbot python scripts/backtest_pmm_mister.py --days 3 --chart
    conda run -n hummingbot python scripts/backtest_pmm_mister.py --chart --output backtest.html
"""
import argparse
import asyncio
import os
import sys
import time

# Ensure repo root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Patch broken optional dependency (injective proto mismatch)
try:
    from pyinjective.proto.injective.stream.v2 import query_pb2
    if not hasattr(query_pb2, "OrderFailuresFilter"):
        query_pb2.OrderFailuresFilter = type("OrderFailuresFilter", (), {})
except ImportError:
    pass

from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase  # noqa: E402
from hummingbot.strategy_v2.backtesting.backtesting_result import BacktestingResult  # noqa: E402
from hummingbot.strategy_v2.models.executors import CloseType  # noqa: E402


def build_config(connector: str, trading_pair: str, total_amount_quote: int):
    config_data = {
        "id": "backtest_pmm_mister",
        "controller_name": "pmm_mister",
        "controller_type": "generic",
        "connector_name": connector,
        "trading_pair": trading_pair,
        "total_amount_quote": total_amount_quote,
        "leverage": 1,
        "portfolio_allocation": "0.02",
        "target_base_pct": "0.5",
        "min_base_pct": "0.3",
        "max_base_pct": "0.7",
        "buy_spreads": "0.0002",
        "sell_spreads": "0.0002",
        "buy_amounts_pct": "1",
        "sell_amounts_pct": "1",
        "executor_refresh_time": 30,
        "buy_cooldown_time": 30,
        "sell_cooldown_time": 30,
        "buy_position_effectivization_time": 1660,
        "sell_position_effectivization_time": 1660,
        "price_distance_tolerance": 0.0002,
        "take_profit": "0.0002",
        "max_active_executors_by_level": 20,
        "position_profit_protection": True
    }
    return BacktestingEngineBase.get_controller_config_instance_from_dict(
        config_data, controllers_module="controllers"
    )


async def main(days: float, show_chart: bool, output_path: str | None,
               connector: str, trading_pair: str, total_amount_quote: int,
               resolution: str):
    end_ts = int(time.time())
    start_ts = end_ts - int(days * 24 * 3600)

    config = build_config(connector, trading_pair, total_amount_quote)
    engine = BacktestingEngineBase()

    print(f"Running backtest: pmm_mister | {connector} {trading_pair} | {days}d | {resolution} ...")
    t0 = time.perf_counter()
    result = await engine.run_backtesting(
        config, start_ts, end_ts,
        backtesting_resolution=resolution,
        trade_cost=0.0002,
    )
    elapsed = time.perf_counter() - t0

    r = result["results"]
    position_holds = result["position_holds"]
    executors = result["executors"]
    ph_executors = [e for e in executors if e.close_type == CloseType.POSITION_HOLD]

    n_candles = len(result["processed_data"].get("features", []))
    candles_per_sec = n_candles / elapsed if elapsed > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"  pmm_mister backtest ({days}d @ {resolution})")
    print(f"{'=' * 60}")
    print(f"  Duration:               {elapsed:.2f}s ({n_candles} candles, {candles_per_sec:.0f} candles/s)")
    print(f"  Total executors:        {r['total_executors']}")
    print(f"  With position:          {r['total_executors_with_position']}")
    print(f"  Net PnL:                {r['net_pnl_quote']:.4f} USDT ({r['net_pnl'] * 100:.2f}%)")
    print(f"  Position Realized PnL:  {r['position_realized_pnl_quote']:.4f} USDT")
    print(f"  Unrealized PnL:         {r['unrealized_pnl_quote']:.4f} USDT")
    print(f"  Accuracy:               {r['accuracy']:.2%}")
    print(f"  Sharpe ratio:           {r['sharpe_ratio']:.4f}")
    print(f"  Max drawdown:           {r['max_drawdown_pct']:.4%}")
    print(f"  Profit factor:          {r['profit_factor']:.4f}")
    print(f"  Close types:            {r['close_types']}")
    print(f"  Position Hold execs:    {len(ph_executors)}")
    print(f"  Position holds:         {len(position_holds)}")
    for ph in position_holds:
        print(f"    {ph.connector_name} {ph.trading_pair}: "
              f"buy={float(ph.buy_amount_base):.6f} sell={float(ph.sell_amount_base):.6f} "
              f"net={float(ph.net_amount_base):.6f}")

    bt_result = BacktestingResult(result, config)
    print(f"\n{bt_result.get_results_summary()}")

    if show_chart:
        try:
            fig = bt_result.get_backtesting_figure()
            if output_path:
                fig.write_html(output_path)
                print(f"\n  Chart saved to {output_path}")
            else:
                fig.show()
        except ImportError:
            print("\n  plotly not installed: pip install plotly")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest pmm_mister")
    parser.add_argument("--days", type=float, default=0.5, help="Number of days to backtest (e.g. 0.5 for 12h)")
    parser.add_argument("--connector", type=str, default="binance")
    parser.add_argument("--trading-pair", type=str, default="SOL-USDT")
    parser.add_argument("--amount", type=int, default=1000, help="Total amount quote")
    parser.add_argument("--resolution", type=str, default="1s", help="Backtesting resolution (e.g. 1s, 1m, 5m)")
    parser.add_argument("--chart", action="store_true", default=True, help="Show/save the chart")
    parser.add_argument("--output", type=str, default=None, help="Save chart to HTML file instead of showing")
    args = parser.parse_args()

    asyncio.run(main(args.days, args.chart, args.output, args.connector, args.trading_pair, args.amount, args.resolution))
