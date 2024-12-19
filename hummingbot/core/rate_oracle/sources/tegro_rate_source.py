from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache

if TYPE_CHECKING:
    from hummingbot.connector.exchange.tegro.tegro_exchange import TegroExchange


class TegroRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        self._exchange: Optional[TegroExchange] = None  # delayed because of circular reference

    @property
    def name(self) -> str:
        return "tegro"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        self._ensure_exchange()
        results = {}
        try:
            pairs_prices = await self._exchange.get_all_pairs_prices()
            for pair_price in pairs_prices:
                pair = pair_price["symbol"]
                try:
                    trading_pair = await self._exchange.trading_pair_associated_to_exchange_symbol(symbol=pair)
                except KeyError:
                    continue  # skip pairs that we don't track
                if quote_token is not None:
                    _, quote = split_hb_trading_pair(trading_pair=trading_pair)
                    if quote != quote_token:
                        continue
                price = pair_price["price"]
                if price is not None:
                    results[trading_pair] = Decimal(price)
        except Exception:
            self.logger().exception(
                msg="Unexpected error while retrieving rates from Tegro. Check the log file for more info.",
            )
        return results

    def _ensure_exchange(self):
        if self._exchange is None:
            self._exchange = self._build_tegro_connector_without_private_keys()

    @staticmethod
    def _build_tegro_connector_without_private_keys() -> 'TegroExchange':
        from hummingbot.client.hummingbot_application import HummingbotApplication
        from hummingbot.connector.exchange.tegro.tegro_exchange import TegroExchange

        app = HummingbotApplication.main_application()
        client_config_map = app.client_config_map

        return TegroExchange(
            client_config_map=client_config_map,
            tegro_api_secret="",  # noqa: mock
            trading_pairs=[],  # noqa: mock
            tegro_api_key="",
            chain_name= "base",
            trading_required=False,
        )
