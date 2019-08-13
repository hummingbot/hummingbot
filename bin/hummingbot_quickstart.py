#!/usr/bin/env python

import os
if "hummingbot-dist" in __file__:
    # Dist environment.
    import sys
    sys.path.append(sys.path.pop(0))
    sys.path.insert(0, os.getcwd())
    import hummingbot;hummingbot.set_prefix_path(os.getcwd())
else:
    # Dev environment.
    from os.path import join, realpath
    import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

import argparse
import asyncio
import logging

from hummingbot import init_logging
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.in_memory_config_map import in_memory_config_map
from hummingbot.client.config.config_helpers import (
    create_yml_files,
    read_configs_from_yml
)
from hummingbot.client.ui.stdout_redirection import patch_stdout
from hummingbot.client.settings import STRATEGIES
from hummingbot.core.utils.wallet_setup import unlock_wallet


class CmdlineParser(argparse.ArgumentParser):
    def __init__(self):
        super().__init__()
        self.add_argument("--strategy", "-s",
                          type=str,
                          choices=STRATEGIES,
                          help="Choose the strategy you would like to run.")
        self.add_argument("--config-file-path", "-f",
                          type=str,
                          help="Specify a file in `conf/` to load as the strategy config file.")
        self.add_argument("--wallet", "-w",
                          type=str,
                          required=False,
                          help="Specify the wallet public key you would like to use.")
        self.add_argument("--wallet-password", "-p",
                          type=str,
                          required=False,
                          help="Specify the password if you need to unlock your wallet.")


async def func_wrapper(func):
    func()


async def main():
    try:
        args = CmdlineParser().parse_args()
        os.chdir(os.path.realpath(os.path.join(__file__, "../../")))

        strategy = args.strategy
        config_file_path = args.config_file_path
        wallet = args.wallet
        wallet_password = args.wallet_password

        await create_yml_files()
        init_logging("hummingbot_logs.yml")
        read_configs_from_yml()
        hb = HummingbotApplication()

        if wallet is not None and wallet_password is not None:
            hb.acct = unlock_wallet(public_key=wallet, password=wallet_password)

        in_memory_config_map.get("strategy").value = strategy
        in_memory_config_map.get("strategy").validate(strategy)
        in_memory_config_map.get("strategy_file_path").value = config_file_path
        in_memory_config_map.get("strategy_file_path").validate(config_file_path)
        global_config_map.get("wallet").value = wallet

        empty_configs = hb._get_empty_configs()
        if len(empty_configs) > 0:
            empty_config_description: str = "\n- ".join([""] + empty_configs)
            raise ValueError(f"Missing empty configs: {empty_config_description}\n")

        with patch_stdout(log_field=hb.app.log_field):
            init_logging("hummingbot_logs.yml", override_log_level=global_config_map.get("log_level").value)
            hb.start()
            await asyncio.gather(hb.run())
    except KeyboardInterrupt:
        logging.getLogger().error("KeyboardInterrupt: Aborted.")
    except Exception as e:
        logging.getLogger().error(str(e), exc_info=True)


if __name__ == "__main__":
    ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    ev_loop.run_until_complete(main())
