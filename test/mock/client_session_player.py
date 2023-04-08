"""
The `ClientSessionPlayer` module provides a class for replaying HTTP conversations made over an
aiohttp.ClientSession object using recorded data stored in an SQLite database file.

Description
-----------
The `ClientSessionPlayer` class patches the aiohttp.ClientSession object to enable replaying HTTP conversations using
recorded data stored in an SQLite database file. The module defines a method for matching recorded data with requests
made by the client session, and a utility method for printing all recorded HTTP conversations to the console.

Example usage
-------------
Here's an example usage of the `ClientSessionPlayer` module:

    from aiohttp import ClientSession

    recorder = ClientSessionPlayer('test.db')
    with recorder.patch_aiohttp_client:
        # all aiohttp responses within this block will be replays from past records in test.db.
        async with aiohttp.ClientSession() as client:
            async with client.get("https://api.binance.com/api/v3/time") as resp:
                data = await resp.json()  # the data returned will be the recorded response

Module name: client_session_player.py
Module description: A class for replaying HTTP conversations made over an aiohttp.ClientSession object using recorded
                    data stored in an SQLite database file.
Copyright (c) 2023
License: MIT
Author: Unknown
Creation date: 2023/04/08
"""
from test.mock.client_session_playback import ClientSessionPlayback
from test.mock.client_session_player_base import ClientSessionPlayerBase
from test.mock.client_session_response_player import ClientSessionResponsePlayer
from test.mock.client_session_wrapped_request import ClientSessionWrappedRequest
from typing import Optional, cast

from aiohttp import ClientResponse
from aiohttp.typedefs import StrOrURL
from sqlalchemy import and_
from sqlalchemy.orm import Query


class ClientSessionPlayer(ClientSessionPlayerBase):
    """
    A class that patches aiohttp.ClientSession to replay HTTP conversations from a database.

    This class uses a SQLite database to store HTTP conversations. When aiohttp.ClientSession makes any request inside
    `patch_aiohttp_client()`, the player will search for a matching response by URL, request params, and request JSON
    in the database. If no matching response is found, then an exception will be raised.

    Attributes:
    -----------
    _replay_timestamp_ms : Optional[int]
        The timestamp in milliseconds to use as the start point for replaying conversations. If None, all conversations
        will be replayed.

    Methods:
    --------
    __init__(self, db_path: str)
        Constructs a new ClientSessionPlayer instance.

    async def __aenter__(self, *client_args, **client_kwargs) -> ClientSessionWrappedRequest:
        Enter the context of this `ClientSessionRecorder` instance and return a wrapped request object.

    @property
    def replay_timestamp_ms(self) -> Optional[int]:
        Getter for the replay_timestamp_ms attribute.

    @replay_timestamp_ms.setter
    def replay_timestamp_ms(self, value: Optional[int]):
        Setter for the replay_timestamp_ms attribute.

    async def aiohttp_request_method(
            self,
            method: str,
            url: StrOrURL,
            **kwargs) -> ClientSessionResponsePlayer:
        A method to be used as a request wrapper for aiohttp.ClientSession.

    def print_all_records(self):
        Prints all recorded HTTP conversations to the console.

    """
    _replay_timestamp_ms: Optional[int]

    def __init__(self, db_path: str):
        """
        Constructs a new ClientSessionPlayer instance.

        Parameters:
        ----------
        db_path : str
            The path to the SQLite database to use for storing HTTP conversations.
        """
        super().__init__(db_path)
        self._replay_timestamp_ms = None

    async def __aenter__(self, *client_args, **client_kwargs) -> ClientSessionWrappedRequest:
        """
        Enter the context of this `ClientSessionRecorder` instance and return a wrapped request object.

        :param client_args: Positional arguments for the client session.
        :type client_args: tuple
        :param client_kwargs: Keyword arguments for the client session.
        :type client_kwargs: dict
        :returns: A `ClientSessionWrappedRequest` object.
        :rtype: ClientSessionWrappedRequest
        """
        player = await super().__aenter__(*client_args,
                                          request_wrapper=self.aiohttp_request_method,
                                          response_class=ClientResponse,
                                          **client_kwargs)
        self._player = player
        return player

    @property
    def replay_timestamp_ms(self) -> Optional[int]:
        """
        Gets the timestamp in milliseconds after which only recorded conversations with a matching timestamp should be
        replayed.

        :returns: The timestamp in milliseconds.
        :rtype: Optional[int]
        """
        return self._replay_timestamp_ms

    @replay_timestamp_ms.setter
    def replay_timestamp_ms(self, value: Optional[int]):
        """
        Sets the timestamp in milliseconds after which only recorded conversations with a matching timestamp should be
        replayed.

        :param value: The timestamp in milliseconds.
        :type value: Optional[int]
        """
        self._replay_timestamp_ms = value

    async def aiohttp_request_method(
            self,
            method: str,
            url: StrOrURL,
            **kwargs) -> ClientSessionResponsePlayer:
        with self.begin() as session:
            query: Query = (ClientSessionPlayback.url == str(url))
            query = cast(Query, and_(query, ClientSessionPlayback.method == method))

            if "params" in kwargs and kwargs["params"]:
                query = cast(Query, and_(query, ClientSessionPlayback.request_params == kwargs["params"]))
            else:
                query = cast(Query, and_(query, ClientSessionPlayback.request_params.is_(None)))

            if "json" in kwargs and kwargs["json"]:
                query = cast(Query, and_(query, ClientSessionPlayback.request_json == kwargs["json"]))
            else:
                query = cast(Query, and_(query, ClientSessionPlayback.request_json.is_(None)))

            if self._replay_timestamp_ms is not None:
                query = cast(Query, and_(query, ClientSessionPlayback.timestamp >= self._replay_timestamp_ms))

            playback_entry: Optional[ClientSessionPlayback] = (
                session.query(ClientSessionPlayback).filter(query).first()
            )

            # Loosen the query conditions if the first, precise query didn't work.
            if playback_entry is None:
                query = (ClientSessionPlayback.url == str(url))
                query = cast(Query, and_(query, ClientSessionPlayback.method == method))
                if self._replay_timestamp_ms is not None:
                    query = cast(Query, and_(query, ClientSessionPlayback.timestamp >= self._replay_timestamp_ms))
                playback_entry = (
                    session.query(ClientSessionPlayback).filter(query).first()
                )

            if playback_entry is None:
                raise Exception("No matching response found")

            return ClientSessionResponsePlayer(
                method,
                url,
                playback_entry.response_code,
                playback_entry.response_text,
                playback_entry.response_json,
                playback_entry.response_binary,
            )

    def print_all_records(self):
        with self.begin() as session:
            all_records = session.query(ClientSessionPlayback).all()
            for record in all_records:
                print(record)
