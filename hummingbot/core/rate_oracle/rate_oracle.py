import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional

import hummingbot.client.settings  # noqa
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.network_base import NetworkBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.rate_oracle.sources.ascend_ex_rate_source import AscendExRateSource
from hummingbot.core.rate_oracle.sources.binance_rate_source import BinanceRateSource
from hummingbot.core.rate_oracle.sources.binance_us_rate_source import BinanceUSRateSource
from hummingbot.core.rate_oracle.sources.coin_cap_rate_source import CoinCapRateSource
from hummingbot.core.rate_oracle.sources.coin_gecko_rate_source import CoinGeckoRateSource
from hummingbot.core.rate_oracle.sources.coinbase_advanced_trade_rate_source import CoinbaseAdvancedTradeRateSource
from hummingbot.core.rate_oracle.sources.cube_rate_source import CubeRateSource
from hummingbot.core.rate_oracle.sources.gate_io_rate_source import GateIoRateSource
from hummingbot.core.rate_oracle.sources.kucoin_rate_source import KucoinRateSource
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.rate_oracle.utils import find_rate
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger

RATE_ORACLE_SOURCES = {
    "binance": BinanceRateSource,
    "binance_us": BinanceUSRateSource,
    "coin_gecko": CoinGeckoRateSource,
    "coin_cap": CoinCapRateSource,
    "kucoin": KucoinRateSource,
    "ascend_ex": AscendExRateSource,
    "gate_io": GateIoRateSource,
    "coinbase_advanced_trade": CoinbaseAdvancedTradeRateSource,
    "cube": CubeRateSource,
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
        # Reset stored prices so that they are not used if they are not being updated
        self._prices = {}

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

    def get_pair_rate(self, pair: str) -> Decimal:
        """
        Finds a conversion rate for a given trading pair, this can be direct or indirect prices as
        long as it can find a route to achieve this.

        :param pair: A trading pair, e.g. BTC-USDT
        :return A conversion rate
        """
        return find_rate(self._prices, pair)

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
