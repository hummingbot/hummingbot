from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache

if TYPE_CHECKING:
    from hummingbot.connector.exchange.dexalot.dexalot_exchange import DexalotExchange


class DexalotRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        self._exchange: Optional[DexalotExchange] = None  # delayed because of circular reference

    @property
    def name(self) -> str:
        return "dexalot"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        self._ensure_exchange()
        results = {}
        try:
            records = await self._exchange.get_all_pairs_prices()
            for record in records:
                try:
                    pair = await self._exchange.trading_pair_associated_to_exchange_symbol(record["pair"])
                except KeyError:
                    # Ignore results for which their symbols is not tracked by the connector
                    continue

                # Validate that record has required fields and they are valid numbers
                try:
                    low_val = str(record.get("low", ""))
                    high_val = str(record.get("high", ""))
                    # Skip if values are empty, 'null', 'None', or non-numeric
                    if not low_val or not high_val or low_val in ('null', 'None') or high_val in ('null', 'None'):
                        continue
                    low_decimal = Decimal(low_val)
                    high_decimal = Decimal(high_val)
                    if low_decimal > 0 and high_decimal > 0:
                        results[pair] = (low_decimal + high_decimal) / Decimal("2")
                except (KeyError, TypeError, ValueError):
                    # Skip records with invalid data
                    continue

        except Exception:
            self.logger().exception(
                msg="Unexpected error while retrieving rates from Dexalot. Check the log file for more info.",
            )
        return results

    def _ensure_exchange(self):
        if self._exchange is None:
            self._exchange = self._build_dexalot_connector_without_private_keys()

    @staticmethod
    def _build_dexalot_connector_without_private_keys() -> 'DexalotExchange':
        from hummingbot.connector.exchange.dexalot.dexalot_exchange import DexalotExchange
        return DexalotExchange(
            dexalot_api_key="",
            dexalot_api_secret="13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930",  # noqa: mock
            trading_pairs=[],
            trading_required=False,
        )
