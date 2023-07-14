import asyncio
import re
from typing import Any, AsyncIterable, Callable, Dict, NamedTuple, Optional, Tuple, TypeVar, Union

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

from . import coinbase_advanced_trade_v2_constants as constants


def public_rest_url(path_url: str, domain: str = constants.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param domain: the Coinbase Advanced Trade domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    if path_url in constants.SIGNIN_ENDPOINTS:
        return constants.SIGNIN_URL.format(domain=domain) + path_url

    return constants.REST_URL.format(domain=domain) + path_url


def private_rest_url(path_url: str, domain: str = constants.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param domain: the coinbase_advanced_trade_v2 domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    if any((path_url.startswith(p) for p in constants.SIGNIN_ENDPOINTS)):
        return constants.SIGNIN_URL.format(domain=domain) + path_url

    return constants.REST_URL.format(domain=domain) + path_url


def endpoint_from_url(path_url: str, domain: str = constants.DEFAULT_DOMAIN) -> str:
    """
    Recreates the endpoint from the url
    :param path_url: URL to the endpoint
    :param domain: the coinbase_advanced_trade_v2 domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    if domain not in path_url:
        raise ValueError(f"The domain {domain} is not part of the provided URL {path_url}")

    endpoint: str = re.split(domain, path_url)[1]

    # Must start with '/'
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    return endpoint


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        domain: str = constants.DEFAULT_DOMAIN,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None, ) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time_s(
        throttler=throttler,
        domain=domain,
    ))
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
        ])
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(constants.RATE_LIMITS)


async def get_current_server_time_s(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = constants.DEFAULT_DOMAIN,
) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response: Dict = await rest_assistant.execute_request(
        url=public_rest_url(path_url=constants.SERVER_TIME_EP, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=constants.SERVER_TIME_EP,
    )
    server_time: float = float(get_timestamp_from_exchange_time(response["data"]["iso"], "s"))
    return server_time


# Ok, forgot HB does not like units on time ...
async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = constants.DEFAULT_DOMAIN,
) -> float:
    return await get_current_server_time_s(throttler=throttler, domain=domain)


async def get_current_server_time_ms(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = constants.DEFAULT_DOMAIN,
) -> int:
    server_time_s = await get_current_server_time_s(throttler=throttler, domain=domain)
    return int(server_time_s * 1000)


def get_timestamp_from_exchange_time(exchange_time: str, unit: str) -> float:
    from datetime import datetime
    exchange_time_with_tz: str = exchange_time.replace("Z", "+00:00")

    # Oddly some time (at least in the doc) are not ISO8601 compliant with too many decimals
    # So we truncate the string to make it ISO8601 compliant
    if len(exchange_time_with_tz) > 33:
        exchange_time_truncated = exchange_time_with_tz[:26] + exchange_time_with_tz[-6:]
    else:
        exchange_time_truncated = exchange_time_with_tz
    t_s: float = datetime.fromisoformat(exchange_time_truncated).timestamp()
    if unit == "s" or unit in ("second", "seconds"):
        return t_s
    elif unit == "ms" or unit in ("millisecond", "milliseconds"):
        return t_s * 1000
    else:
        raise ValueError(f"Unsupported time unit {unit}")


def set_exchange_time_from_timestamp(timestamp: Union[int, float], timestamp_unit: str = "s") -> str:
    if timestamp_unit == "ms" or timestamp_unit in ("millisecond", "milliseconds"):
        timestamp: float = timestamp / 1000
    elif timestamp_unit == "s" or timestamp_unit in ("second", "seconds"):
        pass
    else:
        raise ValueError(f"Unsupported timestamp unit {timestamp_unit}")

    from datetime import datetime
    return datetime.utcfromtimestamp(timestamp).isoformat() + "Z"


class CoinbaseAdvancedTradeWSSMessage(NamedTuple):
    """
    Coinbase Advanced Trade Websocket API message
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels
    ```json
    {
      "channel": "market_trades",
      "client_id": "",
      "timestamp": "2023-02-09T20:19:35.39625135Z",
      "sequence_num": 0,
      "events": [
        ...
      ]
    }
    ```
    """

    channel: str
    client_id: str
    timestamp: str
    sequence_num: int
    events: Tuple


async def try_except_queue_put(item: Any, queue: asyncio.Queue):
    """
    Try to put the order into the queue, except if the queue is full.
    :param item: The order to put into the queue.
    :param queue: The queue to put the order into.
    """
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull:
        try:
            await asyncio.wait_for(queue.put(item), timeout=1.0)
        except asyncio.TimeoutError:
            raise asyncio.QueueFull


T = TypeVar("T")


class PipelineMessageItem(NamedTuple):
    message: CoinbaseAdvancedTradeWSSMessage
    out_queue: asyncio.Queue[CoinbaseAdvancedTradeWSSMessage]


MessageProcessorType = Callable[[CoinbaseAdvancedTradeWSSMessage], AsyncIterable[Dict[str, Any]]]


class PipelineMessageProcessor:
    """
    A message processor that preprocesses messages from a websocket feed.
    """

    __slots__ = (
        "_message_queue",
        "_message_queue_task",
        "_preprocessor",
        "_is_started",
        "logger",
    )

    def __init__(self,
                 preprocessor: MessageProcessorType,
                 logger: Callable[[], HummingbotLogger]):
        self._message_queue: Optional[asyncio.Queue[PipelineMessageItem]] = None
        self._message_queue_task: Optional[asyncio.Task] = None
        self._preprocessor: MessageProcessorType = preprocessor
        self.logger = logger
        self._is_started = False

    @property
    def queue(self) -> Optional[asyncio.Queue[PipelineMessageItem]]:
        return self._message_queue

    @property
    def is_started(self) -> bool:
        return self._is_started

    async def start(self):
        self._is_started = True
        if not self._message_queue:
            self._message_queue: asyncio.Queue[PipelineMessageItem] = asyncio.Queue()
        if not self._message_queue_task or self._message_queue_task.done():
            self._message_queue_task = asyncio.create_task(self._preprocess_messages())

    async def stop(self):
        self._is_started = False

        if self._message_queue is not None:
            while not self._message_queue.empty():
                try:
                    self._message_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

        if self._message_queue_task and not self._message_queue_task.done():
            self._message_queue_task.cancel()
            try:
                await self._message_queue_task
            except asyncio.CancelledError:
                pass

    async def _preprocess_messages(self, redirect_queue: Optional[asyncio.Queue] = None):
        while self._is_started:
            try:
                message_out_queue: PipelineMessageItem = await self._message_queue.get()
            except asyncio.CancelledError:
                break

            try:
                async for item in self._preprocessor(message_out_queue.message):
                    if redirect_queue is None:
                        redirect_queue = message_out_queue.out_queue
                    try:
                        await try_except_queue_put(item=item, queue=redirect_queue)
                    except asyncio.QueueFull:
                        self.logger().error("Timeout while waiting to put order into the out queue")
            except Exception as e:
                self.logger().error(f"Exception while processing message: {e}. Message dropped")
