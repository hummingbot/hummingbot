#!/usr/bin/env python

import path_util        # noqa: F401
import asyncio
import logging
from typing import (
    Coroutine,
    List,
)

from hummingbot import (
    check_dev_mode,
    init_logging,
)
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.in_memory_config_map import in_memory_config_map
from hummingbot.client.config.config_helpers import (
    create_yml_files,
    load_required_configs,
    read_configs_from_yml,
)
from hummingbot.client.ui.stdout_redirection import patch_stdout
from hummingbot.client.ui.parser import ThrowingArgumentParser
from hummingbot.client.settings import STRATEGIES
from hummingbot.core.utils.wallet_setup import unlock_wallet
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.management.console import start_management_console
from bin.hummingbot import (
    detect_available_port,
    main as normal_start,
)
from hummingbot.client.config.config_helpers import write_config_to_yml


class CmdlineParser(ThrowingArgumentParser):
    def __init__(self):
        super().__init__()
        self.add_argument("--strategy", "-s",
                          type=str,
                          choices=STRATEGIES,
                          required=True,
                          help="Choose the strategy you would like to run.")
        self.add_argument("--config-file-name", "-f",
                          type=str,
                          required=True,
                          help="Specify a file in `conf/` to load as the strategy config file.")
        self.add_argument("--wallet", "-w",
                          type=str,
                          required=False,
                          help="Specify the wallet public key you would like to use.")
        self.add_argument("--config-password", "--wallet-password", "-p",
                          type=str,
                          required=False,
                          help="Specify the password to unlock your encrypted files and wallets.")


async def quick_start():
    try:
        args = CmdlineParser().parse_args()

        strategy = args.strategy
        config_file_name = args.config_file_name
        wallet = args.wallet
        password = args.config_password

        await create_yml_files()
        init_logging("hummingbot_logs.yml")
        read_configs_from_yml()
        hb = HummingbotApplication.main_application()

        in_memory_config_map.get("password").value = password
        in_memory_config_map.get("strategy").value = strategy
        in_memory_config_map.get("strategy").validate(strategy)
        in_memory_config_map.get("strategy_file_path").value = config_file_name
        in_memory_config_map.get("strategy_file_path").validate(config_file_name)

        # To ensure quickstart runs with the default value of False for kill_switch_enabled if not present
        if not global_config_map.get("kill_switch_enabled"):
            global_config_map.get("kill_switch_enabled").value = False

        if wallet and password:
            global_config_map.get("wallet").value = wallet
            hb.acct = unlock_wallet(public_key=wallet, password=password)

        if not hb.config_complete:
            config_map = load_required_configs()
            empty_configs = [key for key, config in config_map.items() if config.value is None and config.required]
            empty_config_description: str = "\n- ".join([""] + empty_configs)
            raise ValueError(f"Missing empty configs: {empty_config_description}\n")

        with patch_stdout(log_field=hb.app.log_field):
            dev_mode = check_dev_mode()
            if dev_mode:
                hb.app.log("Running from dev branches. Full remote logging will be enabled.")

            log_level = global_config_map.get("log_level").value
            init_logging("hummingbot_logs.yml",
                         override_log_level=log_level,
                         dev_mode=dev_mode,
                         strategy_file_path=config_file_name)
            await write_config_to_yml()
            hb.start(log_level)

            tasks: List[Coroutine] = [hb.run()]
            if global_config_map.get("debug_console").value:
                management_port: int = detect_available_port(8211)
                tasks.append(start_management_console(locals(), host="localhost", port=management_port))
            await safe_gather(*tasks)

    except Exception as e:
        # In case of quick start failure, start the bot normally to allow further configuration
        logging.getLogger().warning(f"Bot config incomplete: {str(e)}. Starting normally...")
        await normal_start()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(quick_start())
