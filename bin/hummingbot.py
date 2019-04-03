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
from typing import (
    List,
    Coroutine
)

from hummingbot import (
    init_logging
)

from hummingbot.cli.hummingbot_application import HummingbotApplication
from hummingbot.cli.settings import (
    global_config_map,
    create_yml_files,
    read_configs_from_yml
)
from hummingbot.cli.ui.stdout_redirection import patch_stdout
from hummingbot.management.console import start_management_console


async def main():
    await create_yml_files()
    read_configs_from_yml()

    init_logging("hummingbot_logs.yml")

    hb = HummingbotApplication()
    with patch_stdout(log_field=hb.app.log_field):
        init_logging("hummingbot_logs.yml",
                     override_log_level=global_config_map.get("log_level").value)
        tasks: List[Coroutine] = [hb.run()]
        if global_config_map.get("debug_console").value:
            tasks.append(start_management_console(locals(), host="localhost", port=8211))
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    ev_loop.run_until_complete(main())
