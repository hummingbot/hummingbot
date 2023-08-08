from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict

from hummingbot.connector.utils import combine_to_hb_trading_pair


@dataclass(frozen=True)
class InjectiveToken:
    denom: str
    symbol: str
    unique_symbol: str
    name: str
    decimals: int

    def value_from_chain_format(self, chain_value: Decimal) -> Decimal:
        scaler = Decimal(f"1e{-self.decimals}")
        return chain_value * scaler


@dataclass(frozen=True)
class InjectiveSpotMarket:
    market_id: str
    base_token: InjectiveToken
    quote_token: InjectiveToken
    market_info: Dict[str, Any]

    def trading_pair(self):
        return combine_to_hb_trading_pair(self.base_token.unique_symbol, self.quote_token.unique_symbol)

    def quantity_from_chain_format(self, chain_quantity: Decimal) -> Decimal:
        return self.base_token.value_from_chain_format(chain_value=chain_quantity)

    def price_from_chain_format(self, chain_price: Decimal) -> Decimal:
        scaler = Decimal(f"1e{self.base_token.decimals-self.quote_token.decimals}")
        return chain_price * scaler

    def min_price_tick_size(self) -> Decimal:
        min_price_tick_size = Decimal(self.market_info["minPriceTickSize"])
        return self.price_from_chain_format(chain_price=min_price_tick_size)

    def min_quantity_tick_size(self) -> Decimal:
        min_quantity_tick_size = Decimal(self.market_info["minQuantityTickSize"])
        return self.quantity_from_chain_format(chain_quantity=min_quantity_tick_size)

    def maker_fee_rate(self) -> Decimal:
        return Decimal(self.market_info["makerFeeRate"])

    def taker_fee_rate(self) -> Decimal:
        return Decimal(self.market_info["takerFeeRate"])
