#!/usr/bin/env python

import path_util        # noqa: F401
import argparse
import asyncio
import logging
from typing import (
    Coroutine,
    List,
)
import os
import subprocess

from hummingbot import (
    check_dev_mode,
    init_logging,
)
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.config_helpers import (
    create_yml_files,
    write_config_to_yml,
    read_system_configs_from_yml,
    update_strategy_config_map_from_file,
    all_configs_complete,
)
from hummingbot.client.ui import login_prompt
from hummingbot.client.ui.stdout_redirection import patch_stdout
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.management.console import start_management_console
from bin.hummingbot import (
    detect_available_port,
)
from hummingbot.client.settings import CONF_FILE_PATH, AllConnectorSettings
from hummingbot.client.config.security import Security


class CmdlineParser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__()
        self.add_argument("--config-file-name", "-f",
                          type=str,
                          required=False,
                          help="Specify a file in `conf/` to load as the strategy config file.")
        self.add_argument("--wallet", "-w",
                          type=str,
                          required=False,
                          help="Specify the wallet public key you would like to use.")
        self.add_argument("--config-password", "--wallet-password", "-p",
                          type=str,
                          required=False,
                          help="Specify the password to unlock your encrypted files and wallets.")
        self.add_argument("--auto-set-permissions",
                          type=str,
                          required=False,
                          help="Try to automatically set config / logs / data dir permissions, "
                               "useful for Docker containers.")


def autofix_permissions(user_group_spec: str):
    project_home: str = os.path.realpath(os.path.join(__file__, "../../"))
    subprocess.run(f"cd '{project_home}' && "
                   f"sudo chown -R {user_group_spec} conf/ data/ logs/", capture_output=True, shell=True)


async def quick_start(args):
    config_file_name = args.config_file_name
    wallet = args.wallet
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

    if wallet and password:
        global_config_map.get("ethereum_wallet").value = wallet

    if hb.strategy_name and hb.strategy_file_name:
        if not all_configs_complete(hb.strategy_name):
            hb.status()

    with patch_stdout(log_field=hb.app.log_field):
        dev_mode = check_dev_mode()
        if dev_mode:
            hb.app.log("Running from dev branches. Full remote logging will be enabled.")

        log_level = global_config_map.get("log_level").value
        init_logging("hummingbot_logs.yml",
                     override_log_level=log_level,
                     dev_mode=dev_mode)

        if hb.strategy_file_name is not None and hb.strategy_name is not None:
            await write_config_to_yml(hb.strategy_name, hb.strategy_file_name)
            hb.start(log_level)

        tasks: List[Coroutine] = [hb.run()]
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
    if args.wallet is None and len(os.environ.get("WALLET", "")) > 0:
        args.wallet = os.environ["WALLET"]
    if args.config_password is None and len(os.environ.get("CONFIG_PASSWORD", "")) > 0:
        args.config_password = os.environ["CONFIG_PASSWORD"]

    # If no password is given from the command line, prompt for one.
    if args.config_password is None:
        if not login_prompt():
            return

    asyncio.get_event_loop().run_until_complete(quick_start(args))


if __name__ == "__main__":
    main()
