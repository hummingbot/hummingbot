"""
The `ClientSessionPlayback` module defines the `ClientSessionPlayback` class which represents a recorded HTTP
conversation that can be played back using a `ClientSessionPlayer` instance.

Description
-----------
The `ClientSessionPlayback` class defines an ORM model that represents a recorded HTTP conversation. It defines
attributes for the URL, request and response data, and the timestamp. The class also provides a method for returning the
class instance as a dictionary.

Attributes
----------
id : int
    The primary key of the conversation in the database.
timestamp : int
    The timestamp of the conversation, in milliseconds since the Unix epoch.
url : str
    The URL of the conversation.
method : ClientSessionRequestMethod
    The HTTP method used in the conversation.
request_type : ClientSessionRequestType
    The type of request data in the conversation.
request_headers : Dict[str, str]
    The headers of the request in the conversation.
request_params : Dict[str, Any]
    The query parameters of the request in the conversation.
request_json : Dict[str, Any]
    The JSON data of the request in the conversation.
response_type : ClientSessionResponseType
    The type of response data in the conversation.
response_code : int
    The HTTP status code of the response in the conversation.
response_text : str
    The text data of the response in the conversation.
response_json : Dict[str, Any]
    The JSON data of the response in the conversation.
response_binary : bytes
    The binary data of the response in the conversation.

Methods
-------
__repr__()
    Return a string representation of the `ClientSessionPlayback` instance.
as_dict() -> Dict[str, Any]
    Return a dictionary representation of the `ClientSessionPlayback` instance.

Example usage
-------------
Here's an example of how to use the `ClientSessionPlayback` module:

    from test.mock.client_session_recorder_utils import (
        ClientSessionPlayback,
        ClientSessionRequestMethod,
        ClientSessionRequestType,
        ClientSessionResponseType,
    )

    conversation = ClientSessionPlayback(
        timestamp=1234567890,
        url='https://example.com/api/v1/data',
        method=ClientSessionRequestMethod.GET,
        request_type=ClientSessionRequestType.PLAIN,
        request_headers={'Authorization': 'Bearer token'},
        request_params={'param1': 'value1', 'param2': 'value2'},
        response_type=ClientSessionResponseType.JSON,
        response_code=200,
        response_text='{"key1": "value1", "key2": "value2"}',
        response_json={'key1': 'value1', 'key2': 'value2'},
    )

Module name: client_session_playback.py
Module description: The `ClientSessionPlayback` module defines the `ClientSessionPlayback` class which represents a
                     recorded HTTP conversation that can be played back using a `ClientSessionPlayer` instance.
Copyright (c) 2023
License: MIT
Author: Unknown
Creation date: 2023/04/08
"""
from test.mock.client_session_recorder_utils import (
    Base,
    ClientSessionRequestMethod,
    ClientSessionRequestType,
    ClientSessionResponseType,
)
from typing import Any, Dict

from sqlalchemy import JSON, BigInteger, Column, Enum as SQLEnum, Integer, LargeBinary, Text


class ClientSessionPlayback(Base):
    """
    A class that represents an HTTP conversation recorded in a database by `ClientSessionRecorder`.

    Attributes:
    -----------
    id : int
        The unique identifier of this HTTP conversation record.
    timestamp : int
        The timestamp of when this conversation occurred, in milliseconds since the Unix epoch.
    url : str
        The URL of the HTTP request.
    method : str
        The HTTP method of the request.
    request_type : str
        The type of the request, either "regular" or "websocket".
    request_headers : dict
        A dictionary of headers included in the request.
    request_params : dict
        A dictionary of parameters included in the request.
    request_json : dict
        A dictionary representing the JSON payload of the request, if any.
    response_type : str
        The type of the response, either "regular" or "websocket".
    response_code : int
        The HTTP status code of the response.
    response_text : str
        The text content of the response.
    response_json : dict
        A dictionary representing the JSON payload of the response, if any.
    response_binary : bytes
        The binary content of the response.

    Methods:
    --------
    __repr__(self)
        Returns a string representation of this HTTP conversation record.
    as_dict(self) -> Dict[str, Any]
        Returns a dictionary representation of this HTTP conversation record.
    """
    __tablename__ = "ClientSessionPlayback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(BigInteger, nullable=False)
    url = Column(Text, index=True, nullable=False)
    method = Column(SQLEnum(ClientSessionRequestMethod), nullable=False)
    request_type = Column(SQLEnum(ClientSessionRequestType), nullable=False)
    request_headers = Column(JSON)
    request_params = Column(JSON)
    request_json = Column(JSON)
    response_type = Column(SQLEnum(ClientSessionResponseType), nullable=False)
    response_code = Column(Integer, nullable=False)
    response_text = Column(Text)
    response_json = Column(JSON)
    response_binary = Column(LargeBinary)

    def __repr__(self):
        return f"<ClientSessionPlayback(id={self.id}, " \
               f"timestamp={self.timestamp}, " \
               f"url={self.url}, " \
               f"method={self.method}, " \
               f"request_type={self.request_type}, " \
               f"request_params={self.request_params}, " \
               f"request_headers={self.request_headers}, " \
               f"request_json={self.request_json}, " \
               f"response_type={self.response_type}, " \
               f"response_code={self.response_code}, " \
               f"response_text={self.response_text}, " \
               f"response_binary={self.response_binary}, " \
               f"response_json={self.response_json})>"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "url": self.url,
            "method": self.method,
            "request_type": self.request_type,
            "request_params": self.request_params,
            'request_headers': self.request_headers,
            "request_json": self.request_json,
            "response_type": self.response_type,
            "response_code": self.response_code,
            "response_text": self.response_text,
            "response_json": self.response_json,
            "response_binary": self.response_binary,
        }
