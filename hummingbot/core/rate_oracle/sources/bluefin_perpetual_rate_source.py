"""
Rate oracle source for Bluefin Perpetual.

Provides real-time price data from Bluefin to the rate oracle system.
"""
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache

if TYPE_CHECKING:
    from hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative import (
        BluefinPerpetualDerivative,
    )


class BluefinPerpetualRateSource(RateSourceBase):
    """Rate source for Bluefin Perpetual exchange."""

    def __init__(self):
        super().__init__()
        self._exchange: Optional["BluefinPerpetualDerivative"] = None

    @property
    def name(self) -> str:
        """Name of the rate source."""
        return "bluefin_perpetual"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        """
        Fetch current prices from Bluefin.

        :param quote_token: Optional filter for specific quote token
        :return: Dict of trading_pair -> price
        """
        self._ensure_exchange()
        results = {}
        try:
            # Exchange method to get all pairs prices would need to be implemented
            # For now, get prices from trading rules/market data
            await self._exchange._update_trading_rules()

            for trading_pair in self._exchange.trading_rules:
                if quote_token is not None:
                    base, quote = split_hb_trading_pair(trading_pair=trading_pair)
                    if quote != quote_token:
                        continue

                # Get mark price from data source if available
                try:
                    if hasattr(self._exchange, "_data_source") and self._exchange._data_source:
                        market_symbols = await self._exchange._data_source.get_market_symbols()
                        # Find matching symbol and get mark price
                        exchange_symbol = await self._exchange.exchange_symbol_associated_to_pair(trading_pair)
                        for symbol_data in market_symbols:
                            if symbol_data.get("symbol") == exchange_symbol:
                                mark_price = symbol_data.get("markPrice")
                                if mark_price:
                                    results[trading_pair] = Decimal(str(mark_price))
                                break
                except Exception as symbol_error:
                    self.logger().debug(
                        f"Error fetching price for {trading_pair}: {symbol_error}",
                        exc_info=True
                    )
                    continue

        except Exception:
            self.logger().exception(
                msg="Unexpected error while retrieving rates from Bluefin. Check the log file for more info.",
            )
        return results

    def _ensure_exchange(self):
        """Ensure exchange instance exists."""
        if self._exchange is None:
            self._exchange = self._build_bluefin_perpetual_connector_without_private_keys()

    def _build_bluefin_perpetual_connector_without_private_keys(self) -> "BluefinPerpetualDerivative":
        """
        Build Bluefin connector instance for rate oracle (no real trading).

        Uses a test mnemonic for initialization since we only need price data.
        """
        from hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_derivative import (
            BluefinPerpetualDerivative,
        )

        # Use test mnemonic for price feed only (no trading)
        test_mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"

        connector = BluefinPerpetualDerivative(
            bluefin_perpetual_wallet_mnemonic=test_mnemonic,
            bluefin_perpetual_network="MAINNET",
            trading_pairs=[],
            trading_required=False,
        )

        return connector
