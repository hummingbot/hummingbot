import asyncio
import logging
import math
import time
from typing import Awaitable, Callable, Dict, Generic, List, Mapping, Optional, TypeVar

from neutronx_sdk import MAINNET, TESTNET, Network
from neutronx_sdk.indexer.api import API_KEY_HEADER, requests_per_minute

from hummingbot.connector.derivative.neutronx_perpetual import neutronx_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, RESTResponse
from hummingbot.core.web_assistant.rest_post_processors import RESTPostProcessorBase
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

NETWORKS: Dict[str, Network] = {CONSTANTS.DOMAIN: MAINNET, CONSTANTS.TESTNET_DOMAIN: TESTNET}
RETRY_AFTER_HEADER = "Retry-After"

T = TypeVar("T")


class IndexerRateLimitedError(IOError):
    def __init__(self, url: str, retry_after: float) -> None:
        super().__init__(f"the NeutronX indexer rate-limited {url}, requests pause for {retry_after:.0f} s")
        self.retry_after = retry_after


class IndexerBackoff:
    _logger: Optional[HummingbotLogger] = None

    def __init__(self) -> None:
        self._strikes = 0
        self._until = 0.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    @property
    def remaining(self) -> float:
        return max(0.0, self._until - time.monotonic())

    def hit(self, retry_after: Optional[float]) -> float:
        now = time.monotonic()
        fresh = now >= self._until
        if fresh:
            self._strikes += 1
        delay = max(retry_after or 1.0, min(CONSTANTS.RATE_LIMIT_BACKOFF_MAX, 2.0 ** (max(self._strikes, 1) - 1)))
        self._until = max(self._until, now + delay)
        if fresh and self._strikes == 1:
            self.logger().warning(f"The NeutronX indexer rate limit was hit, REST requests pause for {delay:.0f} s")
        return delay

    def clear(self) -> None:
        self._strikes = 0

    async def wait(self) -> None:
        delay = self.remaining
        if delay > 0:
            await asyncio.sleep(delay)


class IndexerBackoffPreProcessor(RESTPreProcessorBase):
    def __init__(self, backoff: IndexerBackoff) -> None:
        self._backoff = backoff

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.throttler_limit_id != CONSTANTS.INDEXER_STATUS_LIMIT_ID:
            await self._backoff.wait()
        return request


class IndexerBackoffPostProcessor(RESTPostProcessorBase):
    def __init__(self, backoff: IndexerBackoff) -> None:
        self._backoff = backoff

    async def post_process(self, response: RESTResponse) -> RESTResponse:
        if response.status == CONSTANTS.HTTP_TOO_MANY_REQUESTS:
            delay = self._backoff.hit(retry_after(response.headers))
            await response.text()
            raise IndexerRateLimitedError(response.url, delay)
        if response.status < 400:
            self._backoff.clear()
        return response


class SharedRequest(Generic[T]):
    def __init__(self, fetch: Callable[[], Awaitable[T]], ttl: float = 0.0) -> None:
        self._fetch = fetch
        self._ttl = ttl
        self._task: Optional["asyncio.Future[T]"] = None
        self._value: Optional[T] = None
        self._fetched_at = -math.inf

    async def get(self) -> T:
        if self._value is not None and time.monotonic() - self._fetched_at < self._ttl:
            return self._value
        if self._task is None or self._task.done():
            self._task = asyncio.ensure_future(self._refresh())
            self._task.add_done_callback(_consume_exception)
        return await asyncio.shield(self._task)

    async def _refresh(self) -> T:
        value = await self._fetch()
        self._value, self._fetched_at = value, time.monotonic()
        return value


def _consume_exception(task: "asyncio.Future") -> None:
    if not task.cancelled():
        task.exception()


def retry_after(headers: Optional[Mapping[str, str]]) -> Optional[float]:
    try:
        return float((headers or {})[RETRY_AFTER_HEADER])
    except (KeyError, TypeError, ValueError):
        return None


class IndexerApiKeyPreProcessor(RESTPreProcessorBase):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        request.headers = {**(request.headers or {}), API_KEY_HEADER: self._api_key}
        return request


def network_for(domain: str) -> Network:
    return NETWORKS[domain]


def indexer_rest_url(network: Network, path_url: str) -> str:
    if not network.indexer_url:
        raise ValueError(f"the indexer REST URL of NeutronX {network.name} is not configured")
    return f"{network.indexer_url}{path_url}"


def indexer_ws_url(network: Network) -> str:
    if not network.indexer_ws_url:
        raise ValueError(f"the indexer WebSocket URL of NeutronX {network.name} is not configured")
    return network.indexer_ws_url


def indexer_headers(api_key: Optional[str]) -> Dict[str, str]:
    return {API_KEY_HEADER: api_key} if api_key else {}


def public_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    return indexer_rest_url(network_for(domain), path_url)


def private_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    return public_rest_url(path_url, domain)


def rate_limits(api_key: Optional[str] = None) -> List[RateLimit]:
    general = requests_per_minute(api_key) - CONSTANTS.NETWORK_CHECKS_PER_MINUTE
    return [
        RateLimit(limit_id=CONSTANTS.INDEXER_REST_LIMIT_ID, limit=general, time_interval=60),
        RateLimit(
            limit_id=CONSTANTS.INDEXER_STATUS_LIMIT_ID, limit=CONSTANTS.STATUS_REQUESTS_PER_MINUTE, time_interval=60
        ),
    ]


def create_throttler(api_key: Optional[str] = None) -> AsyncThrottler:
    return AsyncThrottler(rate_limits(api_key))


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    api_key: Optional[str] = None,
    backoff: Optional[IndexerBackoff] = None,
) -> WebAssistantsFactory:
    backoff = backoff or IndexerBackoff()
    pre_processors: List[RESTPreProcessorBase] = [IndexerBackoffPreProcessor(backoff)]
    if api_key:
        pre_processors.append(IndexerApiKeyPreProcessor(api_key))
    return WebAssistantsFactory(
        throttler=throttler or create_throttler(api_key),
        rest_pre_processors=pre_processors,
        rest_post_processors=[IndexerBackoffPostProcessor(backoff)],
    )


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DOMAIN,
) -> float:
    return time.time() * 1e3
