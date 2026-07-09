from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache

if TYPE_CHECKING:
    from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
        DecibelPerpetualDerivative,
    )


class DecibelPerpetualRateSource(RateSourceBase):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self._api_key = api_key
        self._exchange: Optional[DecibelPerpetualDerivative] = None

    @property
    def name(self) -> str:
        return "decibel_perpetual"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        if quote_token is not None and quote_token not in ("USD", "USDC"):
            raise ValueError("Decibel Perpetual only supports USD as quote token.")

        self._ensure_exchange()
        results = {}
        try:
            pairs_prices = await self._exchange.get_all_pairs_prices()
            for pair_price in pairs_prices:
                trading_pair = pair_price["trading_pair"]
                if quote_token is not None:
                    base, quote = split_hb_trading_pair(trading_pair=trading_pair)
                    if quote != quote_token and quote != "USD":
                        continue
                price = pair_price["price"]
                results[trading_pair] = Decimal(price)
        except Exception:
            self.logger().exception(
                msg="Unexpected error while retrieving rates from Decibel. Check the log file for more info.",
            )
        return results

    def _ensure_exchange(self):
        if self._exchange is None:
            self._exchange = self._build_decibel_connector()

    def _build_decibel_connector(self) -> 'DecibelPerpetualDerivative':
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants import DEFAULT_DOMAIN
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_derivative import (
            DecibelPerpetualDerivative,
        )

        return DecibelPerpetualDerivative(
            decibel_perpetual_api_wallet_private_key="0x" + "00" * 32,
            decibel_perpetual_main_wallet_public_key="0x" + "00" * 32,
            decibel_perpetual_api_key=self._api_key or "dummy_api_key",
            decibel_perpetual_gas_station_api_key="dummy_gas_station_key",
            trading_pairs=[],
            trading_required=False,
            domain=DEFAULT_DOMAIN,
        )
