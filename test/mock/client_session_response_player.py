"""
The `ClientSessionResponsePlayer` class implements the `ClientResponseProtocol` protocol for playing back responses.

Description
-----------
The `ClientSessionResponsePlayer` class is used to play back previously recorded responses for a client session. This class
implements the `ClientResponseProtocol` protocol, which defines methods for accessing the response data. If a response
was recorded for a request, the corresponding `ClientSessionResponsePlayer` instance can be used to play back the response.

Example usage
-------------
Here's an example usage of the `ClientSessionResponsePlayer` class:

    response_player = ClientSessionResponsePlayer(method="GET", url="https://example.com", status=200,
                                                   response_text="Hello, world!", response_json=None, response_binary=None)
    response_text = await response_player.text()

Module name: client_session_response_player.py
Module description: Class for playing back recorded client session responses.
Copyright (c) 2023
License: MIT
Author: Unknown
Creation date: 2023/04/08
"""
from test.mock.client_session_response_protocol import ClientResponseProtocol
from typing import Any, Optional


class ClientSessionResponsePlayer(ClientResponseProtocol):
    """
    Implements the `ClientResponseProtocol` protocol for playing back previously recorded responses.

    :param method: The HTTP method used for the request.
    :type method: str
    :param url: The URL of the request.
    :type url: str
    :param status: The HTTP status code of the response.
    :type status: int
    :param response_text: The text content of the response, if any.
    :type response_text: Optional[str]
    :param response_json: The JSON content of the response, if any.
    :type response_json: Optional[Any]
    :param response_binary: The binary content of the response, if any.
    :type response_binary: Optional[bytes]
    """
    def __init__(self,
                 method: str,
                 url: str,
                 status: int,
                 response_text: Optional[str],
                 response_json: Optional[Any],
                 response_binary: Optional[bytes],
                 ):
        self.method = method
        self.url = url
        self.status = status
        self._response_text: Optional[str] = response_text
        self._response_json: Optional[Any] = response_json
        self._response_binary: Optional[bytes] = response_binary

    async def text(self, *args, **kwargs) -> str:
        """
        Retrieve the text content of the response.

        :returns: The text content of the response.
        :rtype: str
        :raises EnvironmentError: If no response text has been recorded for replaying.
        """
        if self._response_text is None:
            raise EnvironmentError("No response text has been recorded for replaying.")
        return self._response_text

    async def json(self) -> Any:
        """
        Retrieve the JSON content of the response.

        :returns: The JSON content of the response.
        :rtype: Any
        :raises EnvironmentError: If no response JSON has been recorded for replaying.
        """
        if self._response_json is None:
            raise EnvironmentError("No response json has been recorded for replaying.")
        return self._response_json

    async def read(self) -> bytes:
        """
        Retrieve the binary content of the response.

        :returns: The binary content of the response.
        :rtype: bytes
        :raises EnvironmentError: If no response binary has been recorded for replaying.
        """
        if self._response_binary is None:
            raise EnvironmentError("No response binary has been recorded for replaying.")
        return self._response_binary

    def release(self):
        """
        This is needed to satisfy ClientSession logic.
        """
        pass
