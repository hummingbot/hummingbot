import time
from contextlib import contextmanager
from enum import Enum
from typing import Any, Callable, Dict, Generator, Optional, Type, cast
from weakref import ReferenceType, ref

from aiohttp import ClientResponse, ClientSession
from sqlalchemy import JSON, BigInteger, Column, Enum as SQLEnum, Integer, Text, and_, create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Query, Session, sessionmaker

from hummingbot.model.transaction_base import TransactionBase

Base = declarative_base()


class HttpRequestMethod(Enum):
    POST = 1
    GET = 2
    PUT = 3
    PATCH = 4
    DELETE = 5


class HttpRequestType(Enum):
    PLAIN = 1
    WITH_PARAMS = 2
    WITH_JSON = 3


class HttpResponseType(Enum):
    HEADER_ONLY = 1
    WITH_TEXT = 2
    WITH_JSON = 3


class HttpPlayback(Base):
    __tablename__ = "HttpPlayback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(BigInteger, nullable=False)
    url = Column(Text, index=True, nullable=False)
    method = Column(SQLEnum(HttpRequestMethod), nullable=False)
    request_type = Column(SQLEnum(HttpRequestType), nullable=False)
    request_params = Column(JSON)
    request_json = Column(JSON)
    response_type = Column(SQLEnum(HttpResponseType), nullable=False)
    response_code = Column(Integer, nullable=False)
    response_text = Column(Text)
    response_json = Column(JSON)


class HttpRecorderClientResponse(ClientResponse):
    _database_id: Optional[int]
    _parent_recorder_ref: Optional[ReferenceType]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._database_id = None
        self._parent_recorder_ref = None

    @property
    def database_id(self) -> Optional[int]:
        return self._database_id

    @database_id.setter
    def database_id(self, value: int):
        self._database_id = value

    @property
    def parent_recorder(self) -> Optional["HttpRecorder"]:
        if self._parent_recorder_ref is not None:
            return self._parent_recorder_ref()
        return None

    @parent_recorder.setter
    def parent_recorder(self, value: "HttpRecorder"):
        self._parent_recorder_ref = ref(value)

    def get_playback_entry(self, session: Session) -> HttpPlayback:
        return session.query(HttpPlayback).filter(HttpPlayback.id == self.database_id).one()

    async def text(self, *args, **kwargs) -> str:
        response_text: str = await super().text(*args, **kwargs)
        with self.parent_recorder.begin() as session:
            session: Session = session
            playback_entry: HttpPlayback = self.get_playback_entry(session)
            playback_entry.response_text = HttpResponseType.WITH_TEXT
            playback_entry.response_text = response_text
        return response_text

    async def json(self, *args, **kwargs) -> Any:
        response_obj: Any = await super().json(*args, **kwargs)
        with self.parent_recorder.begin() as session:
            session: Session = session
            playback_entry: HttpPlayback = self.get_playback_entry(session)
            playback_entry.response_type = HttpResponseType.WITH_JSON
            playback_entry.response_json = response_obj
        return response_obj


class HttpPlayerBase(TransactionBase):
    def __init__(self, db_path: str):
        self._db_path: str = db_path
        self._db_engine: Engine = create_engine(f"sqlite:///{db_path}")
        self._session_factory: Callable[[], Session] = sessionmaker(bind=self._db_engine)
        Base.metadata.create_all(self._db_engine)

    def get_new_session(self) -> Session:
        return self._session_factory()

    @contextmanager
    def patch_aiohttp_client(self) -> Generator[Type[ClientSession], None, None]:
        try:
            ClientSession._original_request_func = ClientSession._request
            ClientSession._request = lambda s, *args, **kwargs: self.aiohttp_request_method(s, *args, **kwargs)
            yield ClientSession
        finally:
            ClientSession._request = ClientSession._original_request_func
            del ClientSession._original_request_func


class HttpRecorder(HttpPlayerBase):
    """
    Records HTTP conversations made over any aiohttp.ClientSession object, and records them to an SQLite database file
    for replaying.

    Usage:
    recorder = HttpRecorder('test.db')
    with recorder.patch_aiohttp_client:
      # all aiohttp conversations inside this block will be recorded to test.db
      async with aiohttp.ClientSession() as client:
        async with client.get("https://api.binance.com/api/v3/time") as resp:
          data = await resp.json()      # the request and response are recorded to test.db
          ...
    """
    async def aiohttp_request_method(
            self,
            client: ClientSession,
            method: str,
            url: str,
            **kwargs) -> HttpRecorderClientResponse:
        try:
            if hasattr(client, "_reentrant_ref_count"):
                client._reentrant_ref_count += 1
            else:
                client._reentrant_ref_count = 1
                client._original_response_class = client._response_class
                client._response_class = HttpRecorderClientResponse
            request_type: HttpRequestType = HttpRequestType.PLAIN
            request_params: Optional[Dict[str, str]] = None
            request_json: Optional[Any] = None
            if "params" in kwargs:
                request_type = HttpRequestType.WITH_PARAMS
                request_params = kwargs.get("params")
            if "json" in kwargs:
                request_type = HttpRequestType.WITH_JSON
                request_json = kwargs.get("json")
            response: HttpRecorderClientResponse = await client._original_request_func(method, url, **kwargs)
            response.parent_recorder = self
            with self.begin() as session:
                session: Session = session
                playback_entry: HttpPlayback = HttpPlayback(
                    timestamp=int(time.time() * 1e3),
                    url=url,
                    method=method,
                    request_type=request_type,
                    request_params=request_params,
                    request_json=request_json,
                    response_type=HttpResponseType.HEADER_ONLY,
                    response_code=response.status
                )
                session.add(playback_entry)
                session.flush()
                response.database_id = playback_entry.id
            return response
        finally:
            client._reentrant_ref_count -= 1
            if client._reentrant_ref_count < 1:
                client._response_class = client._original_response_class
                del client._original_response_class
                del client._reentrant_ref_count


class HttpPlayerResponse:
    def __init__(self, method: str, url: str, status: int, response_text: Optional[str], response_json: Optional[Any]):
        self.method = method
        self.url = url
        self.status = status
        self._response_text: Optional[str] = response_text
        self._response_json: Optional[Any] = response_json

    async def text(self) -> str:
        if self._response_text is None:
            raise EnvironmentError("No response text has been recorded for replaying.")
        return self._response_text

    async def json(self) -> Any:
        if self._response_json is None:
            raise EnvironmentError("No response json has been recorded for replaying.")
        return self._response_json

    def release(self):
        """
        This is needed to satisfy ClientSession logic.
        """
        pass


class HttpPlayer(HttpPlayerBase):
    """
    Given a HTTP conversation record db, patch aiohttp.ClientSession such that it will only replay matched recorded
    conversations.

    When aiohttp.ClientSession makes any request inside `patch_aiohttp_client()`, the player will search for a matching
    response by URL, request params and request JSON. If no matching response is found, then an exception will be
    raised.

    Usage:
    recorder = HttpPlayer('test.db')
    with recorder.patch_aiohttp_client:
      # all aiohttp responses within this block will be replays from past records in test.db.
      async with aiohttp.ClientSession() as client:
        async with client.get("https://api.binance.com/api/v3/time") as resp:
          data = await resp.json()      # the data returned will be the recorded response
          ...
    """
    _replay_timestamp_ms: Optional[int]

    def __init__(self, db_path: str):
        super().__init__(db_path)
        self._replay_timestamp_ms = None

    @property
    def replay_timestamp_ms(self) -> Optional[int]:
        return self._replay_timestamp_ms

    @replay_timestamp_ms.setter
    def replay_timestamp_ms(self, value: Optional[int]):
        self._replay_timestamp_ms = value

    async def aiohttp_request_method(
            self,
            _: ClientSession,
            method: str,
            url: str,
            **kwargs) -> HttpPlayerResponse:
        with self.begin() as session:
            session: Session = session
            query: Query = (HttpPlayback.url == url)
            if "params" in kwargs:
                query = cast(Query, and_(query, HttpPlayback.request_params == kwargs["params"]))
            if "json" in kwargs:
                query = cast(Query, and_(query, HttpPlayback.request_json == kwargs["json"]))
            if self._replay_timestamp_ms is not None:
                query = cast(Query, and_(query, HttpPlayback.timestamp >= self._replay_timestamp_ms))
            playback_entry: Optional[HttpPlayback] = (
                session.query(HttpPlayback).filter(query).first()
            )

            # Loosen the query conditions if the first, precise query didn't work.
            if playback_entry is None:
                query = (HttpPlayback.url == url)
                if self._replay_timestamp_ms is not None:
                    query = cast(Query, and_(query, HttpPlayback.timestamp >= self._replay_timestamp_ms))
                playback_entry = (
                    session.query(HttpPlayback).filter(query).first()
                )

            return HttpPlayerResponse(
                method,
                url,
                playback_entry.response_code,
                playback_entry.response_text,
                playback_entry.response_json
            )
