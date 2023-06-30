# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp
import bisect
import logging
import time
from typing import (
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
)

import numpy as np
import pandas as pd

from cython.operator cimport(
    address as ref,
    dereference as deref,
    postincrement as inc,
)

from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_query_result import OrderBookQueryResult
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.OrderBookEntry cimport truncateOverlapEntries
from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.events import (
    OrderBookEvent,
    OrderBookTradeEvent
)

cimport numpy as np

ob_logger = None
NaN = float("nan")


cdef class OrderBook(PubSub):
    ORDER_BOOK_TRADE_EVENT_TAG = OrderBookEvent.TradeEvent.value

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ob_logger
        if ob_logger is None:
            ob_logger = logging.getLogger(__name__)
        return ob_logger

    def __init__(self, dex=False):
        super().__init__()
        self._snapshot_uid = 0
        self._last_diff_uid = 0
        self._best_bid = self._best_ask = float("NaN")
        self._last_trade_price = float("NaN")
        self._last_applied_trade = -1000.0
        self._last_trade_price_rest_updated = -1000
        self._dex = dex

    cdef c_apply_diffs(self, vector[OrderBookEntry] bids, vector[OrderBookEntry] asks, int64_t update_id):
        cdef:
            set[OrderBookEntry].iterator bid_book_end = self._bid_book.end()
            set[OrderBookEntry].iterator ask_book_end = self._ask_book.end()
            set[OrderBookEntry].reverse_iterator bid_iterator
            set[OrderBookEntry].iterator ask_iterator
            set[OrderBookEntry].iterator result
            OrderBookEntry top_bid
            OrderBookEntry top_ask

        # Apply the diffs. Diffs with 0 amounts mean deletion.
        for bid in bids:
            result = self._bid_book.find(bid)
            if result != bid_book_end:
                self._bid_book.erase(result)
            if bid.getAmount() > 0:
                self._bid_book.insert(bid)
        for ask in asks:
            result = self._ask_book.find(ask)
            if result != ask_book_end:
                self._ask_book.erase(result)
            if ask.getAmount() > 0:
                self._ask_book.insert(ask)

        # If any overlapping entries between the bid and ask books, centralised: newer entries win, dex: see OrderBookEntry.cpp
        truncateOverlapEntries(self._bid_book, self._ask_book, self._dex)

        # Record the current best prices, for faster c_get_price() calls.
        bid_iterator = self._bid_book.rbegin()
        ask_iterator = self._ask_book.begin()
        if bid_iterator != self._bid_book.rend():
            top_bid = deref(bid_iterator)
            self._best_bid = top_bid.getPrice()
        if ask_iterator != self._ask_book.end():
            top_ask = deref(ask_iterator)
            self._best_ask = top_ask.getPrice()

        # Remember the last diff update ID.
        self._last_diff_uid = update_id

    cdef c_apply_snapshot(self, vector[OrderBookEntry] bids, vector[OrderBookEntry] asks, int64_t update_id):
        cdef:
            double best_bid_price = float("NaN")
            double best_ask_price = float("NaN")
            set[OrderBookEntry].reverse_iterator bid_iterator
            set[OrderBookEntry].iterator ask_iterator
            OrderBookEntry top_bid
            OrderBookEntry top_ask

        # Start with an empty order book, and then insert all entries.
        self._bid_book.clear()
        self._ask_book.clear()
        for bid in bids:
            self._bid_book.insert(bid)
            if not (bid.getPrice() <= best_bid_price):
                best_bid_price = bid.getPrice()
        for ask in asks:
            self._ask_book.insert(ask)
            if not (ask.getPrice() >= best_ask_price):
                best_ask_price = ask.getPrice()

        if self._dex:
            truncateOverlapEntries(self._bid_book, self._ask_book, self._dex)
            # Record the current best prices, for faster c_get_price() calls.
            bid_iterator = self._bid_book.rbegin()
            ask_iterator = self._ask_book.begin()
            if bid_iterator != self._bid_book.rend():
                top_bid = deref(bid_iterator)
                best_bid_price = top_bid.getPrice()
            if ask_iterator != self._ask_book.end():
                top_ask = deref(ask_iterator)
                best_ask_price = top_ask.getPrice()

        # Record the current best prices, for faster c_get_price() calls.
        self._best_bid = best_bid_price
        self._best_ask = best_ask_price

        # Remember the last snapshot update ID.
        self._snapshot_uid = update_id

    cdef c_apply_trade(self, object trade_event):
        self._last_trade_price = trade_event.price
        self._last_applied_trade = time.perf_counter()
        self.c_trigger_event(self.ORDER_BOOK_TRADE_EVENT_TAG, trade_event)

    @property
    def last_trade_price(self) -> float:
        return self._last_trade_price

    @last_trade_price.setter
    def last_trade_price(self, value: float):
        self._last_trade_price = value

    @property
    def last_applied_trade(self) -> float:
        return self._last_applied_trade

    @property
    def last_trade_price_rest_updated(self) -> float:
        return self._last_trade_price_rest_updated

    @last_trade_price_rest_updated.setter
    def last_trade_price_rest_updated(self, value: float):
        self._last_trade_price_rest_updated = value

    @property
    def snapshot_uid(self) -> int:
        return self._snapshot_uid

    @property
    def last_diff_uid(self) -> int:
        return self._last_diff_uid

    @property
    def snapshot(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        bids_rows = list(self.bid_entries())
        asks_rows = list(self.ask_entries())
        bids_df = pd.DataFrame(data=bids_rows, columns=OrderBookRow._fields, dtype="float64")
        asks_df = pd.DataFrame(data=asks_rows, columns=OrderBookRow._fields, dtype="float64")
        return bids_df, asks_df

    def apply_diffs(self, bids: List[OrderBookRow], asks: List[OrderBookRow], update_id: int):
        cdef:
            vector[OrderBookEntry] cpp_bids
            vector[OrderBookEntry] cpp_asks
        for row in bids:
            cpp_bids.push_back(OrderBookEntry(row.price, row.amount, row.update_id))
        for row in asks:
            cpp_asks.push_back(OrderBookEntry(row.price, row.amount, row.update_id))
        self.c_apply_diffs(cpp_bids, cpp_asks, update_id)

    def apply_snapshot(self, bids: List[OrderBookRow], asks: List[OrderBookRow], update_id: int):
        cdef:
            vector[OrderBookEntry] cpp_bids
            vector[OrderBookEntry] cpp_asks
        for row in bids:
            cpp_bids.push_back(OrderBookEntry(row.price, row.amount, row.update_id))
        for row in asks:
            cpp_asks.push_back(OrderBookEntry(row.price, row.amount, row.update_id))
        self.c_apply_snapshot(cpp_bids, cpp_asks, update_id)

    def apply_trade(self, trade: OrderBookTradeEvent):
        self.c_apply_trade(trade)

    def apply_pandas_diffs(self, bids_df: pd.DataFrame, asks_df: pd.DataFrame):
        """
        The diffs data frame must have 3 columns, [price, amount, update_id], and a UNIX timestamp index.

        All columns are of double type.
        """
        self.apply_numpy_diffs(bids_df.values, asks_df.values)

    def apply_numpy_diffs(self, bids_array: np.ndarray, asks_array: np.ndarray):
        """
        The diffs data frame must have 3 columns, [price, amount, update_id].
        All columns are of double type.
        """
        self.c_apply_numpy_diffs(bids_array, asks_array)

    cdef c_apply_numpy_diffs(self,
                             np.ndarray[np.float64_t, ndim=2] bids_array,
                             np.ndarray[np.float64_t, ndim=2] asks_array):
        """
        The diffs data frame must have 3 columns, [price, amount, update_id].
        All columns are of double type.
        """
        cdef:
            vector[OrderBookEntry] cpp_bids
            vector[OrderBookEntry] cpp_asks
            int64_t last_update_id = 0

        for row in bids_array:
            cpp_bids.push_back(OrderBookEntry(row[0], row[1], <int64_t>(row[2])))
            last_update_id = max(last_update_id, <int64_t>row[2])
        for row in asks_array:
            cpp_asks.push_back(OrderBookEntry(row[0], row[1], <int64_t>(row[2])))
            last_update_id = max(last_update_id, <int64_t>row[2])
        self.c_apply_diffs(cpp_bids, cpp_asks, last_update_id)

    def apply_numpy_snapshot(self, bids_array: np.ndarray, asks_array: np.ndarray):
        """
        The diffs data frame must have 3 columns, [price, amount, update_id].
        All columns are of double type.
        """
        self.c_apply_numpy_snapshot(bids_array, asks_array)

    cdef c_apply_numpy_snapshot(self,
                                np.ndarray[np.float64_t, ndim=2] bids_array,
                                np.ndarray[np.float64_t, ndim=2] asks_array):
        """
        The diffs data frame must have 3 columns, [price, amount, update_id].
        All columns are of double type.
        """
        cdef:
            vector[OrderBookEntry] cpp_bids
            vector[OrderBookEntry] cpp_asks
            int64_t last_update_id = 0

        for row in bids_array:
            cpp_bids.push_back(OrderBookEntry(row[0], row[1], <int64_t>(row[2])))
            last_update_id = max(last_update_id, <int64_t>row[2])
        for row in asks_array:
            cpp_asks.push_back(OrderBookEntry(row[0], row[1], <int64_t>(row[2])))
            last_update_id = max(last_update_id, <int64_t>row[2])
        self.c_apply_snapshot(cpp_bids, cpp_asks, last_update_id)

    def bid_entries(self) -> Iterator[OrderBookRow]:
        cdef:
            set[OrderBookEntry].reverse_iterator it = self._bid_book.rbegin()
            OrderBookEntry entry
        while it != self._bid_book.rend():
            entry = deref(it)
            yield OrderBookRow(entry.getPrice(), entry.getAmount(), entry.getUpdateId())
            inc(it)

    def ask_entries(self) -> Iterator[OrderBookRow]:
        cdef:
            set[OrderBookEntry].iterator it = self._ask_book.begin()
            OrderBookEntry entry
        while it != self._ask_book.end():
            entry = deref(it)
            yield OrderBookRow(entry.getPrice(), entry.getAmount(), entry.getUpdateId())
            inc(it)

    def simulate_buy(self, amount: float) -> List[OrderBookRow]:
        amount_left = amount
        retval = []
        for ask_entry in self.ask_entries():
            ask_entry = ask_entry
            if ask_entry.amount < amount_left:
                retval.append(ask_entry)
                amount_left -= ask_entry.amount
            else:
                retval.append(OrderBookRow(ask_entry.price, amount_left, ask_entry.update_id))
                amount_left = 0.0
                break
        return retval

    def simulate_sell(self, amount: float) -> List[OrderBookRow]:
        amount_left = amount
        retval = []
        for bid_entry in self.bid_entries():
            bid_entry = bid_entry
            if bid_entry.amount < amount_left:
                retval.append(bid_entry)
                amount_left -= bid_entry.amount
            else:
                retval.append(OrderBookRow(bid_entry.price, amount_left, bid_entry.update_id))
                amount_left = 0.0
                break
        return retval

    cdef double c_get_price(self, bint is_buy) except? -1:
        cdef:
            set[OrderBookEntry] *book = ref(self._ask_book) if is_buy else ref(self._bid_book)
        if deref(book).size() < 1:
            raise EnvironmentError("Order book is empty - no price quote is possible.")
        return self._best_ask if is_buy else self._best_bid

    def get_price(self, is_buy: bool) -> float:
        return self.c_get_price(is_buy)

    cdef OrderBookQueryResult c_get_price_for_volume(self, bint is_buy, double volume):
        cdef:
            double cumulative_volume = 0
            double result_price = NaN

        if is_buy:
            for order_book_row in self.ask_entries():
                cumulative_volume += order_book_row.amount
                if cumulative_volume >= volume:
                    result_price = order_book_row.price
                    break
        else:
            for order_book_row in self.bid_entries():
                cumulative_volume += order_book_row.amount
                if cumulative_volume >= volume:
                    result_price = order_book_row.price
                    break

        return OrderBookQueryResult(NaN, volume, result_price, min(cumulative_volume, volume))

    cdef OrderBookQueryResult c_get_vwap_for_volume(self, bint is_buy, double volume):
        cdef:
            double total_cost = 0
            double total_volume = 0
            double result_vwap = NaN
        if is_buy:
            for order_book_row in self.ask_entries():
                total_cost += order_book_row.amount * order_book_row.price
                total_volume += order_book_row.amount
                if total_volume >= volume:
                    total_cost -= order_book_row.amount * order_book_row.price
                    total_volume -= order_book_row.amount
                    incremental_amount = volume - total_volume
                    total_cost += incremental_amount * order_book_row.price
                    total_volume += incremental_amount
                    result_vwap = total_cost / total_volume
                    break
        else:
            for order_book_row in self.bid_entries():
                total_cost += order_book_row.amount * order_book_row.price
                total_volume += order_book_row.amount
                if total_volume >= volume:
                    total_cost -= order_book_row.amount * order_book_row.price
                    total_volume -= order_book_row.amount
                    incremental_amount = volume - total_volume
                    total_cost += incremental_amount * order_book_row.price
                    total_volume += incremental_amount
                    result_vwap = total_cost / total_volume
                    break

        return OrderBookQueryResult(NaN, volume, result_vwap, min(total_volume, volume))

    cdef OrderBookQueryResult c_get_price_for_quote_volume(self, bint is_buy, double quote_volume):
        cdef:
            double cumulative_volume = 0
            double result_price = NaN

        if is_buy:
            for order_book_row in self.ask_entries():
                cumulative_volume += order_book_row.amount * order_book_row.price
                if cumulative_volume >= quote_volume:
                    result_price = order_book_row.price
                    break
        else:
            for order_book_row in self.bid_entries():
                cumulative_volume += order_book_row.amount * order_book_row.price
                if cumulative_volume >= quote_volume:
                    result_price = order_book_row.price
                    break

        return OrderBookQueryResult(NaN, quote_volume, result_price, min(cumulative_volume, quote_volume))

    cdef OrderBookQueryResult c_get_quote_volume_for_base_amount(self, bint is_buy, double base_amount):
        cdef:
            double cumulative_volume = 0
            double cumulative_base_amount = 0
            double row_amount = 0

        if is_buy:
            for order_book_row in self.ask_entries():
                row_amount = order_book_row.amount
                if row_amount + cumulative_base_amount >= base_amount:
                    row_amount = base_amount - cumulative_base_amount
                cumulative_base_amount += row_amount
                cumulative_volume += row_amount * order_book_row.price
                if cumulative_base_amount >= base_amount:
                    break
        else:
            for order_book_row in self.bid_entries():
                row_amount = order_book_row.amount
                if row_amount + cumulative_base_amount >= base_amount:
                    row_amount = base_amount - cumulative_base_amount
                cumulative_base_amount += row_amount
                cumulative_volume += row_amount * order_book_row.price
                if cumulative_base_amount >= base_amount:
                    break

        return OrderBookQueryResult(NaN, base_amount, NaN, cumulative_volume)

    cdef OrderBookQueryResult c_get_volume_for_price(self, bint is_buy, double price):
        cdef:
            double cumulative_volume = 0
            double result_price = NaN

        if is_buy:
            for order_book_row in self.ask_entries():
                if order_book_row.price > price:
                    break
                cumulative_volume += order_book_row.amount
                result_price = order_book_row.price
        else:
            for order_book_row in self.bid_entries():
                if order_book_row.price < price:
                    break
                cumulative_volume += order_book_row.amount
                result_price = order_book_row.price

        return OrderBookQueryResult(price, NaN, result_price, cumulative_volume)

    cdef OrderBookQueryResult c_get_quote_volume_for_price(self, bint is_buy, double price):
        cdef:
            double cumulative_volume = 0
            double result_price = NaN

        if is_buy:
            for order_book_row in self.ask_entries():
                if order_book_row.price > price:
                    break
                cumulative_volume += order_book_row.amount * order_book_row.price
                result_price = order_book_row.price
        else:
            for order_book_row in self.bid_entries():
                if order_book_row.price < price:
                    break
                cumulative_volume += order_book_row.amount * order_book_row.price
                result_price = order_book_row.price

        return OrderBookQueryResult(price, NaN, result_price, cumulative_volume)

    def get_price_for_volume(self, is_buy: bool, volume: float) -> OrderBookQueryResult:
        return self.c_get_price_for_volume(is_buy, volume)

    def get_vwap_for_volume(self, is_buy: bool, volume: float) -> OrderBookQueryResult:
        return self.c_get_vwap_for_volume(is_buy, volume)

    def get_price_for_quote_volume(self, is_buy: bool, quote_volume: float) -> OrderBookQueryResult:
        return self.c_get_price_for_quote_volume(is_buy, quote_volume)

    def get_quote_volume_for_base_amount(self, is_buy: bool, base_amount: float) -> OrderBookQueryResult:
        return self.c_get_quote_volume_for_base_amount(is_buy, base_amount)

    def get_volume_for_price(self, bint is_buy, double price) -> OrderBookQueryResult:
        return self.c_get_volume_for_price(is_buy, price)

    def get_quote_volume_for_price(self, is_buy: bool, price: float) -> OrderBookQueryResult:
        return self.c_get_quote_volume_for_price(is_buy, price)

    def restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        replay_position = bisect.bisect_right(diffs, snapshot)
        replay_diffs = diffs[replay_position:]
        self.apply_snapshot(snapshot.bids, snapshot.asks, snapshot.update_id)
        for diff in replay_diffs:
            self.apply_diffs(diff.bids, diff.asks, diff.update_id)
