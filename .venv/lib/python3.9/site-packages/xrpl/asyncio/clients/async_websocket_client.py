"""A client for interacting with the rippled WebSocket API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import TracebackType
from typing import Any, Dict, Type

from typing_extensions import Self

from xrpl.asyncio.clients.async_client import AsyncClient
from xrpl.asyncio.clients.client import REQUEST_TIMEOUT
from xrpl.asyncio.clients.exceptions import XRPLWebsocketException
from xrpl.asyncio.clients.websocket_base import WebsocketBase
from xrpl.models.requests.request import Request
from xrpl.models.response import Response


class AsyncWebsocketClient(AsyncClient, WebsocketBase):
    """
    An async client for interacting with the rippled WebSocket API.

    Instead of calling ``open`` and ``close`` yourself, you
    can use a context like so::

        async with AsyncWebsocketClient(url) as client:
            # inside the context the client is open
        # after exiting the context, the client is closed

    Doing this will open and close the client for you and is
    preferred.

    NOTE: if you are not using subscriptions or other WebSocket-only
    features of rippled, you may not need to do anything other than
    open the client and make requests::

        from xrpl.asyncio.clients import AsyncWebsocketClient
        from xrpl.asyncio.ledger import get_fee
        from xrpl.models import Fee


        async with AsyncWebsocketClient(url) as client:
            # using helper functions
            print(await get_fee(client))

            # using raw requests yourself
            print(await client.request(Fee())

    However, if you are using some functionality that makes use of
    subscriptions or other "websocket-y" things, you can iterate over
    the client like so to read incoming messages::

        async with AsyncWebsocketClient(url) as client:
            # inside the context the client is open
            async for message in client:
                # do something with a message
        # after exiting the context, the client is closed

    The recommended way to use this client is to set up a Task
    using the ``asyncio`` library to listen to incoming
    messages and do something with them, but the above will
    work fine if you want to listen indefinitely. This is how
    you can use a Task to listen to messages without blocking. Note this
    example can be copied directly into a file and run with no changes::

        import asyncio

        from xrpl.asyncio.clients import AsyncWebsocketClient
        from xrpl.models import Subscribe, Unsubscribe, StreamParameter

        URL = "wss://s.altnet.rippletest.net:51233"


        def on_open():
            print("I have opened a connection!")


        async def on_message(client):
            async for message in client:
                # do something with a message - we'll just print
                print(message)


        def on_close():
            print("I have closed a connection cleanly!")


        def on_error():
            print("An error occurred!")


        async def main():
            # we'll use this to determine if the websocket closed cleanly or
            # not
            error_happened = False

            async with AsyncWebsocketClient(URL) as client:
                try:
                    # here you'll run any code that should happen immediately
                    # after the connection is made. this is equivalent to the
                    # javascript 'open' event
                    on_open()

                    # set up the `on_message` function as a Task
                    # so that it doesn't wait for a response, but
                    # will "awaken" whenever the `asyncio` event
                    # loop toggles to it. this is equivalent to the javascript
                    # 'message' event
                    asyncio.create_task(on_message(client))

                    # now, the `on_message` function will run as if
                    # it were "in the background", doing whatever you
                    # want as soon as it has a message.

                    # now let's subscribe to something. in this case,
                    # we can just use `send` instead of `request`
                    # because we don't really care about the response
                    # since the `on_message` handler will also get it.
                    await client.send(Subscribe(
                        streams=[StreamParameter.LEDGER],
                    ))
                    print("Subscribed to the ledger!")

                    # in the meantime, you can continue to do whatever
                    # you want and the python `asyncio` event loop
                    # will toggle between your code and the listener
                    # as messages are ready. let's just sleep. note,
                    # you need to use `asyncio.sleep` within
                    # async code instead of `time.sleep`, otherwise
                    # you will block all the waiting tasks instead of
                    # just this code path.
                    await asyncio.sleep(50)

                    # now that we're done, we can unsubscribe if
                    # we like
                    await client.send(Unsubscribe(
                        streams=[StreamParameter.LEDGER],
                    ))
                    print("Unsubscribed from the ledger!")
                except:
                    # if you wish you perform some logic when the websocket
                    # connection closes due to error, you can catch and run
                    # whatever you need to here. this is equivalent to the
                    # javascript 'error' event
                    error_happened = True
                    on_error()
            # now, outside of the context, the client is closed.
            # the `on_message` task will now never receive a new message. you
            # can now run any code you need to run after the connection is
            # closed. this is equivalent to the javascript 'close' event
            if not error_happened:
                on_close()


        if __name__ == "__main__":
            # remember to run your entire program within a
            # `asyncio.run` call.
            asyncio.run(main())


    If you need to ensure that you reconnect your websockets whenever they
    disconnect, you can create a supervisor like the example below. Note this
    example can be copied and run directly with no changes::

        import asyncio

        from xrpl.asyncio.clients import AsyncWebsocketClient
        from xrpl.models import Subscribe, StreamParameter

        URL = "wss://s.altnet.rippletest.net:51233"


        async def websocket_supervisor():
            # whenever the websocket disconnects, for any reason, the loop
            # will restart, reconnect, and set everything up again.
            while True:
                try:
                    await long_websocket_task()
                except:
                    print("Lost connection! Reconnecting")


        async def on_message(client):
            async for message in client:
                print(message)


        async def long_websocket_task():
            async with AsyncWebsocketClient(URL) as client:
                # set up a listener task
                listener = asyncio.create_task(on_message(client))

                # subscribe to the ledger
                await client.send(Subscribe(
                    streams=[StreamParameter.LEDGER],
                ))

                # sleep infinitely until the connection closes on us
                while client.is_open():
                    await asyncio.sleep(0)
                listener.cancel()


        async def main():
            await websocket_supervisor()


        if __name__ == "__main__":
            asyncio.run(main())
    """

    async def open(self: Self) -> None:
        """Connects the client to the Web Socket API at the given URL."""
        if not self.is_open():
            await self._do_open()

    async def close(self: Self) -> None:
        """Closes the connection."""
        if self.is_open():
            await self._do_close()

    async def __aenter__(self: Self) -> Self:
        """
        Enters an async context after opening itself.

        Returns:
            The opened client.
        """
        await self.open()
        return self

    async def __aexit__(
        self: Self,
        _exc_type: Type[BaseException],
        _exc_val: BaseException,
        _trace: TracebackType,
    ) -> None:
        """Exits an async context after closing itself."""
        await self.close()

    async def __aiter__(self: Self) -> AsyncIterator[Dict[str, Any]]:
        """
        Iterate on received messages.

        Yields:
            Message at the top of the queue.
        """
        while self.is_open():
            yield await self._do_pop_message()

    async def send(self: Self, request: Request) -> None:
        """
        Submit the request represented by the request to the
        rippled node specified by this client's URL. Unlike ``request``,
        ``send`` does not wait for this request's response. In many cases
        it may be more convenient to use ``request``.

        Arguments:
            request: A Request object representing information about a rippled request.

        Raises:
            XRPLWebsocketException: If there is already an open request by the
                request's ID, or if this WebsocketBase is not open.
        """
        if not self.is_open():
            raise XRPLWebsocketException("Websocket is not open")
        await self._do_send(request)

    async def _request_impl(
        self: Self, request: Request, *, timeout: float = REQUEST_TIMEOUT
    ) -> Response:
        """
        ``_request_impl`` implementation for async websocket.

        Arguments:
            request: An object representing information about a rippled request.

        Returns:
            The response from the server, as a Response object.

        Raises:
            XRPLWebsocketException: If there is already an open request by the
                request's ID, or if this WebsocketBase is not open.

        :meta private:
        """
        if not self.is_open():
            raise XRPLWebsocketException("Websocket is not open")
        return await self._do_request_impl(request, timeout)
