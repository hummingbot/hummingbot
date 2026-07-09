"""
Backtest bollinger_v2 directional trading strategy with optional chart output.

Usage:
    conda run -n hummingbot python scripts/backtest_bollinger_v2.py
    conda run -n hummingbot python scripts/backtest_bollinger_v2.py --days 3 --chart
    conda run -n hummingbot python scripts/backtest_bollinger_v2.py --chart --output backtest.html
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


def build_config(connector: str, trading_pair: str, total_amount_quote: int,
                 interval: str, bb_length: int, bb_std: float,
                 bb_long_threshold: float, bb_short_threshold: float,
                 leverage: int, stop_loss: float, take_profit: float,
                 time_limit: int, cooldown_time: int):
    config_data = {
        "id": "backtest_bollinger_v2",
        "controller_name": "bollinger_v2",
        "controller_type": "directional_trading",
        "connector_name": connector,
        "trading_pair": trading_pair,
        "candles_connector": connector,
        "candles_trading_pair": trading_pair,
        "total_amount_quote": total_amount_quote,
        "leverage": leverage,
        "max_executors_per_side": 2,
        "cooldown_time": cooldown_time,
        "stop_loss": str(stop_loss),
        "take_profit": str(take_profit),
        "time_limit": time_limit,
        "interval": interval,
        "bb_length": bb_length,
        "bb_std": bb_std,
        "bb_long_threshold": bb_long_threshold,
        "bb_short_threshold": bb_short_threshold,
    }
    return BacktestingEngineBase.get_controller_config_instance_from_dict(
        config_data, controllers_module="controllers"
    )


async def main(days: int, show_chart: bool, output_path: str | None,
               connector: str, trading_pair: str, total_amount_quote: int,
               interval: str, bb_length: int, bb_std: float,
               bb_long_threshold: float, bb_short_threshold: float,
               leverage: int, stop_loss: float, take_profit: float,
               time_limit: int, cooldown_time: int):
    end_ts = int(time.time())
    start_ts = end_ts - days * 24 * 3600

    config = build_config(connector, trading_pair, total_amount_quote,
                          interval, bb_length, bb_std,
                          bb_long_threshold, bb_short_threshold,
                          leverage, stop_loss, take_profit,
                          time_limit, cooldown_time)
    engine = BacktestingEngineBase()

    print(f"Running backtest: bollinger_v2 | {connector} {trading_pair} | {days}d ...")
    t0 = time.perf_counter()
    result = await engine.run_backtesting(
        config, start_ts, end_ts,
        backtesting_resolution="1m",
        trade_cost=0.0002,
    )
    elapsed = time.perf_counter() - t0

    r = result["results"]
    executors = result["executors"]

    print(f"\n{'=' * 60}")
    print(f"  bollinger_v2 backtest ({days}d)")
    print(f"{'=' * 60}")
    print(f"  Duration:               {elapsed:.2f}s")
    print(f"  Total executors:        {r['total_executors']}")
    print(f"  With position:          {r['total_executors_with_position']}")
    print(f"  Net PnL:                {r['net_pnl_quote']:.4f} USDT ({r['net_pnl'] * 100:.2f}%)")
    print(f"  Accuracy:               {r['accuracy']:.2%}")
    print(f"  Sharpe ratio:           {r['sharpe_ratio']:.4f}")
    print(f"  Max drawdown:           {r['max_drawdown_pct']:.4%}")
    print(f"  Profit factor:          {r['profit_factor']:.4f}")
    print(f"  Close types:            {r['close_types']}")
    print(f"  Total executors:        {len(executors)}")

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
    parser = argparse.ArgumentParser(description="Backtest bollinger_v2")
    parser.add_argument("--days", type=int, default=1, help="Number of days to backtest")
    parser.add_argument("--connector", type=str, default="binance_perpetual")
    parser.add_argument("--trading-pair", type=str, default="ETH-USDT")
    parser.add_argument("--amount", type=int, default=1000, help="Total amount quote")
    parser.add_argument("--interval", type=str, default="3m", help="Candle interval")
    parser.add_argument("--bb-length", type=int, default=100, help="Bollinger Bands length")
    parser.add_argument("--bb-std", type=float, default=2.0, help="Bollinger Bands std dev")
    parser.add_argument("--bb-long-threshold", type=float, default=0.0, help="BB long threshold")
    parser.add_argument("--bb-short-threshold", type=float, default=1.0, help="BB short threshold")
    parser.add_argument("--leverage", type=int, default=20, help="Leverage")
    parser.add_argument("--stop-loss", type=float, default=0.03, help="Stop loss percentage")
    parser.add_argument("--take-profit", type=float, default=0.02, help="Take profit percentage")
    parser.add_argument("--time-limit", type=int, default=2700, help="Time limit in seconds")
    parser.add_argument("--cooldown-time", type=int, default=300, help="Cooldown time in seconds")
    parser.add_argument("--chart", action="store_true", default=True, help="Show/save the chart")
    parser.add_argument("--output", type=str, default=None, help="Save chart to HTML file instead of showing")
    args = parser.parse_args()

    asyncio.run(main(args.days, args.chart, args.output, args.connector, args.trading_pair,
                     args.amount, args.interval, args.bb_length, args.bb_std,
                     args.bb_long_threshold, args.bb_short_threshold, args.leverage,
                     args.stop_loss, args.take_profit, args.time_limit, args.cooldown_time))
