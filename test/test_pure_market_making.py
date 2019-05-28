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
from hummingbot.strategy.pure_market_making import PureMarketMakingStrategy
from hummingbot.strategy.pure_market_making.pure_market_pair import PureMarketPair


class PureMarketMakingUnitTest(unittest.TestCase):
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
        self.maker_data.set_balanced_order_book(mid_price= self.mid_price, min_price= 1,
                                                max_price= 200, price_step_size= 1, volume_step_size= 10)
        self.maker_market.add_data(self.maker_data)
        self.maker_market.set_balance("COINALPHA", 500)
        self.maker_market.set_balance("WETH", 500)
        self.maker_market.set_balance("QETH", 500)
        self.maker_market.set_quantization_param(
            QuantizationParams(
                self.maker_symbols[0], 5, 5, 5, 5
            )
        )

        self.market_pair: PureMarketPair = PureMarketPair(
            *(
                [self.maker_market] + self.maker_symbols
            )
        )

        logging_options: int = (PureMarketMakingStrategy.OPTION_LOG_ALL &
                                (~PureMarketMakingStrategy.OPTION_LOG_NULL_ORDER_SIZE))
        self.strategy: {PureMarketMakingStrategy} = PureMarketMakingStrategy(
            [self.market_pair],
            order_size=1,
            bid_place_threshold=self.bid_threshold,
            ask_place_threshold=self.ask_threshold,
            cancel_order_wait_time= 45,
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
            self.mid_price * (1-self.bid_threshold -0.01) if not is_buy else self.mid_price * (1+self.ask_threshold +0.01),
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

    def test_correct_price_correct_size(self):
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(self.mid_price*(1 + self.ask_threshold),
                         self.strategy.active_asks[0][1].price)
        self.assertEqual(self.mid_price*(1 - self.bid_threshold),
                         self.strategy.active_bids[0][1].price)
        self.assertEqual(1, self.strategy.active_bids[0][1].quantity)
        self.assertEqual(1, self.strategy.active_asks[0][1].quantity)

    def test_check_sufficient_balance(self):
        self.maker_market.set_balance("WETH", 0)
        end_ts = self.start_timestamp + self.clock_tick_size
        self.clock.backtest_til(end_ts)
        self.assertEqual(0, len(self.strategy.active_bids))
        self.assertEqual(0, len(self.strategy.active_asks))
        self.maker_market.set_balance("WETH", 500)
        end_ts += self.clock_tick_size
        self.clock.backtest_til(end_ts)
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

    def test_check_if_active_orders_are_cancelled_every_tick(self):
        end_ts = self.start_timestamp + self.clock_tick_size
        self.clock.backtest_til(end_ts)
        old_bid = self.strategy.active_bids[0][1]
        old_ask = self.strategy.active_asks[0][1]
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))
        end_ts += self.clock_tick_size + 1
        self.clock.backtest_til(end_ts)
        new_bid = self.strategy.active_bids[0][1]
        new_ask = self.strategy.active_asks[0][1]
        self.assertNotEqual(old_ask, new_ask)
        self.assertNotEqual(old_bid, new_bid)

    def test_order_fills(self):
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

        self.simulate_maker_market_trade(True, 5.0)

        self.clock.backtest_til(self.start_timestamp + 2*self.clock_tick_size+1)
        self.assertEqual(1, len(self.maker_order_fill_logger.event_log))

        maker_fill: OrderFilledEvent = self.maker_order_fill_logger.event_log[0]
        self.assertEqual(TradeType.SELL, maker_fill.trade_type)
        self.assertAlmostEqual(101, maker_fill.price)
        self.assertAlmostEqual(1.0, maker_fill.amount)

    def test_market_become_wider(self):
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)

        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

        self.simulate_order_book_widening(self.maker_data.order_book, 90, 110)

        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size + 1)
        self.assertEqual(2, len(self.cancel_order_logger.event_log))
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

    def test_market_became_narrower(self):
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

        self.maker_data.order_book.apply_diffs([OrderBookRow(99.5, 30, 2)], [OrderBookRow(100.5, 30, 2)], 2)

        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size + 1)
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

        bid_order = self.strategy.active_bids[0][1]
        ask_order = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

    def test_order_fills_after_cancellation(self):
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size + 1)
        self.assertEqual(2, len(self.cancel_order_logger.event_log))
        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

        self.simulate_limit_order_fill(self.maker_market, bid_order)
        self.simulate_limit_order_fill(self.maker_market, ask_order)

        fill_events = self.maker_order_fill_logger.event_log
        self.assertEqual(2, len(fill_events))
        bid_fills: List[OrderFilledEvent] = [evt for evt in fill_events if evt.trade_type is TradeType.SELL]
        ask_fills: List[OrderFilledEvent] = [evt for evt in fill_events if evt.trade_type is TradeType.BUY]
        self.assertEqual(1, len(bid_fills))
        self.assertEqual(1, len(ask_fills))


    def test_create_new_orders(self):
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

        self.strategy.create_new_orders(self.market_pair)

        self.assertEqual(2, len(self.strategy.active_bids))
        self.assertEqual(2, len(self.strategy.active_asks))

        bid_order: LimitOrder = self.strategy.active_bids[1][1]
        ask_order: LimitOrder = self.strategy.active_asks[1][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

        self.strategy.create_new_orders(self.market_pair)

        self.assertEqual(3, len(self.strategy.active_bids))
        self.assertEqual(3, len(self.strategy.active_asks))

        bid_order: LimitOrder = self.strategy.active_bids[2][1]
        ask_order: LimitOrder = self.strategy.active_asks[2][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

    def test_strategy_after_user_cancels_orders(self):
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

        self.strategy.cancel_order(self.market_pair, bid_order.client_order_id)
        self.strategy.cancel_order(self.market_pair, ask_order.client_order_id)

        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size + 1)
        self.assertEqual(0, len(self.strategy.active_bids))
        self.assertEqual(0, len(self.strategy.active_asks))


def main():
    unittest.main()


if __name__ == "__main__":
    main()
