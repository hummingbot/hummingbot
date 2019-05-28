#!/usr/bin/env python

import asyncio
import aioconsole
import logging
from typing import Dict


async def start_management_console(local_vars: Dict = locals(),
                                   host: str = "localhost",
                                   port: int = 8211,
                                   banner: str = "hummingbot") -> asyncio.base_events.Server:
    def factory_method(*args, **kwargs):
        from aioconsole.code import AsynchronousConsole
        return AsynchronousConsole(locals=local_vars, *args, **kwargs)

    retval = await aioconsole.start_interactive_server(host=host, port=port, banner=banner,
                                                       factory=factory_method)
    logging.getLogger(__name__).info(f"Started debug console at {host}:{port}.")
    return retval
