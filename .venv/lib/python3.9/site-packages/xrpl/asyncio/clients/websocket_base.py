"""A client for interacting with the rippled WebSocket API."""

from __future__ import annotations

import asyncio
import json
from random import randrange
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from typing_extensions import Final, Self
from websockets import client as websocket_client

from xrpl.asyncio.clients.client import Client
from xrpl.asyncio.clients.exceptions import XRPLWebsocketException
from xrpl.asyncio.clients.utils import request_to_websocket, websocket_to_response
from xrpl.models.requests.request import Request
from xrpl.models.response import Response

_REQ_ID_MAX: Final[int] = 1_000_000

# the types from asyncio are not implemented as generics in python 3.8 and
# lower, so we need to only subscript them when running typechecking.
if TYPE_CHECKING:
    _REQUESTS_TYPE = Dict[str, asyncio.Future[Dict[str, Any]]]
    _MESSAGES_TYPE = asyncio.Queue[Dict[str, Any]]
    _HANDLER_TYPE = asyncio.Task[None]
else:
    _REQUESTS_TYPE = Dict[str, asyncio.Future]
    _MESSAGES_TYPE = asyncio.Queue
    _HANDLER_TYPE = asyncio.Task


def _inject_request_id(request: Request) -> Request:
    """
    Given a Request with an ID, return the same Request.

    Given a Request without an ID, make a copy with a randomly generated ID.

    Arguments:
        request: The request to inject an ID into.

    Returns:
        The request with an ID injected into it.
    """
    if request.id is not None:
        return request
    request_dict = request.to_dict()
    request_dict["id"] = f"{request.method}_{randrange(_REQ_ID_MAX)}"
    return Request.from_dict(request_dict)


class WebsocketBase(Client):
    """
    A client for interacting with the rippled WebSocket API.

    :meta private:
    """

    def __init__(self: Self, url: str) -> None:
        """
        Initializes a websocket client.

        Arguments:
            url: The URL of the rippled node to submit requests to.
        """
        self._open_requests: _REQUESTS_TYPE = {}
        self._websocket: Optional[websocket_client.WebSocketClientProtocol] = None
        self._handler_task: Optional[_HANDLER_TYPE] = None
        # unfortunately, we cannot create the Queue here because it needs to be
        # tied to a currently-running event loop. the sync websocket client
        # will initialize a new event loop when it opens the connection, so for
        # that client the initializer cannot create the queue
        self._messages: Optional[_MESSAGES_TYPE] = None
        super().__init__(url)

    def is_open(self: Self) -> bool:
        """
        Returns whether the client is currently open.

        Returns:
            True if the client is currently open, False otherwise.
        """
        return (
            self._handler_task is not None
            and self._messages is not None
            and self._websocket is not None
            and self._websocket.open
        )

    async def _do_open(self: Self) -> None:
        """Connects the client to the Web Socket API at its URL."""
        # open the connection
        self._websocket = await websocket_client.connect(self.url)

        # make a message queue
        self._messages = asyncio.Queue()

        # start the handler
        self._handler_task = asyncio.create_task(self._handler())

    async def _do_close(self: Self) -> None:
        """Closes the connection."""
        # cancel the handler
        cast(_HANDLER_TYPE, self._handler_task).cancel()
        self._handler_task = None

        # cancel any pending request Futures
        for future in self._open_requests.values():
            future.cancel()
        self._open_requests = {}

        # clear the message queue
        for _ in range(cast(_MESSAGES_TYPE, self._messages).qsize()):
            cast(_MESSAGES_TYPE, self._messages).get_nowait()
            cast(_MESSAGES_TYPE, self._messages).task_done()
        self._messages = None

        # close the connection
        await cast(websocket_client.WebSocketClientProtocol, self._websocket).close()

    async def _handler(self: Self) -> None:
        """
        This is basically a middleware for the websocket library. For all received
        messages we check whether there is an outstanding future we need to resolve,
        and if so do so.

        Then we store the already-parsed JSON in our own queue for generic iteration.

        As long as a given client remains open, this handler will be running as a Task.
        """
        async for response in cast(
            websocket_client.WebSocketClientProtocol, self._websocket
        ):
            response_dict = json.loads(response)

            # if this response corresponds to request, fulfill the Future
            if "id" in response_dict and response_dict["id"] in self._open_requests:
                self._open_requests[response_dict["id"]].set_result(response_dict)

            # enqueue the response for the message queue
            cast(_MESSAGES_TYPE, self._messages).put_nowait(response_dict)

    def _set_up_future(self: Self, request: Request) -> None:
        """
        Only to be called from the public send and _request_impl functions.
        Given a request with an ID, ensure that that ID is backed by an open
        Future in self._open_requests.

        Arguments:
            request: The request with which to set up a future.

        Raises:
            XRPLWebsocketException: if there is already a request with this ID
                in progress.
        """
        if request.id is None:
            return
        request_str = str(request.id)
        if (
            request_str in self._open_requests
            and not self._open_requests[request_str].done()
        ):
            raise XRPLWebsocketException(
                f"Request {request_str} is already in progress."
            )
        self._open_requests[request_str] = asyncio.get_running_loop().create_future()

    async def _do_send_no_future(self: Self, request: Request) -> None:
        """
        Base websocket send function

        Arguments:
            request: The request to send.
        """
        await cast(websocket_client.WebSocketClientProtocol, self._websocket).send(
            json.dumps(
                request_to_websocket(request),
            ),
        )

    async def _do_send(self: Self, request: Request) -> None:
        """
        Websocket send function that should be used by
        any inherited classes.

        Arguments:
            request: The request to send.
        """
        # we need to set up a future here, even if no one cares about it, so
        # that if a user submits a few requests with the same ID they fail.
        self._set_up_future(request)
        await self._do_send_no_future(request)

    async def _do_pop_message(self: Self) -> Dict[str, Any]:
        """
        Returns:
            The top message from the queue
        """
        msg = await cast(_MESSAGES_TYPE, self._messages).get()
        cast(_MESSAGES_TYPE, self._messages).task_done()
        return msg

    async def _do_request_impl(
        self: Self, request: Request, timeout: float
    ) -> Response:
        """
        Base ``_request_impl`` implementation for websockets.

        Arguments:
            request: An object representing information about a rippled request.

        Returns:
            The response from the server, as a Response object.

        Raises:
            XRPLWebsocketException: If there is already an open request by the
                request's ID, or if this WebsocketBase is not open.
        """
        # if no ID on this request, generate and inject one, and ensure it
        # is backed by a future
        request_with_id = _inject_request_id(request)
        request_str = str(request_with_id.id)
        self._set_up_future(request_with_id)

        # fire-and-forget the send, and await the Future
        asyncio.create_task(self._do_send_no_future(request_with_id))

        try:
            raw_response = await asyncio.wait_for(
                self._open_requests[request_str], timeout
            )
        finally:
            # remove the resolved Future, hopefully getting it garbage colleted
            # Ensure the request is removed whether it times out or not
            del self._open_requests[request_str]

        return websocket_to_response(raw_response)
