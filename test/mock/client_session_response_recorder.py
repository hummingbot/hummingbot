"""
The `client_session_response_recorder` module provides classes for recording and playing back client session responses.

Description
-----------
The `client_session_response_recorder` module defines several classes for handling responses
received from a client session. These classes include the `ClientSessionResponseRecorderProtocol`,
`ClientSessionPlaybackProtocol`, and `ClientSessionResponseRecorder` classes. The `ClientSessionResponseRecorder`
class records the responses received from a client session and stores them in a database, while the
`ClientSessionPlaybackProtocol` class plays back the recorded responses. The `ClientSessionResponseRecorderProtocol`
class defines a protocol for recording responses, and the `ClientSessionPlaybackProtocol` class defines a protocol
for playing back responses. The module also provides several utility functions for working with client sessions.

Example usage
-------------
Here's an example usage of the `client_session_response_recorder` module:

    from aiohttp import ClientSession
    from sqlalchemy.orm import Session

    client_session = ClientSession()
    db_session = Session()
    recorder = ClientSessionResponseRecorder(client_session=client_session, db_session=db_session)
    response = await client_session.get(url)
    await recorder.record_response(response)

Module name: client_session_response_recorder.py
Module description: Classes for recording and playing back client session responses.
Copyright (c) 2023
License: MIT
Author: Unknown
Creation date: 2023/04/07
"""
import weakref
from contextlib import contextmanager
from test.mock.client_session_playback import ClientSessionPlayback
from test.mock.client_session_recorder_utils import ClientSessionResponseType
from typing import Callable, Optional, Protocol, Type, TypeVar, Union

from aiohttp import ClientResponse
from sqlalchemy.orm import Session


class CustomResponseClassNotClientResponseError(Exception):
    """
    CustomResponseClassNotClientResponseError is raised when the custom_response_class is not a subclass of
    ClientResponse.
    """
    pass


class CustomResponseClassNotClientSessionResponseRecorderError(Exception):
    """
    CustomResponseClassNotClientSessionResponseRecorderError is raised when the custom_response_class is not a
    subclass of ClientSessionResponseRecorder.
    """
    pass


class ClientSessionResponseRecorderProtocol(Protocol):
    begin: Callable[[], Session]


T = TypeVar("T", bound=ClientResponse)


class ClientSessionResponseRecorder(ClientResponse):
    _database_id: Optional[int] = None
    _parent_recorder_ref: Optional[weakref.ReferenceType] = None

    @classmethod
    def factory(cls,
                *,
                parent_recorder: ClientSessionResponseRecorderProtocol,
                custom_response_class: Optional[Type[T]] = None,
                ) -> Union[Type["ClientSessionResponseRecorder"], Type[T]]:
        """
        Factory method to create and return a new `ClientSessionResponseRecorder` class.

        :param parent_recorder: An instance of `ClientSessionResponseRecorderProtocol`.
        :type parent_recorder: ClientSessionResponseRecorderProtocol
        :param custom_response_class: A custom `ClientSessionResponseRecorder` class.
        :type custom_response_class: Optional[Type[ClientSessionResponseRecorder]]
        :returns: A new `ClientSessionResponseRecorder` class.
        :rtype: Type[ClientSessionResponseRecorder]
        """
        cls._parent_recorder_ref: weakref.ReferenceType = weakref.ref(parent_recorder)
        if custom_response_class is not None:
            if not issubclass(custom_response_class, ClientResponse):
                raise CustomResponseClassNotClientResponseError(
                    "custom_response_class must be a subclass of ClientResponse")
            if not issubclass(custom_response_class, cls):
                raise CustomResponseClassNotClientSessionResponseRecorderError(
                    f"custom_response_class must be a subclass of {cls.__name__}")
            custom_response_class._parent_recorder_ref = weakref.ref(parent_recorder)
            return custom_response_class
        return cls

    def __init__(self,
                 *args,
                 **kwargs):
        """
        Initializes a new instance of `ClientSessionResponseRecorder`.

        :param args: Positional arguments passed to the `ClientResponse` constructor.
        :type args: Any
        :param kwargs: Keyword arguments passed to the `ClientResponse` constructor.
        :type kwargs: Any
        """
        super().__init__(*args, **kwargs)
        self._database_id = None
        if self._parent_recorder_ref is not None:
            self._parent_recorder = self._parent_recorder_ref()

    @property
    def database_id(self) -> Optional[int]:
        """
        Return the database ID for this `ClientSessionResponseRecorder` instance.

        :returns: The database ID, if it exists.
        :rtype: Optional[int]
        """
        return self._database_id

    @database_id.setter
    def database_id(self, value: int):
        """
        Set the database ID for this `ClientSessionResponseRecorder` instance.

        :param value: The database ID to set.
        :type value: int
        """
        self._database_id = value

    @property
    def parent_recorder(self) -> ClientSessionResponseRecorderProtocol:
        """
        Return the parent `ClientSessionResponseRecorderProtocol` instance for this `ClientSessionResponseRecorder` instance.

        :returns: The parent instance.
        :rtype: ClientSessionResponseRecorderProtocol
        """
        return self._parent_recorder_ref()

    @classmethod
    def set_parent_recorder(cls, value: ClientSessionResponseRecorderProtocol):
        """
        Set the parent `ClientSessionResponseRecorderProtocol` class attribute for all instances of this class.

        :param value: The parent instance to set.
        :type value: ClientSessionResponseRecorderProtocol
        """
        cls._parent_recorder_ref = weakref.ref(value)

    def get_playback_entry(self, db_session: Session) -> ClientSessionPlayback:
        """
        Retrieve the `ClientSessionPlayback` entry from the database corresponding to this instance's `database_id`.

        :param db_session: The SQLAlchemy database session.
        :type db_session: Session
        :returns: The corresponding `ClientSessionPlayback` entry, or None if it does not exist.
        :rtype: ClientSessionPlayback
        """
        return db_session.query(ClientSessionPlayback).filter(
            ClientSessionPlayback.id == self.database_id).one_or_none()

    async def text(self, encoding=None, errors='strict', *args, **kwargs) -> str:
        """
        Read the response text and update the playback entry in the database.

        :param encoding: The encoding of the response text.
        :type encoding: str
        :param errors: The error handling scheme to use for decoding errors.
        :type errors: str
        :returns: The response text.
        :rtype: str
        """
        with self._use_original_read():
            response_text: str = await super().text(encoding=encoding, errors=errors)
        self._update_playback_entry(ClientSessionResponseType.WITH_TEXT, response_text=response_text)
        return response_text

    async def json(self, encoding=None, content_type="application/json", *args, **kwargs) -> dict:
        """
        Read the response JSON and update the playback entry in the database.

        :param encoding: The encoding of the response JSON.
        :type encoding: str
        :param content_type: The content type of the response JSON.
        :type content_type: str
        :returns: The response JSON.
        :rtype: dict
        """
        with self._use_original_read():
            response_json = await super().json(encoding=encoding, content_type=content_type, *args, **kwargs)
        self._update_playback_entry(ClientSessionResponseType.WITH_JSON, response_json=response_json)
        return response_json

    async def read(self) -> bytes:
        """
        Read the response binary and update the playback entry in the database.

        :returns: The response binary.
        :rtype: bytes
        """
        response_binary = await super().read()
        self._update_playback_entry(ClientSessionResponseType.WITH_BINARY, response_binary=response_binary)
        return response_binary

    @contextmanager
    def _use_original_read(self):
        """
        A context manager that temporarily sets the `read` method to its original implementation.

        This method is used to ensure that the `read` method used by the `super` class is used instead of the overridden
        method in this class. This is necessary because the overridden `read` method updates the playback entry in the
        database, while the `read` method in the `super` class does not.

        :yields: None
        """
        original_read = self.read
        self.read = super().read
        try:
            yield
        finally:
            self.read = original_read

    def _update_playback_entry(self, response_type: ClientSessionResponseType, **kwargs):
        """
        Update the playback entry in the database with the given response type and keyword arguments.

        :param response_type: The type of the response (text, JSON, or binary).
        :type response_type: ClientSessionResponseType
        :param kwargs: The keyword arguments for the playback entry.
        """
        with self.parent_recorder.begin() as session:
            playback_entry: Optional[ClientSessionPlayback] = self.get_playback_entry(session)
            if playback_entry is None:
                # Handle the case when there's no matching playback entry, e.g., log an error or raise an exception
                print(f"Error: No matching playback entry found for database_id: {self.database_id}")
                return
            # Update the playback entry
            playback_entry.response_type = response_type.name
            for key, value in kwargs.items():
                if hasattr(playback_entry, key):
                    setattr(playback_entry, key, value)
                else:
                    print(f"Warning: attribute {key} not found in playback_entry.")
            session.commit()
