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


@dataclass(frozen=True)
class InjectiveSpotMarket:
    market_id: str
    base_token: InjectiveToken
    quote_token: InjectiveToken
    market_info: Dict[str, Any]

    def trading_pair(self):
        return combine_to_hb_trading_pair(self.base_token.unique_symbol, self.quote_token.unique_symbol)

    def quantity_from_chain_format(self, chain_quantity: Decimal) -> Decimal:
        scaler = Decimal(f"1e{-self.base_token.decimals}")
        return chain_quantity * scaler

    def price_from_chain_format(self, chain_price: Decimal) -> Decimal:
        scaler = Decimal(f"1e{self.base_token.decimals-self.quote_token.decimals}")
        return chain_price * scaler
