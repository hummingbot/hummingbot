#!/usr/bin/env python

import argparse
import asyncio
import grp
import logging
import os
import pwd
import subprocess
from pathlib import Path
from typing import (
    Coroutine,
    List,
)

import path_util        # noqa: F401
from bin.hummingbot import (
    detect_available_port,
    UIStartListener,
)
from hummingbot import init_logging
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.config_helpers import (
    create_yml_files,
    read_system_configs_from_yml,
    update_strategy_config_map_from_file,
    all_configs_complete,
)
from hummingbot.client.ui import login_prompt
from hummingbot.core.event.events import HummingbotUIEvent
from hummingbot.core.gateway import start_existing_gateway_container
from hummingbot.core.management.console import start_management_console
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.client.settings import AllConnectorSettings, CONF_FILE_PATH
from hummingbot.client.config.security import Security

from bin.docker_connection import fork_and_start


class CmdlineParser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__()
        self.add_argument("--config-file-name", "-f",
                          type=str,
                          required=False,
                          help="Specify a file in `conf/` to load as the strategy config file.")
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


async def quick_start(args: argparse.Namespace):
    config_file_name = args.config_file_name
    password = args.config_password

    if args.auto_set_permissions is not None:
        autofix_permissions(args.auto_set_permissions)

    if password is not None and not Security.login(password):
        logging.getLogger().error("Invalid password.")
        return

    await Security.wait_til_decryption_done()
    await create_yml_files()
    init_logging("hummingbot_logs.yml")
    await read_system_configs_from_yml()

    AllConnectorSettings.initialize_paper_trade_settings(global_config_map.get("paper_trade_exchanges").value)

    hb = HummingbotApplication.main_application()
    # Todo: validate strategy and config_file_name before assinging

    if config_file_name is not None:
        hb.strategy_file_name = config_file_name
        hb.strategy_name = await update_strategy_config_map_from_file(os.path.join(CONF_FILE_PATH, config_file_name))

    # To ensure quickstart runs with the default value of False for kill_switch_enabled if not present
    if not global_config_map.get("kill_switch_enabled"):
        global_config_map.get("kill_switch_enabled").value = False

    if hb.strategy_name and hb.strategy_file_name:
        if not all_configs_complete(hb.strategy_name):
            hb.status()

    # The listener needs to have a named variable for keeping reference, since the event listener system
    # uses weak references to remove unneeded listeners.
    start_listener: UIStartListener = UIStartListener(hb)
    hb.app.add_listener(HummingbotUIEvent.Start, start_listener)

    tasks: List[Coroutine] = [hb.run(), start_existing_gateway_container()]
    if global_config_map.get("debug_console").value:
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
    if args.config_password is None and len(os.environ.get("CONFIG_PASSWORD", "")) > 0:
        args.config_password = os.environ["CONFIG_PASSWORD"]

    # If no password is given from the command line, prompt for one.
    if args.config_password is None:
        if not login_prompt():
            return

    asyncio.get_event_loop().run_until_complete(quick_start(args))


if __name__ == "__main__":
    fork_and_start(main)
