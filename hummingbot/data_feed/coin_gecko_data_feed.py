import aiohttp
import asyncio
import logging
from typing import (
    Dict,
    List,
    Optional
)

from hummingbot.core.utils import async_ttl_cache
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.coin_cap_data_feed import CoinCapDataFeed


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

    @async_ttl_cache(ttl=60 * 60, maxsize=1)
    async def fetch_supported_id_asset_map(self) -> Dict[str, str]:
        """
            Returns map of asset to id, which is required for fetching price
            Example: {"bitcoin": "BTC", "ethereum": "ETH", ...}
        """
        try:
            client: aiohttp.ClientSession = await self._http_client()
            async with client.request("GET", f"{self.BASE_URL}/coins/list") as resp:
                assets: List[Dict[str, str]] = await resp.json()
                asset_map: Dict[str, str] = {}
                for asset in assets:
                    # Make BUSD map to Binance Usd
                    if asset['symbol'] == "busd" and asset['id'] != "binance-usd":
                        continue
                    # Make ONE map to Harmony
                    if asset["symbol"] == "one" and asset["id"] != "harmony":
                        continue
                    asset_map[asset['id']] = asset['symbol'].upper()
                return asset_map
        except Exception:
            raise

    async def update_asset_prices(self, id_asset_map: Dict[str, str]):
        try:
            await CoinCapDataFeed.get_instance().get_ready()
            all_ids = [k for k, v in id_asset_map.items() if v in CoinCapDataFeed.get_instance().price_dict.keys()]
            ids_chunks: List[List[str]] = [all_ids[x:x + 70] for x in range(0, len(all_ids), 70)]
            client: aiohttp.ClientSession = await self._http_client()
            price_url: str = f"{self.BASE_URL}/simple/price"
            price_dict: Dict[str, float] = {}

            for ids_chunk in ids_chunks:
                ids: str = ",".join(ids_chunk)
                params: Dict[str, str] = {"ids": ids, "vs_currencies": "usd"}
                try:
                    async with client.request("GET", price_url, params=params) as resp:
                        results: Dict[str, Dict[str, float]] = await resp.json()
                        if 'error' in results:
                            raise Exception(f"{results['error']}")
                        for id, usd_price in results.items():
                            asset: str = id_asset_map[id].upper()
                            price: float = float(usd_price.get("usd", 0.0))
                            price_dict[asset] = price
                except Exception as e:
                    self.logger().warning(f"Coin Gecko API request failed. Exception: {str(e)}")
                    raise e
                await asyncio.sleep(0.1)

            self._price_dict = price_dict
        except Exception:
            raise

    async def fetch_data(self):
        try:
            id_asset_map: Dict[str, str] = await self.fetch_supported_id_asset_map()
            await self.update_asset_prices(id_asset_map)
            self._ready_event.set()
        except Exception:
            raise

    async def start_network(self):
        await self.stop_network()
        self.fetch_data_loop_task = safe_ensure_future(self.fetch_data_loop())

    async def stop_network(self):
        if self.fetch_data_loop_task is not None:
            self.fetch_data_loop_task.cancel()
            self.fetch_data_loop_task = None
