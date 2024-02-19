from decimal import Decimal
from typing import Dict, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.logger import HummingbotLogger


class XrplRateSource(RateSourceBase):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self):
        self._prices = {}

    @property
    def name(self) -> str:
        return "xrpl"

    async def start_network(self):
        pass

    async def stop_network(self):
        pass

    async def check_network(self) -> NetworkStatus:
        pass

    def set_prices(self, prices: Dict[str, Decimal]):
        self._prices = prices

    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        prices = self._prices

        return prices
