"""Serve the python console using socket communication."""

import asyncio
import socket
from functools import partial

from . import compat
from . import console


async def handle_connect(reader, writer, factory, banner=None):
    streams = reader, writer
    interface = factory(streams=streams)
    await interface.interact(banner=banner, stop=False, handle_sigint=False)
    writer.close()


async def start_interactive_server(
    factory=console.AsynchronousConsole,
    host=None,
    port=None,
    path=None,
    banner=None,
    *,
    loop=None,
):
    if compat.platform == "win32" and port is None:
        raise ValueError("A TCP port should be provided")
    if (port is None) == (path is None):
        raise ValueError("Either a TCP port or a UDS path should be provided")
    if port is not None:
        # Override asyncio behavior (i.e serve on all interfaces by default)
        host = host or "localhost"
        start_server = partial(asyncio.start_server, host=host, port=port)
    else:
        start_server = partial(asyncio.start_unix_server, path=path)

    client_connected = partial(handle_connect, factory=factory, banner=banner)
    server = await start_server(client_connected)
    return server


async def start_console_server(
    host=None,
    port=None,
    path=None,
    locals=None,
    filename="<console>",
    banner=None,
    prompt_control=None,
    *,
    loop=None,
):
    def factory(streams):
        client_locals = dict(locals) if locals is not None else None
        return console.AsynchronousConsole(
            streams=streams,
            locals=client_locals,
            filename=filename,
            prompt_control=prompt_control,
        )

    server = await start_interactive_server(
        factory, host=host, port=port, path=path, banner=banner, loop=loop
    )
    return server


def print_server(server, name="console", file=None):
    interface = server.sockets[0].getsockname()
    AF_UNIX = None if compat.platform == "win32" else socket.AF_UNIX
    if server.sockets[0].family != AF_UNIX:
        interface = "{}:{}".format(*interface)
    print(f"The {name} is being served on {interface}", file=file)


def run(host=None, port=None, path=None):
    loop = asyncio.get_event_loop()
    coro = start_interactive_server(host=host, port=port, path=path)
    loop.server = loop.run_until_complete(coro)
    print_server(loop.server)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass


def parse_server(server, parser=None):
    try:
        host, port = server.rsplit(":", maxsplit=1)
    except ValueError:
        host, port = "localhost", server
    try:
        port = int(port)
    except (ValueError, TypeError):
        msg = f"{server!r} is not a valid server [HOST:]PORT"
        if not parser:
            raise ValueError(msg)
        parser.error(msg)
    return host, port
