from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache

if TYPE_CHECKING:
    from hummingbot.connector.derivative.pacifica_perpetual.pacifica_perpetual_derivative import (
        PacificaPerpetualDerivative,
    )


class PacificaPerpetualRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        self._exchange: Optional[PacificaPerpetualDerivative] = None

    @property
    def name(self) -> str:
        return "pacifica_perpetual"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        if quote_token is not None and quote_token != "USDC":
            raise ValueError("Pacifica Perpetual only supports USDC as quote token.")

        self._ensure_exchange()
        results = {}
        try:
            pairs_prices = await self._exchange.get_all_pairs_prices()
            for pair_price in pairs_prices:
                trading_pair = pair_price["trading_pair"]
                if quote_token is not None:
                    base, quote = split_hb_trading_pair(trading_pair=trading_pair)
                    if quote != quote_token:
                        continue
                price = pair_price["price"]
                results[trading_pair] = Decimal(price)
        except Exception:
            self.logger().exception(
                msg="Unexpected error while retrieving rates from Pacifica. Check the log file for more info.",
            )
        return results

    def _ensure_exchange(self):
        if self._exchange is None:
            self._exchange = self._build_pacifica_connector_without_private_keys()

    @staticmethod
    def _build_pacifica_connector_without_private_keys() -> 'PacificaPerpetualDerivative':
        from hummingbot.connector.derivative.pacifica_perpetual.pacifica_perpetual_derivative import (
            PacificaPerpetualDerivative,
        )

        return PacificaPerpetualDerivative(
            pacifica_perpetual_agent_wallet_public_key="dummy_public_key",
            pacifica_perpetual_agent_wallet_private_key="5Bnr1LtPzXwFBd8z4F1ceR42yycUeUt4zoiDChW7cLDzVD6SmbHwwFhwbbLDExscxeVBbW6WVbWTKX4Dse4WUung",  # dummy 64-byte base58 encoded key
            pacifica_perpetual_user_wallet_public_key="dummy_user_key",
            trading_pairs=[],
            trading_required=False,
        )
