#!/usr/bin/env python

from enum import Enum
import logging
from os.path import join
from sqlalchemy import (
    create_engine,
    MetaData,
)
from sqlalchemy.engine.base import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import (
    sessionmaker,
    Session,
    Query
)
from typing import Optional

from hummingbot import data_path
from hummingbot.logger.logger import HummingbotLogger
from . import get_declarative_base
from .metadata import Metadata as LocalMetadata


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
    _scm_logger: Optional[HummingbotLogger] = None
    _scm_trade_fills_instance: Optional["SQLConnectionManager"] = None

    LOCAL_DB_VERSION_KEY = "local_db_version"
    LOCAL_DB_VERSION_VALUE = "20190614"

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._scm_logger is None:
            cls._scm_logger = logging.getLogger(__name__)
        return cls._scm_logger

    @classmethod
    def get_declarative_base(cls):
        return get_declarative_base()

    @classmethod
    def get_trade_fills_instance(cls) -> "SQLConnectionManager":
        if cls._scm_trade_fills_instance is None:
            cls._scm_trade_fills_instance = SQLConnectionManager(SQLConnectionType.TRADE_FILLS)
        return cls._scm_trade_fills_instance

    def __init__(self,
                 connection_type: SQLConnectionType,
                 db_path: Optional[str] = None):
        if db_path is None:
            db_path = join(data_path(), "hummingbot_trades.sqlite")

        if connection_type is SQLConnectionType.TRADE_FILLS:
            self._engine: Engine = create_engine(f"sqlite:///{db_path}")
            self._metadata: MetaData = self.get_declarative_base().metadata
            self._metadata.create_all(self._engine)

        self._session_cls = sessionmaker(bind=self._engine)
        self._shared_session: Session = self._session_cls()

        if connection_type is SQLConnectionType.TRADE_FILLS:
            self.check_and_upgrade_trade_fills_db()

    @property
    def engine(self) -> Engine:
        return self._engine

    @classmethod
    def get_db_engine(cls, 
                      dialect: str, 
                      params: dict) -> Engine:
        if "sqlite" in dialect:
            db_path = params.get("db_path")

            return create_engine(f"{dialect}:///{db_path}")
        elif "oracle" in dialect:
            username = params.get("username")
            password = params.get("password")
            sid = params.get("sid")

            return create_engine(f"{dialect}://{username}:{password}@{sid}")
        else:
            username = params.get("username")
            password = params.get("password")
            host = params.get("host")
            port = params.get("port")
            db_name = params.get("db_name")

            return create_engine(f"{dialect}://{username}:{password}@{host}:{port}/{db_name}")

    def get_shared_session(self) -> Session:
        return self._shared_session

    def check_and_upgrade_trade_fills_db(self):
        try:
            query: Query = (self._shared_session.query(LocalMetadata)
                            .filter(LocalMetadata.key == self.LOCAL_DB_VERSION_KEY))
            result: Optional[LocalMetadata] = query.one_or_none()

            if result is None:
                version_info: LocalMetadata = LocalMetadata(key=self.LOCAL_DB_VERSION_KEY,
                                                            value=self.LOCAL_DB_VERSION_VALUE)
                self._shared_session.add(version_info)
                self._shared_session.commit()
            else:
                # There's no past db version to upgrade from at this moment. So we'll just update the version value
                # if needed.
                if result.value < self.LOCAL_DB_VERSION_VALUE:
                    result.value = self.LOCAL_DB_VERSION_VALUE
                    self._shared_session.commit()
        except SQLAlchemyError:
            self.logger().error("Unexpected error while checking and upgrading the local database.",
                                exc_info=True)

    def commit(self):
        self._shared_session.commit()

    def begin(self) -> SQLSessionWrapper:
        return SQLSessionWrapper(self._session_cls())
