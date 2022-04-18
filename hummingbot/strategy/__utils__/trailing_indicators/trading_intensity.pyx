from decimal import Decimal
from math import floor, ceil
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from scipy.optimize import OptimizeWarning
from typing import (
    Tuple,
)
import warnings


cdef class TradingIntensityIndicator():

    def __init__(self, sampling_length: int = 30):
        self._alpha = 0
        self._kappa = 0
        self._trades = []
        self._bids_df = None
        self._asks_df = None
        self._sampling_length = sampling_length
        self._samples_length = 0
        self._last_trade = None
        self._last_timestamp = 0

        warnings.simplefilter("ignore", OptimizeWarning)

    def _process_sample(self, bids_df, asks_df, trades):
        self.c_simulate_execution(bids_df, asks_df, trades)

    cdef c_process_sample(self, new_bids_df, new_asks_df, trades):
        cdef:
            object _bids_df = self._bids_df
            object _asks_df = self._asks_df
            object bids_df = new_bids_df
            object asks_df = new_asks_df
            int _sampling_length = self._sampling_length
            float last_timestamp = self._last_timestamp
            object bid
            object ask
            object price
            object bid_prev
            object ask_prev
            object price_prev
            list new_trades

        bid = bids_df["price"].iloc[0]
        ask = asks_df["price"].iloc[0]
        price = (bid + ask) / 2

        bid_prev = _bids_df["price"].iloc[0]
        ask_prev = _asks_df["price"].iloc[0]
        price_prev = (bid_prev + ask_prev) / 2

        new_trades = []

        # Iterate from the most recent trade towards the last processed trade
        # Process only trades after the last stored order book / previous mid price, or at the timestamp (in case they were not processed yet)
        for idx in reversed(trades[trades.timestamp >= last_timestamp].index):
            if self._last_trade is not None and self._last_trade.equals(trades.loc[idx]):
                # No last trade exists, but this current trade happened after the last stored order book snapshot
                # OR this and all following trades were already processed
                break
            else:
                # New / unprocessed trades
                amount = trades.loc[idx].amount
                price_level = abs(trades.loc[idx].price - price_prev)
                new_trades += [{'price_level': price_level, 'amount': amount}]

        # Store the last processed trade
        self._last_trade = trades.iloc[-1]

        print(new_trades)

        # Add trades
        self._trades += [new_trades]
        if len(self._trades) > _sampling_length:
            self._trades = self._trades[-_sampling_length:]

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
        for tick in self._trades:
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

    def add_sample(self, timestamp: float, snapshot: Tuple[pd.DataFrame, pd.DataFrame], trades: pd.DataFrame):
        bids_df = snapshot[0]
        asks_df = snapshot[1]

        # Skip empty order books
        if bids_df.empty or asks_df.empty:
            return

        # Skip empty trades
        if len(trades) <= 0:
            return

        # Do not process until a previous order book is not available
        if self._bids_df is not None and self._asks_df is not None:
            self.c_process_sample(bids_df, asks_df, trades)

            if self.is_sampling_buffer_full:
                # Estimate alpha and kappa
                self.c_estimate_intensity()

        # Store the orderbook
        self._bids_df = bids_df
        self._asks_df = asks_df
        self._last_timestamp = timestamp

    @property
    def current_value(self) -> Tuple[float, float]:
        return self._alpha, self._kappa

    @property
    def is_sampling_buffer_full(self) -> bool:
        return len(self._trades) == self._sampling_length

    @property
    def is_sampling_buffer_changed(self) -> bool:
        is_changed = self._samples_length != len(self._trades)
        self._samples_length = len(self._trades)
        return is_changed

    @property
    def sampling_length(self) -> int:
        return self._sampling_length
