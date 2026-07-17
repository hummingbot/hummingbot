import asyncio
import sys
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.data_feed.coin_paprika_data_feed import coin_paprika_constants as CONSTANTS
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class CoinPaprikaDataFeed(DataFeedBase):
    _logger: Optional[HummingbotLogger] = None
    _async_throttler: Optional["AsyncThrottler"] = None

    @classmethod
    def _get_async_throttler(cls) -> "AsyncThrottler":
        """This avoids circular imports."""
        from hummingbot.core.api_throttler.async_throttler import AsyncThrottler

        if cls._async_throttler is None:
            cls._async_throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        return cls._async_throttler

    def __init__(self):
        super().__init__()
        self._api_factory: Optional[WebAssistantsFactory] = None
        self._ready_event.set()

    @property
    def name(self) -> str:
        return "coin_paprika_api"

    @property
    def health_check_endpoint(self) -> str:
        return f"{CONSTANTS.BASE_REST_URL}{CONSTANTS.HEALTH_CHECK_ENDPOINT}"

    @property
    def universal_quote_token(self) -> str:
        return CONSTANTS.UNIVERSAL_QUOTE_TOKEN

    async def start_network(self):
        pass  # nothing to start: all requests are made on demand

    async def stop_network(self):
        pass  # nothing to stop

    async def check_network(self) -> NetworkStatus:
        try:
            await self._make_request(url=self.health_check_endpoint)
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    @staticmethod
    def is_quote_token_supported(quote_token: str) -> bool:
        return quote_token.upper() in CONSTANTS.SUPPORTED_QUOTE_TOKENS

    async def get_all_prices(self, quote_token: str) -> Dict[str, Decimal]:
        """
        Fetches prices of all active coins on coinpaprika.com in a single request. The keyless API
        returns the top 2000 coins by rank.

        Ticker symbols are not unique on CoinPaprika (several coins can share one symbol), so entries
        are processed in rank order and only the highest-ranked coin is kept for each symbol.

        :param quote_token: The quote currency for the returned prices. Must be one of
            CONSTANTS.SUPPORTED_QUOTE_TOKENS.
        :return: A dictionary of trading pairs and prices
        """
        quote_token = quote_token.upper()
        prices: Dict[str, Decimal] = {}
        url = f"{CONSTANTS.BASE_REST_URL}{CONSTANTS.ALL_TICKERS_ENDPOINT}"
        params = {"quotes": quote_token}

        data = await self._make_request(url=url, params=params)
        for ticker_data in sorted(data, key=lambda ticker: ticker.get("rank") or sys.maxsize):
            trading_pair = combine_to_hb_trading_pair(base=ticker_data["symbol"], quote=quote_token)
            quote_data = (ticker_data.get("quotes") or {}).get(quote_token) or {}
            price = quote_data.get("price")
            if trading_pair not in prices and price:
                prices[trading_pair] = Decimal(str(price))

        return prices

    def _get_api_factory(self) -> WebAssistantsFactory:
        # Delayed creation to avoid circular logic (the throttler needs a client config map, which
        # needs a data feed)
        if self._api_factory is None:
            self._api_factory = WebAssistantsFactory(throttler=self._get_async_throttler())
        return self._api_factory

    async def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        api_factory = self._get_api_factory()
        rest_assistant = await api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=url,
            throttler_limit_id=CONSTANTS.REQUESTS_LIMIT_ID,
            params=params,
            method=RESTMethod.GET,
        )
        return data
