from dataclasses import dataclass
from decimal import Decimal

from pyinjective.core.market import DerivativeMarket, SpotMarket
from pyinjective.core.token import Token

from hummingbot.connector.utils import combine_to_hb_trading_pair


@dataclass(frozen=True)
class InjectiveToken:
    unique_symbol: str
    native_token: Token

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
        scaler = Decimal(f"1e{-self.decimals}")
        return chain_value * scaler

    def value_from_special_chain_format(self, chain_value: Decimal) -> Decimal:
        scaler = Decimal(f"1e{-self.decimals-18}")
        return chain_value * scaler


@dataclass(frozen=True)
class InjectiveSpotMarket:
    market_id: str
    base_token: InjectiveToken
    quote_token: InjectiveToken
    native_market: SpotMarket

    def trading_pair(self):
        return combine_to_hb_trading_pair(self.base_token.unique_symbol, self.quote_token.unique_symbol)

    def quantity_from_chain_format(self, chain_quantity: Decimal) -> Decimal:
        return self.base_token.value_from_chain_format(chain_value=chain_quantity)

    def price_from_chain_format(self, chain_price: Decimal) -> Decimal:
        scaler = Decimal(f"1e{self.base_token.decimals-self.quote_token.decimals}")
        return chain_price * scaler

    def quantity_from_special_chain_format(self, chain_quantity: Decimal) -> Decimal:
        quantity = chain_quantity / Decimal("1e18")
        return self.quantity_from_chain_format(chain_quantity=quantity)

    def price_from_special_chain_format(self, chain_price: Decimal) -> Decimal:
        price = chain_price / Decimal("1e18")
        return self.price_from_chain_format(chain_price=price)

    def min_price_tick_size(self) -> Decimal:
        return self.price_from_chain_format(chain_price=self.native_market.min_price_tick_size)

    def min_quantity_tick_size(self) -> Decimal:
        return self.quantity_from_chain_format(chain_quantity=self.native_market.min_quantity_tick_size)

    def maker_fee_rate(self) -> Decimal:
        return self.native_market.maker_fee_rate

    def taker_fee_rate(self) -> Decimal:
        return self.native_market.taker_fee_rate

    def min_notional(self) -> Decimal:
        return self.quote_token.value_from_chain_format(chain_value=self.native_market.min_notional)


@dataclass(frozen=True)
class InjectiveDerivativeMarket:
    market_id: str
    quote_token: InjectiveToken
    native_market: DerivativeMarket

    def base_token_symbol(self):
        ticker_base, _ = self.native_market.ticker.split("/") if "/" in self.native_market.ticker else (self.native_market.ticker, 0)
        return ticker_base

    def trading_pair(self):
        ticker_base, _ = self.native_market.ticker.split("/") if "/" in self.native_market.ticker else (self.native_market.ticker, 0)
        return combine_to_hb_trading_pair(ticker_base, self.quote_token.unique_symbol)

    def quantity_from_chain_format(self, chain_quantity: Decimal) -> Decimal:
        return chain_quantity

    def price_from_chain_format(self, chain_price: Decimal) -> Decimal:
        scaler = Decimal(f"1e{-self.quote_token.decimals}")
        return chain_price * scaler

    def quantity_from_special_chain_format(self, chain_quantity: Decimal) -> Decimal:
        quantity = chain_quantity / Decimal("1e18")
        return self.quantity_from_chain_format(chain_quantity=quantity)

    def price_from_special_chain_format(self, chain_price: Decimal) -> Decimal:
        price = chain_price / Decimal("1e18")
        return self.price_from_chain_format(chain_price=price)

    def min_price_tick_size(self) -> Decimal:
        return self.price_from_chain_format(chain_price=self.native_market.min_price_tick_size)

    def min_quantity_tick_size(self) -> Decimal:
        return self.quantity_from_chain_format(chain_quantity=self.native_market.min_quantity_tick_size)

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
        return self.quote_token.value_from_chain_format(chain_value=self.native_market.min_notional)
