#!/usr/bin/env python

import argparse
import asyncio
import grp
import logging
import os
import pwd
import subprocess
from pathlib import Path
from typing import Coroutine, List

import path_util  # noqa: F401

from bin.hummingbot import UIStartListener, detect_available_port
from hummingbot import init_logging
from hummingbot.client.command.start_command import GATEWAY_READY_TIMEOUT
from hummingbot.client.config.config_crypt import BaseSecretsManager, ETHKeyFileSecretManger
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    all_configs_complete,
    create_yml_files_legacy,
    load_client_config_map_from_file,
    load_strategy_config_map_from_file,
    read_system_configs_from_yml,
)
from hummingbot.client.config.security import Security
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.client.settings import (
    SCRIPT_STRATEGIES_PATH,
    SCRIPT_STRATEGY_CONF_DIR_PATH,
    STRATEGIES_CONF_DIR_PATH,
    AllConnectorSettings,
)
from hummingbot.client.ui import login_prompt
from hummingbot.client.ui.style import load_style
from hummingbot.core.event.events import HummingbotUIEvent
from hummingbot.core.management.console import start_management_console
from hummingbot.core.utils.async_utils import safe_gather


class CmdlineParser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__()
        self.add_argument("--config-file-name", "-f",
                          type=str,
                          required=False,
                          help="Specify a file in `conf/` to load as the strategy config file.")
        self.add_argument("--script-conf", "-c",
                          type=str,
                          required=False,
                          help="Specify a file in `conf/scripts` to configure a script strategy.")
        self.add_argument("--config-password", "-p",
                          type=str,
                          required=False,
                          help="Specify the password to unlock your encrypted files.")
        self.add_argument("--auto-set-permissions",
                          type=str,
                          required=False,
                          help="Try to automatically set config / logs / data dir permissions, "
                               "useful for Docker containers.")
        self.add_argument("--headless",
                          type=bool,
                          nargs='?',
                          const=True,
                          default=None,
                          help="Run in headless mode without CLI interface.")


def autofix_permissions(user_group_spec: str):
    uid, gid = [sub_str for sub_str in user_group_spec.split(':')]

    uid = int(uid) if uid.isnumeric() else pwd.getpwnam(uid).pw_uid
    gid = int(gid) if gid.isnumeric() else grp.getgrnam(gid).gr_gid

    os.environ["HOME"] = pwd.getpwuid(uid).pw_dir
    project_home: str = os.path.realpath(os.path.join(__file__, "../../"))

    gateway_path: str = Path.home().joinpath(".hummingbot-gateway").as_posix()
    subprocess.run(
        f"cd '{project_home}' && "
        f"sudo chown -R {user_group_spec} conf/ data/ logs/ scripts/ {gateway_path}",
        capture_output=True,
        shell=True
    )
    os.setgid(gid)
    os.setuid(uid)


async def quick_start(args: argparse.Namespace, secrets_manager: BaseSecretsManager):
    """Start Hummingbot using unified HummingbotApplication in either UI or headless mode."""
    client_config_map = load_client_config_map_from_file()

    if args.auto_set_permissions is not None:
        autofix_permissions(args.auto_set_permissions)

    if not Security.login(secrets_manager):
        logging.getLogger().error("Invalid password.")
        return

    await Security.wait_til_decryption_done()
    await create_yml_files_legacy()
    # Initialize logging with basic setup first - will be re-initialized later with correct strategy file name if needed
    init_logging("hummingbot_logs.yml", client_config_map)
    await read_system_configs_from_yml()

    # Automatically enable MQTT autostart for headless mode
    if args.headless:
        client_config_map.mqtt_bridge.mqtt_autostart = True

    AllConnectorSettings.initialize_paper_trade_settings(client_config_map.paper_trade.paper_trade_exchanges)

    # Create unified application that handles both headless and UI modes
    hb = HummingbotApplication.main_application(client_config_map=client_config_map, headless_mode=args.headless)

    # Load and start strategy if provided
    if args.config_file_name is not None:
        success = await load_and_start_strategy(hb, args)
        if not success:
            logging.getLogger().error("Failed to load strategy. Exiting.")
            raise SystemExit(1)

    await wait_for_gateway_ready(hb)

    # Run the application
    await run_application(hb, args, client_config_map)


async def wait_for_gateway_ready(hb):
    """Wait until the gateway is ready before starting the strategy."""
    exchange_settings = [
        AllConnectorSettings.get_connector_settings().get(e, None)
        for e in hb.trading_core.connector_manager.connectors.keys()
    ]
    uses_gateway = any([s.uses_gateway_generic_connector() for s in exchange_settings])
    if not uses_gateway:
        return
    try:
        await asyncio.wait_for(hb._gateway_monitor.ready_event.wait(), timeout=GATEWAY_READY_TIMEOUT)
    except asyncio.TimeoutError:
        logging.getLogger().error(
            f"TimeoutError waiting for gateway service to go online... Please ensure Gateway is configured correctly."
            f"Unable to start strategy {hb.trading_core.strategy_name}. ")
        raise


async def load_and_start_strategy(hb: HummingbotApplication, args: argparse.Namespace,):
    """Load and start strategy based on file type and mode."""
    if args.config_file_name.endswith(".py"):
        # Script strategy
        strategy_name = args.config_file_name.replace(".py", "")
        strategy_config_file = args.script_conf  # Optional config file for script

        # Validate that the script file exists
        script_file_path = SCRIPT_STRATEGIES_PATH / args.config_file_name
        if not script_file_path.exists():
            logging.getLogger().error(f"Script file not found: {script_file_path}")
            return False

        # Validate that the script config file exists if provided
        if strategy_config_file:
            script_config_path = SCRIPT_STRATEGY_CONF_DIR_PATH / strategy_config_file
            if not script_config_path.exists():
                logging.getLogger().error(f"Script config file not found: {script_config_path}")
                return False

        # Set strategy_file_name to config file if provided, otherwise script file (matching start_command logic)
        hb.strategy_file_name = strategy_config_file.split(".")[0] if strategy_config_file else strategy_name
        hb.strategy_name = strategy_name

        if args.headless:
            logging.getLogger().info(f"Starting script strategy: {strategy_name}")
            success = await hb.trading_core.start_strategy(
                strategy_name,
                strategy_config_file,  # Pass config file path if provided
                hb.strategy_file_name + (".yml" if strategy_config_file else ".py")  # Full file name for strategy
            )
            if not success:
                logging.getLogger().error("Failed to start strategy")
                return False
        else:
            # UI mode - set properties for UIStartListener
            if strategy_config_file:
                hb.script_config = strategy_config_file
    else:
        # Regular strategy with YAML config
        hb.strategy_file_name = args.config_file_name.split(".")[0]  # Remove .yml extension

        try:
            strategy_config = await load_strategy_config_map_from_file(
                STRATEGIES_CONF_DIR_PATH / args.config_file_name
            )
        except FileNotFoundError:
            logging.getLogger().error(f"Strategy config file not found: {STRATEGIES_CONF_DIR_PATH / args.config_file_name}")
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

        if args.headless:
            logging.getLogger().info(f"Starting regular strategy: {strategy_name}")
            success = await hb.trading_core.start_strategy(
                strategy_name,
                strategy_config,
                args.config_file_name
            )
            if not success:
                logging.getLogger().error("Failed to start strategy")
                return False
        else:
            # UI mode - set properties for UIStartListener
            hb.strategy_config_map = strategy_config

            # Check if config is complete for UI mode
            if not all_configs_complete(strategy_config, hb.client_config_map):
                hb.status()

    return True


async def run_application(hb: HummingbotApplication, args: argparse.Namespace, client_config_map):
    """Run the application in headless or UI mode."""
    if args.headless:
        # Re-initialize logging with proper strategy file name for headless mode
        from hummingbot import init_logging
        log_file_name = hb.strategy_file_name.split(".")[0] if hb.strategy_file_name else "hummingbot"
        init_logging("hummingbot_logs.yml", hb.client_config_map,
                     override_log_level=hb.client_config_map.log_level,
                     strategy_file_path=log_file_name)
        await hb.run()
    else:
        # Set up UI mode with start listener
        start_listener: UIStartListener = UIStartListener(
            hb,
            is_script=args.config_file_name.endswith(".py") if args.config_file_name else False,
            script_config=hb.script_config,
            is_quickstart=True
        )
        hb.app.add_listener(HummingbotUIEvent.Start, start_listener)

        tasks: List[Coroutine] = [hb.run()]
        if client_config_map.debug_console:
            management_port: int = detect_available_port(8211)
            tasks.append(start_management_console(locals(), host="localhost", port=management_port))

        await safe_gather(*tasks)


def main():
    args = CmdlineParser().parse_args()

    # Parse environment variables from Dockerfile.
    # If an environment variable is not empty and it's not defined in the arguments, then we'll use the environment
    # variable.
    if args.config_file_name is None and len(os.environ.get("CONFIG_FILE_NAME", "")) > 0:
        args.config_file_name = os.environ["CONFIG_FILE_NAME"]

    if args.script_conf is None and len(os.environ.get("SCRIPT_CONFIG", "")) > 0:
        args.script_conf = os.environ["SCRIPT_CONFIG"]

    if args.config_password is None and len(os.environ.get("CONFIG_PASSWORD", "")) > 0:
        args.config_password = os.environ["CONFIG_PASSWORD"]

    if args.headless is None and len(os.environ.get("HEADLESS_MODE", "")) > 0:
        args.headless = os.environ["HEADLESS_MODE"].lower() == "true"

    # If no password is given from the command line, prompt for one.
    secrets_manager_cls = ETHKeyFileSecretManger
    client_config_map = load_client_config_map_from_file()
    if args.config_password is None:
        secrets_manager = login_prompt(secrets_manager_cls, style=load_style(client_config_map))
        if not secrets_manager:
            return
    else:
        secrets_manager = secrets_manager_cls(args.config_password)

    try:
        ev_loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    except RuntimeError:
        ev_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(ev_loop)

    ev_loop.run_until_complete(quick_start(args, secrets_manager))


if __name__ == "__main__":
    main()
