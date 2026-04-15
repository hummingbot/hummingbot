import asyncio
import logging
import typing
from decimal import Decimal
from typing import Dict, Optional

import hummingbot.client.settings  # noqa
from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.data_type.common import PriceType
from hummingbot.core.network_base import NetworkBase

if typing.TYPE_CHECKING:  # avoid circular import problems
    from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.rate_oracle.sources.aevo_rate_source import AevoRateSource
from hummingbot.core.rate_oracle.sources.architect_perpetual_rate_source import ArchitectPerpetualRateSource
from hummingbot.core.rate_oracle.sources.ascend_ex_rate_source import AscendExRateSource
from hummingbot.core.rate_oracle.sources.binance_rate_source import BinanceRateSource
from hummingbot.core.rate_oracle.sources.coin_cap_rate_source import CoinCapRateSource
from hummingbot.core.rate_oracle.sources.coin_gecko_rate_source import CoinGeckoRateSource
from hummingbot.core.rate_oracle.sources.coinbase_advanced_trade_rate_source import CoinbaseAdvancedTradeRateSource
from hummingbot.core.rate_oracle.sources.cube_rate_source import CubeRateSource
from hummingbot.core.rate_oracle.sources.derive_rate_source import DeriveRateSource
from hummingbot.core.rate_oracle.sources.dexalot_rate_source import DexalotRateSource
from hummingbot.core.rate_oracle.sources.evedex_perpetual_rate_source import EvedexPerpetualRateSource
from hummingbot.core.rate_oracle.sources.gate_io_rate_source import GateIoRateSource
from hummingbot.core.rate_oracle.sources.hyperliquid_perpetual_rate_source import HyperliquidPerpetualRateSource
from hummingbot.core.rate_oracle.sources.hyperliquid_rate_source import HyperliquidRateSource
from hummingbot.core.rate_oracle.sources.kucoin_rate_source import KucoinRateSource
from hummingbot.core.rate_oracle.sources.mexc_rate_source import MexcRateSource
from hummingbot.core.rate_oracle.sources.pacifica_perpetual_rate_source import PacificaPerpetualRateSource
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.rate_oracle.utils import find_rate
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger

RATE_ORACLE_SOURCES = {
    "aevo_perpetual": AevoRateSource,
    "binance": BinanceRateSource,
    "coin_gecko": CoinGeckoRateSource,
    "coin_cap": CoinCapRateSource,
    "kucoin": KucoinRateSource,
    "ascend_ex": AscendExRateSource,
    "gate_io": GateIoRateSource,
    "coinbase_advanced_trade": CoinbaseAdvancedTradeRateSource,
    "cube": CubeRateSource,
    "dexalot": DexalotRateSource,
    "hyperliquid": HyperliquidRateSource,
    "hyperliquid_perpetual": HyperliquidPerpetualRateSource,
    "architect_perpetual": ArchitectPerpetualRateSource,
    "derive": DeriveRateSource,
    "mexc": MexcRateSource,
    "evedex_perpetual": EvedexPerpetualRateSource,
    "pacifica_perpetual": PacificaPerpetualRateSource,
}


class RateOracle(NetworkBase):
    """
    RateOracle provides conversion rates for any given pair token symbols in both async and sync fashions.
    It achieves this by query URL on a given source for prices and store them, either in cache or as an object member.
    The find_rate is then used on these prices to find a rate on a given pair.
    """
    _logger: Optional[HummingbotLogger] = None
    _shared_instance: "RateOracle" = None

    @classmethod
    def get_instance(cls) -> "RateOracle":
        if cls._shared_instance is None:
            cls._shared_instance = RateOracle()
        return cls._shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, source: Optional[RateSourceBase] = None, quote_token: Optional[str] = None):
        super().__init__()
        self._source: RateSourceBase = source if source is not None else BinanceRateSource()
        self._prices: Dict[str, Decimal] = {}
        self._fetch_price_task: Optional[asyncio.Task] = None
        self._ready_event = asyncio.Event()
        self._quote_token = quote_token if quote_token is not None else "USD"
        self._connectors: Dict[str, "ConnectorBase"] = {}

    def register_connector(self, connector: "ConnectorBase") -> None:
        """
        Registers a live connector so that its order books can be used as a fallback
        price source when the configured rate source does not have a given pair.
        """
        self._connectors[connector.name] = connector

    def unregister_connector(self, connector_name: str) -> None:
        """
        Removes a previously registered connector from the fallback pool.
        """
        self._connectors.pop(connector_name, None)

    def _get_rate_from_connectors(self, pair: str) -> Optional[Decimal]:
        """
        Iterates over registered connectors (sorted by name for determinism) and returns
        the first positive mid price found for the requested pair, trying the reverse pair
        on each connector when the direct one is unavailable.
        """
        base, quote = split_hb_trading_pair(pair)
        reverse_pair = combine_to_hb_trading_pair(base=quote, quote=base)
        for name in sorted(self._connectors):
            connector = self._connectors[name]
            order_books = getattr(connector, "order_books", None) or {}
            if pair in order_books:
                rate = connector.get_price_by_type(pair, PriceType.MidPrice)
                if rate is not None and rate > Decimal("0"):
                    return rate
            if reverse_pair in order_books:
                reverse_rate = connector.get_price_by_type(reverse_pair, PriceType.MidPrice)
                if reverse_rate is not None and reverse_rate > Decimal("0"):
                    return Decimal("1") / reverse_rate
        return None

    def __str__(self):
        return f"{self._source.name} rate oracle"

    async def get_ready(self):
        """
        The network is ready when it first successfully get prices for a given source.
        """
        try:
            if not self._ready_event.is_set():
                await self._ready_event.wait()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error while waiting for data feed to get ready.",
                                exc_info=True)

    @property
    def name(self) -> str:
        return "rate_oracle"

    @property
    def source(self) -> RateSourceBase:
        return self._source

    @source.setter
    def source(self, new_source: RateSourceBase):
        self._source = new_source

    @property
    def quote_token(self) -> str:
        return self._quote_token

    @quote_token.setter
    def quote_token(self, new_token: str):
        if new_token != self._quote_token:
            self._quote_token = new_token
            self._prices = {}

    @property
    def prices(self) -> Dict[str, Decimal]:
        """
        Actual prices retrieved from URL
        """
        return self._prices.copy()

    async def start_network(self):
        await self.stop_network()
        self._fetch_price_task = safe_ensure_future(self._fetch_price_loop())

    async def stop_network(self):
        if self._fetch_price_task is not None:
            self._fetch_price_task.cancel()
            self._fetch_price_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            prices = await self._source.get_prices(quote_token=self._quote_token)
            if not prices:
                raise Exception(f"Error fetching new prices from {self._source.name}.")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def get_value(self, amount: Decimal, base_token: str) -> Decimal:
        """
        Finds a value in the configured quote of a given token amount.

        :param amount: An amount of token to be converted to value
        :param base_token: The token symbol that we want to price, e.g. BTC
        :return A value of the token in the configured quote token unit
        """
        rate = await self.get_rate(base_token=base_token)
        rate = Decimal("0") if rate is None else rate
        return amount * rate

    async def get_rate(self, base_token: str) -> Decimal:
        """
        Finds a conversion rate of a given token to a global token

        :param base_token: The token symbol that we want to price, e.g. BTC
        :return A conversion rate
        """
        prices = await self._source.get_prices(quote_token=self._quote_token)
        pair = combine_to_hb_trading_pair(base=base_token, quote=self._quote_token)
        return find_rate(prices, pair)

    def get_pair_rate(self, pair: str) -> Optional[Decimal]:
        """
        Finds a conversion rate for a given trading pair. The lookup tries, in order:
          1. the configured rate source cache (direct pair)
          2. registered connectors' live order books (direct and reverse pair)
          3. the configured rate source cache (reverse pair, inverted)
        Returns ``None`` when no rate can be resolved.

        :param pair: A trading pair, e.g. BTC-USDT
        :return A conversion rate, or ``None`` if no rate is available
        """
        rate = find_rate(self._prices, pair)
        if rate is not None and rate > Decimal("0"):
            return rate
        connector_rate = self._get_rate_from_connectors(pair)
        if connector_rate is not None:
            return connector_rate
        base, quote = split_hb_trading_pair(pair)
        reverse_pair = combine_to_hb_trading_pair(base=quote, quote=base)
        reverse_rate = find_rate(self._prices, reverse_pair)
        if reverse_rate is not None and reverse_rate > Decimal("0"):
            return Decimal("1") / reverse_rate
        return None

    async def stored_or_live_rate(self, pair: str) -> Decimal:
        """
        Finds a conversion rate for a given symbol trying to use the local prices. If local prices are not initialized
            uses the async rate finder (directly from the exchange)

        :param pair: A trading pair, e.g. BTC-USDT

        :return A conversion rate
        """
        if self._prices:
            rate = self.get_pair_rate(pair)
        else:
            rate = await self.rate_async(pair)

        return rate

    async def rate_async(self, pair: str) -> Decimal:
        """
        Finds a conversion rate in an async operation, it is a class method which can be used directly without having to
        start the RateOracle network.
        :param pair: A trading pair, e.g. BTC-USDT
        :return A conversion rate
        """
        prices = await self._source.get_prices(quote_token=self._quote_token)
        return find_rate(prices, pair)

    def set_price(self, pair: str, price: Decimal):
        """
        Update keys in self._prices with new prices
        """
        self._prices[pair] = price

    async def _fetch_price_loop(self):
        while True:
            try:
                new_prices = await self._source.get_prices(quote_token=self._quote_token)
                self._prices.update(new_prices)

                if self._prices:
                    self._ready_event.set()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(f"Error fetching new prices from {self.source.name}.", exc_info=True,
                                      app_warning_msg=f"Couldn't fetch newest prices from {self.source.name}.")
            await asyncio.sleep(1)
