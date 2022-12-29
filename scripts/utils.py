import math
from array import array
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Union

import numpy as np

from hummingbot.connector.gateway.clob.clob_types import OrderSide

vwap_threshold = 50
int_zero = int(0)
decimal_zero = Decimal(0)
alignment_column = 11


class MidPriceStrategy(Enum):
    SIMPLE_AVERAGE = 'SIMPLE_AVERAGE'
    WEIGHTED_AVERAGE = 'WEIGHTED_AVERAGE'
    VWAP = 'VOLUME_WEIGHTED_AVERAGE_PRICE'


def parse_order_book(orderbook: Dict[str, Any]) -> List[Union[List[Dict[str, Any]], List[Dict[str, Any]], Decimal, Decimal]]:
    bids_list = []
    asks_list = []

    bids: [str, Any] = orderbook["bids"]
    asks: [str, Any] = orderbook["asks"]
    top_ask = Decimal(orderbook["topAsk"])
    top_bid = Decimal(orderbook["topBid"])

    for bid in bids:
        if isinstance(bid["TakerGets"], str):
            bids_list.append({'price': pow(Decimal(bid["quality"]), -1) * 1000000, 'amount': Decimal(bid["TakerGets"])})
        else:
            bids_list.append({'price': pow(Decimal(bid["quality"]), -1), 'amount': Decimal(bid["TakerGets"]["value"])})

    for ask in asks:
        if isinstance(ask["TakerGets"], str):
            asks_list.append({'price': Decimal(ask["quality"]) * 1000000, 'amount': Decimal(ask["TakerGets"])})
        else:
            asks_list.append({'price': Decimal(ask["quality"]), 'amount': Decimal(ask["TakerGets"]["value"])})

    bids_list.sort(key=lambda x: x['price'], reverse=True)
    asks_list.sort(key=lambda x: x['price'], reverse=False)

    return [bids_list, asks_list, top_ask, top_bid]


def split_percentage(bids: [Dict[str, Any]], asks: [Dict[str, Any]]) -> List[Any]:
    asks = asks[:math.ceil((vwap_threshold / 100) * len(asks))]
    bids = bids[:math.ceil((vwap_threshold / 100) * len(bids))]

    return [bids, asks]


def compute_vwap(book: [Dict[str, Any]]) -> np.array:
    prices = [order['price'] for order in book]
    amounts = [order['amount'] for order in book]

    prices = np.array(prices)
    amounts = np.array(amounts)

    vwap = (np.cumsum(amounts * prices) / np.cumsum(amounts))

    return vwap


def remove_outliers(order_book: [Dict[str, Any]], side: OrderSide) -> [Dict[str, Any]]:
    prices = [order['price'] for order in order_book]

    q75, q25 = np.percentile(prices, [75, 25])

    # https://www.askpython.com/python/examples/detection-removal-outliers-in-python
    # intr_qr = q75-q25
    # max_threshold = q75+(1.5*intr_qr)
    # min_threshold = q75-(1.5*intr_qr) # Error: Sometimes this function assigns negative value for min

    max_threshold = q75 * 1.5
    min_threshold = q25 * 0.5

    orders = []
    if side == OrderSide.SELL:
        orders = [order for order in order_book if order['price'] < max_threshold]
    elif side == OrderSide.BUY:
        orders = [order for order in order_book if order['price'] > min_threshold]

    return orders


def calculate_mid_price(bids: [Dict[str, Any]], asks: [Dict[str, Any]], strategy: MidPriceStrategy) -> Decimal:
    if strategy == MidPriceStrategy.SIMPLE_AVERAGE:
        bid_prices = [item['price'] for item in bids]
        ask_prices = [item['price'] for item in asks]

        best_bid_price = max(bid_prices)
        best_ask_price = min(ask_prices)

        return Decimal((best_ask_price + best_bid_price) / 2.0)
    elif strategy == MidPriceStrategy.WEIGHTED_AVERAGE:
        ask_prices = [item['price'] for item in asks]
        bid_prices = [item['price'] for item in bids]

        best_bid_idx = bid_prices.index(max(bid_prices))
        best_ask_idx = ask_prices.index(min(ask_prices))

        best_bid_price = bids[best_bid_idx]['price']
        best_bid_amount = bids[best_bid_idx]['amount']

        best_ask_price = asks[best_ask_idx]['price']
        best_ask_volume = asks[best_ask_idx]['amount']

        return Decimal((best_ask_price * best_ask_volume + best_bid_price * best_bid_amount) / (best_ask_volume + best_bid_amount))
    elif strategy == MidPriceStrategy.VWAP:
        bids, asks = split_percentage(bids, asks)

        bids = remove_outliers(bids, OrderSide.BUY)
        asks = remove_outliers(asks, OrderSide.SELL)

        book = [*bids, *asks]

        vwap = compute_vwap(book)

        return Decimal(vwap[-1])
    else:
        raise ValueError(f'Unrecognized mid price strategy "{strategy}".')


def format_line(left, right, column=alignment_column):
    right = str(right) if str(right).startswith("-") else f" {str(right)}"

    return f"""{left}{" " * (column - len(left))}{right}"""


def format_currency(target: Decimal, precision: int) -> str:
    return ("{:0,." + str(precision) + "f}").format(round(target, precision))


def format_percentage(target: Decimal, precision: int = 2) -> str:
    decimal_near_zero = Decimal("0E-2")

    value = round(target, precision)
    if math.isclose(value, decimal_zero, rel_tol=decimal_near_zero, abs_tol=decimal_near_zero):
        return f"{math.fabs(value)}%"
    elif target < 0:
        return f"{value}% 🔴"
    else:
        return f"{value}% 🟢"


def format_lines(groups: List[List[str]]) -> str:
    lines: array[str] = [""] * len(groups[0])
    for items in groups:
        length = len(max(items, key=lambda i: len(i)))

        for index, item in enumerate(items):
            lines[index] += f"""{" " * (length - len(item))}{item} """

    for line in range(len(lines)):
        lines[line] = f"""{lines[line].rstrip(" ")}"""

    return "\n".join(lines)
