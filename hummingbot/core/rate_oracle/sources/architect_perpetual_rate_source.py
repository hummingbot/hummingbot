from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache

if TYPE_CHECKING:
    from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative import (
        ArchitectPerpetualDerivative,
    )


class ArchitectPerpetualRateSource(RateSourceBase):
    def __init__(self, domain: str):
        super().__init__()
        self._domain = domain
        self._exchange: Optional[ArchitectPerpetualDerivative] = None  # delayed because of circular reference

    @property
    def name(self) -> str:
        import hummingbot.connector.derivative.architect_perpetual.architect_perpetual_constants as CONSTANTS
        return CONSTANTS.EXCHANGE_NAME

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        self._ensure_exchange()
        results = {}
        try:
            records = await self._exchange.get_all_pairs_prices()
            for record in records["tickers"]:
                try:
                    pair = await self._exchange.trading_pair_associated_to_exchange_symbol(record["s"])
                except KeyError:
                    # Ignore results for which their symbols is not tracked by the connector
                    continue
                if record["p"] is not None:
                    results[pair] = Decimal(record["p"])
                elif record["lsp"] is not None:
                    self.logger().warning(f"No last price for {record['s']}. Using last settlement price.")
                    results[pair] = Decimal(record["lsp"])
                else:
                    self.logger().warning(f"No last price nor settlement price for {record['s']}. Skipping.")
        except Exception:
            self.logger().exception(
                msg="Unexpected error while retrieving rates from Architect Perpetual."
                    " Check the log file for more info.",
            )
        return results

    def _ensure_exchange(self):
        if self._exchange is None:
            self._exchange = self._build_connector()

    def _build_connector(self) -> 'ArchitectPerpetualDerivative':
        from hummingbot.client.settings import AllConnectorSettings
        from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative import (
            ArchitectPerpetualDerivative,
        )

        connector_config = AllConnectorSettings.get_connector_config_keys(self._domain)

        return ArchitectPerpetualDerivative(
            api_key=connector_config.api_key.get_secret_value(),
            api_secret=connector_config.api_secret.get_secret_value(),
            domain=self._domain
        )
