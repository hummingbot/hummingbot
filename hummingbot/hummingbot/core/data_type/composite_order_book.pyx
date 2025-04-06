# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

from typing import Iterator

from cython.operator cimport address as ref, dereference as deref, postincrement as inc
from hummingbot.core.data_type.OrderBookEntry cimport OrderBookEntry
from libcpp.set cimport set
from libcpp.vector cimport vector

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_row import OrderBookRow

cdef class CompositeOrderBook(OrderBook):
    """
    Record orders that are bought during back testing and used to simulate order book consumption without modifying
    the actual order book.
    Override the order book bid_entries, ask_entries methods to return the composite order book entries
    """
    def __init__(self, order_book: OrderBook = None):
        super().__init__()
        self._traded_order_book = OrderBook()

    @property
    def traded_order_book(self) -> OrderBook:
        return self._traded_order_book

    def clear_traded_order_book(self):
        self._traded_order_book._bid_book.clear()
        self._traded_order_book._ask_book.clear()

    def record_filled_order(self, order_fill_event):
        cdef:
            vector[OrderBookEntry] cpp_bids
            vector[OrderBookEntry] cpp_asks
            set[OrderBookEntry].reverse_iterator bid_order_it = self._traded_order_book._bid_book.rbegin()
            set[OrderBookEntry].iterator ask_order_it = self._traded_order_book._ask_book.begin()
            OrderBookEntry entry

        price = order_fill_event.price
        amount = float(order_fill_event.amount)
        timestamp = order_fill_event.timestamp

        if order_fill_event.trade_type is TradeType.BUY:
            while ask_order_it != self._traded_order_book._ask_book.end():
                entry = deref(ask_order_it)
                # price is in the order book, sum the amount
                if entry.getPrice() == price:
                    amount += entry.getAmount()
                    break
                # price is outside of the ask price range, break and insert the new filled ask order into the ask book
                elif entry.getPrice() > price:
                    break
                # price is further up the ask price range, continue searching
                elif entry.getPrice() < price:
                    inc(ask_order_it)
            cpp_asks.push_back(OrderBookEntry(price, amount, timestamp))

        elif order_fill_event.trade_type is TradeType.SELL:
            while bid_order_it != self._traded_order_book._bid_book.rend():
                entry = deref(bid_order_it)
                if entry.getPrice() == price:
                    amount += entry.getAmount()
                    break
                # price is further down the bid price range, continue searching
                elif entry.getPrice() > price:
                    inc(bid_order_it)
                # price is outside of the bid price range, break and insert the new filled order into the bid book
                elif entry.getPrice() < price:
                    break
            cpp_bids.push_back(OrderBookEntry(price, amount, timestamp))

        self._traded_order_book.c_apply_diffs(cpp_bids, cpp_asks, timestamp)

    def original_bid_entries(self) -> Iterator[OrderBookRow]:
        return super().bid_entries()

    def original_ask_entries(self) -> Iterator[OrderBookRow]:
        return super().ask_entries()

    def bid_entries(self) -> Iterator[OrderBookRow]:
        cdef:
            set[OrderBookEntry].reverse_iterator order_it = self._bid_book.rbegin()
            set[OrderBookEntry].reverse_iterator traded_order_it = self._traded_order_book._bid_book.rbegin()
            OrderBookEntry traded_order_entry
            OrderBookEntry original_order_entry
            vector[OrderBookEntry] cpp_asks_changes
            vector[OrderBookEntry] cpp_bids_changes

        while order_it != self._bid_book.rend():
            original_order_entry = deref(order_it)
            original_order_price = original_order_entry.getPrice()
            original_order_amount = original_order_entry.getAmount()
            original_order_update_id = original_order_entry.getUpdateId()

            while traded_order_it != self._traded_order_book._bid_book.rend():
                traded_order_entry = deref(traded_order_it)
                traded_order_price = traded_order_entry.getPrice()
                traded_order_amount = traded_order_entry.getAmount()
                traded_order_update_id = traded_order_entry.getUpdateId()

                # Found matching price for the recorded filled order, return composite order book row
                if traded_order_price == original_order_price:
                    composite_amount = original_order_amount - traded_order_amount
                    if composite_amount > 0:
                        yield OrderBookRow(original_order_price, composite_amount, original_order_update_id)
                    else:
                        cpp_bids_changes.push_back(OrderBookEntry(original_order_price,
                                                                  min(original_order_amount, traded_order_amount),
                                                                  traded_order_update_id))
                    inc(traded_order_it)
                    # continue to next original order book row
                    break
                # Recorded filled order price is outside of the bid price range
                elif traded_order_price > original_order_price:
                    # Remove the recorded entry and increment the pointer
                    cpp_bids_changes.push_back(OrderBookEntry(traded_order_price, 0, traded_order_update_id))
                    inc(traded_order_it)
                # Recorded filled order price is within lower end of the bid price range, yield original bid entry
                elif traded_order_price < original_order_price:
                    yield OrderBookRow(original_order_price, original_order_amount, original_order_update_id)
                    break
            else:
                yield OrderBookRow(original_order_price, original_order_amount, original_order_update_id)

            inc(order_it)

        self._traded_order_book.c_apply_diffs(cpp_bids_changes, cpp_asks_changes, self._last_diff_uid)

    def ask_entries(self) -> Iterator[OrderBookRow]:
        cdef:
            set[OrderBookEntry].iterator order_it = self._ask_book.begin()
            set[OrderBookEntry].iterator traded_order_it = self._traded_order_book._ask_book.begin()
            OrderBookEntry original_order_entry
            OrderBookEntry traded_order_entry
            vector[OrderBookEntry] cpp_asks_changes
            vector[OrderBookEntry] cpp_bids_changes

        while order_it != self._ask_book.end():
            original_order_entry = deref(order_it)
            original_order_price = original_order_entry.getPrice()
            original_order_amount = original_order_entry.getAmount()
            original_order_update_id = original_order_entry.getUpdateId()

            while traded_order_it != self._traded_order_book._ask_book.end():
                traded_order_entry = deref(traded_order_it)
                traded_order_price = traded_order_entry.getPrice()
                traded_order_amount = traded_order_entry.getAmount()
                traded_order_update_id = traded_order_entry.getUpdateId()

                if traded_order_price == original_order_price:
                    composite_amount = original_order_amount - traded_order_amount
                    if composite_amount > 0:
                        yield OrderBookRow(original_order_price, composite_amount, original_order_update_id)
                    else:
                        cpp_asks_changes.push_back(OrderBookEntry(original_order_price,
                                                                  min(original_order_amount, traded_order_amount),
                                                                  traded_order_update_id))
                    inc(traded_order_it)
                    # continue to next original order book row
                    break
                # Recorded filled order price is within upper end of the ask price range, yield original ask entry
                elif traded_order_price > original_order_price:
                    yield OrderBookRow(original_order_price, original_order_amount, original_order_update_id)
                    break
                # Recorded filled order price is outside of the ask price range, remove the recorded ask order
                elif traded_order_price < original_order_price:
                    cpp_asks_changes.push_back(OrderBookEntry(traded_order_price, 0, traded_order_update_id))
                    inc(traded_order_it)

            else:
                yield OrderBookRow(original_order_price, original_order_amount, original_order_update_id)

            inc(order_it)

        self._traded_order_book.c_apply_diffs(cpp_bids_changes, cpp_asks_changes, self._last_diff_uid)

    cdef double c_get_price(self, bint is_buy) except? -1:
        cdef:
            set[OrderBookEntry] *book = ref(self._ask_book) if is_buy else ref(self._bid_book)
        if deref(book).size() < 1:
            raise EnvironmentError("Order book is empty - no price quote is possible.")

        ask_it = self.ask_entries()
        bid_it = self.bid_entries()
        try:
            if is_buy:
                best_ask = next(ask_it)
                return best_ask.price
            else:
                best_bid = next(bid_it)
                return best_bid.price
        except Exception:
            raise
