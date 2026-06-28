"""The detached bot engine (the child process spawned by ``hbot start``).

Unlike ``HummingbotApplication.run_headless()`` — which mandates an MQTT broker — this engine
keeps the process alive with its own loop. Status is computed **on demand**: the engine writes a
fresh ``status.json`` only when it receives SIGUSR1 (sent by ``hbot status``), plus once at
startup (so ``hbot start`` can detect readiness) and once on shutdown. There is no polling
interval — the agent decides how often to query. On SIGTERM/SIGINT it stops the strategy
gracefully (cancelling open orders) and shuts down.

Invoked as: ``python -m hummingbot.cli.engine --name <name> [--config f | --script-config c]``
The password is passed via the ``HBOT_PASSWORD`` env var (never argv).
"""
import argparse
import asyncio
import inspect
import logging
import os
import signal
import sys
import time
from typing import Any, Dict, Optional

from hummingbot import init_logging
from hummingbot.cli.instances import Instance
from hummingbot.cli.runner import autofix_permissions, load_and_start_strategy, wait_for_gateway_ready
from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
from hummingbot.client.config.config_helpers import (
    create_yml_files_legacy,
    load_client_config_map_from_file,
    read_system_configs_from_yml,
)
from hummingbot.client.config.security import Security
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.client.settings import AllConnectorSettings

BALANCE_TIMEOUT = 10.0


def _silence_console_handlers() -> None:
    """Remove stdout (console) log handlers. Every logger keeps its file_handler, so the structured
    log is unaffected; this just stops the console stream from duplicating into the redirected bot.log."""
    from hummingbot.logger.cli_handler import CLIHandler
    loggers = [logging.getLogger()] + [logging.getLogger(n) for n in list(logging.root.manager.loggerDict)]
    for lg in loggers:
        for handler in list(getattr(lg, "handlers", [])):
            if isinstance(handler, CLIHandler) or (
                    isinstance(handler, logging.StreamHandler)
                    and getattr(handler, "stream", None) in (sys.stdout, sys.stderr)):
                lg.removeHandler(handler)


async def _collect_balances(hb: HummingbotApplication) -> Dict[str, Dict[str, float]]:
    balances: Dict[str, Dict[str, float]] = {}
    tc = hb.trading_core
    for name in list(tc.connector_manager.connectors.keys()):
        try:
            bals = await asyncio.wait_for(tc.get_current_balances(name), BALANCE_TIMEOUT)
            balances[name] = {asset: float(amt) for asset, amt in bals.items() if amt}
        except Exception:
            continue
    return balances


async def _format_status_text(hb: HummingbotApplication) -> Optional[str]:
    strategy = hb.trading_core.strategy
    if strategy is None:
        return None
    try:
        result = strategy.format_status()
        # some strategies (e.g. spot_perpetual_arbitrage) define format_status as a coroutine
        if inspect.iscoroutine(result):
            result = await result
        return result
    except Exception:
        return None


async def _write_snapshot(hb: HummingbotApplication, instance: Instance, *, running: bool) -> None:
    snapshot: Dict[str, Any] = {
        "name": instance.name,
        "pid": os.getpid(),
        "running": running,
        "updated_at": time.time(),
    }
    try:
        snapshot["engine"] = hb.trading_core.get_status()
    except Exception:
        snapshot["engine"] = None
    snapshot["format_status"] = await _format_status_text(hb)
    if running:
        snapshot["balances"] = await _collect_balances(hb)
    instance.write_status(snapshot)


async def _serve(hb: HummingbotApplication, instance: Instance) -> None:
    """Keep the process alive until a stop signal arrives.

    Status snapshots are written on demand (SIGUSR1 from ``hbot status``), not on a timer.
    """
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)
    loop.add_signal_handler(
        signal.SIGUSR1,
        lambda: loop.create_task(_write_snapshot(hb, instance, running=True)))

    # Initial snapshot so `hbot start` can detect readiness.
    await _write_snapshot(hb, instance, running=True)
    try:
        await stop_event.wait()
    finally:
        logging.getLogger().info("Stop requested — winding down strategy and cancelling orders.")
        try:
            await hb.stop_loop()
        except Exception:
            logging.getLogger().error("Error during graceful stop.", exc_info=True)
        try:
            await hb.trading_core.shutdown()
        except Exception:
            logging.getLogger().error("Error during shutdown.", exc_info=True)
        await _write_snapshot(hb, instance, running=False)
        instance.clear_pid()


async def run_engine(name: str,
                     config_file_name: Optional[str],
                     v2_conf: Optional[str],
                     password: str,
                     auto_set_permissions: Optional[str]) -> int:
    instance = Instance(name)
    client_config_map = load_client_config_map_from_file()

    if auto_set_permissions is not None:
        autofix_permissions(auto_set_permissions)

    if not Security.login(ETHKeyFileSecretManger(password)):
        logging.getLogger().error("Invalid password.")
        return 4

    await Security.wait_til_decryption_done()
    await create_yml_files_legacy()
    # Initialize per-instance logging once, up front: the structured log at logs/logs_<name>.log is the
    # single, complete, rotating log (read by `hbot logs`). Then drop the stdout console handlers — in a
    # detached process they only duplicate the file handler into bot.log, which never rotates.
    init_logging("hummingbot_logs.yml", client_config_map,
                 override_log_level=client_config_map.log_level, strategy_file_path=name)
    _silence_console_handlers()
    await read_system_configs_from_yml()
    AllConnectorSettings.initialize_paper_trade_settings(client_config_map.paper_trade.paper_trade_exchanges)

    hb = HummingbotApplication.main_application(client_config_map=client_config_map, headless_mode=True)

    started = await load_and_start_strategy(
        hb, config_file_name=config_file_name, v2_conf=v2_conf, headless=True)
    if not started:
        logging.getLogger().error("Failed to load strategy. Exiting.")
        return 1

    await wait_for_gateway_ready(hb)

    # Record the sqlite DB path so `hbot trades/history` can find it deterministically.
    db_path = hb.trading_core.trade_fill_db.db_path if hb.trading_core.trade_fill_db is not None else None
    instance.update_meta(
        db_path=db_path,
        config_file_path=hb.trading_core._strategy_file_name or hb.strategy_file_name,
        strategy_name=hb.trading_core.strategy_name,
    )

    await _serve(hb, instance)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="hbot detached bot engine (internal).")
    parser.add_argument("--name", required=True)
    parser.add_argument("--config", default=None)
    parser.add_argument("--script-config", default=None, dest="script_config")
    parser.add_argument("--auto-set-permissions", default=None, dest="auto_set_permissions")
    args = parser.parse_args()

    password = os.environ.get("HBOT_PASSWORD") or os.environ.get("CONFIG_PASSWORD")
    if not password:
        sys.stderr.write("HBOT_PASSWORD is not set; the engine cannot unlock the keystore.\n")
        sys.exit(4)

    try:
        ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(ev_loop)
        rc = ev_loop.run_until_complete(
            run_engine(args.name, args.config, args.script_config, password, args.auto_set_permissions))
    except Exception:
        logging.getLogger().error("Engine crashed.", exc_info=True)
        rc = 1
    sys.exit(rc)


if __name__ == "__main__":
    main()
