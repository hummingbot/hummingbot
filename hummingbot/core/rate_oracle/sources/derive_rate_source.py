from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache

if TYPE_CHECKING:
    from hummingbot.connector.exchange.derive.derive_exchange import DeriveExchange


class DeriveRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        self._exchange: Optional[DeriveExchange] = None  # delayed because of circular reference

    @property
    def name(self) -> str:
        return "derive"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        await self._ensure_exchange()
        pairs_prices = await self._exchange.get_all_pairs_prices()
        results = {}
        for pair_price in pairs_prices:
            try:
                trading_pair = await self._exchange.trading_pair_associated_to_exchange_symbol(symbol=pair_price["symbol"]["instrument_name"])
            except KeyError:
                continue  # skip pairs that we don't track
            if quote_token is not None:
                base, quote = split_hb_trading_pair(trading_pair=trading_pair)
                if quote != quote_token:
                    continue
                bid_price = pair_price["symbol"].get("best_bid")
                ask_price = pair_price["symbol"].get("best_ask")
                if bid_price is not None and ask_price is not None and 0 < Decimal(bid_price) <= Decimal(ask_price):
                    results[trading_pair] = (Decimal(bid_price) + Decimal(ask_price)) / Decimal("2")

        return results

    async def _ensure_exchange(self):
        if self._exchange is None:
            self._exchange = self._build_derive_connector_without_private_keys()
        if len(self._exchange._instrument_ticker) == 0:
            await self._exchange._make_trading_rules_request()

    @staticmethod
    def _build_derive_connector_without_private_keys() -> 'DeriveExchange':
        from hummingbot.client.hummingbot_application import HummingbotApplication
        from hummingbot.connector.exchange.derive.derive_exchange import DeriveExchange

        app = HummingbotApplication.main_application()
        client_config_map = app.client_config_map

        return DeriveExchange(
            client_config_map=client_config_map,
            derive_api_secret="",
            trading_pairs=[],
            sub_id = "",
            derive_api_key="",
            trading_required=False,
        )
