#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

from decimal import Decimal
import logging; logging.basicConfig(level=logging.ERROR)
import pandas as pd
from typing import List
import unittest

from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import (
    AssetType,
    Market,
    MarketConfig,
    QuantizationParams
)
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    OrderBookTradeEvent,
    TradeType,
    OrderType,
    OrderFilledEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent
)
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.strategy.pure_market_making.pure_market_making_v2 import PureMarketMakingStrategyV2
from hummingbot.strategy.pure_market_making.data_types import MarketInfo


class PureMarketMakingV2UnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    maker_symbols: List[str] = ["COINALPHA-WETH", "COINALPHA", "WETH"]

    def setUp(self):
        self.clock: Clock = Clock(ClockMode.BACKTEST, 60.0, self.start_timestamp, self.end_timestamp)
        self.clock_tick_size = 60
        self.maker_market: BacktestMarket = BacktestMarket()
        self.maker_data: MockOrderBookLoader = MockOrderBookLoader(*self.maker_symbols)
        self.mid_price = 100
        self.bid_threshold = 0.01
        self.ask_threshold = 0.01
        self.cancel_order_wait_time = 45
        self.maker_data.set_balanced_order_book(mid_price=self.mid_price, min_price=1,
                                                max_price=200, price_step_size=1, volume_step_size=10)
        self.maker_market.add_data(self.maker_data)
        self.maker_market.set_balance("COINALPHA", 500)
        self.maker_market.set_balance("WETH", 500)
        self.maker_market.set_balance("QETH", 500)
        self.maker_market.set_quantization_param(
            QuantizationParams(
                self.maker_symbols[0], 5, 5, 5, 5
            )
        )

        self.market_info: MarketInfo = MarketInfo(
            *(
                [self.maker_market] + self.maker_symbols
            )
        )

        logging_options: int = (PureMarketMakingStrategyV2.OPTION_LOG_ALL &
                                (~PureMarketMakingStrategyV2.OPTION_LOG_NULL_ORDER_SIZE))
        self.strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            legacy_order_size=1.0,
            legacy_bid_spread=self.bid_threshold,
            legacy_ask_spread=self.ask_threshold,
            cancel_order_wait_time=45,
            logging_options=logging_options
        )
        self.logging_options = logging_options
        self.clock.add_iterator(self.maker_market)
        self.clock.add_iterator(self.strategy)

        self.maker_order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.maker_market.add_listener(MarketEvent.OrderFilled, self.maker_order_fill_logger)
        self.maker_market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

    def simulate_maker_market_trade(self, is_buy: bool, quantity: float):
        maker_symbol: str = self.maker_symbols[0]
        order_book: OrderBook = self.maker_market.get_order_book(maker_symbol)
        trade_event: OrderBookTradeEvent = OrderBookTradeEvent(
            maker_symbol,
            self.clock.current_timestamp,
            TradeType.BUY if is_buy else TradeType.SELL,
            (self.mid_price * (1 - self.bid_threshold - 0.01)
             if not is_buy
             else self.mid_price * (1 + self.ask_threshold + 0.01)),
            quantity
        )
        order_book.apply_trade(trade_event)

    # Update the orderbook so that the top bids and asks are lower than actual for a wider bid ask spread
    # this basially removes the orderbook entries above top bid and below top ask
    @staticmethod
    def simulate_order_book_widening(order_book: OrderBook, top_bid: float, top_ask: float):
        bid_diffs: List[OrderBookRow] = []
        ask_diffs: List[OrderBookRow] = []
        update_id: int = order_book.last_diff_uid + 1
        for row in order_book.bid_entries():
            if row.price > top_bid:
                bid_diffs.append(OrderBookRow(row.price, 0, update_id))
            else:
                break
        for row in order_book.ask_entries():
            if row.price < top_ask:
                ask_diffs.append(OrderBookRow(row.price, 0, update_id))
            else:
                break
        order_book.apply_diffs(bid_diffs, ask_diffs, update_id)

    @staticmethod
    def simulate_limit_order_fill(market: Market, limit_order: LimitOrder):
        quote_currency_traded: float = float(float(limit_order.price) * float(limit_order.quantity))
        base_currency_traded: float = float(limit_order.quantity)
        quote_currency: str = limit_order.quote_currency
        base_currency: str = limit_order.base_currency
        config: MarketConfig = market.config

        if limit_order.is_buy:
            market.set_balance(quote_currency, market.get_balance(quote_currency) - quote_currency_traded)
            market.set_balance(base_currency, market.get_balance(base_currency) + base_currency_traded)
            market.trigger_event(MarketEvent.OrderFilled, OrderFilledEvent(
                market.current_timestamp,
                limit_order.client_order_id,
                limit_order.symbol,
                TradeType.BUY,
                OrderType.LIMIT,
                float(limit_order.price),
                float(limit_order.quantity)
            ))
            market.trigger_event(MarketEvent.BuyOrderCompleted, BuyOrderCompletedEvent(
                market.current_timestamp,
                limit_order.client_order_id,
                base_currency,
                quote_currency,
                base_currency if config.buy_fees_asset is AssetType.BASE_CURRENCY else quote_currency,
                base_currency_traded,
                quote_currency_traded,
                0.0,
                OrderType.LIMIT
            ))
        else:
            market.set_balance(quote_currency, market.get_balance(quote_currency) + quote_currency_traded)
            market.set_balance(base_currency, market.get_balance(base_currency) - base_currency_traded)
            market.trigger_event(MarketEvent.OrderFilled, OrderFilledEvent(
                market.current_timestamp,
                limit_order.client_order_id,
                limit_order.symbol,
                TradeType.SELL,
                OrderType.LIMIT,
                float(limit_order.price),
                float(limit_order.quantity)
            ))
            market.trigger_event(MarketEvent.SellOrderCompleted, SellOrderCompletedEvent(
                market.current_timestamp,
                limit_order.client_order_id,
                base_currency,
                quote_currency,
                base_currency if config.sell_fees_asset is AssetType.BASE_CURRENCY else quote_currency,
                base_currency_traded,
                quote_currency_traded,
                0.0,
                OrderType.LIMIT
            ))

    def test_confirm_active_bids_asks(self):
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

