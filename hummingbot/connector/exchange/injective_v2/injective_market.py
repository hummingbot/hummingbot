from dataclasses import dataclass
from decimal import Decimal

from pyinjective.core.market_v2 import DerivativeMarket, SpotMarket
from pyinjective.core.token import Token

from hummingbot.connector.utils import combine_to_hb_trading_pair


@dataclass(frozen=True)
class InjectiveToken:
    unique_symbol: str
    native_token: Token

    @staticmethod
    def convert_value_to_extended_decimal_format(value: Decimal) -> Decimal:
        return Token.convert_value_to_extended_decimal_format(value=value)

    @staticmethod
    def convert_value_from_extended_decimal_format(value: Decimal) -> Decimal:
        return Token.convert_value_from_extended_decimal_format(value=value)

    @property
    def denom(self) -> str:
        return self.native_token.denom

    @property
    def symbol(self) -> str:
        return self.native_token.symbol

    @property
    def name(self) -> str:
        return self.native_token.name

    @property
    def decimals(self) -> int:
        return self.native_token.decimals

    def value_from_chain_format(self, chain_value: Decimal) -> Decimal:
        return self.native_token.human_readable_value(chain_formatted_value=chain_value)

    def value_from_special_chain_format(self, chain_value: Decimal) -> Decimal:
        real_chain_value = self.convert_value_from_extended_decimal_format(value=chain_value)
        return self.value_from_chain_format(chain_value=real_chain_value)


@dataclass(frozen=True)
class InjectiveSpotMarket:
    market_id: str
    base_token: InjectiveToken
    quote_token: InjectiveToken
    native_market: SpotMarket

    def trading_pair(self):
        base_token_symbol = self.base_token.unique_symbol.replace("-", "_")
        quote_token_symbol = self.quote_token.unique_symbol.replace("-", "_")
        return combine_to_hb_trading_pair(base_token_symbol, quote_token_symbol)

    def quantity_from_chain_format(self, chain_quantity: Decimal) -> Decimal:
        return self.native_market.quantity_from_chain_format(chain_value=chain_quantity)

    def price_from_chain_format(self, chain_price: Decimal) -> Decimal:
        return self.native_market.price_from_chain_format(chain_value=chain_price)

    def quantity_to_chain_format(self, human_readable_quantity: Decimal) -> Decimal:
        return self.native_market.quantity_to_chain_format(human_readable_value=human_readable_quantity)

    def price_to_chain_format(self, human_readable_price: Decimal) -> Decimal:
        return self.native_market.price_to_chain_format(human_readable_value=human_readable_price)

    def quantity_from_special_chain_format(self, chain_quantity: Decimal) -> Decimal:
        return self.native_market.quantity_from_extended_chain_format(chain_value=chain_quantity)

    def price_from_special_chain_format(self, chain_price: Decimal) -> Decimal:
        return self.native_market.price_from_extended_chain_format(chain_value=chain_price)

    def min_price_tick_size(self) -> Decimal:
        return self.native_market.min_price_tick_size

    def min_quantity_tick_size(self) -> Decimal:
        return self.native_market.min_quantity_tick_size

    def maker_fee_rate(self) -> Decimal:
        return self.native_market.maker_fee_rate

    def taker_fee_rate(self) -> Decimal:
        return self.native_market.taker_fee_rate

    def min_notional(self) -> Decimal:
        return self.native_market.min_notional


@dataclass(frozen=True)
class InjectiveDerivativeMarket:
    market_id: str
    quote_token: InjectiveToken
    native_market: DerivativeMarket

    def base_token_symbol(self):
        ticker_base, _ = self.native_market.ticker.split("/") if "/" in self.native_market.ticker else (self.native_market.ticker, "")
        return ticker_base

    def trading_pair(self):
        base_token_symbol = self.base_token_symbol().replace("-", "_")
        quote_token_symbol = self.quote_token.unique_symbol.replace("-", "_")
        return combine_to_hb_trading_pair(base_token_symbol, quote_token_symbol)

    def quantity_from_chain_format(self, chain_quantity: Decimal) -> Decimal:
        return self.native_market.quantity_from_chain_format(chain_value=chain_quantity)

    def price_from_chain_format(self, chain_price: Decimal) -> Decimal:
        return self.native_market.price_from_chain_format(chain_value=chain_price)

    def quantity_to_chain_format(self, human_readable_quantity: Decimal) -> Decimal:
        return self.native_market.quantity_to_chain_format(human_readable_value=human_readable_quantity)

    def price_to_chain_format(self, human_readable_price: Decimal) -> Decimal:
        return self.native_market.price_to_chain_format(human_readable_value=human_readable_price)

    def quantity_from_special_chain_format(self, chain_quantity: Decimal) -> Decimal:
        return self.native_market.quantity_from_extended_chain_format(chain_value=chain_quantity)

    def price_from_special_chain_format(self, chain_price: Decimal) -> Decimal:
        return self.native_market.price_from_extended_chain_format(chain_value=chain_price)

    def min_price_tick_size(self) -> Decimal:
        return self.native_market.min_price_tick_size

    def min_quantity_tick_size(self) -> Decimal:
        return self.native_market.min_quantity_tick_size

    def maker_fee_rate(self) -> Decimal:
        return self.native_market.maker_fee_rate

    def taker_fee_rate(self) -> Decimal:
        return self.native_market.taker_fee_rate

    def oracle_base(self) -> str:
        return self.native_market.oracle_base

    def oracle_quote(self) -> str:
        return self.native_market.oracle_quote

    def oracle_type(self) -> str:
        return self.native_market.oracle_type

    def min_notional(self) -> Decimal:
        return self.native_market.min_notional
