#!/usr/bin/env python

import path_util        # noqa: F401
import asyncio
import errno
import socket

from typing import (
    List,
    Coroutine,
)

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.config_helpers import (
    create_yml_files,
    read_system_configs_from_yml
)
from hummingbot import (
    init_logging,
    check_dev_mode,
    chdir_to_data_directory
)
from hummingbot.client.ui import login_prompt
from hummingbot.client.ui.stdout_redirection import patch_stdout
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.core.utils.async_utils import safe_gather


def detect_available_port(starting_port: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        current_port: int = starting_port
        while current_port < 65535:
            try:
                s.bind(("127.0.0.1", current_port))
                break
            except OSError as e:
                if e.errno == errno.EADDRINUSE:
                    current_port += 1
                    continue
        return current_port


async def main():
    await create_yml_files()

    # This init_logging() call is important, to skip over the missing config warnings.
    init_logging("hummingbot_logs.yml")

    await read_system_configs_from_yml()

    AllConnectorSettings.initialize_paper_trade_settings(global_config_map.get("paper_trade_exchanges").value)

    hb = HummingbotApplication.main_application()

    with patch_stdout(log_field=hb.app.log_field):
        dev_mode = check_dev_mode()
        if dev_mode:
            hb.app.log("Running from dev branches. Full remote logging will be enabled.")
        init_logging("hummingbot_logs.yml",
                     override_log_level=global_config_map.get("log_level").value,
                     dev_mode=dev_mode)
        tasks: List[Coroutine] = [hb.run()]
        if global_config_map.get("debug_console").value:
            if not hasattr(__builtins__, "help"):
                import _sitebuiltins
                __builtins__.help = _sitebuiltins._Helper()

            from hummingbot.core.management.console import start_management_console
            management_port: int = detect_available_port(8211)
            tasks.append(start_management_console(locals(), host="localhost", port=management_port))
        await safe_gather(*tasks)


if __name__ == "__main__":
    chdir_to_data_directory()
    if login_prompt():
        ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        ev_loop.run_until_complete(main())
