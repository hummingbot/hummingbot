import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - fallback for environments without redis installed
    Redis = None  # type: ignore


class EventBus(ABC):
    """
    Minimal publish/subscribe abstraction used by the Market Data Service and UserEngines.
    Concrete implementations must provide fan-out semantics so multiple subscribers can consume the same topic.
    """

    @abstractmethod
    async def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        ...

    @abstractmethod
    async def subscribe(self, topic: str):
        """
        Returns an async iterator that yields payload dictionaries for the requested topic.
        The iterator must expose `aclose()` for deterministic shutdown.
        """
        ...


class InMemorySubscription:
    def __init__(self, queue: "asyncio.Queue[Dict[str, Any]]", on_close):
        self._queue = queue
        self._on_close = on_close
        self._active = True

    def __aiter__(self) -> AsyncIterator[Dict[str, Any]]:
        return self

    async def __anext__(self) -> Dict[str, Any]:
        if not self._active:
            raise StopAsyncIteration
        while self._active:
            try:
                payload = await self._queue.get()
                if payload is None:
                    continue
                return payload
            except asyncio.CancelledError:
                self._active = False
                raise
        raise StopAsyncIteration

    async def aclose(self):
        if not self._active:
            return
        self._active = False
        await self._on_close()


class InMemoryEventBus(EventBus):
    """
    Lightweight EventBus implementation used in unit tests.
    """

    def __init__(self):
        self._topics: Dict[str, List[asyncio.Queue]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    async def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        queues = self._topics.get(topic, [])
        for queue in queues:
            await queue.put(payload)

    async def subscribe(self, topic: str):
        queue: asyncio.Queue = asyncio.Queue()
        async with self._locks.setdefault(topic, asyncio.Lock()):
            self._topics.setdefault(topic, []).append(queue)

        async def _teardown():
            async with self._locks.setdefault(topic, asyncio.Lock()):
                subscribers = self._topics.get(topic, [])
                if queue in subscribers:
                    subscribers.remove(queue)

        return InMemorySubscription(queue, _teardown)


class RedisStreamSubscription:
    def __init__(
        self,
        redis_client: "Redis",
        topic: str,
        group: str,
        consumer: str,
        block_ms: int,
    ):
        self._redis = redis_client
        self._topic = topic
        self._group = group
        self._consumer = consumer
        self._block_ms = block_ms
        self._active = True

    def __aiter__(self) -> AsyncIterator[Dict[str, Any]]:
        return self

    async def __anext__(self) -> Dict[str, Any]:
        if not self._active:
            raise StopAsyncIteration
        while self._active:
            try:
                response = await self._redis.xreadgroup(
                    groupname=self._group,
                    consumername=self._consumer,
                    streams={self._topic: ">"},
                    count=10,
                    block=self._block_ms,
                )
                if not response:
                    continue
                for _, entries in response:
                    for entry_id, data in entries:
                        payload = self._deserialize_entry(data)
                        await self._redis.xack(self._topic, self._group, entry_id)
                        if payload is not None:
                            return payload
            except asyncio.CancelledError:
                self._active = False
                raise
        raise StopAsyncIteration

    async def aclose(self):
        self._active = False

    @staticmethod
    def _deserialize_entry(data: Dict[bytes, bytes]) -> Optional[Dict[str, Any]]:
        raw = data.get(b"data")
        if raw is None:
            return None
        try:
            return json.loads(raw.decode())
        except Exception:
            return None


class RedisEventBus(EventBus):
    """
    Redis Streams backed EventBus. Uses consumer groups (one per topic) to provide fan-out to many subscribers while
    maintaining backpressure semantics (each subscription receives every message exactly once).
    """

    def __init__(
        self,
        redis_client: "Redis",
        maxlen: int = 1000,
        consumer_group_prefix: str = "jarvis",
        block_ms: int = 1000,
    ):
        if Redis is None:
            raise RuntimeError("redis package is required to use RedisEventBus.")
        self._redis = redis_client
        self._maxlen = maxlen
        self._group_prefix = consumer_group_prefix
        self._block_ms = block_ms
        self._group_cache: Dict[str, bool] = {}
        self._group_lock = asyncio.Lock()

    async def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload)
        await self._redis.xadd(topic, {"data": data}, maxlen=self._maxlen, approximate=True)

    async def subscribe(self, topic: str):
        group = f"{self._group_prefix}:{topic}"
        await self._ensure_group(topic, group)
        consumer = uuid.uuid4().hex
        subscription = RedisStreamSubscription(self._redis, topic, group, consumer, self._block_ms)
        return subscription

    async def _ensure_group(self, topic: str, group: str):
        if self._group_cache.get(group):
            return
        async with self._group_lock:
            if self._group_cache.get(group):
                return
            try:
                await self._redis.xgroup_create(name=topic, groupname=group, id="0", mkstream=True)
            except Exception:
                # Group might already exist; ignore
                pass
            self._group_cache[group] = True
