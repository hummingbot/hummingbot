from decimal import Decimal
from typing import Dict, Optional

from hummingbot.connector.derivative.rubin_perpetual import (
    rubin_perpetual_constants as CONSTANTS,
    rubin_perpetual_web_utils as web_utils,
)
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class RubinPerpetualRateSource(RateSourceBase):
    """
    Conversion-rate source backed by the Rubin chain indexer oracle prices
    (``/v4/perpetualMarkets``). Fully self-contained — no external pricing API.
    Mainnet by default; the testnet variant overrides ``_domain``.
    """
    _domain: str = "mainnet"

    def __init__(self):
        super().__init__()
        self._api_factory = None

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME if self._domain == "mainnet" else f"{CONSTANTS.EXCHANGE_NAME}_{self._domain}"

    def _ensure_api_factory(self):
        if self._api_factory is None:
            self._api_factory = web_utils.build_api_factory_without_time_synchronizer_pre_processor(
                throttler=AsyncThrottler(CONSTANTS.RATE_LIMITS)
            )

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        results: Dict[str, Decimal] = {}
        self._ensure_api_factory()
        try:
            rest_assistant = await self._api_factory.get_rest_assistant()
            response = await rest_assistant.execute_request(
                url=f"{CONSTANTS.rest_url(self._domain)}{CONSTANTS.PATH_MARKETS}",
                throttler_limit_id=CONSTANTS.PATH_MARKETS,
                method=RESTMethod.GET,
            )
            markets = response.get("markets", {}) if isinstance(response, dict) else {}
            for trading_pair, market in markets.items():
                price = market.get("oraclePrice")
                if price is None:
                    continue
                if quote_token is not None:
                    base, quote = split_hb_trading_pair(trading_pair=trading_pair)
                    if quote != quote_token:
                        continue
                results[trading_pair] = Decimal(str(price))
        except Exception:
            self.logger().exception(
                msg="Unexpected error while retrieving rates from Rubin Perpetual. Check the log file for more info.",
            )
        return results


class RubinPerpetualTestnetRateSource(RubinPerpetualRateSource):
    """Testnet variant — same indexer API, testnet endpoints."""
    _domain: str = "testnet"
