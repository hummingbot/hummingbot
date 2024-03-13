from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


@dataclass
class Asset:
    id: str
    name: str
    symbol: str
    hb_name: str
    quantum: Decimal


@dataclass
class Market:
    id: str
    name: str
    symbol: str
    status: str
    hb_trading_pair: str
    hb_base_name: str
    # address: str
    base_name: str
    hb_base_name: str
    quote_name: str
    quote_asset_id: str
    hb_quote_name: str
    funding_fee_interval: Optional[int]
    quote: Asset
    linear_slippage_factor: Optional[Decimal]
    min_order_size: Decimal
    min_price_increment: Decimal
    min_base_amount_increment: Decimal
    max_price_significant_digits: Decimal
    buy_collateral_token: Asset
    sell_collateral_token: Asset
    min_notional: Decimal
    maker_fee: Decimal
    liquidity_fee: Decimal
    infrastructure_fee: Decimal
    price_quantum: Decimal
    quantity_quantum: Decimal

    def __init__(self):
        self.id = ""


class VegaTimeInForce(Enum):
    TIME_IN_FORCE_UNSPECIFIED = 0
    TIME_IN_FORCE_GTC = 1
    TIME_IN_FORCE_GTT = 2
    TIME_IN_FORCE_IOC = 3
    TIME_IN_FORCE_FOK = 4
    TIME_IN_FORCE_GFA = 5
    TIME_IN_FORCE_GFN = 6


@dataclass
class TransactionData:
    transaction_hash: str
    submitted_order_id: Optional[str]
    reference: Optional[str]
    market_id: Optional[str]
    error_message: Optional[str]
    transaction_type: Optional[str]
    error_code: int
