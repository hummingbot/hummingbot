import asyncio
from concurrent.futures import (
    ThreadPoolExecutor,
)
import logging
import os
import threading
import time
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
)

from aiohttp import (
    ClientResponse,
    ClientSession,
    ClientTimeout,
    TCPConnector,
)
from eth_typing import (
    URI,
)
import requests

from web3._utils.async_caching import (
    async_lock,
)
from web3._utils.caching import (
    generate_cache_key,
)
from web3._utils.http import (
    DEFAULT_HTTP_TIMEOUT,
)
from web3.exceptions import (
    TimeExhausted,
)
from web3.utils.caching import (
    SimpleCache,
)


class HTTPSessionManager:
    logger = logging.getLogger("web3._utils.http_session_manager.HTTPSessionManager")
    _lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        cache_size: int = 100,
        session_pool_max_workers: int = 5,
    ) -> None:
        self.session_cache = SimpleCache(cache_size)
        self.session_pool = ThreadPoolExecutor(max_workers=session_pool_max_workers)

    @staticmethod
    def get_default_http_endpoint() -> URI:
        return URI(os.environ.get("WEB3_HTTP_PROVIDER_URI", "http://localhost:8545"))

    def cache_and_return_session(
        self,
        endpoint_uri: URI,
        session: requests.Session = None,
        request_timeout: Optional[float] = None,
    ) -> requests.Session:
        # cache key should have a unique thread identifier
        cache_key = generate_cache_key(f"{threading.get_ident()}:{endpoint_uri}")

        cached_session = self.session_cache.get_cache_entry(cache_key)
        if cached_session is not None:
            # If read from cache yields a session, no need to lock; return the session.
            # Sync is a bit simpler in this way since a `requests.Session` doesn't
            # really "close" in the same way that an async `ClientSession` does.
            # When "closed", it still uses http / https adapters successfully if a
            # request is made.
            return cached_session

        if session is None:
            session = requests.Session()

        with self._lock:
            cached_session, evicted_items = self.session_cache.cache(cache_key, session)
            self.logger.debug(f"Session cached: {endpoint_uri}, {cached_session}")

        if evicted_items is not None:
            evicted_sessions = evicted_items.values()
            for evicted_session in evicted_sessions:
                self.logger.debug(
                    "Session cache full. Session evicted from cache: "
                    f"{evicted_session}",
                )
            threading.Timer(
                # If `request_timeout` is `None`, don't wait forever for the closing
                # session to finish the request. Instead, wait over the default timeout.
                request_timeout or DEFAULT_HTTP_TIMEOUT + 0.1,
                self._close_evicted_sessions,
                args=[evicted_sessions],
            ).start()

        return cached_session

    def get_response_from_get_request(
        self, endpoint_uri: URI, *args: Any, **kwargs: Any
    ) -> requests.Response:
        kwargs.setdefault("timeout", DEFAULT_HTTP_TIMEOUT)
        session = self.cache_and_return_session(
            endpoint_uri, request_timeout=kwargs["timeout"]
        )
        response = session.get(endpoint_uri, *args, **kwargs)
        return response

    def json_make_get_request(
        self, endpoint_uri: URI, *args: Any, **kwargs: Any
    ) -> Dict[str, Any]:
        response = self.get_response_from_get_request(endpoint_uri, *args, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_response_from_post_request(
        self, endpoint_uri: URI, *args: Any, **kwargs: Any
    ) -> requests.Response:
        kwargs.setdefault("timeout", DEFAULT_HTTP_TIMEOUT)
        session = self.cache_and_return_session(
            endpoint_uri, request_timeout=kwargs["timeout"]
        )
        return session.post(endpoint_uri, *args, **kwargs)

    def json_make_post_request(
        self, endpoint_uri: URI, *args: Any, **kwargs: Any
    ) -> Dict[str, Any]:
        response = self.get_response_from_post_request(endpoint_uri, *args, **kwargs)
        response.raise_for_status()
        return response.json()

    def make_post_request(
        self, endpoint_uri: URI, data: Union[bytes, Dict[str, Any]], **kwargs: Any
    ) -> bytes:
        kwargs.setdefault("timeout", DEFAULT_HTTP_TIMEOUT)
        kwargs.setdefault("stream", False)

        start = time.time()
        timeout = kwargs["timeout"]

        with self.get_response_from_post_request(
            endpoint_uri, data=data, **kwargs
        ) as response:
            response.raise_for_status()
            if kwargs.get("stream"):
                return self._handle_streaming_response(response, start, timeout)
            else:
                return response.content

    @staticmethod
    def _handle_streaming_response(
        response: requests.Response, start: float, timeout: float
    ) -> bytes:
        response_body = b""
        for data in response.iter_content():
            response_body += data
            # Manually manage timeout so streaming responses time out
            # rather than resetting the timeout each time a response comes back
            if (time.time() - start) > timeout:
                raise TimeExhausted
        return response_body

    def _close_evicted_sessions(self, evicted_sessions: List[requests.Session]) -> None:
        for evicted_session in evicted_sessions:
            evicted_session.close()
            self.logger.debug(f"Closed evicted session: {evicted_session}")

    # -- async -- #

    async def async_cache_and_return_session(
        self,
        endpoint_uri: URI,
        session: Optional[ClientSession] = None,
        request_timeout: Optional[ClientTimeout] = None,
    ) -> ClientSession:
        # cache key should have a unique thread identifier
        cache_key = generate_cache_key(f"{threading.get_ident()}:{endpoint_uri}")

        evicted_items = None
        async with async_lock(self.session_pool, self._lock):
            if cache_key not in self.session_cache:
                if session is None:
                    session = ClientSession(
                        raise_for_status=True,
                        connector=TCPConnector(
                            force_close=True, enable_cleanup_closed=True
                        ),
                    )

                cached_session, evicted_items = self.session_cache.cache(
                    cache_key, session
                )
                self.logger.debug(
                    f"Async session cached: {endpoint_uri}, {cached_session}"
                )

            else:
                # get the cached session
                cached_session = self.session_cache.get_cache_entry(cache_key)
                session_is_closed = cached_session.closed
                session_loop_is_closed = cached_session._loop.is_closed()

                warning = (
                    "Async session was closed"
                    if session_is_closed
                    else (
                        "Loop was closed for async session"
                        if session_loop_is_closed
                        else None
                    )
                )
                if warning:
                    self.logger.debug(
                        f"{warning}: {endpoint_uri}, {cached_session}. "
                        f"Creating and caching a new async session for uri."
                    )

                    self.session_cache._data.pop(cache_key)
                    if not session_is_closed:
                        # if loop was closed but not the session, close the session
                        await cached_session.close()
                    self.logger.debug(
                        f"Async session closed and evicted from cache: {cached_session}"
                    )

                    # replace stale session with a new session at the cache key
                    _session = ClientSession(
                        raise_for_status=True,
                        connector=TCPConnector(
                            force_close=True, enable_cleanup_closed=True
                        ),
                    )
                    cached_session, evicted_items = self.session_cache.cache(
                        cache_key, _session
                    )
                    self.logger.debug(
                        f"Async session cached: {endpoint_uri}, {cached_session}"
                    )

        if evicted_items is not None:
            # At this point the evicted sessions are already popped out of the cache and
            # just stored in the `evicted_sessions` dict. So we can kick off a future
            # task to close them and it should be safe to pop out of the lock here.
            evicted_sessions = list(evicted_items.values())
            for evicted_session in evicted_sessions:
                self.logger.debug(
                    "Async session cache full. Session evicted from cache: "
                    f"{evicted_session}",
                )
            # Kick off an asyncio `Task` to close the evicted sessions. In the case
            # that the cache filled very quickly and some sessions have been evicted
            # before their original request has been made, we set the timer to a bit
            # more than the `request_timeout` for a call. This should make it so that
            # any call from an evicted session can still be made before the session
            # is closed.
            asyncio.create_task(
                self._async_close_evicted_sessions(
                    # if `ClientTimeout.total` is `None`, don't wait forever for the
                    # closing session to finish the request. Instead, use the default
                    # timeout.
                    request_timeout.total or DEFAULT_HTTP_TIMEOUT + 0.1,
                    evicted_sessions,
                )
            )

        return cached_session

    async def async_get_response_from_get_request(
        self, endpoint_uri: URI, *args: Any, **kwargs: Any
    ) -> ClientResponse:
        kwargs.setdefault("timeout", ClientTimeout(DEFAULT_HTTP_TIMEOUT))
        session = await self.async_cache_and_return_session(
            endpoint_uri, request_timeout=kwargs["timeout"]
        )
        response = await session.get(endpoint_uri, *args, **kwargs)
        return response

    async def async_json_make_get_request(
        self, endpoint_uri: URI, *args: Any, **kwargs: Any
    ) -> Dict[str, Any]:
        response = await self.async_get_response_from_get_request(
            endpoint_uri, *args, **kwargs
        )
        response.raise_for_status()
        return await response.json()

    async def async_get_response_from_post_request(
        self, endpoint_uri: URI, *args: Any, **kwargs: Any
    ) -> ClientResponse:
        kwargs.setdefault("timeout", ClientTimeout(DEFAULT_HTTP_TIMEOUT))
        session = await self.async_cache_and_return_session(
            endpoint_uri, request_timeout=kwargs["timeout"]
        )
        response = await session.post(endpoint_uri, *args, **kwargs)
        return response

    async def async_json_make_post_request(
        self, endpoint_uri: URI, *args: Any, **kwargs: Any
    ) -> Dict[str, Any]:
        response = await self.async_get_response_from_post_request(
            endpoint_uri, *args, **kwargs
        )
        response.raise_for_status()
        return await response.json()

    async def async_make_post_request(
        self, endpoint_uri: URI, data: Union[bytes, Dict[str, Any]], **kwargs: Any
    ) -> bytes:
        response = await self.async_get_response_from_post_request(
            endpoint_uri, data=data, **kwargs
        )
        response.raise_for_status()
        return await response.read()

    async def _async_close_evicted_sessions(
        self, timeout: float, evicted_sessions: List[ClientSession]
    ) -> None:
        await asyncio.sleep(timeout)

        for evicted_session in evicted_sessions:
            await evicted_session.close()
            self.logger.debug(f"Closed evicted async session: {evicted_session}")

        if any(not evicted_session.closed for evicted_session in evicted_sessions):
            self.logger.warning(
                "Some evicted async sessions were not properly closed: "
                f"{evicted_sessions}"
            )
