from decimal import Decimal
from typing import Dict, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.data_feed.coin_cap_data_feed import CoinCapDataFeed
from hummingbot.logger import HummingbotLogger


class CoinCapRateSource(RateSourceBase):
    """
    DEPRECATED: this rate source is backed by the CoinCap v2 API, whose host (api.coincap.io) no
    longer resolves, so price requests fail. It is kept only so that existing configurations keep
    loading. Please switch to another rate source, for example coin_gecko or coin_paprika.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(self, assets_map: Dict[str, str], api_key: str):
        self.logger().warning(
            "The coin_cap rate source is deprecated: the CoinCap v2 API host (api.coincap.io) is no"
            " longer available, so this source cannot fetch prices. Please switch your rate oracle"
            " source to another provider, for example coin_gecko or coin_paprika."
        )
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
