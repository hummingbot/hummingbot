"""A common interface for JsonRpc requests."""

from __future__ import annotations

from json import JSONDecodeError

from httpx import AsyncClient
from typing_extensions import Self

from xrpl.asyncio.clients.client import REQUEST_TIMEOUT, Client
from xrpl.asyncio.clients.exceptions import XRPLRequestFailureException
from xrpl.asyncio.clients.utils import json_to_response, request_to_json_rpc
from xrpl.models.requests.request import Request
from xrpl.models.response import Response


class JsonRpcBase(Client):
    """
    A common interface for JsonRpc requests.

    :meta private:
    """

    async def _request_impl(
        self: Self, request: Request, *, timeout: float = REQUEST_TIMEOUT
    ) -> Response:
        """
        Base ``_request_impl`` implementation for JSON RPC.

        Arguments:
            request: An object representing information about a rippled request.
            timeout: The duration within which we expect to hear a response from the
            rippled validator.

        Returns:
            The response from the server, as a Response object.

        Raises:
            XRPLRequestFailureException: if response can't be JSON decoded.

        :meta private:
        """
        async with AsyncClient(timeout=timeout) as http_client:
            response = await http_client.post(
                self.url,
                json=request_to_json_rpc(request),
            )
            try:
                return json_to_response(response.json())
            except JSONDecodeError:
                raise XRPLRequestFailureException(
                    {
                        "error": response.status_code,
                        "error_message": response.text,
                    }
                )
