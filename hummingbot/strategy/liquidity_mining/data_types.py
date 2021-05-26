#!/usr/bin/env python

"""
Liquidity mining data types...
"""

from decimal import Decimal


class PriceSize:
    """
    What is this? price of asset and amount of asset to sell?
    """
    def __init__(self, price: Decimal, size: Decimal):
        self.price: Decimal = price
        self.size: Decimal = size

    def __repr__(self):
        return f"[ p: {self.price} s: {self.size} ]"


class Proposal:
    """
    What is this? name of the market, PriceSize for sale, PriceSize for buy
    """
    def __init__(self, market: str, buy: PriceSize, sell: PriceSize):
        self.market: str = market
        self.buy: PriceSize = buy
        self.sell: PriceSize = sell

    def __repr__(self):
        return f"{self.market} buy: {self.buy} sell: {self.sell}"

    def base(self):
        return self.market.split("-")[0]

    def quote(self):
        return self.market.split("-")[1]
