import asyncio
import logging
from typing import Any, Dict, List, Optional

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.data_feed.coin_gecko_data_feed import coin_gecko_constants as CONSTANTS
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.logger import HummingbotLogger


class CoinGeckoDataFeed(DataFeedBase):
    cgdf_logger: Optional[HummingbotLogger] = None
    _cgdf_shared_instance: "CoinGeckoDataFeed" = None

    @classmethod
    def get_instance(cls) -> "CoinGeckoDataFeed":
        if cls._cgdf_shared_instance is None:
            cls._cgdf_shared_instance = CoinGeckoDataFeed()
        return cls._cgdf_shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.cgdf_logger is None:
            cls.cgdf_logger = logging.getLogger(__name__)
        return cls.cgdf_logger

    def __init__(self, update_interval: float = 30.0):
        super().__init__()
        self._ev_loop = asyncio.get_event_loop()
        self._price_dict: Dict[str, float] = {}
        self._update_interval = update_interval
        self.fetch_data_loop_task: Optional[asyncio.Task] = None
        async_throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self._api_factory = WebAssistantsFactory(throttler=async_throttler)

    @property
    def name(self) -> str:
        return "coin_gecko_api"

    @property
    def price_dict(self) -> Dict[str, float]:
        return self._price_dict.copy()

    @property
    def health_check_endpoint(self) -> str:
        return f"{CONSTANTS.BASE_URL}{CONSTANTS.PING_REST_ENDPOINT}"

    async def start_network(self):
        await self.stop_network()
        self.fetch_data_loop_task = safe_ensure_future(self._fetch_data_loop())

    async def stop_network(self):
        if self.fetch_data_loop_task is not None:
            self.fetch_data_loop_task.cancel()
            self.fetch_data_loop_task = None

    def get_price(self, asset: str) -> float:
        return self._price_dict.get(asset.upper())

    async def get_supported_vs_tokens(self) -> List[str]:
        rest_assistant = await self._api_factory.get_rest_assistant()
        supported_vs_tokens_url = f"{CONSTANTS.BASE_URL}{CONSTANTS.SUPPORTED_VS_TOKENS_REST_ENDPOINT}"
        vs_tokens = await rest_assistant.execute_request(
            url=supported_vs_tokens_url, throttler_limit_id=CONSTANTS.REST_CALL_RATE_LIMIT_ID
        )
        return vs_tokens

    async def get_prices_by_page(
        self, vs_currency: str, page_no: int, category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetches prices specified by 250-length page. Only 50 when category is specified"""
        rest_assistant = await self._api_factory.get_rest_assistant()
        price_url: str = f"{CONSTANTS.BASE_URL}{CONSTANTS.PRICES_REST_ENDPOINT}"
        params = {
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": 250,
            "page": page_no,
            "sparkline": "false",
        }
        if category is not None:
            params["category"] = category
        resp = await rest_assistant.execute_request(
            url=price_url, throttler_limit_id=CONSTANTS.REST_CALL_RATE_LIMIT_ID, params=params
        )
        return resp

    async def get_prices_by_token_id(self, vs_currency: str, token_ids: List[str]) -> List[Dict[str, Any]]:
        rest_assistant = await self._api_factory.get_rest_assistant()
        price_url: str = f"{CONSTANTS.BASE_URL}{CONSTANTS.PRICES_REST_ENDPOINT}"
        token_ids_str = ",".join(map(str.lower, token_ids))
        params = {
            "vs_currency": vs_currency,
            "ids": token_ids_str,
        }
        resp = await rest_assistant.execute_request(
            url=price_url, throttler_limit_id=CONSTANTS.REST_CALL_RATE_LIMIT_ID, params=params
        )
        return resp

    async def _fetch_data_loop(self):
        while True:
            try:
                await self._fetch_data()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(f"Error getting data from {self.name}", exc_info=True,
                                      app_warning_msg="Couldn't fetch newest prices from Coin Gecko. "
                                                      "Check network connection.")

            await self._async_sleep(self._update_interval)

    async def _fetch_data(self):
        await self._update_asset_prices()
        self._ready_event.set()

    async def _update_asset_prices(self):
        price_dict: Dict[str, float] = {}

        for i in range(1, 5):
            try:
                results = await self.get_prices_by_page(vs_currency="usd", page_no=i)
                if 'error' in results:
                    raise Exception(f"{results['error']}")
                for result in results:
                    symbol = result["symbol"].upper()
                    price = float(result["current_price"]) if result["current_price"] is not None else 0.0
                    if symbol not in price_dict:
                        price_dict[symbol] = price
                        self._price_dict[symbol] = price
            except Exception as e:
                self.logger().warning(f"Coin Gecko API request failed. Exception: {str(e)}")
                raise e
            if i < 4:
                await self._async_sleep(0.1)
        self._price_dict = price_dict

    @staticmethod
    async def _async_sleep(delay: float):
        """Used to mock in test cases."""
        await asyncio.sleep(delay)
