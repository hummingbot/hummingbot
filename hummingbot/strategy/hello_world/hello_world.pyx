# distutils: language=c++
import asyncio
import logging

import pandas as pd
from typing import (
    List
)

from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy. import HelloWorldMarketPair
from hummingbot.strategy.strategy_base cimport StrategyBase
from hummingbot.market.market_base cimport MarketBase

from libc.stdint cimport int64_t
from hummingbot.core.data_type.order_book cimport OrderBook
import itertools

NaN = float("nan")
ds_logger = None


cdef class HelloWorldStrategy(StrategyBase):
    OPTION_LOG_STATUS_REPORT = 1 << 0
    OPTION_LOG_ALL = 0xfffffffffffffff

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ds_logger
        if ds_logger is None:
            ds_logger = logging.getLogger(__name__)
        return ds_logger

    def __init__(self,
                 market_pairs: List[HelloWorldMarketPair],
                 discovery_method: str = "arbitrage",
                 target_amount: float = float("inf"),
                 target_profitability: float = 0.0,
                 logging_options: int = OPTION_LOG_ALL,
                 status_report_interval: float = 900,
                 target_symbols: list = [],
                 equivalent_token: list = []):
        if len(market_pairs) < 0:
            raise ValueError(f"market_pairs must not be empty.")
        self._market_pairs = market_pairs
        self._target_amount = target_amount
        self._target_profitability = target_profitability
        self._logging_options = logging_options
        self._status_report_interval = status_report_interval
        self._refetch_market_info_interval = 60.0 * 60
        self._all_markets_ready = False
        self._markets = set()
        self._last_timestamp = 0
        self._discovery_stats = {}
        self._discovery_method = discovery_method
        self._market_info = {}
        self._matching_pairs = set()
        self._equivalent_token = equivalent_token
        self._target_symbols = target_symbols
        self._equivalent_token_dict = self.parse_equivalent_token(self._equivalent_token)
        self._fetch_market_info_task_list = None

        cdef:
            MarketBase typed_market

        for market_pair in self._market_pairs:
            for market in [market_pair.market_1, market_pair.market_2]:
                self._markets.add(market)
    async def fetch_market_info(self, market_pair):
        try:
            for market, fetch_market_info in [(market_pair.market_1, market_pair.market_1_fetch_market_info),
                                              (market_pair.market_2, market_pair.market_2_fetch_market_info)]:
                markets = self.filter_trading_pairs(self._target_symbols,
                                                    await fetch_market_info(),
                                                    self._equivalent_token)
                self._market_info[market] = {"markets": markets,
                                             "base_quote_to_symbol": {},
                                             "timestamp": self._current_timestamp}
                for trading_symbol, b, q in zip(markets.index, markets.baseAsset, markets.quoteAsset):
                    self._market_info[market]["base_quote_to_symbol"][(b, q)] = (trading_symbol, b, q)

            self._matching_pairs = self.get_matching_pair(market_pair)

        except Exception as e:
            self.logger().network(f"Could not fetch market info for {market_pair}", exc_info=True,
                                  app_warning_msg=f"Failed to fetch market info for {market_pair}. "
                                                  f"Check network connection.")

    def get_matching_pair(self, market_pair):
        market_1 = market_pair.market_1
        market_2 = market_pair.market_2
        market_1_info_df = self._market_info[market_1]["markets"]
        market_2_info_df = self._market_info[market_2]["markets"]
        market_1_base_quote = set(zip(market_1_info_df.baseAsset, market_1_info_df.quoteAsset))
        market_2_base_quote = set(zip(market_2_info_df.baseAsset, market_2_info_df.quoteAsset))
        matching_pair = set()

        for base_1, quote_1 in market_1_base_quote:
            # check for all equivalent base and quote token from market1 in market2
            for equivalent_base_1, equivalent_quote_1 in itertools.product(
                    self._equivalent_token_dict.get(base_1, {base_1}),
                    self._equivalent_token_dict.get(quote_1, {quote_1})):

                if (equivalent_base_1, equivalent_quote_1) in market_2_base_quote:
                    matching_pair.add((
                        self._market_info[market_1]["base_quote_to_symbol"][(base_1, quote_1)],
                        self._market_info[market_2]["base_quote_to_symbol"][(equivalent_base_1,
                                                                             equivalent_quote_1)]
                    ))
        return matching_pair

    cdef c_tick(self, double timestamp):
        StrategyBase.c_tick(self, timestamp)
        if not self._fetch_market_info_task_list:
            self._fetch_market_info_task_list = [asyncio.ensure_future(self.fetch_market_info(market_pair))
                                                for market_pair in self._market_pairs]

        for market in self._markets:
            if not market in self._market_info:
                self.log_with_clock(logging.INFO, f"Waiting to finish fetching trading pair from {market.name}.")
                return

        if not self._all_markets_ready:
            self._all_markets_ready = all([market.ready for market in self._markets])
            if not self._all_markets_ready:
                # Markets not ready yet. Don't do anything.
                return
        for market_pair in self._market_pairs:
            try:
                self.c_process_market_pair(market_pair)
            except Exception:
                self.logger().error(f"Error processing market pair {market_pair}.", exc_info=True)

        cdef:
            int64_t current_tick
            int64_t last_tick

        if self._logging_options & self.OPTION_LOG_STATUS_REPORT:
            current_tick = <int64_t>(timestamp // self._status_report_interval)
            last_tick = <int64_t>(self._last_timestamp // self._status_report_interval)
            if current_tick < last_tick:
                self.logger().info(self.format_status())
        self._last_timestamp = timestamp

