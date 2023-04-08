"""
The `DatabaseMixin` module provides a mixin class for adding database functionality to another class.

Description
-----------
The `DatabaseMixin` module defines a mixin class for adding database functionality to another class. The class
provides methods for initializing a new SQLite database file, creating a new session factory, and retrieving
a new database session. The module also defines several enums that are used to represent different types of
client session requests and responses.

Example usage
-------------
Here's an example usage of the `DatabaseMixin` module:

    from hummingbot.model.database import DatabaseMixin

    class MyClass(DatabaseMixin):
        def __init__(self):
            DatabaseMixin.__init__(self, "test.db")

        def my_func(self):
            session = self.get_new_session()
            ...

Module name: database_mixin.py
Module description: A mixin class for adding database functionality to another class.
Copyright (c) 2023
License: MIT
Author: Unknown
Creation date: 2023/04/08
"""
from enum import Enum
from typing import Callable

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from hummingbot.model.transaction_base import TransactionBase

Base = declarative_base()


class DatabaseMixin(TransactionBase):
    def __init__(self, db_path: str):
        self._db_path: str = db_path
        self._db_engine: Engine = create_engine(f"sqlite:///{db_path}")
        self._session_factory: Callable[[], Session] = sessionmaker(bind=self._db_engine)
        Base.metadata.create_all(self._db_engine)

    def get_new_session(self) -> Session:
        return self._session_factory()


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
    WITH_BINARY = 4
