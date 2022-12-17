import asyncio
import logging
import sqlite3
from collections import defaultdict
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from typing import (
    Any,
    AsyncIterable,
    ContextManager,
    Dict,
    List,
    NamedTuple,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_type_hints,
)

from juno import time
from juno.itertools import generate_missing_spans, merge_adjacent_spans

_log = logging.getLogger(__name__)

# Version should be incremented every time a storage schema changes.
_VERSION = "v54"

T = TypeVar("T")

Primitive = Union[bool, int, float, Decimal, str]


def _serialize_decimal(d: Decimal) -> bytes:
    return str(d).encode("ascii")


def _deserialize_decimal(s: bytes) -> Decimal:
    return Decimal(s.decode("ascii"))


sqlite3.register_adapter(Decimal, _serialize_decimal)
sqlite3.register_converter("DECIMAL", _deserialize_decimal)

sqlite3.register_adapter(bool, int)
sqlite3.register_converter("BOOLEAN", lambda v: bool(int(v)))


class SQLite:
    def __init__(self) -> None:
        self._tables: Dict[Any, Set[str]] = defaultdict(set)

    async def stream_time_series_spans(
        self,
        shard: str,
        key: str,
        start: int = 0,
        end: int = time.MAX_TIME,
    ) -> AsyncIterable[Tuple[int, int]]:
        def inner() -> List[Tuple[int, int]]:
            _log.info(f"Streaming span(s) between {time.format_span(start, end)} from shard {shard} {key}.")
            with self._connect(shard) as conn:
                span_key = f"{key}_{_SPAN_KEY}"
                self._ensure_table(conn, span_key, Span)
                return conn.execute(
                    f"SELECT * FROM {span_key} WHERE start < ? AND end > ? ORDER BY start",
                    [end, start],
                ).fetchall()

        rows = await asyncio.get_running_loop().run_in_executor(None, inner)
        for span_start, span_end in merge_adjacent_spans(rows):
            yield max(span_start, start), min(span_end, end)

    async def stream_time_series(
        self,
        shard: str,
        key: str,
        type_: Type[T],
        start: int = 0,
        end: int = time.MAX_TIME,
    ) -> AsyncIterable[T]:
        def inner() -> List[T]:
            _log.info(f"Streaming items between {time.format_span(start, end)} from shard {shard} {key}.")
            with self._connect(shard) as conn:
                self._ensure_table(conn, key, type_)
                return conn.execute(
                    f"SELECT * FROM {key} WHERE time >= ? AND time < ? ORDER BY time",
                    [start, end],
                ).fetchall()

        rows = await asyncio.get_running_loop().run_in_executor(None, inner)
        for row in rows:
            yield type_(*row)

    async def store_time_series_and_span(self, shard: str, key: str, items: List[Any], start: int, end: int) -> None:
        # Even if items list is empty, we still want to store a span for the period!
        if len(items) > 0:
            type_ = type(items[0])
            if start > items[0].time:
                raise ValueError(f"Span start {start} bigger than first item time {items[0].time}.")
            if end <= items[-1].time:
                raise ValueError(f"Span end {end} smaller than or equal to last item time {items[-1].time}.")

        def inner() -> None:
            span_key = f"{key}_{_SPAN_KEY}"
            with self._connect(shard) as conn:
                self._ensure_table(conn, span_key, Span)
                if len(items) > 0:
                    self._ensure_table(conn, key, type_)

                c = conn.cursor()
                existing_spans = c.execute(
                    f"SELECT * FROM {span_key} WHERE start < ? AND end > ? ORDER BY start",
                    [end, start],
                ).fetchall()
                merged_existing_spans = merge_adjacent_spans(existing_spans)
                missing_spans = list(generate_missing_spans(start, end, merged_existing_spans))
                if len(missing_spans) == 0:
                    return
                missing_item_spans = (
                    [items]
                    if len(existing_spans) == 0
                    else [[i for i in items if i.time >= s and i.time < e] for s, e in missing_spans]
                )
                for (mstart, mend), mitems in zip(missing_spans, missing_item_spans):
                    _log.info(
                        f"Inserting {len(mitems)} item(s) between {time.format_span(mstart, mend)} to shard {shard} "
                        f"{key}."
                    )
                    if len(mitems) > 0:
                        try:
                            c.executemany(
                                f"INSERT INTO {key} " f'VALUES ({", ".join(["?"] * len(get_type_hints(type_)))})',
                                mitems,
                            )
                        except sqlite3.IntegrityError as err:
                            _log.error(f"{err} {shard} {key}")
                            raise
                    c.execute(f"INSERT INTO {span_key} VALUES (?, ?)", [mstart, mend])
                conn.commit()

        await asyncio.get_running_loop().run_in_executor(None, inner)

    def _connect(self, shard: str) -> ContextManager[sqlite3.Connection]:
        path = str(_home_path("data") / f"{_VERSION}_{shard}.db")
        _log.debug(f"Opening shard {path}.")
        return closing(sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES))

    def _ensure_table(self, conn: sqlite3.Connection, name: str, type_: Type[Any]) -> None:
        tables = self._tables[conn]
        if name not in tables:
            c = conn.cursor()
            _create_table(c, type_, name)
            conn.commit()
            tables.add(name)


def _create_table(c: sqlite3.Cursor, type_: Type[Any], name: str) -> None:
    type_hints = get_type_hints(type_)
    col_types = [(k, _type_to_sql_type(v)) for k, v in type_hints.items()]

    # Create table.
    cols = []
    for col_name, col_type in col_types:
        cols.append(f"{col_name} {col_type} NOT NULL")
    c.execute(f'CREATE TABLE IF NOT EXISTS {name} ({", ".join(cols)})')

    # Add indices.
    meta_getter = getattr(type_, "meta", None)
    meta = meta_getter() if meta_getter else None
    if meta:
        for cname, ctype in meta.items():
            if ctype == "index":
                c.execute(f"CREATE INDEX IF NOT EXISTS {name}Index ON {name}({cname})")
            elif ctype == "unique":
                c.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {name}UniqueIndex ON {name}({cname})")
            else:
                raise NotImplementedError()


def _type_to_sql_type(type_: Type[Primitive]) -> str:
    if type_ is int:
        return "INTEGER"
    if type_ is float:
        return "REAL"
    if type_ is Decimal:
        return "DECIMAL"
    if type_ is str:
        return "TEXT"
    if type_ is bool:
        return "BOOLEAN"
    raise NotImplementedError(f"Missing conversion for type {type_}.")


def _home_path(*args: str) -> Path:
    path = Path(Path.home(), ".juno").joinpath(*args)
    path.mkdir(parents=True, exist_ok=True)
    return path


class Span(NamedTuple):
    start: int
    end: int

    @staticmethod
    def meta() -> Dict[str, str]:
        return {
            "start": "unique",
            "end": "unique",
        }


_SPAN_KEY = Span.__name__.lower()
