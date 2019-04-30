#!/usr/bin/env python

if "hummingbot-dist" in __file__:
    # Dist environment.
    import os
    import sys
    sys.path.append(sys.path.pop(0))
    sys.path.insert(0, os.getcwd())

    import hummingbot;hummingbot.set_prefix_path(os.getcwd())
else:
    # Dev environment.
    from os.path import join, realpath
    import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

import logging
import asyncio
from typing import (
    List,
    Coroutine
)

from hummingbot import init_logging
from hummingbot.cli.hummingbot_application import HummingbotApplication
from hummingbot.cli.config.global_config_map import global_config_map
from hummingbot.cli.config.in_memory_config_map import in_memory_config_map
from hummingbot.cli.config.config_helpers import (
    create_yml_files,
    read_configs_from_yml
)
from hummingbot.cli.ui.stdout_redirection import patch_stdout
from hummingbot.cli.utils.wallet_setup import unlock_wallet


STRATEGY = "<INSERT_STRATEGY>"
STRATEGY_PATH = "<INSERT_STRATEGY_PATH>"
WALLET_PUBLIC_KEY = "<INSERT_WALLET_PUBLIC_KEY>"
WALLET_PASSWORD = "<INSERT_WALLET_PASSWORD>"


async def main():
    await create_yml_files()
    init_logging("hummingbot_logs.yml")
    read_configs_from_yml()
    hb = HummingbotApplication()
    hb.acct = unlock_wallet(public_key=WALLET_PUBLIC_KEY, password=WALLET_PASSWORD)

    with patch_stdout(log_field=hb.app.log_field):
        init_logging("hummingbot_logs.yml", override_log_level=global_config_map.get("log_level").value)
        logging.getLogger().info("____DEV_MODE__start_directly__")

        in_memory_config_map.get("strategy").value = STRATEGY
        in_memory_config_map.get("strategy").validate(STRATEGY)
        in_memory_config_map.get("strategy_file_path").value = STRATEGY_PATH
        in_memory_config_map.get("strategy_file_path").validate(STRATEGY_PATH)
        global_config_map.get("wallet").value = WALLET_PUBLIC_KEY

        tasks: List[Coroutine] = [hb.run()]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    ev_loop.run_until_complete(main())
