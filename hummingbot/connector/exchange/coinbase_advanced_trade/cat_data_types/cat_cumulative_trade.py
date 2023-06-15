from decimal import Decimal
from typing import NamedTuple


class CoinbaseAdvancedTradeCumulativeUpdate(NamedTuple):
    client_order_id: str
    exchange_order_id: str
    status: str
    trading_pair: str
    fill_timestamp: float  # seconds
    average_price: Decimal
    cumulative_base_amount: Decimal
    remainder_base_amount: Decimal
    cumulative_fee: Decimal
    is_taker: bool = False  # Coinbase Advanced Trade delivers trade events from the maker's perspective
