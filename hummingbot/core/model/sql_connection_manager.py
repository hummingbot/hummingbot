#!/usr/bin/env python

from enum import Enum
from sqlalchemy import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import (
    sessionmaker,
    Session
)
from typing import (
    Optional,
    Dict
)
import conf
from . import (
    get_wings_base,
    get_sparrow_base
)


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
    ORDER_BOOKS = 2
    SPARROW = 3


class SQLConnectionManager:
    _scm_instances: Dict[str, "SQLConnectionManager"] = {}

    @classmethod
    def get_wings_base(cls):
        return get_wings_base()

    @classmethod
    def get_sparrow_base(cls):
        return get_sparrow_base()

    @classmethod
    def get_order_books_instance(cls,
                                 db_name: Optional[str] = None,
                                 db_conf: Optional[Dict] = None) -> "SQLConnectionManager":
        if not db_conf:
            db_conf: Dict = {
                "user": conf.mysql_user,
                "password": conf.mysql_password,
                "host": conf.mysql_master_server
            }
        if not db_name:
            db_name = conf.order_book_db
        instance_key: str = f"{db_conf['host']}/{db_name}"

        if instance_key not in cls._scm_instances:
            cls._scm_instances[instance_key] = cls(SQLConnectionType.ORDER_BOOKS,
                                                   db_name=db_name,
                                                   db_conf=db_conf)
        return cls._scm_instances[instance_key]

    @classmethod
    def get_sparrow_instance(cls,
                             db_name: Optional[str] = None,
                             db_conf: Optional[Dict] = None) -> "SQLConnectionManager":
        if not db_conf:
            db_conf = {
                "user": conf.mysql_user,
                "password": conf.mysql_password,
                "host": conf.mysql_master_server,
            }
        if not db_name:
            db_name = conf.sparrow_db
        instance_key: str = f"{db_conf['host']}/{db_name}"

        if instance_key not in cls._scm_instances:
            cls._scm_instances[instance_key] = cls(SQLConnectionType.SPARROW,
                                                   db_name=db_name,
                                                   db_conf=db_conf)
        return cls._scm_instances[instance_key]

    def __init__(self, connection_type: SQLConnectionType, db_conf: Dict, db_name: Optional[str] = None):
        if db_name is None:
            if connection_type is SQLConnectionType.ORDER_BOOKS:
                db_name = conf.order_book_db
            elif connection_type is SQLConnectionType.SPARROW:
                db_name = conf.sparrow_db

        self._engine: Engine = create_engine(f"mysql+mysqldb://{db_conf['user']}:{db_conf['password']}"
                                             f"@{db_conf['host']}/{db_name}",
                                             pool_pre_ping=True)

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
