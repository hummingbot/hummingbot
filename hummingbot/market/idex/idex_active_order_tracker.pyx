# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

from cachetools import TTLCache
from decimal import Decimal
import heapq
import logging
import numpy as np
import pandas as pd
from typing import (
    Any,
    Dict,
    List
)
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_row import OrderBookRow

s_empty_diff = np.ndarray(shape=(0, 4), dtype="float64")
s_decimal_zero = Decimal(0)
s_decimal_neg_one = Decimal(-1)
_idaot_logger = None


cdef class IDEXActiveOrderTracker:
    def __init__(self, active_asks=None, active_bids=None, base_asset=None, quote_asset=None, order_hash_price_map=None):
        super().__init__()
        self._active_asks = active_asks or {}
        self._active_bids = active_bids or {}
        self._base_asset = base_asset or {}
        self._quote_asset = quote_asset or {}
        self._latest_snapshot_timestamp = 0.0
        self._order_hash_price_map = order_hash_price_map or {}
        self._received_trade_ids: TTLCache = TTLCache(maxsize=1000, ttl=60 * 10)
        self._order_hashes_to_delete = set()
        self._bid_heap = []
        self._ask_heap = []

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _idaot_logger
        if _idaot_logger is None:
            _idaot_logger = logging.getLogger(__name__)
        return _idaot_logger

    @property
    def active_asks(self):
        return self._active_asks

    @property
    def active_bids(self):
        return self._active_bids

    @property
    def base_asset(self):
        return self._base_asset

    @property
    def quote_asset(self):
        return self._quote_asset

    @property
    def ask_heap(self):
        return self._ask_heap

    @property
    def latest_snapshot_timestamp(self):
        return self._latest_snapshot_timestamp

    def volume_for_ask_price(self, price):
        return sum([float(msg["availableAmountBase"]) for msg in self._active_asks[price].values()])

    def volume_for_bid_price(self, price):
        return sum([float(msg["availableAmountBase"]) for msg in self._active_bids[price].values()])
    
    def _is_ask(self, content: Dict[str, Any]):
        return content["tokenBuy"] == self._quote_asset["address"] and content["tokenSell"] == self._base_asset["address"]

    def _is_bid(self, content: Dict[str, Any]):
        return content["tokenBuy"] == self._base_asset["address"] and content["tokenSell"] == self._quote_asset["address"]


    cdef tuple c_convert_diff_message_to_np_arrays(self, object message):
        cdef:
            object content = message.content
            str event = content["event"]
            str order_hash
            int tid
            object amount_base
            object amount_quote
            object price
            double quantity = 0
            dict order_dict

        if event == "market_orders":
            """
            Sample IDEX "market_orders" message
            {
                id: 101010,
                amountBuy: '205795770000',
                amountSell: '1392477916542192014',
                tokenBuy: '0x3db6ba6ab6f95efed1a6e794cad492faaabf294d',
                tokenSell: '0x0000000000000000000000000000000000000000',
                nonce: 101010,
                hash: '0x...',
                user: '0x...',
                createdAt: '1969-01-01T01:01:01.000Z',
                updatedAt: '1969-01-01T01:01:01.000Z',
            }
            """

            order_hash = content["hash"]
            if self._is_bid(content):
                amount_base = Decimal(content["amountBuy"]) / Decimal(f"1e{self._base_asset['decimals']}")
                amount_quote = Decimal(content["amountSell"]) / Decimal(f"1e{self._quote_asset['decimals']}")
                price = amount_quote / amount_base
                # use negative price for _bid_heap to sort by descending (returns highest bid)
                # use negative amount for _bid_heap to sort by descending (minimize number of different orders)
                heapq.heappush(self._bid_heap, (price * s_decimal_neg_one, amount_base * s_decimal_neg_one, order_hash))

                order_dict = {
                    **content,
                    "availableAmountBase": amount_base,
                    "availableAmountQuote": amount_quote,
                    "orderHash": order_hash,
                    "updateTimestamp": message.timestamp,
                    "price": price
                }
                if price in self._active_bids:
                    self._active_bids[price][order_hash] = order_dict
                else:
                    self._active_bids[price] = {
                        order_hash: order_dict
                    }
                self._order_hash_price_map[order_hash] = price
                quantity = self.volume_for_bid_price(price)
                return (
                    np.array([[message.timestamp, float(price), quantity, message.timestamp]], dtype="float64"),
                    s_empty_diff
                )

            elif self._is_ask(content):
                amount_base = Decimal(content["amountSell"]) / Decimal(f"1e{self._base_asset['decimals']}")
                amount_quote = Decimal(content["amountBuy"]) / Decimal(f"1e{self._quote_asset['decimals']}")
                price = amount_quote / amount_base
                # use positive price for _ask_heap to sort by ascending (returns lowest ask)
                # use negative amount for _ask_heap to sort by descending (minimize number of different orders)
                heapq.heappush(self._ask_heap, (price, amount_base * s_decimal_neg_one, order_hash))
                order_dict = {
                    **content,
                    "availableAmountBase": amount_base,
                    "availableAmountQuote": amount_quote,
                    "orderHash": order_hash,
                    "updateTimestamp": message.timestamp,
                    "price": price
                }
                if price in self._active_asks:
                    self._active_asks[price][order_hash] = order_dict
                else:
                    self._active_asks[price] = {
                        order_hash: order_dict
                    }
                quantity = self.volume_for_ask_price(price)
                self._order_hash_price_map[order_hash] = price
                return (
                    s_empty_diff,
                    np.array([[message.timestamp, float(price), quantity, message.timestamp]], dtype="float64")
                )
            else:
                raise ValueError(f"Unknown order side. Aborting.")

        elif event == "market_cancels":
            """
            Sample IDEX "market_cancels" message
            {
                id: 101010,
                orderHash: '0x...',
                createdAt: '1969-01-01T01:01:01.000Z',
            }
            """
            order_hash = content["orderHash"]
            price = self._order_hash_price_map.get(order_hash)
            if price in self._active_bids and order_hash in self._active_bids[price]:
                del self._active_bids[price][order_hash]
                del self._order_hash_price_map[order_hash]
                self._order_hashes_to_delete.add(order_hash)
                if len(self._active_bids[price]) < 1:
                    del self._active_bids[price]
                    return (
                        np.array([[message.timestamp, float(price), 0.0, message.update_id]], dtype="float64"),
                        s_empty_diff
                    )
                quantity = self.volume_for_bid_price(price)
                return (
                    np.array([[message.timestamp, float(price), quantity, message.update_id]], dtype="float64"),
                    s_empty_diff
                )
            if price in self._active_asks and order_hash in self._active_asks[price]:
                del self._active_asks[price][order_hash]
                del self._order_hash_price_map[order_hash]
                self._order_hashes_to_delete.add(order_hash)
                if len(self._active_asks[price]) < 1:
                    del self._active_asks[price]
                    return (
                        s_empty_diff,
                        np.array([[message.timestamp, float(price), 0.0, message.update_id]], dtype="float64")
                    )
                quantity = self.volume_for_ask_price(price)
                return (
                    s_empty_diff,
                    np.array([[message.timestamp, float(price), quantity, message.update_id]], dtype="float64")
                )

            return s_empty_diff, s_empty_diff

        elif event == "market_trades":
            """
            Sample IDEX "market_trades" message
            {
                tid: 101010,
                type: 'buy',
                date: '1969-01-01T01:01:01.000Z',
                timestamp: 1552536625,
                market: 'ETH_LTO',
                usdValue: '411.171696117038254309',
                price: '0.000687600842795718',
                amount: '4557.68612841',
                total: '3.133868823093068736',
                taker: '0x...',
                maker: '0x...',
                orderHash: '0x...',
                gasFee: '1.483418775132356598',
                tokenBuy: '0x0000000000000000000000000000000000000000',
                tokenSell: '0x3db6ba6ab6f95efed1a6e794cad492faaabf294d',
                buyerFee: '4.55768612841',
                sellerFee: '0.002193708176165148',
                amountWei: '3133868823093068736',
                updatedAt: '1969-01-01T01:01:01.000Z',
            }
            """
            # market_trades need to be de-duplicated (should not be counted more than once)
            tid = content["tid"]
            if tid in self._received_trade_ids:
                self.logger().debug(f"Received duplicate IDEX trade message - '{content}'")
                return s_empty_diff, s_empty_diff
            self._received_trade_ids[tid] = True

            order_hash = content["orderHash"]
            price = self._order_hash_price_map.get(order_hash)
            if self._is_bid(content) and price in self._active_bids and order_hash in self._active_bids[price]:
                if self._active_bids[price][order_hash]["updateTimestamp"] > message.timestamp:
                    self.logger().debug(f"Received old IDEX trade message - '{content}'")
                    return s_empty_diff, s_empty_diff
 
                self._active_bids[price][order_hash]["availableAmountBase"] -= Decimal(content["amount"])
                self._active_bids[price][order_hash]["availableAmountQuote"] -= Decimal(content["total"])

                if self._active_bids[price][order_hash]["availableAmountBase"] == s_decimal_zero or \
                    self._active_bids[price][order_hash]["availableAmountQuote"] == s_decimal_zero:
                    del self._active_bids[price][order_hash]
                    del self._order_hash_price_map[order_hash]
                    self._order_hashes_to_delete.add(order_hash)
                    if len(self._active_bids[price]) < 1:
                        del self._active_bids[price]
                        return (
                            np.array([[message.timestamp, float(price), 0.0, message.update_id]], dtype="float64"),
                            s_empty_diff
                        )
                quantity = self.volume_for_bid_price(price)
                return (
                    np.array([[message.timestamp, float(price), quantity, message.update_id]], dtype="float64"),
                    s_empty_diff
                )
            elif self._is_ask(content) and price in self._active_asks and order_hash in self._active_asks[price]:
                if self._active_asks[price][order_hash]["updateTimestamp"] > message.timestamp:
                    self.logger().debug(f"Received old IDEX trade message - '{content}'")
                    return s_empty_diff, s_empty_diff

                self._active_asks[price][order_hash]["availableAmountBase"] -= Decimal(content["amount"])
                self._active_asks[price][order_hash]["availableAmountQuote"] -= Decimal(content["total"])

                if self._active_asks[price][order_hash]["availableAmountBase"] == s_decimal_zero or \
                    self._active_asks[price][order_hash]["availableAmountQuote"] == s_decimal_zero:
                    del self._active_asks[price][order_hash]
                    del self._order_hash_price_map[order_hash]
                    self._order_hashes_to_delete.add(order_hash)
                    if len(self._active_asks[price]) < 1:
                        del self._active_asks[price]
                        return (
                            s_empty_diff,
                            np.array([[message.timestamp, float(price), 0.0, message.update_id]], dtype="float64")
                        )
                quantity = self.volume_for_ask_price(price)
                return (
                    s_empty_diff,
                    np.array([[message.timestamp, float(price), quantity, message.update_id]], dtype="float64")
                )
            self.logger().debug(f"Unable to find matching order in orderbook from trade message - '{content}'")
            return s_empty_diff, s_empty_diff
        else:
            raise ValueError(f"Unrecognized message - '{message}'")
    
    def get_best_limit_orders(self, is_buy: bool, amount: Decimal) -> List[Dict[str, Any]]:
        current_amount = s_decimal_zero
        orders = []
        
        if is_buy:
            ask_heap = self._ask_heap.copy()
            while current_amount < amount:
                if len(ask_heap) == 0:
                    raise ValueError(f"Not enough volume ({current_amount}) to buy {amount} tokens.")
                while True:
                    order_price, order_amount, order_hash = heapq.heappop(ask_heap)
                    if order_hash in self._order_hashes_to_delete:
                        # ignore and delete the order from the original heap
                        # check the next available order
                        heapq.heappop(self._ask_heap)
                        self._order_hashes_to_delete.remove(order_hash)
                    else:
                        break
                current_amount += abs(order_amount)
                orders.append(self._active_asks[order_price][order_hash])
            ask_heap.clear()
        else:
            bid_heap = self._bid_heap.copy()
            while current_amount < amount:
                if len(bid_heap) == 0:
                    raise ValueError(f"Not enough volume ({current_amount}) to sell {amount} tokens.")
                while True:
                    order_price, order_amount, order_hash = heapq.heappop(bid_heap)
                    if order_hash in self._order_hashes_to_delete:
                        # ignore and delete the order from the original heap
                        # check the next available order
                        heapq.heappop(self._bid_heap)
                        self._order_hashes_to_delete.remove(order_hash)
                    else:
                        break
                current_amount += abs(order_amount)
                orders.append(self._active_bids[abs(order_price)][order_hash])
            bid_heap.clear()
        return orders

    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message):
        cdef:
            list orders
            object price
            object amount_base
            object amount_quote
            str order_hash
            dict order_dict
            double order_timestamp

        # Refresh all order tracking.
        self._received_trade_ids.clear()
        self._active_bids.clear()
        self._active_asks.clear()
        self._order_hash_price_map.clear()
        self._order_hashes_to_delete.clear()
        self._bid_heap.clear()
        self._ask_heap.clear()
        self._latest_snapshot_timestamp = 0.0

        orders = message.content.get("orders")
        if orders is None:
            return {}, {}

        for order in orders:
            order_hash = order["hash"]
            order_timestamp = pd.Timestamp(order["updatedAt"]).timestamp()
            if order_timestamp > self._latest_snapshot_timestamp:
                # final snapshot timestamp should be the latest order update received
                self._latest_snapshot_timestamp = order_timestamp

            if self._is_bid(order):
                amount_base = Decimal(order["amountBuy"]) / Decimal(f"1e{self._base_asset['decimals']}")
                amount_quote = Decimal(order["amountSell"]) / Decimal(f"1e{self._quote_asset['decimals']}")
                price = amount_quote / amount_base
                # use negative price for _bid_heap to sort by descending (returns highest bid)
                # use negative amount for _bid_heap to sort by descending (minimize number of different orders)
                heapq.heappush(self._bid_heap, (price * s_decimal_neg_one, amount_base * s_decimal_neg_one, order_hash))

                order_dict = {
                    **order,
                    "availableAmountBase": amount_base,
                    "availableAmountQuote": amount_quote,
                    "orderHash": order_hash,
                    "updateTimestamp": order_timestamp,
                    "price": price
                }
                if price in self._active_bids:
                    self._active_bids[price][order_hash] = order_dict
                else:
                    self._active_bids[price] = {
                        order_hash: order_dict
                    }
                self._order_hash_price_map[order_hash] = price

            elif self._is_ask(order):
                amount_base = Decimal(order["amountSell"]) / Decimal(f"1e{self._base_asset['decimals']}")
                amount_quote = Decimal(order["amountBuy"]) / Decimal(f"1e{self._quote_asset['decimals']}")
                # use positive price for _ask_heap to sort by ascending (returns lowest ask)
                # use negative amount for _ask_heap to sort by descending (minimize number of different orders)
                price = amount_quote / amount_base
                heapq.heappush(self._ask_heap, (price, amount_base * s_decimal_neg_one, order_hash))

                order_dict = {
                    **order,
                    "availableAmountBase": amount_base,
                    "availableAmountQuote": amount_quote,
                    "orderHash": order_hash,
                    "updateTimestamp": order_timestamp,
                    "price": price
                }
                if price in self._active_asks:
                    self._active_asks[price][order_hash] = order_dict
                else:
                    self._active_asks[price] = {
                        order_hash: order_dict
                    }
                self._order_hash_price_map[order_hash] = price

            else:
                self.logger().error(f"Unrecognized token address in order - {order}.")
        # Return the sorted snapshot tables.
        cdef:
            np.ndarray[np.float64_t, ndim=2] bids = np.array(
                [
                    [
                        self._latest_snapshot_timestamp,
                        float(price),
                        self.volume_for_bid_price(price),
                        self._latest_snapshot_timestamp
                    ]
                    for price in sorted(self._active_bids.keys(), reverse=True)
                ],
                dtype="float64",
                ndmin=2
            )
            np.ndarray[np.float64_t, ndim=2] asks = np.array(
                [
                    [
                        self._latest_snapshot_timestamp,
                        float(price),
                        self.volume_for_ask_price(price),
                        self._latest_snapshot_timestamp
                    ]
                    for price in sorted(self._active_asks.keys(), reverse=True)
                ],
                dtype="float64",
                ndmin=2
            )

        # If there're no rows, the shape would become (1, 0) and not (0, 4).
        # Reshape to fix that.
        if bids.shape[1] != 4:
            bids = bids.reshape((0, 4))
        if asks.shape[1] != 4:
            asks = asks.reshape((0, 4))

        return bids, asks

    cdef np.ndarray[np.float64_t, ndim=1] c_convert_trade_message_to_np_array(self, object message):
        cdef:
            double trade_type_value = 1.0 if self._is_ask(message.content) else 2.0

        return np.array([
                message.timestamp,
                trade_type_value,
                float(message.content["price"]),
                float(message.content["amount"])
            ],
            dtype="float64"
        )

    def convert_diff_message_to_order_book_row(self, message):
        np_bids, np_asks = self.c_convert_diff_message_to_np_arrays(message)
        bids_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
        asks_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]
        return bids_row, asks_row

    def convert_snapshot_message_to_order_book_row(self, message):
        np_bids, np_asks = self.c_convert_snapshot_message_to_np_arrays(message)
        bids_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
        asks_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]
        return bids_row, asks_row
