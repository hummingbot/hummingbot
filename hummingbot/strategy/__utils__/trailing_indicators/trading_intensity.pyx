# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

import warnings
from decimal import Decimal
from typing import Tuple

import numpy as np
from scipy.optimize import curve_fit
from scipy.optimize import OptimizeWarning

from hummingbot.core.data_type.common import (
    PriceType,
)
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.event_listener cimport EventListener
from hummingbot.core.event.events import OrderBookEvent
from hummingbot.strategy.asset_price_delegate import AssetPriceDelegate

cdef class TradesForwarder(EventListener):
    def __init__(self, indicator: 'TradingIntensityIndicator'):
        self._indicator = indicator

    cdef c_call(self, object arg):
        self._indicator.c_register_trade(arg)


cdef class TradingIntensityIndicator:

    def __init__(self, order_book: OrderBook, price_delegate: AssetPriceDelegate, sampling_length: int = 30):
        self._alpha = 0
        self._kappa = 0
        self._trade_samples = {}
        self._current_trade_sample = []
        self._trades_forwarder = TradesForwarder(self)
        self._order_book = order_book
        self._order_book.c_add_listener(OrderBookEvent.TradeEvent, self._trades_forwarder)
        self._price_delegate = price_delegate
        self._sampling_length = sampling_length
        self._samples_length = 0
        self._last_quotes = []

        warnings.simplefilter("ignore", OptimizeWarning)

    @property
    def current_value(self) -> Tuple[float, float]:
        return self._alpha, self._kappa

    @property
    def is_sampling_buffer_full(self) -> bool:
        return len(self._trade_samples.keys()) == self._sampling_length

    @property
    def is_sampling_buffer_changed(self) -> bool:
        is_changed = self._samples_length != len(self._trade_samples.keys())
        self._samples_length = len(self._trade_samples.keys())
        return is_changed

    @property
    def sampling_length(self) -> int:
        return self._sampling_length

    @sampling_length.setter
    def sampling_length(self, new_len: int):
        self._sampling_length = new_len

    @property
    def last_quotes(self) -> list:
        """A helper method to be used in unit tests"""
        return self._last_quotes

    @last_quotes.setter
    def last_quotes(self, value):
        """A helper method to be used in unit tests"""
        self._last_quotes = value

    def calculate(self, timestamp):
        """A helper method to be used in unit tests"""
        self.c_calculate(timestamp)

    cdef c_calculate(self, timestamp):
        price = self._price_delegate.get_price_by_type(PriceType.MidPrice)
        # Descending order of price-timestamp quotes
        self._last_quotes = [{'timestamp': timestamp, 'price': price}] + self._last_quotes

        latest_processed_quote_idx = None
        for trade in self._current_trade_sample:
            for i, quote in enumerate(self._last_quotes):
                if quote["timestamp"] < trade.timestamp:
                    if latest_processed_quote_idx is None or i < latest_processed_quote_idx:
                        latest_processed_quote_idx = i
                    trade = {"price_level": abs(trade.price - float(quote["price"])), "amount": trade.amount}

                    if quote["timestamp"] + 1 not in self._trade_samples.keys():
                        self._trade_samples[quote["timestamp"] + 1] = []

                    self._trade_samples[quote["timestamp"] + 1] += [trade]
                    break

        # THere are no trades left to process
        self._current_trade_sample = []
        # Store quotes that happened after the latest trade + one before
        if latest_processed_quote_idx is not None:
            self._last_quotes = self._last_quotes[0:latest_processed_quote_idx + 1]

        if len(self._trade_samples.keys()) > self._sampling_length:
            timestamps = list(self._trade_samples.keys())
            timestamps.sort()
            timestamps = timestamps[-self._sampling_length:]

            trade_samples = {}
            for timestamp in timestamps:
                trade_samples[timestamp] = self._trade_samples[timestamp]
            self._trade_samples = trade_samples

        if self.is_sampling_buffer_full:
            self.c_estimate_intensity()

    def register_trade(self, trade):
        """A helper method to be used in unit tests"""
        self.c_register_trade(trade)

    cdef c_register_trade(self, object trade):
        self._current_trade_sample.append(trade)

    cdef c_estimate_intensity(self):
        cdef:
            dict trades_consolidated
            list lambdas
            list price_levels

        # Calculate lambdas / trading intensities
        lambdas = []

        trades_consolidated = {}
        price_levels = []
        for timestamp in self._trade_samples.keys():
            tick = self._trade_samples[timestamp]
            for trade in tick:
                if trade['price_level'] not in trades_consolidated.keys():
                    trades_consolidated[trade['price_level']] = 0
                    price_levels += [trade['price_level']]

                trades_consolidated[trade['price_level']] += trade['amount']

        price_levels = sorted(price_levels, reverse=True)

        for price_level in price_levels:
            lambdas += [trades_consolidated[price_level]]

        # Adjust to be able to calculate log
        lambdas_adj = [10**-10 if x==0 else x for x in lambdas]

        # Fit the probability density function; reuse previously calculated parameters as initial values
        try:
            params = curve_fit(lambda t, a, b: a*np.exp(-b*t),
                               price_levels,
                               lambdas_adj,
                               p0=(self._alpha, self._kappa),
                               method='dogbox',
                               bounds=([0, 0], [np.inf, np.inf]))

            self._kappa = Decimal(str(params[0][1]))
            self._alpha = Decimal(str(params[0][0]))
        except (RuntimeError, ValueError) as e:
            pass
