from typing import NamedTuple
from decimal import Decimal


class CeloExchangeRate(NamedTuple):
    from_token: str
    from_amount: Decimal
    to_token: str
    to_amount: Decimal


class CeloArbTradeProfit(NamedTuple):
    is_celo_buy: bool
    ctp_price: Decimal  # Counter party order price, sell if is_celo_buy
    ctp_vwap: Decimal  # Counter party avg price, used to calculate celo buy volume and profit
    celo_price: Decimal  # Celo price, buy if is_celo_buy
    profit: Decimal  # profit in percentage


class CeloOrder(NamedTuple):
    tx_hash: str
    is_buy: bool
    price: Decimal
    amount: Decimal
    timestamp: float
