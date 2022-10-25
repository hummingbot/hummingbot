import aiohttp
import asyncio
import logging
from typing import (
    Dict,
    Optional
)
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.async_utils import safe_ensure_future


class CoinGeckoDataFeed(DataFeedBase):
    cgdf_logger: Optional[HummingbotLogger] = None
    _cgdf_shared_instance: "CoinGeckoDataFeed" = None

    BASE_URL = "https://api.coingecko.com/api/v3"

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

    @property
    def name(self) -> str:
        return "coin_gecko_api"

    @property
    def price_dict(self) -> Dict[str, float]:
        return self._price_dict.copy()

    @property
    def health_check_endpoint(self) -> str:
        return f"{self.BASE_URL}/ping"

    def get_price(self, asset: str) -> float:
        return self._price_dict.get(asset.upper())

    async def fetch_data_loop(self):
        while True:
            try:
                await self.fetch_data()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(f"Error getting data from {self.name}", exc_info=True,
                                      app_warning_msg="Couldn't fetch newest prices from Coin Gecko. "
                                                      "Check network connection.")

            await asyncio.sleep(self._update_interval)

    async def update_asset_prices(self):
        try:
            client: aiohttp.ClientSession = await self._http_client()
            price_url: str = f"{self.BASE_URL}/coins/markets"
            price_dict: Dict[str, float] = {}

            for i in range(1, 5):
                params: Dict[str, str] = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250,
                                          "page": i, "sparkline": "false"}
                try:
                    async with client.request("GET", price_url, params=params) as resp:
                        results: Dict[str, Dict[str, float]] = await resp.json()
                        if 'error' in results:
                            raise Exception(f"{results['error']}")
                        for result in results:
                            symbol = result["symbol"].upper()
                            price = float(result["current_price"]) if result["current_price"] is not None else 0.0
                            if symbol not in price_dict:
                                price_dict[symbol] = price
                except Exception as e:
                    self.logger().warning(f"Coin Gecko API request failed. Exception: {str(e)}")
                    raise e
                await asyncio.sleep(0.1)
            self._price_dict = price_dict
        except Exception:
            raise

    async def fetch_data(self):
        await self.update_asset_prices()
        self._ready_event.set()

    async def start_network(self):
        await self.stop_network()
        self.fetch_data_loop_task = safe_ensure_future(self.fetch_data_loop())

    async def stop_network(self):
        if self.fetch_data_loop_task is not None:
            self.fetch_data_loop_task.cancel()
            self.fetch_data_loop_task = None
