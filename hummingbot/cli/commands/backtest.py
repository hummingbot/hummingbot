"""``hbot backtest`` — run a controller config through the backtesting engine.

  hbot backtest conf_pmm.yml --start 2026-07-01 --end 2026-07-08 --json

This is the CLI door to ``hummingbot.strategy_v2.backtesting`` (4b): a
supervisor (or the improve loop) invokes the backtester as a subprocess
behind the CLI contract instead of importing hummingbot as a library. The
JSON output's ``results`` block is the canonical metrics schema
(``summarize_results``: net_pnl_quote, total_volume, accuracy, profit
factor, max drawdown, sharpe, …).

Only V2 controller configs are backtestable — scripts and V1 strategies
exit 4 (CONFIG_ERROR), the "backtester can't model this" signal callers
branch on (the improve loop then falls back to a short evaluation run).
"""
from datetime import datetime, timezone

import typer

from hummingbot.cli.output import ExitCode, emit, fail, json_option, render_kv


def _parse_when(raw: str, name: str) -> int:
    """Accept a unix timestamp or an ISO date/datetime (UTC assumed)."""
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        fail(f"--{name} must be a unix timestamp or ISO date (got {raw!r})",
             ExitCode.CONFIG_ERROR)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def backtest(
    config: str = typer.Argument(..., help="Controller config file (in conf/controllers/, or a path)."),
    start: str = typer.Option(..., "--start", help="Window start: unix ts or ISO date (UTC)."),
    end: str = typer.Option(..., "--end", help="Window end: unix ts or ISO date (UTC)."),
    resolution: str = typer.Option("1m", "--resolution", help="Candle resolution (e.g. 1m, 3m, 1h)."),
    trade_cost: float = typer.Option(0.0006, "--trade-cost", help="Per-side trade cost fraction."),
    as_json: bool = json_option(),
) -> None:
    """Backtest a controller config over a window; JSON out is the canonical metrics schema."""
    import asyncio
    from pathlib import Path

    from hummingbot.cli.strategy_configs import config_path, resolve_config_type

    start_ts = _parse_when(start, "start")
    end_ts = _parse_when(end, "end")
    if end_ts <= start_ts:
        fail(f"--end ({end_ts}) must be after --start ({start_ts})", ExitCode.CONFIG_ERROR)

    path = Path(config)
    if not path.exists():
        try:
            stype = resolve_config_type(config, None)
        except Exception:
            stype = None
        if stype is not None and stype != "controller":
            fail(f"{config} is a {stype} config — only V2 controller configs are "
                 "backtestable", ExitCode.CONFIG_ERROR)
        path = config_path("controller", config)
    if not path.exists():
        fail(f"controller config {config} not found (looked at {path})", ExitCode.NOT_FOUND)

    from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase

    try:
        controller_config = BacktestingEngineBase.get_controller_config_instance_from_yml(
            config_path=path.name, controllers_conf_dir_path=str(path.parent)
        )
    except Exception as e:
        fail(f"not a backtestable controller config: {e}", ExitCode.CONFIG_ERROR)

    engine = BacktestingEngineBase()

    async def _run():
        return await engine.run_backtesting(
            controller_config, start_ts, end_ts,
            backtesting_resolution=resolution, trade_cost=trade_cost,
        )

    try:
        outcome = asyncio.run(_run())
    except Exception as e:
        # The engine cannot model this config/window (unsupported connector,
        # no candles, unsimulatable executor kind): the improve loop's
        # fall-back-to-eval-run signal, not a crash.
        fail(f"backtest could not run: {e}", ExitCode.CONFIG_ERROR)

    results = outcome["results"]
    payload = {
        "config": path.name,
        "controller_name": getattr(controller_config, "controller_name", None),
        "connector": getattr(controller_config, "connector_name", None),
        "trading_pair": getattr(controller_config, "trading_pair", None),
        "start": start_ts,
        "end": end_ts,
        "resolution": resolution,
        "trade_cost": trade_cost,
        "results": results,
    }
    summary = {
        "net_pnl_quote": results.get("net_pnl_quote"),
        "total_volume": results.get("total_volume"),
        "total_positions": results.get("total_positions"),
        "accuracy": results.get("accuracy"),
        "profit_factor": results.get("profit_factor"),
        "max_drawdown_usd": results.get("max_drawdown_usd"),
        "sharpe_ratio": results.get("sharpe_ratio"),
    }
    emit(payload, render_kv({"config": path.name, **summary}, title="backtest"), as_json)
