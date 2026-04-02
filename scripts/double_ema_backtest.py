"""
Double EMA V1 — Backtesting + Monte Carlo Simulation Runner
===========================================================

Runs a complete backtest of the Double EMA crossover strategy, then stress-tests
the results with bootstrap Monte Carlo simulations and a parameter grid search.

Usage:
    python scripts/double_ema_backtest.py

Requirements:
    - Run from the root of the hummingbot repo, or ensure the repo root is on PYTHONPATH.
    - Internet access to fetch historical candle data from the exchange.
"""

import asyncio
import os
import sys

# Ensure repo root is importable when running as a standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime
from decimal import Decimal
from typing import List

import numpy as np

from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo

# ---------------------------------------------------------------------------
# Import the controller we just built
# ---------------------------------------------------------------------------
from controllers.directional_trading.double_ema_v1 import DoubleEMAV1ControllerConfig

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CONNECTOR = "binance_perpetual"
TRADING_PAIR = "SOL-USDT"
INTERVAL = "1h"

# In-sample period
IS_START = datetime(2024, 1, 1)
IS_END = datetime(2024, 7, 1)

# Out-of-sample period (stress test)
OOS_START = datetime(2024, 7, 1)
OOS_END = datetime(2024, 10, 1)

FAST_EMA = 9
SLOW_EMA = 21
ADX_PERIOD = 14
ADX_THRESHOLD = 20.0

STOP_LOSS = Decimal("0.03")       # 3 %
TAKE_PROFIT = Decimal("0.02")     # 2 %
TIME_LIMIT = 60 * 60 * 4          # 4 hours
LEVERAGE = 10
TOTAL_CAPITAL = Decimal("1000")   # USD
MAX_EXECUTORS_PER_SIDE = 1
COOLDOWN = 3600                   # 1 hour
TRADE_COST = 0.0006               # 0.06 % taker fee

MONTE_CARLO_SIMS = 1000
MONTE_CARLO_SEED = 42

# Parameter grid for optimisation
FAST_GRID = [5, 9, 12, 20]
SLOW_GRID = [21, 34, 50]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(fast: int = FAST_EMA, slow: int = SLOW_EMA, **overrides) -> DoubleEMAV1ControllerConfig:
    return DoubleEMAV1ControllerConfig(
        id=f"dema_{fast}_{slow}",
        connector_name=CONNECTOR,
        trading_pair=TRADING_PAIR,
        candles_connector=CONNECTOR,
        candles_trading_pair=TRADING_PAIR,
        interval=INTERVAL,
        fast_ema_period=fast,
        slow_ema_period=slow,
        adx_period=ADX_PERIOD,
        adx_threshold=ADX_THRESHOLD,
        stop_loss=STOP_LOSS,
        take_profit=TAKE_PROFIT,
        time_limit=TIME_LIMIT,
        leverage=LEVERAGE,
        total_amount_quote=TOTAL_CAPITAL,
        max_executors_per_side=MAX_EXECUTORS_PER_SIDE,
        cooldown_time=COOLDOWN,
        **overrides,
    )


async def run_backtest(config: DoubleEMAV1ControllerConfig, start: datetime, end: datetime) -> dict:
    engine = BacktestingEngineBase()
    return await engine.run_backtesting(
        controller_config=config,
        start=int(start.timestamp()),
        end=int(end.timestamp()),
        backtesting_resolution=INTERVAL,
        trade_cost=TRADE_COST,
    )


def _filled_executors(executors: List[ExecutorInfo]) -> List[ExecutorInfo]:
    return [e for e in executors if e.is_trading]


# ---------------------------------------------------------------------------
# Part A — Print strategy metrics
# ---------------------------------------------------------------------------

def print_metrics(label: str, results: dict, executors: List[ExecutorInfo]):
    filled = _filled_executors(executors)
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  {label}")
    print(sep)
    print(f"  Total trades       : {results.get('total_executors_with_position', 0)}")
    print(f"  Long trades        : {results.get('total_long', 0)}")
    print(f"  Short trades       : {results.get('total_short', 0)}")
    print(f"  Win rate (overall) : {results.get('accuracy', 0):.1%}")
    print(f"  Win rate (long)    : {results.get('accuracy_long', 0):.1%}")
    print(f"  Win rate (short)   : {results.get('accuracy_short', 0):.1%}")
    print(f"  Net PnL            : {results.get('net_pnl', 0):.2%}")
    print(f"  Net PnL (USD)      : ${results.get('net_pnl_quote', 0):.2f}")
    print(f"  Max drawdown       : {results.get('max_drawdown_pct', 0):.2%}")
    print(f"  Max drawdown (USD) : ${results.get('max_drawdown_usd', 0):.2f}")
    print(f"  Sharpe ratio       : {results.get('sharpe_ratio', 0):.3f}")
    print(f"  Profit factor      : {results.get('profit_factor', 0):.3f}")
    close_types = results.get("close_types", {})
    if close_types:
        print("  Close breakdown    :")
        for ct, count in sorted(close_types.items(), key=lambda x: -x[1]):
            print(f"    {str(ct):<25} {count}")
    print(sep)


# ---------------------------------------------------------------------------
# Part B — Monte Carlo / bootstrap simulation
# ---------------------------------------------------------------------------

def _compute_metrics(pnl_pcts: np.ndarray) -> tuple:
    """Return (net_pnl, max_drawdown, sharpe) for a sequence of trade P&L percentages."""
    if len(pnl_pcts) == 0:
        return 0.0, 0.0, 0.0

    equity = np.cumprod(1.0 + pnl_pcts)
    net_pnl = float(equity[-1] - 1.0)

    peak = np.maximum.accumulate(equity)
    drawdowns = (peak - equity) / peak
    max_dd = float(np.max(drawdowns))

    mean_r = np.mean(pnl_pcts)
    std_r = np.std(pnl_pcts, ddof=1)
    # Annualise: assume each trade corresponds to one interval period.
    # For 1h candles, ~8760 periods/year; normalise by sqrt(n_trades/n_trades_per_year).
    periods_per_year = 8760  # hourly
    sharpe = float((mean_r / std_r) * np.sqrt(periods_per_year)) if std_r > 0 else 0.0

    return net_pnl, max_dd, sharpe


def run_monte_carlo(executors: List[ExecutorInfo], n_sims: int = MONTE_CARLO_SIMS, seed: int = MONTE_CARLO_SEED):
    filled = _filled_executors(executors)
    pnl_pcts = np.array([float(e.net_pnl_pct) for e in filled])

    print(f"\n{'=' * 60}")
    print(f"  Monte Carlo Bootstrap  ({n_sims} simulations, {len(pnl_pcts)} trades)")
    print("=" * 60)

    if len(pnl_pcts) < 5:
        print("  Not enough trades for a meaningful simulation (need ≥ 5).")
        print("=" * 60)
        return

    rng = np.random.default_rng(seed)
    sim_net_pnls, sim_max_dds, sim_sharpes = [], [], []

    for _ in range(n_sims):
        sample = rng.choice(pnl_pcts, size=len(pnl_pcts), replace=True)
        net_pnl, max_dd, sharpe = _compute_metrics(sample)
        sim_net_pnls.append(net_pnl)
        sim_max_dds.append(max_dd)
        sim_sharpes.append(sharpe)

    headers = ["Metric", "p5", "p25", "p50 (median)", "p75", "p95"]
    col_w = [22, 8, 8, 14, 8, 8]
    header_row = "  " + "".join(h.ljust(w) for h, w in zip(headers, col_w))
    print(header_row)
    print("  " + "-" * (sum(col_w)))

    def _row(label: str, data: list, fmt: str = ".3f"):
        pcts = np.percentile(data, [5, 25, 50, 75, 95])
        vals = [f"{v:{fmt}}" for v in pcts]
        return "  " + label.ljust(col_w[0]) + "".join(v.ljust(w) for v, w in zip(vals, col_w[1:]))

    print(_row("Net PnL (%)", [v * 100 for v in sim_net_pnls], ".2f"))
    print(_row("Max Drawdown (%)", [v * 100 for v in sim_max_dds], ".2f"))
    print(_row("Sharpe Ratio", sim_sharpes, ".3f"))

    prob_positive = np.mean(np.array(sim_net_pnls) > 0) * 100
    prob_low_dd   = np.mean(np.array(sim_max_dds) < 0.20) * 100
    print(f"\n  Probability of positive return : {prob_positive:.1f}%")
    print(f"  Probability of drawdown < 20%  : {prob_low_dd:.1f}%")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Part C — Parameter grid search
# ---------------------------------------------------------------------------

async def run_parameter_grid(start: datetime, end: datetime):
    print(f"\n{'=' * 60}")
    print("  Parameter Grid Search  (fast EMA × slow EMA, Sharpe ranking)")
    print("=" * 60)

    combos = [
        (f, s)
        for f in FAST_GRID
        for s in SLOW_GRID
        if f < s
    ]

    rows = []
    for fast, slow in combos:
        cfg = _make_config(fast=fast, slow=slow)
        try:
            result = await run_backtest(cfg, start, end)
            r = result["results"]
            rows.append({
                "fast": fast,
                "slow": slow,
                "sharpe": r.get("sharpe_ratio", 0.0),
                "net_pnl": r.get("net_pnl", 0.0),
                "max_dd": r.get("max_drawdown_pct", 0.0),
                "accuracy": r.get("accuracy", 0.0),
                "trades": r.get("total_executors_with_position", 0),
            })
            print(f"  fast={fast:>2}  slow={slow:>2}  → Sharpe={r.get('sharpe_ratio', 0):.3f}  "
                  f"PnL={r.get('net_pnl', 0):.2%}  DD={r.get('max_drawdown_pct', 0):.2%}  "
                  f"Acc={r.get('accuracy', 0):.1%}  Trades={r.get('total_executors_with_position', 0)}")
        except Exception as exc:
            print(f"  fast={fast}  slow={slow}  → ERROR: {exc}")

    if not rows:
        print("  No results to rank.")
        print("=" * 60)
        return

    rows.sort(key=lambda x: x["sharpe"], reverse=True)

    print(f"\n  Top {min(5, len(rows))} configurations by Sharpe ratio:")
    print("  " + "-" * 58)
    for i, row in enumerate(rows[:5], 1):
        print(f"  #{i}  fast={row['fast']:>2}  slow={row['slow']:>2}  "
              f"Sharpe={row['sharpe']:.3f}  PnL={row['net_pnl']:.2%}  "
              f"MaxDD={row['max_dd']:.2%}  Acc={row['accuracy']:.1%}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    print("\n" + "#" * 60)
    print("#   Double EMA V1 — AI Trading Engine")
    print("#   Strategy: EMA crossover + ADX filter")
    print(f"#   Pair    : {TRADING_PAIR}  |  Interval: {INTERVAL}")
    print(f"#   EMA     : fast={FAST_EMA}  slow={SLOW_EMA}")
    print(f"#   ADX     : period={ADX_PERIOD}  threshold={ADX_THRESHOLD}")
    print(f"#   Risk    : SL={float(STOP_LOSS):.1%}  TP={float(TAKE_PROFIT):.1%}  "
          f"TimeLimit={TIME_LIMIT // 3600}h")
    print("#" * 60)

    # --- In-sample backtest ---
    print(f"\n>>> Running IN-SAMPLE backtest: {IS_START.date()} → {IS_END.date()}")
    cfg = _make_config()
    is_result = await run_backtest(cfg, IS_START, IS_END)
    print_metrics("IN-SAMPLE RESULTS", is_result["results"], is_result["executors"])

    # --- Out-of-sample backtest ---
    print(f"\n>>> Running OUT-OF-SAMPLE backtest: {OOS_START.date()} → {OOS_END.date()}")
    oos_result = await run_backtest(cfg, OOS_START, OOS_END)
    print_metrics("OUT-OF-SAMPLE RESULTS", oos_result["results"], oos_result["executors"])

    # --- Monte Carlo on in-sample trades ---
    print("\n>>> Running Monte Carlo simulation on in-sample trades...")
    run_monte_carlo(is_result["executors"])

    # --- Parameter optimisation (in-sample period) ---
    print("\n>>> Running parameter grid search (in-sample period)...")
    await run_parameter_grid(IS_START, IS_END)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
