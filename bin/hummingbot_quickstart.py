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
from hummingbot.client.settings import STRATEGIES_CONF_DIR_PATH, AllConnectorSettings
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
    config_file_name = args.config_file_name
    client_config_map = load_client_config_map_from_file()

    if args.auto_set_permissions is not None:
        autofix_permissions(args.auto_set_permissions)

    if not Security.login(secrets_manager):
        logging.getLogger().error("Invalid password.")
        return

    await Security.wait_til_decryption_done()
    await create_yml_files_legacy()
    init_logging("hummingbot_logs.yml", client_config_map)
    await read_system_configs_from_yml()

    AllConnectorSettings.initialize_paper_trade_settings(client_config_map.paper_trade.paper_trade_exchanges)

    hb = HummingbotApplication.main_application(client_config_map=client_config_map)
    # Todo: validate strategy and config_file_name before assinging

    strategy_config = None
    is_script = False
    script_config = None
    if config_file_name is not None:
        hb.strategy_file_name = config_file_name
        if config_file_name.split(".")[-1] == "py":
            hb.strategy_name = hb.strategy_file_name
            is_script = True
            script_config = args.script_conf if args.script_conf else None
        else:
            strategy_config = await load_strategy_config_map_from_file(
                STRATEGIES_CONF_DIR_PATH / config_file_name
            )
            hb.strategy_name = (
                strategy_config.strategy
                if isinstance(strategy_config, ClientConfigAdapter)
                else strategy_config.get("strategy").value
            )
            hb.strategy_config_map = strategy_config

    if strategy_config is not None:
        if not all_configs_complete(strategy_config, hb.client_config_map):
            hb.status()

    # The listener needs to have a named variable for keeping reference, since the event listener system
    # uses weak references to remove unneeded listeners.
    start_listener: UIStartListener = UIStartListener(hb, is_script=is_script, script_config=script_config,
                                                      is_quickstart=True)
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
        ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    except Exception:
        ev_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(ev_loop)

    ev_loop.run_until_complete(quick_start(args, secrets_manager))


if __name__ == "__main__":
    main()
