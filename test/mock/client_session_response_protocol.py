"""
The `ClientResponseProtocol` module defines a protocol for handling responses received from a client.

Description
-----------
The `ClientResponseProtocol` protocol defines methods for handling responses received from a client. These methods include `text()`, `json()`, and `read()`, which return the response body as a string, Python object, or bytes, respectively. The protocol also includes a `release()` method to free any associated resources and `__aenter__()` and `__aexit__()` methods to define actions to be taken when entering or exiting a context.

Example usage
-------------
Here's an example usage of the `ClientResponseProtocol` protocol:

    async with client.get(url) as response:
        body = await response.text()
        print(body)

Module name: client_response_protocol.py
Module description: A protocol for handling responses received from a client.
Copyright (c) 2023, Memento "RC" Mori
License: MIT
Author: Memento "RC" Mori
Creation date: 2023/04/07
"""
from typing import Any, Protocol


class ClientResponseProtocol(Protocol):
    """
    ClientResponseProtocol is a protocol that defines methods for handling responses received from a client.
    """

    async def text(self) -> str:
        """
        Returns the response body as a string.

        :returns: The response body as a string.
        :rtype: str
        """

    async def json(self) -> Any:
        """
        Returns the response body as JSON, deserialized into a Python object.

        :returns: The response body as a Python object.
        :rtype: Any
        """

    async def read(self) -> bytes:
        """
        Returns the response body as bytes.

        :returns: The response body as bytes.
        :rtype: bytes
        """

    def release(self) -> None:
        """
        Releases the response object and frees any associated resources.

        :returns: None
        """

    async def __aenter__(self) -> "ClientResponseProtocol":
        """
        The asynchronous context manager method that defines actions to be taken upon entering a context.

        :returns: An instance of ClientResponseProtocol.
        :rtype: ClientResponseProtocol
        """

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        The asynchronous context manager method that defines actions to be taken upon exiting a context.

        :param exc_type: The exception type.
        :type exc_type: Any
        :param exc_val: The exception value.
        :type exc_val: Any
        :param exc_tb: The exception traceback.
        :type exc_tb: Any
        :returns: None
        """
