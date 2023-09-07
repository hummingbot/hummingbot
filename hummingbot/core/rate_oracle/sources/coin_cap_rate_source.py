from decimal import Decimal
from typing import Dict, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.data_feed.coin_cap_data_feed import CoinCapDataFeed
from hummingbot.logger import HummingbotLogger


class CoinCapRateSource(RateSourceBase):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self, assets_map: Dict[str, str], api_key: str):
        self._coin_cap_data_feed = CoinCapDataFeed(assets_map=assets_map, api_key=api_key)

    @property
    def name(self) -> str:
        return "coin_cap"

    async def start_network(self):
        await self._coin_cap_data_feed.start_network()

    async def stop_network(self):
        await self._coin_cap_data_feed.stop_network()

    async def check_network(self) -> NetworkStatus:
        return await self._coin_cap_data_feed.check_network()

    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        prices = {}

        if quote_token == self._coin_cap_data_feed.universal_quote_token:
            prices = await self._coin_cap_data_feed.get_all_usd_quoted_prices()
        else:
            self.logger().warning(
                "CoinCapRateSource only supports USD as quote token. Please set your global token to USD."
            )

        return prices
