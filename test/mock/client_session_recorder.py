"""
The `ClientSessionRecorder` module provides a class for recording HTTP conversations made over any
aiohttp.ClientSession object, and recording them to an SQLite database file for replaying.

Description
-----------
The `ClientSessionRecorder` module defines a class for handling responses received from a
client session. The `ClientSessionRecorder` class records the responses received from a client session and stores
them in a database for replaying. The module also provides a utility function for working with client sessions.

Example usage
-------------
Here's an example usage of the `ClientSessionRecorder` module:

    from aiohttp import ClientSession
    from sqlalchemy.orm import Session

    client_session = ClientSession()
    db_session = Session()
    recorder = ClientSessionRecorder(client_session=client_session, db_session=db_session)
    response = await client_session.get(url)
    await recorder.record_response(response)

Module name: client_session_recorder.py
Module description: A class for recording HTTP conversations made over any aiohttp.ClientSession object, and recording
                    them to an SQLite database file for replaying.
Copyright (c) 2023
License: MIT
Author: Unknown
Creation date: 2023/04/07
"""
import time
from test.mock.client_session_playback import ClientSessionPlayback
from test.mock.client_session_player_base import ClientSessionPlayerBase
from test.mock.client_session_recorder_utils import ClientSessionRequestType, ClientSessionResponseType
from test.mock.client_session_response_recorder import ClientSessionResponseRecorder
from test.mock.client_session_wrapped_request import ClientResponseType, ClientSessionWrappedRequest
from typing import Any, Callable, Coroutine, List, Optional, Type


class ResponseClassNotClientResponseRecorderError(Exception):
    """
    ResponseClassNotClientResponseRecorderError is raised when the response_class is not a subclass of
    ClientSessionResponseRecorder.
    """
    pass


class InvalidRequestWrapperError(Exception):
    """
    InvalidRequestWrapperError is raised when the request_wrapper function is not a coroutine function.
    """
    pass


class ClientSessionRecorder(ClientSessionPlayerBase):
    """
    Records HTTP conversations made over any aiohttp.ClientSession object, and records them to an SQLite database file
    for replaying.

    Usage:
    recorder = ClientSessionRecorder('test.db')
    async with recorder.patch_aiohttp_client() as client:
        # all aiohttp conversations inside this block will be recorded to test.db
        async with client.get("https://api.binance.com/api/v3/time") as resp:
            data = await resp.json()      # the request and response are recorded to test.db
          ...
    """

    __slots__ = (
        "_client_session",
        "_custom_response_class",
        "_custom_request_wrapper",
    )

    def __init__(self, db_path: str):
        """
        Initialize a new `ClientSessionRecorder` instance.
        """
        super().__init__(db_path)
        self._client_session: Optional[ClientSessionRequestType] = None
        self._custom_response_class: Optional[Type[ClientResponseType]] = None
        self._custom_request_wrapper: Optional[Callable[..., Coroutine[Any, Any, ClientResponseType]]] = None

    def __call__(
            self,
            *,
            request_wrapper: Optional[Callable[..., Coroutine[Any, Any, ClientResponseType]]] = None,
            response_class: Optional[Type[ClientResponseType]] = None
    ) -> "ClientSessionRecorder":
        """
        Set the custom `response_class` for this `ClientSessionRecorder` instance and return itself.

        :param request_wrapper: A wrapper function to apply to the request before sending it.
        :type request_wrapper: Optional[Callable[..., Coroutine[Any, Any, ClientResponseType]]]
        :param response_class: A custom `ClientResponseType` subclass to use for response recording.
        :type response_class: Optional[Type[ClientResponseType]]
        :returns: This `ClientSessionRecorder` instance.
        :rtype: ClientSessionRecorder
        """
        if response_class is not None and issubclass(response_class, ClientSessionResponseRecorder):
            self._custom_response_class = response_class
        if request_wrapper is not None and callable(request_wrapper):
            self._custom_request_wrapper = request_wrapper
        return self

    async def __aenter__(self, *client_args, **client_kwargs) -> ClientSessionWrappedRequest:
        """
        Enter the context of this `ClientSessionRecorder` instance and return a wrapped request object.

        :param client_args: Positional arguments for the client session.
        :param client_kwargs: Keyword arguments for the client session.
        :returns: A `ClientSessionWrappedRequest` object.
        :rtype: ClientSessionWrappedRequest
        """
        response_class = ClientSessionResponseRecorder.factory(parent_recorder=self,
                                                               custom_response_class=self._custom_response_class)
        recorder = await super().__aenter__(*client_args,
                                            request_wrapper=self._custom_request_wrapper or self.aiohttp_request_method,
                                            response_class=response_class,
                                            **client_kwargs)
        self._recorder = recorder
        return recorder

    async def aiohttp_request_method(
            self,
            *args,
            **kwargs
    ) -> ClientResponseType:
        """
        Send an HTTP request with the given arguments and return a `ClientSessionResponseRecorder` instance.

        :param args: Positional arguments for the request.
        :param kwargs: Keyword arguments for the request.
        :returns: A `ClientSessionResponseRecorder` instance.
        :rtype: ClientSessionResponseRecorder
        """
        wrapped_session: ClientSessionWrappedRequest = kwargs.pop('wrapped_session', None)
        # Handling exceptions
        try:
            # Perform the real request
            response: ClientResponseType = await wrapped_session.client_session_request(*args, **kwargs)
        except KeyError:
            raise ValueError("wrapped_session must be provided in kwargs")

        # Record the request
        (req_type, req_params, req_json) = (ClientSessionRequestType.PLAIN, None, None)
        if kwargs.get("params", None) is not None:
            req_type = ClientSessionRequestType.WITH_PARAMS
            req_params = kwargs.get("params", None)
        elif kwargs.get("json", None) is not None:
            req_type = ClientSessionRequestType.WITH_JSON
            req_json = kwargs.get("json", None)

        # Record custom request headers
        request_headers = kwargs.get('headers', None)

        playback_entry: ClientSessionPlayback = ClientSessionPlayback(
            timestamp=int(time.time_ns() // 1_000_000),
            method=str(kwargs.get("method", None) or args[0]),
            url=str(kwargs.get("url", None) or args[1]),
            request_type=req_type,
            request_headers=request_headers,
            request_params=req_params,
            request_json=req_json,
            response_type=ClientSessionResponseType.HEADER_ONLY,
            response_code=response.status,
        )

        # Record the response text and json
        with self.begin() as session:
            session.add(playback_entry)
            session.commit()
            response.database_id = playback_entry.id
        return response

    def get_records(self) -> List[ClientSessionPlayback]:
        """
        Retrieve all records of requests and responses from the database.

        :returns: A list of dictionaries representing each record.
        :rtype: List[Dict[str, Any]]
        """
        with self.begin() as session:
            records = session.query(ClientSessionPlayback).all()
            return [record.as_dict() for record in records]
