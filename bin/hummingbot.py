#!/usr/bin/env python

import asyncio
from typing import (
    List,
    Coroutine,
)
from weakref import (
    ref,
    ReferenceType,
)

import path_util  # noqa: F401
from hummingbot import (
    chdir_to_data_directory,
    init_logging,
)
from hummingbot.client.config.config_helpers import (
    create_yml_files,
    read_system_configs_from_yml,
    write_config_to_yml,
)
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.client.ui import login_prompt
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.events import HummingbotUIEvent
from hummingbot.core.gateway import start_existing_gateway_container
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils import detect_available_port

from bin.docker_connection import fork_and_start


class UIStartListener(EventListener):
    def __init__(self, hummingbot_app: HummingbotApplication):
        super().__init__()
        self._hb_ref: ReferenceType = ref(hummingbot_app)

    def __call__(self, _):
        asyncio.create_task(self.ui_start_handler())

    @property
    def hummingbot_app(self) -> HummingbotApplication:
        return self._hb_ref()

    async def ui_start_handler(self):
        hb: HummingbotApplication = self.hummingbot_app

        if hb.strategy_file_name is not None and hb.strategy_name is not None:
            await write_config_to_yml(hb.strategy_name, hb.strategy_file_name)
            hb.start(global_config_map.get("log_level").value)


async def main_async():
    await create_yml_files()

    # This init_logging() call is important, to skip over the missing config warnings.
    init_logging("hummingbot_logs.yml")

    await read_system_configs_from_yml()

    AllConnectorSettings.initialize_paper_trade_settings(global_config_map.get("paper_trade_exchanges").value)

    hb = HummingbotApplication.main_application()

    # The listener needs to have a named variable for keeping reference, since the event listener system
    # uses weak references to remove unneeded listeners.
    start_listener: UIStartListener = UIStartListener(hb)
    hb.app.add_listener(HummingbotUIEvent.Start, start_listener)

    tasks: List[Coroutine] = [hb.run(), start_existing_gateway_container()]
    if global_config_map.get("debug_console").value:
        if not hasattr(__builtins__, "help"):
            import _sitebuiltins
            __builtins__.help = _sitebuiltins._Helper()

        from hummingbot.core.management.console import start_management_console
        management_port: int = detect_available_port(8211)
        tasks.append(start_management_console(locals(), host="localhost", port=management_port))
    await safe_gather(*tasks)


def main():
    chdir_to_data_directory()
    if login_prompt():
        ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        ev_loop.run_until_complete(main_async())


if __name__ == "__main__":
    fork_and_start(main)
