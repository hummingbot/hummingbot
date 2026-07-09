"""
Backtest grid_strike controller with optional chart output.

Usage:
    conda run -n hummingbot python scripts/backtest_grid_strike.py
    conda run -n hummingbot python scripts/backtest_grid_strike.py --days 3 --chart
    conda run -n hummingbot python scripts/backtest_grid_strike.py --chart --output backtest_grid.html
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
                 start_price: float, end_price: float, limit_price: float,
                 side: str, take_profit: float, max_open_orders: int,
                 leverage: int):
    config_data = {
        "id": "backtest_grid_strike",
        "controller_name": "grid_strike",
        "controller_type": "generic",
        "connector_name": connector,
        "trading_pair": trading_pair,
        "total_amount_quote": str(total_amount_quote),
        "leverage": leverage,
        "side": 1 if side == "BUY" else 2,
        "start_price": str(start_price),
        "end_price": str(end_price),
        "limit_price": str(limit_price),
        "max_open_orders": max_open_orders,
        "max_orders_per_batch": 1,
        "order_frequency": 3,
        "min_spread_between_orders": "0.001",
        "min_order_amount_quote": "5",
        "keep_position": False,
        "triple_barrier_config": {
            "take_profit": str(take_profit),
            "open_order_type": 3,  # OrderType.LIMIT_MAKER
            "take_profit_order_type": 3,  # OrderType.LIMIT_MAKER
        },
    }
    return BacktestingEngineBase.get_controller_config_instance_from_dict(
        config_data, controllers_module="controllers"
    )


async def fetch_recent_price(connector: str, trading_pair: str, start: int, end: int) -> float:
    """Fetch the first close price from candle data to auto-derive grid bounds."""
    from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
    from hummingbot.strategy_v2.backtesting.backtesting_data_provider import BacktestingDataProvider

    provider = BacktestingDataProvider(connectors={})
    provider.update_backtesting_time(start, end)
    cfg = CandlesConfig(connector=connector, trading_pair=trading_pair, interval="1m")
    await provider.initialize_candles_feed(cfg)
    df = provider.get_candles_df(connector_name=connector, trading_pair=trading_pair, interval="1m")
    if df.empty:
        raise RuntimeError(f"No candle data for {connector} {trading_pair}")
    return float(df.iloc[0]["close"])


async def main(days: float, show_chart: bool, output_path: str | None,
               connector: str, trading_pair: str, total_amount_quote: int,
               resolution: str, start_price: float | None, end_price: float | None,
               limit_price: float | None, side: str, take_profit: float,
               max_open_orders: int, leverage: int, grid_range: float):
    end_ts = int(time.time())
    start_ts = end_ts - int(days * 24 * 3600)

    # Auto-derive grid bounds from actual market data if not provided
    if start_price is None or end_price is None:
        ref = await fetch_recent_price(connector, trading_pair, start_ts, end_ts)
        half = grid_range / 2
        if start_price is None:
            start_price = round(ref * (1 - half), 6)
        if end_price is None:
            end_price = round(ref * (1 + half), 6)
        print(f"  Auto grid bounds from price {ref:.4f}: {start_price} -> {end_price}")
    if limit_price is None:
        if side == "BUY":
            limit_price = round(start_price * 0.99, 6)
        else:
            limit_price = round(end_price * 1.01, 6)

    config = build_config(connector, trading_pair, total_amount_quote,
                          start_price, end_price, limit_price,
                          side, take_profit, max_open_orders, leverage)
    engine = BacktestingEngineBase()

    print(f"Running backtest: grid_strike | {connector} {trading_pair} | {days}d | {resolution} ...")
    print(f"  Grid: {start_price} -> {end_price} | Limit: {limit_price} | Side: {side} | TP: {take_profit}")
    t0 = time.perf_counter()
    result = await engine.run_backtesting(
        config, start_ts, end_ts,
        backtesting_resolution=resolution,
        trade_cost=0.0002,
    )
    elapsed = time.perf_counter() - t0

    r = result["results"]
    _ = result["executors"]

    n_candles = len(result["processed_data"].get("features", []))
    candles_per_sec = n_candles / elapsed if elapsed > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"  grid_strike backtest ({days}d @ {resolution})")
    print(f"{'=' * 60}")
    print(f"  Duration:               {elapsed:.2f}s ({n_candles} candles, {candles_per_sec:.0f} candles/s)")
    print(f"  Total executors:        {r['total_executors']}")
    print(f"  With position:          {r['total_executors_with_position']}")
    print(f"  Net PnL:                {r['net_pnl_quote']:.4f} USDT ({r['net_pnl'] * 100:.2f}%)")
    print(f"  Accuracy:               {r['accuracy']:.2%}")
    print(f"  Sharpe ratio:           {r['sharpe_ratio']:.4f}")
    print(f"  Max drawdown:           {r['max_drawdown_pct']:.4%}")
    print(f"  Profit factor:          {r['profit_factor']:.4f}")
    print(f"  Close types:            {r['close_types']}")
    print(f"  Total volume:           {r['total_volume']:.4f}")
    print(f"  Win/Loss:               {r['win_signals']}/{r['loss_signals']}")

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
    parser = argparse.ArgumentParser(description="Backtest grid_strike")
    parser.add_argument("--days", type=float, default=1, help="Number of days to backtest (e.g. 0.5 for 12h)")
    parser.add_argument("--connector", type=str, default="binance")
    parser.add_argument("--trading-pair", type=str, default="ETH-USDT")
    parser.add_argument("--amount", type=int, default=1000, help="Total amount quote")
    parser.add_argument("--resolution", type=str, default="1m", help="Backtesting resolution (e.g. 1s, 1m, 5m)")
    parser.add_argument("--start-price", type=float, default=None, help="Grid start price (auto-derived if omitted)")
    parser.add_argument("--end-price", type=float, default=None, help="Grid end price (auto-derived if omitted)")
    parser.add_argument("--limit-price", type=float, default=None, help="Limit price (default: start - 1%%)")
    parser.add_argument("--grid-range", type=float, default=0.04, help="Grid range as fraction (default: 0.04 = ±2%%)")
    parser.add_argument("--side", type=str, default="BUY", choices=["BUY", "SELL"], help="Grid side")
    parser.add_argument("--take-profit", type=float, default=0.001, help="Take profit per level (e.g. 0.001 = 0.1%%)")
    parser.add_argument("--max-open-orders", type=int, default=2, help="Max open orders at once")
    parser.add_argument("--leverage", type=int, default=20, help="Leverage")
    parser.add_argument("--chart", action="store_true", help="Show/save the chart")
    parser.add_argument("--output", type=str, default=None, help="Save chart to HTML file instead of showing")
    args = parser.parse_args()

    asyncio.run(main(
        args.days, args.chart, args.output, args.connector, args.trading_pair,
        args.amount, args.resolution, args.start_price, args.end_price,
        args.limit_price, args.side, args.take_profit, args.max_open_orders,
        args.leverage, args.grid_range,
    ))
