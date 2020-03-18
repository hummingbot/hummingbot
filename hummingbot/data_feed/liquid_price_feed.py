import asyncio
import logging
from typing import (
    Dict,
    Optional,
)
from decimal import Decimal
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.async_utils import safe_ensure_future


class LiquidPriceFeed(DataFeedBase):
    ccdf_logger: Optional[HummingbotLogger] = None
    _ccdf_shared_instance: "LiquidPriceFeed" = None

    price_feed_url = "https://api.liquid.com/products"
    health_check_url = price_feed_url

    @classmethod
    def get_instance(cls) -> "LiquidPriceFeed":
        if cls._ccdf_shared_instance is None:
            cls._ccdf_shared_instance = LiquidPriceFeed()
        return cls._ccdf_shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.ccdf_logger is None:
            cls.ccdf_logger = logging.getLogger(__name__)
        return cls.ccdf_logger

    def __init__(self, update_interval: float = 30.0):
        super().__init__()
        self._check_network_interval = 30.0
        self._ev_loop = asyncio.get_event_loop()
        self._trading_pair = []
        self._price_dict: Dict[str, float] = {}
        self._update_interval: float = update_interval
        self._fetch_price_task: Optional[asyncio.Task] = None

    @property
    def name(self):
        return "liquid_price_feed"

    @property
    def price_dict(self):
        return self._price_dict.copy()

    @property
    def health_check_endpoint(self):
        return self.health_check_url

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
        async with client.request("GET", self.price_feed_url) as resp:
            records = await resp.json()
            for record in records:
                trading_pair = f"{record['base_currency']}-{record['quoted_currency']}"
                if record["market_ask"] and record["market_bid"] is not None:
                    self._price_dict[trading_pair] = \
                        (Decimal(record["market_ask"]) + Decimal(record["market_bid"])) / Decimal("2")
                elif record["last_traded_price"] is not None:
                    self._price_dict[trading_pair] = Decimal(record["last_traded_price"])
        self._ready_event.set()

    async def start_network(self):
        await self.stop_network()
        self._fetch_price_task = safe_ensure_future(self.fetch_price_loop())

    async def stop_network(self):
        if self._fetch_price_task is not None:
            self._fetch_price_task.cancel()
            self._fetch_price_task = None
