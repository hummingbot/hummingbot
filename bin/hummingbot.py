#!/usr/bin/env python

import asyncio
from typing import Coroutine, List, Optional
from weakref import ReferenceType, ref

import path_util  # noqa: F401

from hummingbot import chdir_to_data_directory, init_logging
from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    create_yml_files_legacy,
    load_client_config_map_from_file,
    write_config_to_yml,
)
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.client.ui import login_prompt
from hummingbot.client.ui.style import load_style
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.events import HummingbotUIEvent
from hummingbot.core.utils import detect_available_port
from hummingbot.core.utils.async_utils import safe_gather


class UIStartListener(EventListener):
    def __init__(self, hummingbot_app: HummingbotApplication, is_script: Optional[bool] = False, is_quickstart: Optional[bool] = False):
        super().__init__()
        self._hb_ref: ReferenceType = ref(hummingbot_app)
        self._is_script = is_script
        self._is_quickstart = is_quickstart

    def __call__(self, _):
        asyncio.create_task(self.ui_start_handler())

    @property
    def hummingbot_app(self) -> HummingbotApplication:
        return self._hb_ref()

    async def ui_start_handler(self):
        hb: HummingbotApplication = self.hummingbot_app
        if hb.strategy_name is not None:
            if not self._is_script:
                write_config_to_yml(hb.strategy_config_map, hb.strategy_file_name, hb.client_config_map)
            hb.start(log_level=hb.client_config_map.log_level,
                     script=hb.strategy_name if self._is_script else None,
                     is_quickstart=self._is_quickstart)


async def main_async(client_config_map: ClientConfigAdapter):
    await create_yml_files_legacy()

    # This init_logging() call is important, to skip over the missing config warnings.
    init_logging("hummingbot_logs.yml", client_config_map)

    AllConnectorSettings.initialize_paper_trade_settings(client_config_map.paper_trade.paper_trade_exchanges)

    hb = HummingbotApplication.main_application(client_config_map)

    # The listener needs to have a named variable for keeping reference, since the event listener system
    # uses weak references to remove unneeded listeners.
    start_listener: UIStartListener = UIStartListener(hb)
    hb.app.add_listener(HummingbotUIEvent.Start, start_listener)

    tasks: List[Coroutine] = [hb.run()]
    if client_config_map.debug_console:
        if not hasattr(__builtins__, "help"):
            import _sitebuiltins
            __builtins__["help"] = _sitebuiltins._Helper()

        from hummingbot.core.management.console import start_management_console
        management_port: int = detect_available_port(8211)
        tasks.append(start_management_console(locals(), host="localhost", port=management_port))
    await safe_gather(*tasks)


def main():
    chdir_to_data_directory()
    secrets_manager_cls = ETHKeyFileSecretManger

    try:
        ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    except Exception:
        ev_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(ev_loop)

    client_config_map = load_client_config_map_from_file()
    if login_prompt(secrets_manager_cls, style=load_style(client_config_map)):
        ev_loop.run_until_complete(main_async(client_config_map))


if __name__ == "__main__":
    main()
