import time
import asyncio
import logging
from typing import (
    Dict,
    Optional,
)
from hummingbot.core.utils import async_ttl_cache
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.logger import HummingbotLogger


class CoinMetricsDataFeed(DataFeedBase):
    cmdf_logger: Optional[HummingbotLogger] = None
    _cmdf_shared_instance: "CoinCapDataFeed" = None

    BASE_URL = "https://coinmetrics.io/api/v1"

    @classmethod
    def get_instance(cls) -> "CoinMetricsDataFeed":
        if cls._cmdf_shared_instance is None:
            cls._cmdf_shared_instance = CoinMetricsDataFeed()
        return cls._cmdf_shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.cmdf_logger is None:
            cls.cmdf_logger = logging.getLogger(__name__)
        return cls.cmdf_logger

    def __init__(self, update_interval: float = 30.0):
        super().__init__()
        self._ev_loop = asyncio.get_event_loop()
        self._price_dict: Dict[str, float] = {}
        self._update_interval = update_interval
        self.fetch_data_loop_task: Optional[asyncio.Task] = None
        self._started = False

    @property
    def name(self):
        return "coin_metrics_api"

    @property
    def price_dict(self):
        return self._price_dict.copy()

    def get_price(self, asset: str) -> float:
        return self._price_dict.get(asset)

    async def fetch_data_loop(self):
        while True:
            try:
                await self.fetch_data()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(f"Error getting data from {self.name}", exc_info=True,
                                      app_warning_msg="Couldn't fetch newest prices from Coin Metrics. "
                                                      "Check network connection.")

            await asyncio.sleep(self._update_interval)

    @async_ttl_cache(ttl=60*60, maxsize=1)
    async def fetch_supported_assets(self):
        try:
            client = await self._http_client()
            async with client.request("GET", f"{self.BASE_URL}/get_supported_assets") as resp:
                return await resp.json()
        except Exception:
            raise

    async def fetch_asset_price(self, asset, time_start, time_end):
        try:
            client = await self._http_client()
            asset_price_url = f"get_asset_data_for_time_range/{asset}/price(usd)/{time_start}/{time_end}"
            async with client.request("GET", f"{self.BASE_URL}/{asset_price_url}") as resp:
                return await resp.json()
        except Exception:
            raise

    async def fetch_data(self):
        try:
            assets = await self.fetch_supported_assets()
            for asset in assets:
                time_end = int(time.time())
                time_start = time_end - 60*60*24*7 # coin metrics prices are not updated frequently
                rates_dict = await self.fetch_asset_price(asset, time_start, time_end)
                if "error" in rates_dict:
                    coinmetrics_error_msg: str = rates_dict["error"]
                    self.logger().network(f"Issue fetching rate from {self.name}: {coinmetrics_error_msg}",
                                          app_warning_msg=f"Got API error from Coin Metric: "
                                                          f"'{coinmetrics_error_msg}'.")
                    continue
                if len(rates_dict["result"]) > 0:
                    # Get the latest price
                    self._price_dict[asset] = rates_dict["result"][-1][1]
                await asyncio.sleep(0.001)
            self._ready_event.set()
        except Exception:
            raise

    def start(self):
        self.stop()
        self.fetch_data_loop_task = asyncio.ensure_future(self.fetch_data_loop())
        self._started = True

    def stop(self):
        if self.fetch_data_loop_task and not self.fetch_data_loop_task.done():
            self.fetch_data_loop_task.cancel()
        self._started = False

