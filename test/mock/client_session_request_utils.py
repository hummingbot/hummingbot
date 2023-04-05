from enum import Enum

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ClientSessionRequestMethod(Enum):
    POST = 1
    GET = 2
    PUT = 3
    PATCH = 4
    DELETE = 5


class ClientSessionRequestType(Enum):
    PLAIN = 1
    WITH_PARAMS = 2
    WITH_JSON = 3


class ClientSessionResponseType(Enum):
    ERROR = 0
    HEADER_ONLY = 1
    WITH_TEXT = 2
    WITH_JSON = 3
