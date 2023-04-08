import functools
import inspect
from test.mock.client_session_response_protocol import ClientResponseProtocol
from typing import Any, Callable, Coroutine, Dict, Generic, Optional, Tuple, Type, TypeVar

from aiohttp import ClientResponse, ClientSession

ClientResponseType = TypeVar("ClientResponseType", bound=ClientResponseProtocol)


class ClientSessionWrappedRequest(Generic[ClientResponseType]):
    """
    A wrapped aiohttp.ClientSession that allows custom request handling via a provided request_wrapper function.

    :param request_wrapper: An optional async function that takes the same arguments as ClientSession.request
                            and returns a response object.
    :param args: Positional arguments to pass to the ClientSession constructor.
    :param kwargs: Keyword arguments to pass to the ClientSession constructor.
    """
    __slots__ = (
        "_args",
        "_kwargs",
        "_session",
        "_session_request",
        "_request_wrapper",
        "_response_class",
    )

    async def request_wrapper_default_raises(self, *args: Any, **kwargs: Any) -> ClientResponseType:
        """
        Default request_wrapper implementation that raises NotImplementedError.

        :param args: Positional arguments passed to the request.
        :param kwargs: Keyword arguments passed to the request.
        :raises NotImplementedError: This method should be overridden in subclasses or when instantiating the class.
        """
        # Provide an implementation for this method or raise NotImplementedError
        raise NotImplementedError

    def __init__(self,
                 *args,
                 request_wrapper: Optional[Callable[..., Coroutine[Any, Any, ClientResponseType]]] = None,
                 response_class: Type[ClientResponseType] = ClientResponse,
                 **kwargs):
        """
        Initialize the ClientSessionWrappedRequest with the provided request_wrapper, args, and kwargs.

        :param request_wrapper: An optional async function that takes the same arguments as ClientSession.request
                                and returns a response object.
        :param args: Positional arguments to pass to the ClientSession constructor.
        :param kwargs: Keyword arguments to pass to the ClientSession constructor.
        """

        if isinstance(response_class, functools.partial):
            response_class = response_class.func

        if response_class is not None and not issubclass(response_class, ClientResponse):
            raise ValueError(f"response_class {response_class} must be a subclass of ClientResponse")

        self._args: Tuple[Any, ...] = args
        self._kwargs: Dict[str, Any] = kwargs
        self._session: Optional[ClientSession] = None
        self._session_request: Optional[Callable[..., ClientResponseType]] = None
        self._response_class: Type[ClientResponseType] = response_class
        self._request_wrapper: Callable[
            ..., Coroutine[Any, Any, ClientResponseType]] = request_wrapper or self.request_wrapper_default_raises

        if "wrapped_session" not in inspect.signature(self._request_wrapper).parameters:
            self._request_wrapper = functools.partial(self._request_wrapper, wrapped_session=self)

    def __repr__(self):
        representation = f"{self.__class__.__name__}(\n\t{self._args}, {self._kwargs}"
        if self._session is not None:
            representation += f"\n\tsession={self._session}: Closed={self._session.closed}"
        if self._session_request is not None:
            representation += f"\n\tsession_request={self._session_request}"
        if self._request_wrapper is not None:
            representation += f"\n\trequest_wrapper={self._request_wrapper}"
        if self._response_class is not None:
            representation += f"\n\tresponse_class={self._response_class}"
        representation += "\n)"
        return representation

    async def __aenter__(self) -> "ClientSessionWrappedRequest":
        """
        Asynchronously enter the context manager, creating the underlying
        ClientSession and applying the request wrapper. It also initializes the type
        of the request() return value.

        :return: Self.
        """
        # Ensure the session._request() return the desired class
        self._kwargs["response_class"] = self._response_class
        self._session = ClientSession(*self._args, **self._kwargs)
        self._session_request = getattr(self._session, "_request")
        setattr(self._session, "_request", self._request_wrapper)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Asynchronously exit the context manager, closing the underlying ClientSession.

        :param exc_type: Exception type.
        :param exc_val: Exception value.
        :param exc_tb: Exception traceback.
        """
        await self._session.__aexit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, name: str) -> Any:
        """
        Get an attribute from the underlying ClientSession, except for the 'request' attribute,
        which returns the instance's _request_wrapper attribute.

        :param name: The name of the attribute to get.
        :return: The value of the attribute.
        :raises AttributeError: If the attribute is not found.
        """
        if name.startswith("__"):
            raise AttributeError(name)

        if self._session is not None:
            # This is not needed, _request() is not likely to be called directly from ClientSessionWrappedRequest
            # if name == "request":
            #     return getattr(self, "request_wrapper")
            attribute = getattr(self._session, name)
            return attribute
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    async def client_session_request(self, *args, **kwargs) -> ClientResponseType:
        """
        Get the original ClientSession._request() -> ClientResponse recast into the type
        prototype T.

        :return: The ClientResponse recast.
        """
        # Make sure the "wrapped_session" argument is not passed to the underlying ClientSession._request()
        # This class likely adds it (or it is already in the request_wrapper signature)
        kwargs.pop("wrapped_session", None)
        response: ClientResponseType = await self._session_request(*args, **kwargs)
        assert isinstance(response, self._response_class)
        return response
