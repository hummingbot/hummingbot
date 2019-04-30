#!/usr/bin/env python

if "hummingbot-dist" in __file__:
    # Dist environment.
    import os
    import sys
    sys.path.append(sys.path.pop(0))
    sys.path.insert(0, os.getcwd())

    import hummingbot
    hummingbot.set_prefix_path(os.getcwd())
else:
    # Dev environment.
    from os.path import join, realpath
    import sys
    sys.path.insert(0, realpath(join(__file__, "../../")))

import asyncio
import errno
import socket
from typing import (
    List,
    Coroutine
)

from hummingbot import init_logging
from hummingbot.cli.hummingbot_application import HummingbotApplication
from hummingbot.cli.config.global_config_map import global_config_map
from hummingbot.cli.config.config_helpers import (
    create_yml_files,
    read_configs_from_yml
)
from hummingbot.cli.ui.stdout_redirection import patch_stdout
from hummingbot.management.console import start_management_console


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

    read_configs_from_yml()

    hb = HummingbotApplication()
    with patch_stdout(log_field=hb.app.log_field):
        init_logging("hummingbot_logs.yml",
                     override_log_level=global_config_map.get("log_level").value)
        tasks: List[Coroutine] = [hb.run()]
        if global_config_map.get("debug_console").value:
            management_port: int = detect_available_port(8211)
            tasks.append(start_management_console(locals(), host="localhost", port=management_port))
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    ev_loop.run_until_complete(main())
