"""Interface for all network clients to follow."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from typing_extensions import Final, Self

from xrpl.models.requests.request import Request
from xrpl.models.response import Response

# The default request timeout duration. Set in Client._request_impl to allow more time
# for longer running commands.
REQUEST_TIMEOUT: Final[float] = 10.0


class Client(ABC):
    """
    Interface for all network clients to follow.

    :meta private:
    """

    def __init__(self: Self, url: str) -> None:
        """
        Initializes a client.

        Arguments:
            url: The url to which this client will connect
        """
        self.url = url
        self.network_id: Optional[int] = None
        self.build_version: Optional[str] = None

    @abstractmethod
    async def _request_impl(
        self: Self, request: Request, *, timeout: float = REQUEST_TIMEOUT
    ) -> Response:
        """
        This is the actual driver for a given Client's request. It must be
        async because all of the helper functions in this library are
        async-first. Implement this in a given Client.

        Arguments:
            request: An object representing information about a rippled request.
            timeout: The maximum tolerable delay on waiting for a response.

        Returns:
            The response from the server, as a Response object.

        :meta private:
        """
        pass
