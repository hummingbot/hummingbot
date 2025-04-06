"""A sync client for interacting with the rippled WebSocket API."""

from __future__ import annotations

import asyncio
from concurrent.futures import CancelledError, TimeoutError
from threading import Thread
from types import TracebackType
from typing import Any, Dict, Iterator, Optional, Type, Union, cast

from typing_extensions import Self

from xrpl.asyncio.clients.client import REQUEST_TIMEOUT
from xrpl.asyncio.clients.exceptions import XRPLWebsocketException
from xrpl.asyncio.clients.websocket_base import WebsocketBase
from xrpl.clients.sync_client import SyncClient
from xrpl.models.requests.request import Request
from xrpl.models.response import Response


class WebsocketClient(SyncClient, WebsocketBase):
    """
    A sync client for interacting with the rippled WebSocket API.

    Instead of calling ``open`` and ``close`` yourself, you
    can use a context like so::

        with WebsocketClient(url) as client:
            # inside the context the client is open
        # after exiting the context, the client is closed

    Doing this will open and close the client for you and is
    preferred.

    NOTE: if you are not using subscriptions or other WebSocket-only
    features of rippled, you may not need to do anything other than
    open the client and make requests::

        from xrpl.clients import WebsocketClient
        from xrpl.ledger import get_fee
        from xrpl.models import Fee


        with WebsocketClient(url) as client:
            # using helper functions
            print(get_fee(client))

            # using raw requests yourself
            print(client.request(Fee())

    However, if you are using some functionality that makes use of
    subscriptions or other "websocket-y" things, you can iterate over
    the client like so to read incoming messages::

        with WebsocketClient(url) as client:
            # inside the context the client is open
            for message in client:
                # do something with a message
        # after exiting the context, the client is closed

    NOTE: doing the above will cause the client to listen for
    messages indefinitely. For this reason, ``WebsocketClient``
    takes an optional ``timeout`` parameter which will stop
    iterating on messages if none are received in that timeframe.
    Generally, if you have complex needs with python, xrpl, and
    websockets, you should consider using the ``asyncio`` support
    provided by this library and the ``xrpl.asyncio.clients.AsyncWebsocketClient``
    instead.
    """

    def __init__(
        self: Self, url: str, timeout: Optional[Union[int, float]] = None
    ) -> None:
        """
        Constructs a WebsocketClient.

        Arguments:
            url: The URL of the rippled node to submit requests to.
            timeout: Maximum seconds to wait for a new message when
                iterating. A value of 0 or None will result in no limit.
                If this limit is met, iteration will stop.
        """
        self.timeout = timeout
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[Thread] = None
        super().__init__(url)

    def is_open(self: Self) -> bool:
        """
        Returns whether the client is currently open.

        Returns:
            True if the client is currently open, False otherwise.
        """
        return self._loop is not None and self._thread is not None and super().is_open()

    def open(self: Self) -> None:
        """Connects the client to the Web Socket API at the given URL."""
        if self.is_open():
            return

        # make a new asyncio event loop
        self._loop = asyncio.new_event_loop()

        # create and start a thread to run that event loop
        self._thread = Thread(
            target=self._loop.run_forever,
            daemon=True,
        )
        self._thread.start()

        # run WebsocketBase._do_open on the event loop of the child thread and
        # wait for it to finish
        asyncio.run_coroutine_threadsafe(self._do_open(), self._loop).result()

    def close(self: Self) -> None:
        """Closes the connection."""
        if not self.is_open():
            return

        # run WebsocketBase._do_close on the event loop of the child thread and
        # wait for it to finish
        asyncio.run_coroutine_threadsafe(
            self._do_close(), cast(asyncio.AbstractEventLoop, self._loop)
        ).result()

        # request the child thread to stop the loop and wait for it to
        # terminate
        cast(asyncio.AbstractEventLoop, self._loop).call_soon_threadsafe(
            cast(asyncio.AbstractEventLoop, self._loop).stop
        )
        cast(Thread, self._thread).join()

        # close the stopped loop
        cast(asyncio.AbstractEventLoop, self._loop).close()

        # clear state
        self._loop = None
        self._thread = None

    def __enter__(self: Self) -> Self:
        """
        Enters a context after opening itself.

        Returns:
            The opened client.
        """
        self.open()
        return self

    def __exit__(
        self: Self,
        _exc_type: Type[BaseException],
        _exc_val: BaseException,
        _trace: TracebackType,
    ) -> None:
        """Exits a context after closing itself."""
        self.close()

    def __iter__(self: Self) -> Iterator[Dict[str, Any]]:
        """
        Iterate on received messages. This iterator will block until
        a message is received. If no message is received within
        `self.timeout` seconds then the iterator will exit. If
        `self.timeout` is `None` or `0` then the iterator will block
        indefinitely for the next message.

        Yields:
            The message at the top of the queue.
        """
        while self.is_open():
            future = asyncio.run_coroutine_threadsafe(
                self._do_pop_message(), cast(asyncio.AbstractEventLoop, self._loop)
            )
            try:
                yield future.result(self.timeout)
            except TimeoutError:
                # in this case, the future reached its timeout. we can safely
                # cancel and stop listening
                future.cancel()
                break
            except CancelledError:
                # in this case, the future was cancelled by someone else. we
                # stop listening but don't need to cancel it
                break

    def send(self: Self, request: Request) -> None:
        """
        Submit the request represented by the request to the
        rippled node specified by this client's URL. Unlike ``request``,
        ``send`` does not wait for this request's response. In many cases
        it may be more convenient to use ``request``.

        Arguments:
            request: A Request object representing information about a rippled request.

        Raises:
            XRPLWebsocketException: If there is already an open request by the
                request's ID, or if this WebsocketClient is not open.
        """
        if not self.is_open():
            raise XRPLWebsocketException("Websocket is not open")
        asyncio.run_coroutine_threadsafe(
            self._do_send(request), cast(asyncio.AbstractEventLoop, self._loop)
        ).result()

    async def _request_impl(
        self: Self, request: Request, *, timeout: float = REQUEST_TIMEOUT
    ) -> Response:
        """
        ``_request_impl`` implementation for sync websockets that ensures the
        ``WebsocketBase._do_request_impl`` implementation is run on the other thread.

        Arguments:
            request: An object representing information about a rippled request.

        Returns:
            The response from the server, as a Response object.

        Raises:
            XRPLWebsocketException: If there is already an open request by the
                request's ID, or if this WebsocketClient is not open.

        :meta private:
        """
        if not self.is_open():
            raise XRPLWebsocketException("Websocket is not open")

        # it's unusual to write an async function that has no `await` and also
        # has no `async with` or `async for` but in this case that's
        # exactly what we want. the reason we need this is that the helper
        # functions all expect async functions, but since this
        # is a sync client we want to completely block until the request is
        # complete. also, `asyncio.run_coroutine_threadsafe` returns a
        # concurrent.futures.Future which is not awaitable.
        #
        # when this is run via `await client._request_impl`, it will
        # completely block the main thread until completed,
        # just as if it were not async.
        return asyncio.run_coroutine_threadsafe(
            self._do_request_impl(request, timeout),
            cast(asyncio.AbstractEventLoop, self._loop),
        ).result()
