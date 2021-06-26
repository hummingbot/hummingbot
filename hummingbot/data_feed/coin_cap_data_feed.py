import asyncio
import logging
from typing import (
    Dict,
    Optional,
)
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.async_utils import safe_ensure_future


class CoinCapDataFeed(DataFeedBase):
    ccdf_logger: Optional[HummingbotLogger] = None
    _ccdf_shared_instance: "CoinCapDataFeed" = None

    COIN_CAP_BASE_URL = "https://api.coincap.io/v2"

    @classmethod
    def get_instance(cls) -> "CoinCapDataFeed":
        if cls._ccdf_shared_instance is None:
            cls._ccdf_shared_instance = CoinCapDataFeed()
        return cls._ccdf_shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.ccdf_logger is None:
            cls.ccdf_logger = logging.getLogger(__name__)
        return cls.ccdf_logger

    def __init__(self, update_interval: float = 5.0):
        super().__init__()
        self._check_network_interval = 30.0
        self._ev_loop = asyncio.get_event_loop()
        self._price_dict: Dict[str, float] = {}
        self._update_interval: float = update_interval
        self._fetch_price_task: Optional[asyncio.Task] = None

    @property
    def name(self):
        return "coincap_api"

    @property
    def price_dict(self):
        return self._price_dict.copy()

    @property
    def health_check_endpoint(self):
        # Only fetch data of one asset - so that the health check is faster
        return "http://api.coincap.io/v2/assets/bitcoin"

    def get_price(self, asset: str) -> float:
        return self._price_dict.get(asset.upper())

    async def fetch_price_loop(self):
        while True:
            try:
                await self.fetch_prices()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(f"Error fetching new prices from {self.name}.", exc_info=True,
                                      app_warning_msg="Couldn't fetch newest prices from CoinCap. "
                                                      "Check network connection.")

            await asyncio.sleep(self._update_interval)

    async def fetch_prices(self):
        client = await self._http_client()
        async with client.request("GET", f"{self.COIN_CAP_BASE_URL}/assets") as resp:
            rates_dict = await resp.json()
            for rate_obj in rates_dict["data"]:
                asset = rate_obj["symbol"].upper()
                self._price_dict[asset] = float(rate_obj["priceUsd"])

        # coincap does not include all coins in assets
        async with client.request("GET", f"{self.COIN_CAP_BASE_URL}/rates") as resp:
            rates_dict = await resp.json()
            for rate_obj in rates_dict["data"]:
                asset = rate_obj["symbol"].upper()
                self._price_dict[asset] = float(rate_obj["rateUsd"])

        # CoinCap does not have a separate feed for WETH
        self._price_dict["WETH"] = self._price_dict["ETH"]
        self._ready_event.set()

    async def start_network(self):
        await self.stop_network()
        self._fetch_price_task = safe_ensure_future(self.fetch_price_loop())

    async def stop_network(self):
        if self._fetch_price_task is not None:
            self._fetch_price_task.cancel()
            self._fetch_price_task = None
