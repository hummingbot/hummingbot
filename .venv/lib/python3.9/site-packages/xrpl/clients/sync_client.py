"""Interface for all sync network clients to follow."""

from __future__ import annotations

import asyncio

from typing_extensions import Self

from xrpl.asyncio.clients.client import Client
from xrpl.models.requests.request import Request
from xrpl.models.response import Response


class SyncClient(Client):
    """
    Interface for all sync network clients to follow.

    :meta private:
    """

    def request(self: Self, request: Request) -> Response:
        """
        Makes a request with this client and returns the response.

        Arguments:
            request: The Request to send.

        Returns:
            The Response for the given Request.
        """
        return asyncio.run(self._request_impl(request))
