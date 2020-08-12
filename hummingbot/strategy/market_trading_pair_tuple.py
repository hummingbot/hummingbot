from decimal import Decimal
from typing import (
    NamedTuple, Iterator
)
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_query_result import ClientOrderBookQueryResult
from hummingbot.core.data_type.order_book_row import ClientOrderBookRow
from hummingbot.market.market_base import MarketBase
from hummingbot.core.event.events import PriceType


class MarketTradingPairTuple(NamedTuple):
    market: MarketBase
    trading_pair: str
    base_asset: str
    quote_asset: str

    def __repr__(self) -> str:
        return f"MarketTradingPairTuple({self.market.name}, {self.trading_pair}, {self.base_asset}, {self.quote_asset})"

    @property
    def order_book(self) -> OrderBook:
        return self.market.get_order_book(self.trading_pair)

    @property
    def quote_balance(self) -> Decimal:
        return self.market.get_balance(self.quote_asset)

    @property
    def base_balance(self) -> Decimal:
        return self.market.get_balance(self.base_asset)

    def get_mid_price(self) -> Decimal:
        return self.market.get_mid_price(self.trading_pair)

    def get_price(self, is_buy: bool) -> Decimal:
        return self.market.get_price(self.trading_pair, is_buy)

    def get_price_by_type(self, price_type: PriceType) -> Decimal:
        if price_type is PriceType.BestBid:
            return self.get_price(False)
        elif price_type is PriceType.BestAsk:
            return self.get_price(True)
        elif price_type is PriceType.MidPrice:
            return self.get_mid_price()
        elif price_type is PriceType.LastTrade:
            return self.market.get_order_book(self.trading_pair).last_trade_price

    def get_vwap_for_volume(self, is_buy: bool, volume: Decimal) -> ClientOrderBookQueryResult:
        return self.market.get_vwap_for_volume(self.trading_pair, is_buy, volume)

    def get_price_for_volume(self, is_buy: bool, volume: Decimal) -> ClientOrderBookQueryResult:
        return self.market.get_price_for_volume(self.trading_pair, is_buy, volume)

    def order_book_bid_entries(self) -> Iterator[ClientOrderBookRow]:
        return self.market.order_book_bid_entries(self.trading_pair)

    def order_book_ask_entries(self) -> Iterator[ClientOrderBookRow]:
        return self.market.order_book_ask_entries(self.trading_pair)
