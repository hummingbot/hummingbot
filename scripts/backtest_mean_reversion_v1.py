"""
Backtest mean_reversion_v1 directional trading strategy with optional chart output.

Usage:
    conda run -n hummingbot python scripts/backtest_mean_reversion_v1.py
    conda run -n hummingbot python scripts/backtest_mean_reversion_v1.py --days 30 --chart
    conda run -n hummingbot python scripts/backtest_mean_reversion_v1.py --chart --output backtest_mean_reversion_v1.html
"""
import argparse
import asyncio
import os
import sys
import time

import pandas as pd

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


def build_config(
    connector: str,
    candles_connector: str,
    trading_pair: str,
    total_amount_quote: int,
    interval: str,
    lookback_period: int,
    entry_z_score: float,
    exit_z_score: float,
    leverage: int,
    stop_loss: float,
    take_profit: float,
    time_limit: int,
    cooldown_time: int,
    max_executors_per_side: int,
    use_ema: bool,
    rsi_length: int,
    rsi_long_threshold: float,
    rsi_short_threshold: float,
    trend_filter_enabled: bool,
    trend_ema_period: int,
    max_trend_deviation: float,
    volume_lookback: int,
    min_volume_ratio: float,
    min_std_pct: float,
    max_std_pct: float,
    close_on_mean_reversion: bool,
    signal_on_closed_candle: bool,
):
    config_data = {
        "id": "backtest_mean_reversion_v1",
        "controller_name": "mean_reversion_v1",
        "controller_type": "directional_trading",
        "connector_name": connector,
        "trading_pair": trading_pair,
        "total_amount_quote": str(total_amount_quote),
        "leverage": leverage,
        "max_executors_per_side": max_executors_per_side,
        "cooldown_time": cooldown_time,
        "stop_loss": str(stop_loss),
        "take_profit": str(take_profit),
        "time_limit": time_limit,
        "take_profit_order_type": "LIMIT",
        "trailing_stop": None,
        "candles_connector": candles_connector,
        "candles_trading_pair": trading_pair,
        "interval": interval,
        "lookback_period": lookback_period,
        "entry_z_score": str(entry_z_score),
        "exit_z_score": str(exit_z_score),
        "use_ema": use_ema,
        "rsi_length": rsi_length,
        "rsi_long_threshold": str(rsi_long_threshold),
        "rsi_short_threshold": str(rsi_short_threshold),
        "trend_filter_enabled": trend_filter_enabled,
        "trend_ema_period": trend_ema_period,
        "max_trend_deviation": str(max_trend_deviation),
        "volume_lookback": volume_lookback,
        "min_volume_ratio": str(min_volume_ratio),
        "min_std_pct": str(min_std_pct),
        "max_std_pct": str(max_std_pct),
        "close_on_mean_reversion": close_on_mean_reversion,
        "signal_on_closed_candle": signal_on_closed_candle,
    }
    return BacktestingEngineBase.get_controller_config_instance_from_dict(
        config_data, controllers_module="controllers"
    )


async def main(
    days: float,
    show_chart: bool,
    output_path: str | None,
    trace_output_path: str | None,
    connector: str,
    candles_connector: str,
    trading_pair: str,
    total_amount_quote: int,
    resolution: str,
    interval: str,
    lookback_period: int,
    entry_z_score: float,
    exit_z_score: float,
    leverage: int,
    stop_loss: float,
    take_profit: float,
    time_limit: int,
    cooldown_time: int,
    max_executors_per_side: int,
    use_ema: bool,
    rsi_length: int,
    rsi_long_threshold: float,
    rsi_short_threshold: float,
    trend_filter_enabled: bool,
    trend_ema_period: int,
    max_trend_deviation: float,
    volume_lookback: int,
    min_volume_ratio: float,
    min_std_pct: float,
    max_std_pct: float,
    close_on_mean_reversion: bool,
    signal_on_closed_candle: bool,
):
    end_ts = int(time.time())
    start_ts = end_ts - int(days * 24 * 3600)

    config = build_config(
        connector,
        candles_connector,
        trading_pair,
        total_amount_quote,
        interval,
        lookback_period,
        entry_z_score,
        exit_z_score,
        leverage,
        stop_loss,
        take_profit,
        time_limit,
        cooldown_time,
        max_executors_per_side,
        use_ema,
        rsi_length,
        rsi_long_threshold,
        rsi_short_threshold,
        trend_filter_enabled,
        trend_ema_period,
        max_trend_deviation,
        volume_lookback,
        min_volume_ratio,
        min_std_pct,
        max_std_pct,
        close_on_mean_reversion,
        signal_on_closed_candle,
    )
    engine = BacktestingEngineBase()

    print(f"Running backtest: mean_reversion_v1 | {connector} {trading_pair} | {days}d | {resolution} ...")
    print(f"  Candles: {candles_connector} @ {interval} | Trade connector: {connector}")
    t0 = time.perf_counter()
    result = await engine.run_backtesting(
        config,
        start_ts,
        end_ts,
        backtesting_resolution=resolution,
        trade_cost=0.0002,
    )
    elapsed = time.perf_counter() - t0

    r = result["results"]
    executors = result["executors"]
    decision_trace = result.get("decision_trace", [])

    n_candles = len(result["processed_data"].get("features", []))
    candles_per_sec = n_candles / elapsed if elapsed > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"  mean_reversion_v1 backtest ({days}d @ {resolution})")
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
    print(f"  Total executors:        {len(executors)}")
    print(f"  Decision trace rows:    {len(decision_trace)}")

    if trace_output_path:
        os.makedirs(os.path.dirname(trace_output_path) or ".", exist_ok=True)
        pd.DataFrame(decision_trace).to_csv(trace_output_path, index=False)
        print(f"  Decision trace CSV:     {trace_output_path}")

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
    parser = argparse.ArgumentParser(description="Backtest mean_reversion_v1")
    parser.add_argument("--days", type=float, default=7, help="Number of days to backtest (e.g. 0.5 for 12h)")
    parser.add_argument("--connector", type=str, default="coinbase_advanced_trade_paper_trade",
                        help="Simulated trading connector used by the backtester")
    parser.add_argument("--candles-connector", type=str, default="coinbase_advanced_trade",
                        help="Historical data source for candle features")
    parser.add_argument("--trading-pair", type=str, default="BTC-USDC")
    parser.add_argument("--amount", type=int, default=100, help="Total amount quote")
    parser.add_argument("--resolution", type=str, default="1m", help="Backtesting resolution (e.g. 1s, 1m, 5m)")
    parser.add_argument("--interval", type=str, default="5m", help="Controller candle interval")
    parser.add_argument("--lookback-period", type=int, default=120, help="Mean reversion lookback period")
    parser.add_argument("--entry-z-score", type=float, default=2.0, help="Signal entry z-score")
    parser.add_argument("--exit-z-score", type=float, default=0.25, help="Signal exit z-score")
    parser.add_argument("--leverage", type=int, default=1, help="Leverage")
    parser.add_argument("--stop-loss", type=float, default=0.012, help="Stop loss percentage")
    parser.add_argument("--take-profit", type=float, default=0.008, help="Take profit percentage")
    parser.add_argument("--time-limit", type=int, default=3600, help="Time limit in seconds")
    parser.add_argument("--cooldown-time", type=int, default=900, help="Cooldown time in seconds")
    parser.add_argument("--max-executors-per-side", type=int, default=1, help="Max concurrent executors per side")
    parser.add_argument("--use-ema", action="store_true", help="Use EMA instead of SMA for fair value")
    parser.add_argument("--rsi-length", type=int, default=14, help="RSI length")
    parser.add_argument("--rsi-long-threshold", type=float, default=35.0, help="Maximum RSI allowed for long entries")
    parser.add_argument("--rsi-short-threshold", type=float, default=65.0, help="Minimum RSI required for short entries")
    parser.add_argument("--disable-trend-filter", action="store_true", help="Disable the trend regime filter")
    parser.add_argument("--trend-ema-period", type=int, default=200, help="Trend EMA period")
    parser.add_argument("--max-trend-deviation", type=float, default=0.015, help="Maximum allowed distance from trend EMA")
    parser.add_argument("--volume-lookback", type=int, default=60, help="Volume lookback period")
    parser.add_argument("--min-volume-ratio", type=float, default=0.25, help="Minimum current volume relative to rolling average")
    parser.add_argument("--min-std-pct", type=float, default=0.001, help="Minimum rolling standard deviation percentage")
    parser.add_argument("--max-std-pct", type=float, default=0.05, help="Maximum rolling standard deviation percentage")
    parser.add_argument("--disable-close-on-mean-reversion", action="store_true",
                        help="Disable controller-level exits when price reverts inside the exit z-score band")
    parser.add_argument("--signal-on-open-candle", action="store_true",
                        help="Use the latest in-progress candle instead of only closed candles")
    parser.add_argument("--chart", action="store_true", help="Show/save the chart")
    parser.add_argument("--output", type=str, default=None, help="Save chart to HTML file instead of showing")
    parser.add_argument("--trace-output", type=str, default="data/backtest_mean_reversion_v1_trace.csv",
                        help="Write per-tick decision trace CSV to this path; set empty string to disable")
    args = parser.parse_args()

    asyncio.run(main(
        args.days,
        args.chart,
        args.output,
        args.trace_output or None,
        args.connector,
        args.candles_connector,
        args.trading_pair,
        args.amount,
        args.resolution,
        args.interval,
        args.lookback_period,
        args.entry_z_score,
        args.exit_z_score,
        args.leverage,
        args.stop_loss,
        args.take_profit,
        args.time_limit,
        args.cooldown_time,
        args.max_executors_per_side,
        args.use_ema,
        args.rsi_length,
        args.rsi_long_threshold,
        args.rsi_short_threshold,
        not args.disable_trend_filter,
        args.trend_ema_period,
        args.max_trend_deviation,
        args.volume_lookback,
        args.min_volume_ratio,
        args.min_std_pct,
        args.max_std_pct,
        not args.disable_close_on_mean_reversion,
        not args.signal_on_open_candle,
    ))
