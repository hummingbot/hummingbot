from __future__ import annotations

import asyncio
import logging
import warnings
from contextlib import asynccontextmanager, suppress
from decimal import Decimal
from functools import partial
from itertools import cycle
from random import randint
from types import TracebackType
from typing import Any, AsyncContextManager, AsyncIterable, AsyncIterator, Callable, Iterator, List, Optional, TypeVar

import aiohttp
import simplejson as json
from asyncstdlib import chain as chain_async
from multidict import CIMultiDictProxy

_log = logging.getLogger(__name__)

T = TypeVar("T")


class ClientResponse:
    def __init__(self, response: aiohttp.ClientResponse) -> None:
        self._response = response

    @property
    def status(self) -> int:
        return self._response.status

    @property
    def headers(self) -> CIMultiDictProxy:
        return self._response.headers

    async def text(self) -> str:
        return await self._response.text()

    async def json(self) -> Any:
        return await self._response.json(loads=partial(json.loads, use_decimal=True, parse_constant=Decimal))

    def raise_for_status(self) -> None:
        self._response.raise_for_status()


# Adds logging to aiohttp client session.
# https://stackoverflow.com/a/45590516/1466456
# Note that aiohttp client session is not meant to be extended.
# https://github.com/aio-libs/aiohttp/issues/3185
class ClientSession:
    def __init__(
        self,
        raise_for_status: Optional[bool] = None,
        name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self._raise_for_status = raise_for_status
        self._name = name
        self._session = aiohttp.ClientSession(**kwargs)

    async def __aenter__(self) -> ClientSession:
        await self._session.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self._session.__aexit__(exc_type, exc, tb)

    def __del__(self, _warnings: Any = warnings) -> None:
        try:
            if not self._session.closed and self._name:
                _log.error(f"{self._name} unclosed client session.")
        except AttributeError:
            pass

    @asynccontextmanager
    async def request(
        self,
        method: str,
        url: str,
        name: Optional[str] = None,
        raise_for_status: Optional[bool] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ClientResponse]:
        name = name or _rand_id()
        _log.info(f"Req {name} {method} {url}.")
        _log.debug(kwargs)
        async with self._session.request(method, url, **kwargs) as res:
            _log.info(f"Res {name} {res.status} {res.reason}.")
            content = {"headers": res.headers, "body": await res.text()}
            _log.debug(content)
            if raise_for_status or (raise_for_status is None and self._raise_for_status):
                res.raise_for_status()
            yield ClientResponse(res)

    @asynccontextmanager
    async def ws_connect(
        self, url: str, name: Optional[str] = None, **kwargs: Any
    ) -> AsyncIterator[ClientWebSocketResponse]:
        name = name or _rand_id()
        _log.info(f"Req {name} WS {url}: {kwargs}.")
        async with self._session.ws_connect(url, **kwargs) as ws:
            _log.info(f"Res {name} closed: {ws.closed} close code: {ws.close_code}.")
            yield ClientWebSocketResponse(ws, name)


class ClientWebSocketResponse:
    def __init__(self, client_ws_response: aiohttp.ClientWebSocketResponse, name: str) -> None:
        self._client_ws_response = client_ws_response
        self._name = name

    def __aiter__(self) -> ClientWebSocketResponse:
        return self

    async def __anext__(self) -> aiohttp.WSMessage:
        msg = await self._client_ws_response.__anext__()
        _log.debug(f"{self._name} {msg}.")
        return msg

    async def send_json(self, data: Any) -> None:
        _log.debug(f"{self._name} {data}.")
        await self._client_ws_response.send_json(data)

    async def close(self) -> None:
        await self._client_ws_response.close()

    async def receive(self) -> aiohttp.WSMessage:
        msg = await self._client_ws_response.receive()
        _log.debug(f"{self._name} {msg}")
        return msg


@asynccontextmanager
async def connect_refreshing_stream(
    session: ClientSession,
    url: str,
    interval: float,
    loads: Callable[[str], Any],
    take_until: Callable[[Any, Any], bool],
    name: Optional[str] = None,
    raise_on_disconnect: bool = False,
) -> AsyncIterator[AsyncIterable[Any]]:
    """
    Streams messages over WebSocket. The connection is restarted every `interval` seconds.
    Ensures no data is lost during restart when switching from one connection to another.
    """
    name = name or _rand_id()
    counter = cycle(range(0, 10))
    ctx, to_close_ctx = None, None
    timeout_task, receive_task = None, None

    async def inner() -> AsyncIterable[Any]:
        nonlocal ctx, to_close_ctx
        nonlocal timeout_task, receive_task
        assert ctx
        while True:
            to_close_ctx = None
            timeout_task = asyncio.create_task(asyncio.sleep(interval))
            while True:
                receive_task = asyncio.create_task(_receive(ctx.ws))
                done, _pending = await asyncio.wait((receive_task, timeout_task), return_when=asyncio.FIRST_COMPLETED)

                if timeout_task in done:
                    _log.info(f"Refreshing ws {ctx.name} connection.")
                    to_close_ctx = ctx
                    ctx = await _WSConnectionContext.connect(session, url, name, counter)

                    if receive_task.done():
                        new_msg = await _receive(ctx.ws)
                        assert new_msg.type is aiohttp.WSMsgType.TEXT
                        new_data = loads(new_msg.data)
                        async for old_msg in chain_async(_resolved_stream(receive_task.result()), to_close_ctx.ws):
                            if old_msg.type is aiohttp.WSMsgType.CLOSED:
                                break
                            old_data = loads(old_msg.data)
                            if take_until(old_data, new_data):
                                yield old_data
                            else:
                                break
                        yield new_data

                    await to_close_ctx.close()
                    break

                msg = receive_task.result()
                if msg.type is aiohttp.WSMsgType.CLOSED:
                    if raise_on_disconnect:
                        _log.warning(f"Server closed ws {ctx.name} connection; data: {msg.data}; raising exception.")
                        raise aiohttp.WebSocketError(
                            aiohttp.WSCloseCode.GOING_AWAY,
                            "Server unexpectedly closed WS connection.",
                        )
                    else:
                        _log.warning(f"Server closed ws {ctx.name} connection; data: {msg.data}; reconnecting.")
                        timeout_task.cancel()
                        with suppress(asyncio.CancelledError):
                            await asyncio.gather(ctx.close(), timeout_task)
                        ctx = await _WSConnectionContext.connect(session, url, name, counter)
                        break

                yield loads(msg.data)

    try:
        ctx = await _WSConnectionContext.connect(session, url, name, counter)
        yield inner()
    finally:
        tasks: List[asyncio.Task] = []
        if receive_task:
            tasks.append(receive_task)
        if timeout_task:
            tasks.append(timeout_task)
        for task in tasks:
            task.cancel()
        with suppress(asyncio.CancelledError):
            await asyncio.gather(*tasks)
        if ctx:
            await ctx.close()
        if to_close_ctx:
            await to_close_ctx.close()


async def _receive(ws: ClientWebSocketResponse) -> aiohttp.WSMessage:
    while True:
        msg = await ws.receive()
        if msg.type in [aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.CLOSED]:
            return msg
        # Ping is handled implicitly by aiohttp because `autoping=True`. It will never reach here.
        # Close is handled implicitly by aiohttp because `autoclose=True`. It will reach here.
        if msg.type in [aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSE]:
            continue
        raise NotImplementedError(f"Unhandled WS message. Type: {msg.type}; data: {msg.data}.")


class _WSConnectionContext:
    name: str
    conn: AsyncContextManager[ClientWebSocketResponse]
    ws: ClientWebSocketResponse

    @staticmethod
    async def connect(session: ClientSession, url: str, name: str, counter: Iterator[int]) -> _WSConnectionContext:
        name = f"{name}-{next(counter)}"
        conn = session.ws_connect(url, name=name)
        ws = await conn.__aenter__()
        ctx = _WSConnectionContext()
        ctx.name = name
        ctx.conn = conn
        ctx.ws = ws
        return ctx

    async def close(self) -> None:
        await self.ws.close()
        await self.conn.__aexit__(None, None, None)


def _rand_id() -> str:
    return str(randint(100000, 999999))


async def _resolved_stream(*results: T) -> AsyncIterable[T]:
    for result in results:
        yield result
