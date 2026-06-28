from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache

if TYPE_CHECKING:
    from hummingbot.connector.exchange.backpack.backpack_exchange import BackpackExchange


class BackpackRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        self._exchange: Optional[BackpackExchange] = None  # delayed because of circular reference

    @property
    def name(self) -> str:
        return "backpack"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        self._ensure_exchange()
        all_prices: Dict[str, Decimal] = {}
        try:
            pairs_prices = await self._exchange.get_all_pairs_prices()
            for pair_price in pairs_prices:
                symbol = pair_price["symbol"]
                # The bulk tickers endpoint mixes spot and perpetual markets; perpetuals carry a
                # ``_PERP`` suffix (e.g. ``BTC_USDC_PERP``). Skip them so the spot rate source only
                # exposes spot prices.
                if symbol.endswith("_PERP"):
                    continue
                # Backpack symbols map to Hummingbot pairs by replacing ``_`` with ``-``.
                trading_pair = self._exchange.trading_pair_associated_to_exchange_symbol(symbol=symbol)
                last_price = pair_price.get("lastPrice")
                if last_price is not None and Decimal(str(last_price)) > Decimal("0"):
                    all_prices[trading_pair] = Decimal(str(last_price))
        except Exception:
            self.logger().exception(
                msg="Unexpected error while retrieving rates from Backpack. Check the log file for more info.",
            )
            return {}

        if quote_token is None:
            return all_prices

        # Backpack quotes almost everything in USDC and has NO USDT spot markets. Most rate sources
        # simply drop every pair whose quote != quote_token, which would return nothing (and price
        # everything at 0) whenever the global token is USDT. To keep USD valuations working with
        # either USDC or USDT as the global token, we additionally keep "bridge" quotes: any token X
        # for which an X-<quote_token> (or <quote_token>-X) pair exists can be reached, so pairs
        # quoted in X are retained too. Example: with quote_token=USDT and a USDT-USDC market
        # present, USDC becomes reachable, so BP-USDC is kept and find_rate() derives BP-USDT from
        # BP-USDC and USDT-USDC.
        reachable_quotes = {quote_token}
        for pair in all_prices:
            base, quote = split_hb_trading_pair(pair)
            if base == quote_token:
                reachable_quotes.add(quote)
            elif quote == quote_token:
                reachable_quotes.add(base)

        return {
            pair: price for pair, price in all_prices.items()
            if split_hb_trading_pair(pair)[1] in reachable_quotes
        }

    def _ensure_exchange(self):
        if self._exchange is None:
            self._exchange = self._build_backpack_connector_without_private_keys()

    @staticmethod
    def _build_backpack_connector_without_private_keys() -> 'BackpackExchange':
        from hummingbot.connector.exchange.backpack.backpack_exchange import BackpackExchange

        return BackpackExchange(
            backpack_api_key="",
            backpack_api_secret="",
            trading_pairs=[],
            trading_required=False,
        )
