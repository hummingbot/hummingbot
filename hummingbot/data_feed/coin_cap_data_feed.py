import ujson
import logging
import aiohttp
import asyncio
from typing import (
    Dict,
    Optional,
)
from hummingbot.data_feed.data_feed_base import DataFeedBase


class CoinCapDataFeed(DataFeedBase):
    ccdf_logger: Optional[logging.Logger] = None
    _ccdf_shared_instance: "CoinCapDataFeed" = None

    COIN_CAP_BASE_URL = "https://api.coincap.io/v2"

    @classmethod
    def get_instance(cls) -> "CoinCapDataFeed":
        if cls._ccdf_shared_instance is None:
            cls._ccdf_shared_instance = CoinCapDataFeed()
        return cls._ccdf_shared_instance

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls.ccdf_logger is None:
            cls.ccdf_logger = logging.getLogger(__name__)
        return cls.ccdf_logger

    def __init__(self, update_interval: float = 5.0):
        super().__init__()
        self._ev_loop = asyncio.get_event_loop()
        self._session = aiohttp.ClientSession(loop=self._ev_loop, connector=aiohttp.TCPConnector(ssl=False))
        self._price_dict: Dict[str, float] = {}
        self._update_interval = update_interval
        self._fetch_price_task = asyncio.ensure_future(self.fetch_price_loop())

    @property
    def price_dict(self):
        return self._price_dict.copy()

    def get_price(self, asset: str) -> float:
        return self._price_dict.get(asset)

    async def fetch_price_loop(self):
        while True:
            try:
                await self.fetch_prices()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger().error(e, exc_info=True)
            finally:
                await asyncio.sleep(self._update_interval)

    async def fetch_prices(self):
        try:
            async with self._session.request("GET", f"{self.COIN_CAP_BASE_URL}/assets") as resp:
                rates_dict = ujson.loads(await resp.text())
                for rate_obj in rates_dict["data"]:
                    symbol = rate_obj["symbol"]
                    self._price_dict[symbol] = float(rate_obj["priceUsd"])

            # coincap does not include all coins in assets
            async with self._session.request("GET", f"{self.COIN_CAP_BASE_URL}/rates") as resp:
                rates_dict = ujson.loads(await resp.text())
                for rate_obj in rates_dict["data"]:
                    symbol = rate_obj["symbol"]
                    self._price_dict[symbol] = float(rate_obj["rateUsd"])

            # CoinCap does not have a separate feed for WETH
            self._price_dict["WETH"] = self._price_dict["ETH"]
            self._ready = True
        except Exception:
            raise IOError("Error fetching prices from Coin Cap API")

