from typing import (
    List)
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingbot.strategy.market_symbol_pair import MarketSymbolPair
from hummingbot.core.time_iterator cimport TimeIterator
from hummingbot.market.market_base cimport MarketBase
import pandas as pd
from hummingbot.core.data_type.trade import Trade
from hummingbot.core.event.events import OrderFilledEvent


cdef class StrategyBase(TimeIterator):
    def __init__(self):
        super().__init__()

    @property
    def active_markets(self) -> List[MarketBase]:
        raise NotImplementedError

    def format_status(self):
        raise NotImplementedError

    def stop(self):
        pass

    @property
    def trades(self) -> List[Trade]:
        def event_to_trade(order_filled_event: OrderFilledEvent, market_name: str):
            return Trade(order_filled_event.symbol,
                         order_filled_event.trade_type,
                         order_filled_event.price,
                         order_filled_event.amount,
                         order_filled_event.order_type,
                         market_name,
                         order_filled_event.timestamp)

        past_trades = []
        for market in self.active_markets:
            event_logs = market.event_logs
            order_filled_events = list(filter(lambda e: isinstance(e, OrderFilledEvent), event_logs))
            past_trades += list(map(lambda ofe: event_to_trade(ofe, market.__class__.__name__), order_filled_events))

        return sorted(past_trades, key=lambda x: x.timestamp)

    def market_status_data_frame(self, market_symbol_pairs: List[MarketSymbolPair]) -> pd.DataFrame:
        cdef:
            MarketBase market
            double market_1_ask_price
            str trading_pair
            str base_asset
            str quote_asset
            double bid_price
            double ask_price
            double bid_price_adjusted
            double ask_price_adjusted
            list markets_data = []
            list markets_columns = ["Market", "Symbol", "Bid Price", "Ask Price", "Adjusted Bid", "Adjusted Ask"]
        try:
            for market_symbol_pair in market_symbol_pairs:
                market, trading_pair, base_asset, quote_asset = market_symbol_pair
                order_book = market.get_order_book(trading_pair)
                bid_price = order_book.get_price(False)
                ask_price = order_book.get_price(True)
                bid_price_adjusted = ExchangeRateConversion.get_instance().adjust_token_rate(quote_asset, bid_price)
                ask_price_adjusted = ExchangeRateConversion.get_instance().adjust_token_rate(quote_asset, ask_price)
                markets_data.append([
                    market.name,
                    trading_pair,
                    bid_price,
                    ask_price,
                    bid_price_adjusted,
                    ask_price_adjusted
                ])
            return pd.DataFrame(data=markets_data, columns=markets_columns)

        except Exception:
            self.logger().error("Error formatting market stats.", exc_info=True)

    def wallet_balance_data_frame(self, market_symbol_pairs: List[MarketSymbolPair]) -> pd.DataFrame:
        cdef:
            MarketBase market
            str base_asset
            str quote_asset
            double base_balance
            double quote_balance
            double base_asset_conversion_rate
            double quote_asset_conversion_rate
            list assets_data = []
            list assets_columns = ["Market", "Asset", "Balance", "Conversion Rate"]
        try:
            for market_symbol_pair in market_symbol_pairs:
                market, trading_pair, base_asset, quote_asset = market_symbol_pair
                base_balance = market.get_balance(base_asset)
                quote_balance = market.get_balance(quote_asset)
                base_asset_conversion_rate = ExchangeRateConversion.get_instance().adjust_token_rate(base_asset, 1.0)
                quote_asset_conversion_rate = ExchangeRateConversion.get_instance().adjust_token_rate(quote_asset, 1.0)
                assets_data.extend([
                    [market.name, base_asset, base_balance, base_asset_conversion_rate],
                    [market.name, quote_asset, quote_balance, quote_asset_conversion_rate]
                ])

            return pd.DataFrame(data=assets_data, columns=assets_columns)

        except Exception:
            self.logger().error("Error formatting wallet balance stats.", exc_info=True)

    def balance_warning(self, market_symbol_pairs: List[MarketSymbolPair]) -> List[str]:
        cdef:
            double base_balance
            double quote_balance
            list warning_lines = []
        # Add warning lines on null balances.
        # TO-DO: $Use min order size logic to replace the hard-coded 0.0001 value for each asset.
        for market_symbol_pair in market_symbol_pairs:
            base_balance = market_symbol_pair.market.get_balance(market_symbol_pair.base_asset)
            quote_balance = market_symbol_pair.market.get_balance(market_symbol_pair.quote_asset)
            if base_balance <= 0.0001:
                warning_lines.append(f"  {market_symbol_pair.market.name} market "
                                     f"{market_symbol_pair.base_asset} balance is too low. Cannot place order.")
            if quote_balance <= 0.0001:
                warning_lines.append(f"  {market_symbol_pair.market.name} market "
                                     f"{market_symbol_pair.quote_asset} balance is too low. Cannot place order.")
        return warning_lines