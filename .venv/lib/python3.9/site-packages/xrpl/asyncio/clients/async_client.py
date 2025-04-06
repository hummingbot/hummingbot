"""Interface for all async network clients to follow."""

from __future__ import annotations

from typing_extensions import Self

from xrpl.asyncio.clients.client import Client
from xrpl.models.requests.request import Request
from xrpl.models.response import Response


class AsyncClient(Client):
    """
    Interface for all async network clients to follow.

    :meta private:
    """

    async def request(self: Self, request: Request) -> Response:
        """
        Makes a request with this client and returns the response.

        Arguments:
            request: The Request to send.

        Returns:
            The Response for the given Request.
        """
        return await self._request_impl(request)
