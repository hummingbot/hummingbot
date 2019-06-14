#!/usr/bin/env python

from enum import Enum
from os.path import join
from sqlalchemy import (
    create_engine,
    MetaData,
)
from sqlalchemy.engine.base import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import (
    sessionmaker,
    Session
)
from typing import Optional

from hummingbot import data_path
from . import get_declarative_base


class SQLSessionWrapper:
    def __init__(self, session: Session):
        self._session = session

    def __enter__(self) -> Session:
        return self._session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._session.commit()
        else:
            self._session.rollback()


class SQLConnectionType(Enum):
    TRADE_FILLS = 1


class SQLConnectionManager:
    _scm_trade_fills_instance: Optional["SQLConnectionManager"] = None

    @classmethod
    def get_declarative_base(cls):
        return get_declarative_base()

    @classmethod
    def get_trade_fills_instance(cls) -> "SQLConnectionManager":
        if cls._scm_trade_fills_instance is None:
            cls._scm_trade_fills_instance = SQLConnectionManager(SQLConnectionType.TRADE_FILLS)
        return cls._scm_trade_fills_instance

    def __init__(self, connection_type: SQLConnectionType, db_path: Optional[str] = None):
        if db_path is None:
            db_path = join(data_path(), "hummingbot_trades.sqlite")

        if connection_type is SQLConnectionType.TRADE_FILLS:
            self._engine: Engine = create_engine(f"sqlite:///{db_path}")
            self._metadata: MetaData = self.get_declarative_base().metadata
            self._metadata.create_all(self._engine)

        self._session_cls = sessionmaker(bind=self._engine)
        self._shared_session: Session = self._session_cls()

    @property
    def engine(self) -> Engine:
        return self._engine

    def get_shared_session(self) -> Session:
        try:
            # Detect whether the backing connection is still alive or not.
            conn = self._shared_session.connection()
            conn.execute("SELECT 1")
        except SQLAlchemyError:
            # Doing rollback will allow the session to reconnect automatically at the next request.
            self._shared_session.rollback()
        return self._shared_session

    def commit(self):
        self._shared_session.commit()

    def begin(self) -> SQLSessionWrapper:
        return SQLSessionWrapper(self._session_cls())
