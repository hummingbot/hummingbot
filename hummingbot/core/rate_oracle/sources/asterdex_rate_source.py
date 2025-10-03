from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache

if TYPE_CHECKING:
    from hummingbot.connector.exchange.asterdex.asterdex_exchange import AsterdexExchange


class AsterdexRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        self._exchange: Optional[AsterdexExchange] = None  # delayed because of circular reference

    @property
    def name(self) -> str:
        return "asterdex"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        self._ensure_exchange()
        results = {}
        try:
            records = await self._exchange.get_all_pairs_prices()
            for record in records["data"]:
                symbol = record["symbol"]
                price = record["price"]
                if price and Decimal(price) > 0:
                    # Convert AsterDex symbol (e.g., "BTCUSDT") to Hummingbot pair (e.g., "BTC-USDT")
                    try:
                        pair = await self._exchange.trading_pair_associated_to_exchange_symbol(symbol)
                        results[pair] = Decimal(str(price))
                    except Exception as e:
                        # Skip symbols that can't be converted to trading pairs
                        self.logger().debug(f"Skipping symbol {symbol}: {e}")
                        continue
        except Exception as e:
            self.logger().exception(
                msg=f"Unexpected error while retrieving rates from AsterDex: {e}. Check the log file for more info.",
            )
        return results

    def _ensure_exchange(self):
        if self._exchange is None:
            self._exchange = self._build_asterdex_connector_without_private_keys()

    @staticmethod
    def _build_asterdex_connector_without_private_keys() -> 'AsterdexExchange':
        from hummingbot.connector.exchange.asterdex.asterdex_exchange import AsterdexExchange

        return AsterdexExchange(
            asterdex_api_key="",
            asterdex_secret_key="",
            trading_pairs=[],
            trading_required=False,
        )
