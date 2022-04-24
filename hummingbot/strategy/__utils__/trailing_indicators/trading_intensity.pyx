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
from hummingbot.core.event.event_listener cimport EventListener
from hummingbot.core.event.events import TradeType, OrderBookEvent
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
        self._trade_samples = []
        self._current_trade_sample = []
        self._trades_forwarder = TradesForwarder(self)
        self._order_book = order_book
        self._order_book.c_add_listener(OrderBookEvent.TradeEvent, self._trades_forwarder)
        self._price_delegate = price_delegate
        self._sampling_length = sampling_length
        self._samples_length = 0

        warnings.simplefilter("ignore", OptimizeWarning)

    @property
    def current_value(self) -> Tuple[float, float]:
        return self._alpha, self._kappa

    @property
    def is_sampling_buffer_full(self) -> bool:
        return len(self._trade_samples) == self._sampling_length

    @property
    def is_sampling_buffer_changed(self) -> bool:
        is_changed = self._samples_length != len(self._trade_samples)
        self._samples_length = len(self._trade_samples)
        return is_changed

    @property
    def sampling_length(self) -> int:
        return self._sampling_length

    @property
    def last_price(self) -> float:
        return self._last_price

    @last_price.setter
    def last_price(self, value):
        self._last_price = value

    def calculate(self):
        self.c_calculate()

    cdef c_calculate(self):
        self._last_price = self._price_delegate.get_price_by_type(PriceType.MidPrice)
        self._trade_samples.append(self._current_trade_sample)
        if len(self._trade_samples) > self._sampling_length:
            self._trade_samples = self._trade_samples[-self._sampling_length:]
        self._current_trade_sample = []
        if self.is_sampling_buffer_full:
            self.c_estimate_intensity()

    def register_trade(self, trade):
        self.c_register_trade(trade)

    cdef c_register_trade(self, object trade):
        self._current_trade_sample.append({"price_level": abs(trade.price - self._last_price), "amount": trade.amount})

    def _estimate_intensity(self):
        self.c_estimate_intensity()

    cdef c_estimate_intensity(self):
        cdef:
            dict trades_consolidated
            list lambdas
            list price_levels

        # Calculate lambdas / trading intensities
        lambdas = []

        trades_consolidated = {}
        price_levels = []
        for tick in self._trade_samples:
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
