"""The `client_session_context_mixin` module provides a mixin class that allows patching the aiohttp `ClientSession`
with a custom request_wrapper function and response class.

Description
-----------
The `client_session_context_mixin` module defines the `ClientSessionContextMixin` class,
which is a mixin class that allows patching the aiohttp `ClientSession` with a custom `request_wrapper` function and
`response_class`.

Example usage
-------------
Here's an example usage of the `client_session_context_mixin` module:

    import aiohttp

    async def request_wrapper(*args, **kwargs):
        # Wrapper must remove the wrapped_session parameter from kwargs
        # before calling the original ClientSession._request() method.
        wrapped_session = kwargs.pop("wrapped_session", None)
        # To call the original ClientSession._request() method, use the wrapped_session.client_session_request() method.
        return await wrapped_session.client_session_request(*args, **kwargs)
        # Custom request wrapper logic

    class CustomClientResponse(ClientResponse):
        # Custom response class logic
        pass

    async with ClientSession() as session:
        async with ClientSessionContextMixin(request_wrapper, CustomClientResponse).aenter(session=session):
            response = await session.get(url)

Module name: client_session_context_mixin.py
Module description: Provides a mixin class for patching the aiohttp `ClientSession` with a custom request_wrapper function and response class.
Copyright (c) 2023
License: MIT
Author: Unknown
Creation date: 2023/04/07
"""
from test.mock.client_session_wrapped_request import ClientResponseType, ClientSessionWrappedRequest
from typing import Any, AsyncGenerator, Callable, Coroutine, Generic, Optional, Type

from aiohttp import ClientResponse


class InvalidRequestWrapperError(Exception):
    """
    InvalidRequestWrapperError is raised when the request_wrapper function is not a coroutine function.
    """
    pass


class ClientSessionContextMixin(Generic[ClientResponseType]):
    """
    ClientSessionContextMixin is a mixin class that allows patching the aiohttp ClientSession
    with a custom request_wrapper function and response class.

    Note: When using this mixin, if you use ClientSession._request() in your request_wrapper,
    make sure to remove the added "wrapped_session" parameter from the kwargs before calling
    the original _request() method.
    """

    def __init__(self,
                 *,
                 request_wrapper: Optional[Callable[..., Coroutine[Any, Any, ClientResponseType]]] = None,
                 response_class: Optional[Type[ClientResponseType]] = None):
        """
        Initialize a new instance of the ClientSessionContextMixin class.

        :param request_wrapper: A coroutine function that wraps the aiohttp request() method.
        :type request_wrapper: Optional[Callable[..., Coroutine[Any, Any, T]]]
        :param response_class: A subclass of ClientResponse that will be returned from the request method.
        :type response_class: Optional[Type[T]]
        """
        self._patched_client: Optional[AsyncGenerator[Type[ClientSessionWrappedRequest], None]] = None
        self._request_wrapper: Optional[Callable[..., Coroutine[Any, Any, ClientResponseType]]] = request_wrapper
        self._response_class: Optional[Type[ClientResponseType]] = response_class or ClientResponse

    def __call__(self,
                 *,
                 request_wrapper: Optional[Callable[..., Coroutine[Any, Any, ClientResponseType]]] = None,
                 response_class: Optional[Type[ClientResponseType]] = None) -> "ClientSessionContextMixin":
        """
        Call method for the ClientSessionContextMixin instance. Provides the convenience of resetting
        the request_wrapper and response_class parameters without having to create a new instance.

        Usage example:
              async with ClientSessionContextMixin(request_wrapper, CustomClientResponse) as session:
                response = await session.get(url)

        :param request_wrapper: A coroutine function that wraps the aiohttp request() method.
        :type request_wrapper: Optional[Callable[..., Coroutine[Any, Any, T]]]

        """
        if request_wrapper is not None:
            self._request_wrapper = request_wrapper
        if response_class is not None:
            self._response_class = response_class
        return self

    async def __aenter__(self,
                         *client_args,
                         request_wrapper: Optional[Callable[..., Coroutine[Any, Any, ClientResponseType]]] = None,
                         response_class: Optional[Type[ClientResponseType]] = None,
                         **client_kwargs) -> ClientSessionWrappedRequest:
        """
        Asynchronous context manager method that returns an instance of `ClientSessionWrappedRequest`.

        :param request_wrapper: The request wrapper function.
        :type request_wrapper: Optional[Callable[..., Coroutine[Any, Any, T]]]
        :param response_class: The response class.
        :type response_class: Optional[Type[T]]
        :param client_args: Arguments to be passed to `ClientSessionWrappedRequest`.
        :type client_args: Any
        :param client_kwargs: Keyword arguments to be passed to `ClientSessionWrappedRequest`.
        :type client_kwargs: Any
        :returns: An instance of `ClientSessionWrappedRequest`.
        :rtype: ClientSessionWrappedRequest
        """
        if request_wrapper is not None:
            self._request_wrapper = request_wrapper

        if response_class is not None:
            self._response_class = response_class

        if self._request_wrapper is None:
            raise InvalidRequestWrapperError("request_wrapper must be provided")

        client = await ClientSessionWrappedRequest(*client_args,
                                                   request_wrapper=self._request_wrapper,
                                                   response_class=self._response_class,
                                                   **client_kwargs).__aenter__()
        self._patched_client = client
        return client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._patched_client is not None:
            await self._patched_client.__aexit__(exc_type, exc_val, exc_tb)
            self._patched_client = None
