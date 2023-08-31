import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.network_iterator import NetworkStatus, safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.data_feed.coin_cap_data_feed import coin_cap_constants as CONSTANTS
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class CoinCapAPIKeyAppender(RESTPreProcessorBase):
    def __init__(self, api_key: str):
        super().__init__()
        self._api_key = api_key

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        request.headers = request.headers or {}
        request.headers["Authorization"] = self._api_key
        return request


class CoinCapDataFeed(DataFeedBase):
    _logger: Optional[HummingbotLogger] = None
    _async_throttler: Optional["AsyncThrottler"] = None

    @classmethod
    def _get_async_throttler(cls) -> "AsyncThrottler":
        """This avoids circular imports."""
        from hummingbot.core.api_throttler.async_throttler import AsyncThrottler

        if cls._async_throttler is None:
            cls._async_throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return cls._async_throttler

    def __init__(self, assets_map: Dict[str, str], api_key: str):
        super().__init__()
        self._assets_map = assets_map
        self._price_dict: Dict[str, Decimal] = {}
        self._api_factory: Optional[WebAssistantsFactory] = None
        self._api_key = api_key
        self._is_api_key_authorized = True
        self._prices_stream_task: Optional[asyncio.Task] = None

        self._ready_event.set()

    @property
    def name(self):
        return "coin_cap_api"

    @property
    def health_check_endpoint(self):
        return f"{CONSTANTS.BASE_REST_URL}{CONSTANTS.HEALTH_CHECK_ENDPOINT}"

    @property
    def universal_quote_token(self) -> str:
        return CONSTANTS.UNIVERSAL_QUOTE_TOKEN

    async def start_network(self):
        self._prices_stream_task = safe_ensure_future(self._stream_prices())

    async def stop_network(self):
        self._prices_stream_task and self._prices_stream_task.cancel()
        self._prices_stream_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            await self._make_request(url=self.health_check_endpoint)
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def get_all_usd_quoted_prices(self) -> Dict[str, Decimal]:
        prices = (
            self._price_dict
            if self._prices_stream_task and len(self._price_dict) != 0
            else await self._get_all_usd_quoted_prices_by_rest_request()
        )
        return prices

    def _get_api_factory(self) -> WebAssistantsFactory:
        # Avoids circular logic (i.e. CoinCap needs a throttler, which needs a client config map, which needs
        # a data feed — CoinCap, in this case)
        if self._api_factory is None:
            self._api_factory = WebAssistantsFactory(
                throttler=self._get_async_throttler(),
                rest_pre_processors=[CoinCapAPIKeyAppender(api_key=self._api_key)],
            )
        return self._api_factory

    async def _get_all_usd_quoted_prices_by_rest_request(self) -> Dict[str, Decimal]:
        prices = {}
        url = f"{CONSTANTS.BASE_REST_URL}{CONSTANTS.ALL_ASSETS_ENDPOINT}"

        params = {
            "ids": ",".join(self._assets_map.values()),
        }

        data = await self._make_request(url=url, params=params)
        for asset_data in data["data"]:
            base = asset_data["symbol"]
            trading_pair = combine_to_hb_trading_pair(base=base, quote=CONSTANTS.UNIVERSAL_QUOTE_TOKEN)
            try:
                prices[trading_pair] = Decimal(asset_data["priceUsd"])
            except TypeError:
                continue

        return prices

    async def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        api_factory = self._get_api_factory()
        rest_assistant = await api_factory.get_rest_assistant()
        rate_limit_id = CONSTANTS.API_KEY_LIMIT_ID if self._is_api_key_authorized else CONSTANTS.NO_KEY_LIMIT_ID
        response = await rest_assistant.execute_request_and_get_response(
            url=url,
            throttler_limit_id=rate_limit_id,
            params=params,
            method=RESTMethod.GET,
        )
        self._check_is_api_key_authorized(response=response)
        data = await response.json()
        return data

    def _check_is_api_key_authorized(self, response: RESTResponse):
        self.logger().debug(f"CoinCap REST response headers: {response.headers}")
        self._is_api_key_authorized = int(response.headers["X-Ratelimit-Limit"]) == CONSTANTS.API_KEY_LIMIT
        if not self._is_api_key_authorized and self._api_key != "":
            self.logger().warning("CoinCap API key is not authorized. Please check your API key.")

    async def _stream_prices(self):
        while True:
            try:
                api_factory = self._get_api_factory()
                self._price_dict = await self._get_all_usd_quoted_prices_by_rest_request()
                ws = await api_factory.get_ws_assistant()
                symbols_map = {asset_id: symbol for symbol, asset_id in self._assets_map.items()}
                ws_url = f"{CONSTANTS.BASE_WS_URL}{','.join(self._assets_map.values())}"
                async with api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_CONNECTIONS_LIMIT_ID):
                    await ws.connect(ws_url=ws_url)
                async for msg in ws.iter_messages():
                    for asset_id, price_str in msg.data.items():
                        base = symbols_map[asset_id]
                        trading_pair = combine_to_hb_trading_pair(base=base, quote=CONSTANTS.UNIVERSAL_QUOTE_TOKEN)
                        self._price_dict[trading_pair] = Decimal(price_str)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    log_msg="Unexpected error while streaming prices. Restarting the stream.",
                    exc_info=True,
                )
                await self._sleep(delay=1)

    @staticmethod
    async def _sleep(delay: float):
        """Used for unit-test mocking."""
        await asyncio.sleep(delay)
