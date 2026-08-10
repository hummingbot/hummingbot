"""Shared, headless-safe helpers for bootstrapping and launching a Hummingbot strategy.

These bootstrap the one real engine — ``KairosApplication`` + ``TradingCore`` — and are used by
every host that stands it up: the interactive ``bin/kairos.py`` / ``bin/kairos_quickstart.py``
launchers and the detached ``hbot`` engine (``kairos/cli/engine.py``). Because this is core
engine-launch logic (not CLI logic), it lives in the client layer, so ``kairos/cli`` stays a leaf
that depends on the client — never the other way around.

Keep this module free of host concerns (no typer, no argparse, no prompt-toolkit) — it only knows how
to build the application and load/start a strategy.
"""
import grp
import logging
import os
import pwd
import subprocess
from typing import Optional

import yaml

from kairos.client.config.config_helpers import (
    ClientConfigAdapter,
    all_configs_complete,
    load_strategy_config_map_from_file,
)
from kairos.client.kairos_application import KairosApplication
from kairos.client.settings import SCRIPT_STRATEGY_CONF_DIR_PATH, STRATEGIES_CONF_DIR_PATH, AllConnectorSettings


def autofix_permissions(user_group_spec: str) -> None:
    uid, gid = [sub_str for sub_str in user_group_spec.split(':')]

    uid = int(uid) if uid.isnumeric() else pwd.getpwnam(uid).pw_uid
    gid = int(gid) if gid.isnumeric() else grp.getgrnam(gid).gr_gid

    os.environ["HOME"] = pwd.getpwuid(uid).pw_dir
    project_home: str = os.path.realpath(os.path.join(__file__, "../../../"))

    subprocess.run(
        f"cd '{project_home}' && "
        f"sudo chown -R {user_group_spec} conf/ data/ logs/ scripts/",
        capture_output=True,
        shell=True
    )
    os.setgid(gid)
    os.setuid(uid)



async def load_and_start_strategy(hb: KairosApplication,
                                  *,
                                  config_file_name: Optional[str] = None,
                                  v2_conf: Optional[str] = None,
                                  headless: bool = False) -> bool:
    """Load a strategy/script config and (in headless mode) start it.

    Mirrors the legacy quickstart flow. Returns False on any load/start failure.
    """
    if v2_conf:
        # V2 config-driven start: derive script from config file
        conf_path = SCRIPT_STRATEGY_CONF_DIR_PATH / v2_conf
        if not conf_path.exists():
            logging.getLogger().error(f"V2 config file not found: {conf_path}")
            return False

        with open(conf_path) as f:
            config_data = yaml.safe_load(f) or {}
        script_file = config_data.get("script_file_name", "")
        if not script_file:
            logging.getLogger().error("Config file is missing 'script_file_name' field.")
            return False

        strategy_name = script_file.replace(".py", "")
        hb.strategy_file_name = v2_conf
        hb.trading_core.strategy_name = strategy_name

        if headless:
            logging.getLogger().info(f"Starting V2 script strategy: {strategy_name}")
            success = await hb.trading_core.start_strategy(strategy_name, v2_conf, v2_conf)
            if not success:
                logging.getLogger().error("Failed to start strategy")
                return False
        else:
            # UI mode - trigger start via listener
            hb.script_config = v2_conf

    elif config_file_name is not None:
        # Regular strategy with YAML config (V1 flow)
        hb.strategy_file_name = config_file_name.split(".")[0]  # Remove .yml extension

        try:
            strategy_config = await load_strategy_config_map_from_file(
                STRATEGIES_CONF_DIR_PATH / config_file_name
            )
        except FileNotFoundError:
            logging.getLogger().error(
                f"Strategy config file not found: {STRATEGIES_CONF_DIR_PATH / config_file_name}")
            return False
        except Exception as e:
            logging.getLogger().error(f"Error loading strategy config file: {e}")
            return False

        strategy_name = (
            strategy_config.strategy
            if isinstance(strategy_config, ClientConfigAdapter)
            else strategy_config.get("strategy").value
        )
        hb.trading_core.strategy_name = strategy_name

        if headless:
            logging.getLogger().info(f"Starting regular strategy: {strategy_name}")
            # Pydantic-config v1 strategies (e.g. cross_exchange_market_making) read
            # self.strategy_config_map in their start() — start_strategy() doesn't store the config map
            # object, so set it here (mirrors the UI path's setter -> trading_core.strategy_config_map).
            hb.strategy_config_map = strategy_config
            success = await hb.trading_core.start_strategy(strategy_name, strategy_config, config_file_name)
            if not success:
                logging.getLogger().error("Failed to start strategy")
                return False
        else:
            # UI mode - set properties for UIStartListener
            hb.strategy_config_map = strategy_config
            if not all_configs_complete(strategy_config, hb.client_config_map):
                hb.status()

    return True


async def bootstrap_application(
    client_config_map,
    secrets_manager,
    *,
    strategy_file_name: str = "kairos",
    override_log_level: Optional[str] = None,
    headless: bool = False,
    mqtt_autostart: bool = False,
    silence_console: bool = False,
) -> Optional[KairosApplication]:
    """Shared boot sequence for the legacy quickstart and the hbot engine: log in, decrypt, write the
    legacy yml files, init logging, read system configs, apply paper-trade settings, and build the
    ``KairosApplication``. Returns the app, or ``None`` on a bad password. The per-caller bits
    (logging name/level, MQTT autostart, console silencing) are explicit params so behavior is identical.
    """
    from kairos import init_logging
    from kairos.client.config.config_helpers import create_yml_files_legacy, read_system_configs_from_yml
    from kairos.client.config.security import Security
    if not Security.login(secrets_manager):
        logging.getLogger().error("Invalid password.")
        return None
    await Security.wait_til_decryption_done()
    await create_yml_files_legacy()
    init_logging("hummingbot_logs.yml", client_config_map,
                 override_log_level=override_log_level, strategy_file_path=strategy_file_name)
    if silence_console:
        silence_console_handlers()
    await read_system_configs_from_yml()
    if mqtt_autostart:
        client_config_map.mqtt_bridge.mqtt_autostart = True
    AllConnectorSettings.initialize_paper_trade_settings(client_config_map.paper_trade.paper_trade_exchanges)
    return KairosApplication.main_application(client_config_map=client_config_map, headless_mode=headless)


def silence_console_handlers() -> None:
    """Remove stdout/stderr (console) log handlers from every logger. Each keeps its file_handler, so the
    structured log is unaffected; this stops the console stream from duplicating into a redirected log
    (used by the detached engine, whose stdout/stderr go to bot.log)."""
    import sys

    from kairos.logger.cli_handler import CLIHandler
    loggers = [logging.getLogger()] + [logging.getLogger(n) for n in list(logging.root.manager.loggerDict)]
    for lg in loggers:
        for handler in list(getattr(lg, "handlers", [])):
            if isinstance(handler, CLIHandler) or (
                    isinstance(handler, logging.StreamHandler)
                    and getattr(handler, "stream", None) in (sys.stdout, sys.stderr)):
                lg.removeHandler(handler)
