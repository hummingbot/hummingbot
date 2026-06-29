#!/usr/bin/env python

import argparse
import asyncio
import logging
import os
from typing import Coroutine, List

import path_util  # noqa: F401

from bin.hummingbot import UIStartListener, detect_available_port
from hummingbot import init_logging
from hummingbot.cli.runner import (
    autofix_permissions,
    bootstrap_application,
    load_and_start_strategy,
    wait_for_gateway_ready,
)
from hummingbot.client.config.config_crypt import BaseSecretsManager, ETHKeyFileSecretManger
from hummingbot.client.config.config_helpers import load_client_config_map_from_file
from hummingbot.client.hummingbot_application import HummingbotApplication
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
        self.add_argument("--v2",
                          type=str,
                          required=False,
                          dest="v2_conf",
                          help="V2 strategy config file name (from conf/scripts/).")
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


async def quick_start(args: argparse.Namespace, secrets_manager: BaseSecretsManager):
    """Start Hummingbot using unified HummingbotApplication in either UI or headless mode."""
    client_config_map = load_client_config_map_from_file()

    if args.auto_set_permissions is not None:
        autofix_permissions(args.auto_set_permissions)

    # Shared boot (login, yml, basic logging, system configs, paper-trade, build app). Logging is
    # re-initialized later in run_application with the strategy file name. MQTT autostarts only headless.
    hb = await bootstrap_application(client_config_map, secrets_manager,
                                     headless=args.headless, mqtt_autostart=args.headless)
    if hb is None:
        return

    # Load and start strategy if provided
    if args.v2_conf is not None or args.config_file_name is not None:
        success = await load_and_start_strategy(
            hb,
            config_file_name=args.config_file_name,
            v2_conf=args.v2_conf,
            headless=bool(args.headless),
        )
        if not success:
            logging.getLogger().error("Failed to load strategy. Exiting.")
            raise SystemExit(1)

    await wait_for_gateway_ready(hb)

    # Run the application
    await run_application(hb, args, client_config_map)


async def run_application(hb: HummingbotApplication, args: argparse.Namespace, client_config_map):
    """Run the application in headless or UI mode."""
    if args.headless:
        # Re-initialize logging with proper strategy file name for headless mode
        log_file_name = hb.strategy_file_name.split(".")[0] if hb.strategy_file_name else "hummingbot"
        init_logging("hummingbot_logs.yml", hb.client_config_map,
                     override_log_level=hb.client_config_map.log_level,
                     strategy_file_path=log_file_name)
        await hb.run()
    else:
        # Set up UI mode with start listener
        start_listener: UIStartListener = UIStartListener(
            hb,
            is_script=args.v2_conf is not None,
            script_config=getattr(hb, 'script_config', None),
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

    if args.v2_conf is None and len(os.environ.get("SCRIPT_CONFIG", "")) > 0:
        args.v2_conf = os.environ["SCRIPT_CONFIG"]

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
