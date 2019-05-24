import asyncio
import logging
import math
from typing import (
    Optional,
    List,
    Dict)

from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.logger import HummingbotLogger
from hummingbot.data_feed.coin_cap_data_feed import CoinCapDataFeed
from hummingbot.data_feed.data_feed_base import DataFeedBase

NaN = float("nan")


class ExchangeRateConversion:
    erc_logger: Optional[HummingbotLogger] = None
    _erc_shared_instance: "ExchangeRateConversion" = None
    _exchange_rate_config_override: Optional[Dict[str, Dict]] = None
    _data_feeds_override: Optional[List[DataFeedBase]] = None
    _update_interval: float = 5.0
    _data_feeds: List[DataFeedBase] = []
    _exchange_rate_config: Dict[str, Dict] = {"conversion_required": {}, "global_config": {}}
    _exchange_rate: Dict[str, float] = {}
    _started: bool = False

    @classmethod
    def get_instance(cls) -> "ExchangeRateConversion":
        if cls._erc_shared_instance is None:
            cls._erc_shared_instance = ExchangeRateConversion()
        return cls._erc_shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.erc_logger is None:
            cls.erc_logger = logging.getLogger(__name__)
        return cls.erc_logger

    @classmethod
    def set_global_exchange_rate_config(cls, config: Dict[str, Dict]):
        if cls._exchange_rate_config_override is None:
            cls._exchange_rate_config_override = config
        else:
            cls._exchange_rate_config_override.clear()
            cls._exchange_rate_config_override.update(config)
        cls.init_config()

    @classmethod
    def set_data_feeds(cls, data_feeds: List[DataFeedBase]):
        if cls._data_feeds_override is None:
            cls._data_feeds_override = data_feeds
        else:
            cls._data_feeds_override.clear()
            cls._data_feeds_override.extend(data_feeds)
        cls.init_config()

    @classmethod
    def set_update_interval(cls, update_interval: float):
        cls._update_interval = update_interval

    @classmethod
    def init_config(cls):
        try:
            if cls._data_feeds_override is None:
                cls._data_feeds = [CoinCapDataFeed.get_instance()]
            else:
                cls._data_feeds = cls._data_feeds_override
            # Set default rate and source for token rates globally
            fetcher_global_config: List[List[str, str]] = global_config_map["exchange_rate_fetcher"].value or []
            # Set rate and source for tokens that needs conversion, overwrites global config
            rate_conversion_config: List[List[str, str, str]] = global_config_map[
                                                                    "exchange_rate_conversion"].value or []

            if cls._exchange_rate_config_override is None:
                conversion_required = {e[0]: {"default": e[1], "source": e[2]} for e in rate_conversion_config}
                global_config = {e[0]: {"default": NaN, "source": e[1]} for e in fetcher_global_config}
            else:
                conversion_required = cls._exchange_rate_config_override.get("conversion_required", {})
                global_config = cls._exchange_rate_config_override.get("global_config", {})

            cls._exchange_rate_config = {
                "conversion_required": conversion_required,
                "global_config": {**global_config, **conversion_required}
            }
            cls._exchange_rate = {k: v["default"] for k, v in cls._exchange_rate_config["global_config"].items()}
        except Exception:
            cls.logger().error("Error initiating config for exchange rate conversion.", exc_info=True)


    @property
    def exchange_rate(self):
        return self._exchange_rate.copy()

    def __init__(self):
        self._fetch_exchange_rate_task: Optional[asyncio.Task] = None
        self.init_config()

    def adjust_token_rate(self, symbol: str, price: float) -> float:
        """
        Returns the USD rate of a given token if it is found in conversion_required config
        :param symbol:
        :param price:
        :return:
        """
        if not self._started:
            self.start()
        if symbol in self._exchange_rate_config["conversion_required"] and symbol in self._exchange_rate:
            return self._exchange_rate[symbol] * price
        else:
            return price

    def convert_token_value(self, amount: float, from_currency: str, to_currency: str):
        """
        Converts a token amount to the amount of another token with equivalent worth
        :param amount:
        :param from_currency:
        :param to_currency:
        :return:
        """
        if not self._started:
            self.start()
        # assume WETH and ETH are equal value
        if from_currency == "ETH" and to_currency == "WETH" or from_currency == "WETH" and to_currency == "ETH":
            return amount
        from_currency_usd_rate = self._exchange_rate.get(from_currency, NaN)
        to_currency_usd_rate = self._exchange_rate.get(to_currency, NaN)
        if math.isnan(from_currency_usd_rate) or math.isnan(to_currency_usd_rate):
            raise ValueError(f"Unable to convert '{from_currency}' to '{to_currency}'. Aborting.")
        return amount * from_currency_usd_rate / to_currency_usd_rate

    async def update_exchange_rates_from_data_feeds(self):
        try:
            for data_feed in self._data_feeds:
                source_name = data_feed.name
                for symbol, config in self._exchange_rate_config["global_config"].items():
                    if config["source"].lower() == source_name.lower():
                        price = data_feed.get_price(symbol)
                        if price:
                            self._exchange_rate[symbol] = price
                        else:
                            self.logger().network(
                                f"No data found for {symbol} in {source_name} data feed.",
                                app_warning_msg=f"Asset data for {symbol} not found in {source_name} data feed, "
                                                f"please check your 'exchange_rate_conversion' configs."
                            )
        except Exception:
            self.logger().warning(f"Error getting data from {source_name} data feed.", exc_info=True)
            raise

    async def wait_till_ready(self):
        for data_feed in self._data_feeds:
            await data_feed.get_ready()

    async def request_loop(self):
        while True:
            try:
                await self.wait_till_ready()
                await self.update_exchange_rates_from_data_feeds()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(f"Error sending requests.", exc_info=True, extra={"do_not_send": True})

            await asyncio.sleep(self._update_interval)

    def start(self):
        self.stop()
        for data_feed in self._data_feeds:
            data_feed.start()
        self._fetch_exchange_rate_task = asyncio.ensure_future(self.request_loop())
        self._started = True

    def stop(self):
        for data_feed in self._data_feeds:
            data_feed.stop()
        if self._fetch_exchange_rate_task and not self._fetch_exchange_rate_task.done():
            self._fetch_exchange_rate_task.cancel()
        self._started = False
