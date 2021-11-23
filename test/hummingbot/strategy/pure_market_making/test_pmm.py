#!/usr/bin/env python
from typing import List, Optional
from decimal import Decimal
import logging

import pandas as pd
import unittest

from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    OrderBookTradeEvent,
    TradeType,
    PriceType,
    OrderCancelledEvent)
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType,
)
from hummingbot.strategy.pure_market_making.pure_market_making import PureMarketMakingStrategy
from hummingbot.strategy.order_book_asset_price_delegate import OrderBookAssetPriceDelegate
from hummingbot.strategy.pure_market_making.inventory_cost_price_delegate import InventoryCostPriceDelegate
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.client.command.config_command import ConfigCommand
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from test.mock.mock_paper_exchange import MockPaperExchange
from test.mock.mock_asset_price_delegate import MockAssetPriceDelegate

logging.basicConfig(level=logging.ERROR)


# Update the orderbook so that the top bids and asks are lower than actual for a wider bid ask spread
# this basially removes the orderbook entries above top bid and below top ask
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


class PMMUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    trading_pair = "HBOT-ETH"
    base_asset = trading_pair.split("-")[0]
    quote_asset = trading_pair.split("-")[1]

    def setUp(self):
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.market: MockPaperExchange = MockPaperExchange()
        self.mid_price = 100
        self.bid_spread = 0.01
        self.ask_spread = 0.01
        self.order_refresh_time = 30
        self.market.set_balanced_order_book(self.trading_pair,
                                            mid_price=self.mid_price,
                                            min_price=1,
                                            max_price=200,
                                            price_step_size=1,
                                            volume_step_size=10)
        self.market.set_balance("HBOT", 500)
        self.market.set_balance("ETH", 5000)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 6, 6, 6, 6
            )
        )
        self.market_info = MarketTradingPairTuple(self.market, self.trading_pair,
                                                  self.base_asset, self.quote_asset)
        self.clock.add_iterator(self.market)
        self.order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.market.add_listener(MarketEvent.OrderFilled, self.order_fill_logger)
        self.market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

        self.one_level_strategy = PureMarketMakingStrategy()
        self.one_level_strategy.init_params(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=5.0,
            filled_order_delay=5.0,
            order_refresh_tolerance_pct=-1,
            minimum_spread=-1
        )

        self.multi_levels_strategy = PureMarketMakingStrategy()
        self.multi_levels_strategy.init_params(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=5.0,
            filled_order_delay=5.0,
            order_refresh_tolerance_pct=-1,
            order_levels=3,
            order_level_spread=Decimal("0.01"),
            order_level_amount=Decimal("1"),
            minimum_spread=-1,
        )

        self.order_override_strategy = PureMarketMakingStrategy()
        self.order_override_strategy.init_params(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=5.0,
            filled_order_delay=5.0,
            order_refresh_tolerance_pct=-1,
            order_levels=3,
            order_level_spread=Decimal("0.01"),
            order_level_amount=Decimal("1"),
            minimum_spread=-1,
            order_override={"order_one": ["buy", 0.5, 0.7], "order_two": ["buy", 1.3, 1.1], "order_three": ["sell", 1.1, 2]},
        )

        self.custom_asset_price_delegate = MockAssetPriceDelegate(self.market, mock_price=Decimal("100.0"))
        self.custom_price_source_strategy = PureMarketMakingStrategy()
        self.custom_price_source_strategy.init_params(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=5.0,
            filled_order_delay=5.0,
            order_refresh_tolerance_pct=-1,
            minimum_spread=-1,
            asset_price_delegate=self.custom_asset_price_delegate,
            price_type="custom",
        )

        self.ext_market: MockPaperExchange = MockPaperExchange()
        self.ext_market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            self.ext_market, self.trading_pair, self.base_asset, self.quote_asset
        )
        self.ext_market.set_balanced_order_book(trading_pair=self.trading_pair,
                                                mid_price=50, min_price=1, max_price=400, price_step_size=1,
                                                volume_step_size=10)
        self.order_book_asset_del = OrderBookAssetPriceDelegate(self.ext_market, self.trading_pair)
        trade_fill_sql = SQLConnectionManager(
            SQLConnectionType.TRADE_FILLS, db_path=""
        )
        self.inventory_cost_price_del = InventoryCostPriceDelegate(trade_fill_sql, self.trading_pair)

    def simulate_maker_market_trade(
            self, is_buy: bool, quantity: Decimal, price: Decimal, market: Optional[MockPaperExchange] = None,
    ):
        if market is None:
            market = self.market
        order_book = market.get_order_book(self.trading_pair)
        trade_event = OrderBookTradeEvent(
            self.trading_pair,
            self.clock.current_timestamp,
            TradeType.BUY if is_buy else TradeType.SELL,
            price,
            quantity
        )
        order_book.apply_trade(trade_event)

    def test_basic_one_level(self):
        strategy = self.one_level_strategy
        self.clock.add_iterator(strategy)

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        buy_1 = strategy.active_buys[0]
        self.assertEqual(99, buy_1.price)
        self.assertEqual(1, buy_1.quantity)
        sell_1 = strategy.active_sells[0]
        self.assertEqual(101, sell_1.price)
        self.assertEqual(1, sell_1.quantity)

        # After order_refresh_time, a new set of orders is created
        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertNotEqual(buy_1.client_order_id, strategy.active_buys[0].client_order_id)
        self.assertNotEqual(sell_1.client_order_id, strategy.active_sells[0].client_order_id)

        # Simulate buy order filled
        self.clock.backtest_til(self.start_timestamp + 8)
        self.simulate_maker_market_trade(False, 100, 98.9)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        # After filled_ore
        self.clock.backtest_til(self.start_timestamp + 14)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

    def test_basic_one_level_price_type_own_last_trade(self):
        strategy = PureMarketMakingStrategy()
        strategy.init_params(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=5.0,
            filled_order_delay=5.0,
            order_refresh_tolerance_pct=-1,
            minimum_spread=-1,
            price_type='last_own_trade_price',
        )
        self.clock.add_iterator(strategy)

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        buy_1 = strategy.active_buys[0]
        self.assertEqual(99, buy_1.price)
        self.assertEqual(1, buy_1.quantity)
        sell_1 = strategy.active_sells[0]
        self.assertEqual(101, sell_1.price)
        self.assertEqual(1, sell_1.quantity)

        # Simulate buy order filled
        self.simulate_maker_market_trade(False, 100, 98.9)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        # Order has been filled
        self.clock.backtest_til(self.start_timestamp + 7)
        buy_1 = strategy.active_buys[0]
        self.assertEqual(Decimal('98.01'), buy_1.price)
        self.assertEqual(1, buy_1.quantity)
        sell_1 = strategy.active_sells[0]
        self.assertEqual(Decimal('99.99'), sell_1.price)
        self.assertEqual(1, sell_1.quantity)

    def test_basic_one_level_price_type(self):
        strategies = []

        for price_type in ["last_price", "best_bid", "best_ask"]:
            strategy = PureMarketMakingStrategy()
            strategy.init_params(
                self.market_info,
                bid_spread=Decimal("0.01"),
                ask_spread=Decimal("0.01"),
                order_amount=Decimal("1"),
                order_refresh_time=5.0,
                filled_order_delay=5.0,
                order_refresh_tolerance_pct=-1,
                minimum_spread=-1,
                price_type=price_type,
            )
            strategies.append(strategy)
            self.clock.add_iterator(strategy)

        last_strategy, bid_strategy, ask_strategy = strategies

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(last_strategy.active_buys))
        self.assertEqual(1, len(last_strategy.active_sells))
        buy_1 = last_strategy.active_buys[0]
        self.assertEqual(99, buy_1.price)
        self.assertEqual(1, buy_1.quantity)
        sell_1 = last_strategy.active_sells[0]
        self.assertEqual(101, sell_1.price)
        self.assertEqual(1, sell_1.quantity)

        # Simulate buy order filled
        self.simulate_maker_market_trade(False, 100, 98.9)
        self.assertEqual(0, len(last_strategy.active_buys))
        self.assertEqual(1, len(last_strategy.active_sells))

        # After filled_ore
        self.clock.backtest_til(self.start_timestamp + 7)
        buy_1 = last_strategy.active_buys[0]
        self.assertEqual(Decimal('97.911'), buy_1.price)
        self.assertEqual(1, buy_1.quantity)
        sell_1 = last_strategy.active_sells[0]
        self.assertEqual(Decimal('99.889'), sell_1.price)
        self.assertEqual(1, sell_1.quantity)

        buy_bid = bid_strategy.active_buys[0]
        buy_target = self.market_info.get_price_by_type(PriceType.BestBid) * Decimal("0.99")
        self.assertEqual(buy_target, buy_bid.price)
        sell_bid = bid_strategy.active_sells[0]
        sell_target = self.market_info.get_price_by_type(PriceType.BestBid) * Decimal("1.01")
        self.assertEqual(sell_target, sell_bid.price)

        buy_ask = ask_strategy.active_buys[0]
        buy_target = self.market_info.get_price_by_type(PriceType.BestAsk) * Decimal("0.99")
        self.assertEqual(buy_target, buy_ask.price)
        sell_ask = ask_strategy.active_sells[0]
        sell_target = self.market_info.get_price_by_type(PriceType.BestAsk) * Decimal("1.01")
        self.assertEqual(sell_target, sell_ask.price)

    def test_basic_multiple_levels(self):
        strategy = self.multi_levels_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)

        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))
        buys = strategy.active_buys
        sells = strategy.active_sells
        self.assertEqual(3, len(buys))
        self.assertEqual(3, len(sells))
        self.assertEqual(Decimal("99"), buys[0].price)
        self.assertEqual(Decimal("1"), buys[0].quantity)
        self.assertEqual(Decimal("98"), buys[1].price)
        self.assertEqual(Decimal("2"), buys[1].quantity)
        self.assertEqual(Decimal("101"), sells[0].price)
        self.assertEqual(Decimal("1"), sells[0].quantity)
        self.assertEqual(Decimal("103"), sells[2].price)
        self.assertEqual(Decimal("3"), sells[2].quantity)

        # After order_refresh_time, a new set of orders is created
        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))
        self.assertNotEqual(buys[0].client_order_id, strategy.active_buys[0].client_order_id)
        self.assertNotEqual(sells[0].client_order_id, strategy.active_sells[0].client_order_id)

        # Simulate buy order filled
        self.clock.backtest_til(self.start_timestamp + 8)
        self.simulate_maker_market_trade(False, 100, 97.9)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        # After filled_ore
        self.clock.backtest_til(self.start_timestamp + 14)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

    def test_apply_budget_constraint_to_proposal(self):
        strategy = self.multi_levels_strategy
        self.clock.add_iterator(strategy)
        self.market.set_balance("HBOT", Decimal("50"))
        self.market.set_balance("ETH", Decimal("0"))
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        for order in strategy.active_sells:
            strategy.cancel_order(order.client_order_id)

        self.market.set_balance("HBOT", 0)
        self.market.set_balance("ETH", Decimal("5000"))
        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        for order in strategy.active_buys:
            strategy.cancel_order(order.client_order_id)

        self.market.set_balance("HBOT", Decimal("6.0"))
        self.market.set_balance("ETH", Decimal("586.0"))
        self.clock.backtest_til(self.start_timestamp + 20)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))
        self.assertEqual(Decimal("97"), strategy.active_buys[-1].price)
        self.assertEqual(Decimal("3"), strategy.active_buys[-1].quantity)
        self.assertEqual(Decimal("103"), strategy.active_sells[-1].price)
        self.assertEqual(Decimal("3"), strategy.active_sells[-1].quantity)

    def test_order_quantity_available_balance(self):
        """
        When balance is below the specified order amount, checks if orders created
        use the remaining available balance for the order size.
        """
        strategy = PureMarketMakingStrategy()
        strategy.init_params(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_refresh_time=5,
            order_amount=Decimal("100"),
            order_levels=3
        )

        self.clock.add_iterator(strategy)
        self.market.set_balance("HBOT", Decimal("10"))
        self.market.set_balance("ETH", Decimal("1000"))
        self.clock.backtest_til(self.start_timestamp + 1)

        # Check if order size on both sides is equal to the remaining balance
        self.assertEqual(Decimal("10.1010"), strategy.active_buys[0].quantity)
        self.assertEqual(Decimal("10"), strategy.active_sells[0].quantity)

        # Order levels created
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        strategy.cancel_order(strategy.active_buys[0].client_order_id)
        strategy.cancel_order(strategy.active_sells[0].client_order_id)

        # Do not create order on side with 0 balance
        self.market.set_balance("HBOT", 0)
        self.market.set_balance("ETH", Decimal("1000"))
        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

    def test_market_become_wider(self):
        strategy = self.one_level_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(Decimal("99"), strategy.active_buys[0].price)
        self.assertEqual(Decimal("101"), strategy.active_sells[0].price)
        self.assertEqual(Decimal("1.0"), strategy.active_buys[0].quantity)
        self.assertEqual(Decimal("1.0"), strategy.active_sells[0].quantity)

        simulate_order_book_widening(self.market.order_books[self.trading_pair], 90, 110)

        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(2, len(self.cancel_order_logger.event_log))
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        self.assertEqual(Decimal("99"), strategy.active_buys[0].price)
        self.assertEqual(Decimal("101"), strategy.active_sells[0].price)
        self.assertEqual(Decimal("1.0"), strategy.active_buys[0].quantity)
        self.assertEqual(Decimal("1.0"), strategy.active_sells[0].quantity)

    def test_market_became_narrower(self):
        strategy = self.one_level_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(Decimal("99"), strategy.active_buys[0].price)
        self.assertEqual(Decimal("101"), strategy.active_sells[0].price)
        self.assertEqual(Decimal("1.0"), strategy.active_buys[0].quantity)
        self.assertEqual(Decimal("1.0"), strategy.active_sells[0].quantity)

        self.market.order_books[self.trading_pair].apply_diffs([OrderBookRow(99.5, 30, 2)], [OrderBookRow(100.5, 30, 2)], 2)

        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(2, len(self.cancel_order_logger.event_log))
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        self.assertEqual(Decimal("99"), strategy.active_buys[0].price)
        self.assertEqual(Decimal("101"), strategy.active_sells[0].price)
        self.assertEqual(Decimal("1.0"), strategy.active_buys[0].quantity)
        self.assertEqual(Decimal("1.0"), strategy.active_sells[0].quantity)

    def test_price_band_price_ceiling_breach(self):
        strategy = self.multi_levels_strategy
        strategy.price_ceiling = Decimal("105")

        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        simulate_order_book_widening(self.market.order_books[self.trading_pair], self.mid_price, 115, )

        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

    def test_price_band_price_floor_breach(self):
        strategy = self.multi_levels_strategy
        strategy.price_floor = Decimal("95")

        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        simulate_order_book_widening(self.market.order_books[self.trading_pair], 85, self.mid_price)

        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

    def test_add_transaction_costs(self):
        strategy = self.multi_levels_strategy
        strategy.add_transaction_costs_to_orders = True
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))
        # Todo: currently hummingsim market doesn't store fee in a percentage value, so we cannot test further on this.

    def test_filled_order_delay(self):
        strategy = self.one_level_strategy
        strategy.filled_order_delay = 60.0
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        self.clock.backtest_til(self.start_timestamp + 7)
        # Ask is filled and due to delay is not replenished immediately
        self.simulate_maker_market_trade(True, 100, Decimal("101.1"))
        self.assertEqual(1, len(self.order_fill_logger.event_log))
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        self.clock.backtest_til(self.start_timestamp + 15)
        # After order_refresh_time, buy order gets canceled
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        # still no orders
        self.clock.backtest_til(self.start_timestamp + 30)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        # still no orders
        self.clock.backtest_til(self.start_timestamp + 45)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        # Orders are placed after replenish delay
        self.clock.backtest_til(self.start_timestamp + 69)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        # Prices are not adjusted according to filled price as per settings
        self.assertEqual(Decimal("99"), strategy.active_buys[0].price)
        self.assertEqual(Decimal("101"), strategy.active_sells[0].price)
        self.assertEqual(Decimal("1.0"), strategy.active_buys[0].quantity)
        self.assertEqual(Decimal("1.0"), strategy.active_sells[0].quantity)
        self.order_fill_logger.clear()

    def test_filled_order_delay_mulitiple_orders(self):
        strategy = self.multi_levels_strategy
        strategy.filled_order_delay = 10.0
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        self.simulate_maker_market_trade(True, 100, Decimal("101.1"))

        # Ask is filled and due to delay is not replenished immediately
        self.clock.backtest_til(self.start_timestamp + 2)
        self.assertEqual(1, len(self.order_fill_logger.event_log))
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(2, len(strategy.active_sells))

        # After order_refresh_time, buy order gets canceled
        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        # Orders are placed after replenish delay
        self.clock.backtest_til(self.start_timestamp + 12)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        self.order_fill_logger.clear()

    def test_order_optimization(self):
        # Widening the order book, top bid is now 97.5 and top ask 102.5
        simulate_order_book_widening(self.market.order_books[self.trading_pair], 98, 102)
        strategy = self.one_level_strategy
        strategy.order_optimization_enabled = True
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertEqual(Decimal("97.5001"), strategy.active_buys[0].price)
        self.assertEqual(Decimal("102.499"), strategy.active_sells[0].price)

    def test_order_optimization_with_multiple_order_levels(self):
        # Widening the order book, top bid is now 97.5 and top ask 102.5
        simulate_order_book_widening(self.market.order_books[self.trading_pair], 98, 102)
        strategy = self.multi_levels_strategy
        strategy.order_optimization_enabled = True
        strategy.order_level_spread = Decimal("0.025")
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))
        self.assertEqual(Decimal("97.5001"), strategy.active_buys[0].price)
        self.assertEqual(Decimal("102.499"), strategy.active_sells[0].price)
        self.assertEqual(strategy.active_buys[1].price / strategy.active_buys[0].price, Decimal("0.975"))
        self.assertEqual(strategy.active_buys[2].price / strategy.active_buys[0].price, Decimal("0.95"))
        self.assertEqual(strategy.active_sells[1].price / strategy.active_sells[0].price, Decimal("1.025"))
        self.assertEqual(strategy.active_sells[2].price / strategy.active_sells[0].price, Decimal("1.05"))

    def test_hanging_orders(self):
        strategy = self.one_level_strategy
        strategy.order_refresh_time = 4.0
        strategy.filled_order_delay = 8.0
        strategy.hanging_orders_enabled = True
        strategy.hanging_orders_cancel_pct = Decimal("0.05")
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        self.simulate_maker_market_trade(False, 100, 98.9)

        # Bid is filled and due to delay is not replenished immediately
        # Ask order is now hanging but is active
        self.clock.backtest_til(self.start_timestamp + strategy.order_refresh_time + 1)
        self.assertEqual(1, len(self.order_fill_logger.event_log))
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertEqual(1, len(strategy.hanging_order_ids))
        hanging_sell = strategy.active_sells[0]
        self.assertEqual(hanging_sell.client_order_id, strategy.hanging_order_ids[0])

        # At order_refresh_time, hanging order remains.
        self.clock.backtest_til(self.start_timestamp + strategy.order_refresh_time * 2 + 1)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        # At filled_order_delay, a new set of bid and ask orders (one each) is created
        self.clock.backtest_til(self.start_timestamp + strategy.order_refresh_time * 2 + 2)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(2, len(strategy.active_sells))

        self.assertIn(hanging_sell.client_order_id, [order.client_order_id for order in strategy.active_sells])

        simulate_order_book_widening(self.market.order_books[self.trading_pair], 80, 100)
        # As book bids moving lower, the ask hanging order price spread is now more than the hanging_orders_cancel_pct
        # Hanging order is canceled and removed from the active list
        self.clock.backtest_til(self.start_timestamp + 11 * self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertNotIn(strategy.active_sells[0].client_order_id, strategy.hanging_order_ids)

        self.order_fill_logger.clear()

    def test_hanging_order_max_order_age(self):
        # Note: Due to orders created by backtest market don't have timestamp in their IDs, thus max order age cannot
        # be calculated. We manually add the order to to_recreate_hanging_orders and trigger order cancel event here to
        # simulate the recreate.
        strategy = self.one_level_strategy
        strategy.hanging_orders_enabled = True

        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        self.simulate_maker_market_trade(False, 100, 98.9)
        self.clock.backtest_til(self.start_timestamp + strategy.order_refresh_time + 1)
        self.assertEqual(1, len(self.order_fill_logger.event_log))
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertEqual(1, len(strategy.hanging_order_ids))
        hanging_sell: LimitOrder = strategy.active_sells[0]
        self.assertEqual(hanging_sell.client_order_id, strategy.hanging_order_ids[0])

        self.market.trigger_event(MarketEvent.OrderCancelled, OrderCancelledEvent(
            self.market.current_timestamp,
            hanging_sell.client_order_id
        ))
        self.clock.backtest_til(self.start_timestamp + strategy.order_refresh_time * 2 + 1)
        self.assertEqual(1, len(strategy.active_sells))
        new_hang: LimitOrder = [o for o in strategy.active_sells if o.price == hanging_sell.price
                                and o.quantity == hanging_sell.quantity]

        self.assertNotEqual(hanging_sell.client_order_id, new_hang[0].client_order_id)

    def test_hanging_orders_multiple_orders(self):
        strategy = self.multi_levels_strategy
        strategy.order_refresh_time = 4.0
        strategy.filled_order_delay = 8.0
        strategy.hanging_orders_enabled = True
        strategy.hanging_orders_cancel_pct = Decimal("0.05")
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        self.simulate_maker_market_trade(False, 100, 98.9)

        # Bid is filled and due to delay is not replenished immediately
        # Ask order is active
        # Hanging orders are not yet created
        self.clock.backtest_til(self.start_timestamp + strategy.order_refresh_time / 2)
        self.assertEqual(1, len(self.order_fill_logger.event_log))
        self.assertEqual(2, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))
        self.assertEqual(0, len(strategy.hanging_order_ids))

        # At order_refresh_time, hanging orders are created, active orders are cancelled
        self.clock.backtest_til(self.start_timestamp + strategy.order_refresh_time + 1)

        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertEqual(1, len(strategy.hanging_order_ids))

        # At filled_order_delay, a new set of bid and ask orders (one each) is created
        self.clock.backtest_til(self.start_timestamp + strategy.order_refresh_time + strategy.filled_order_delay + 1)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(4, len(strategy.active_sells))

        self.assertTrue(all(id in (order.client_order_id for order in strategy.active_sells)
                            for id in strategy.hanging_order_ids))

        simulate_order_book_widening(self.market.order_books[self.trading_pair], 80, 100)
        # As book bids moving lower, the ask hanging order price spread is now more than the hanging_orders_cancel_pct
        # Hanging order is canceled and removed from the active list
        self.clock.backtest_til(self.start_timestamp + strategy.order_refresh_time * 2 + strategy.filled_order_delay + 1)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))
        self.assertFalse(any(o.client_order_id in strategy.hanging_order_ids for o in strategy.active_sells))

        self.order_fill_logger.clear()

    def test_inventory_skew(self):
        strategy = self.one_level_strategy
        strategy.inventory_skew_enabled = True
        strategy.inventory_target_base_pct = Decimal("0.9")
        strategy.inventory_range_multiplier = Decimal("5.0")
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        first_bid_order = strategy.active_buys[0]
        first_ask_order = strategy.active_sells[0]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("0.5"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.5"), first_ask_order.quantity)

        self.simulate_maker_market_trade(True, 5.0, 101.1)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        self.clock.backtest_til(self.start_timestamp + 2)
        self.assertEqual(1, len(self.order_fill_logger.event_log))

        maker_fill = self.order_fill_logger.event_log[0]
        self.assertEqual(TradeType.SELL, maker_fill.trade_type)
        self.assertAlmostEqual(101, maker_fill.price)
        self.assertAlmostEqual(Decimal("1.5"), Decimal(str(maker_fill.amount)), places=4)

        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        first_bid_order = strategy.active_buys[0]
        first_ask_order = strategy.active_sells[0]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("0.651349"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.34865"), first_ask_order.quantity)

    def test_inventory_skew_multiple_orders(self):
        strategy = PureMarketMakingStrategy()
        strategy.init_params(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=5.0,
            filled_order_delay=5.0,
            order_refresh_tolerance_pct=-1,
            order_levels=5,
            order_level_spread=Decimal("0.01"),
            order_level_amount=Decimal("0.5"),
            inventory_skew_enabled=True,
            inventory_target_base_pct=Decimal("0.9"),
            inventory_range_multiplier=Decimal("0.5"),
            minimum_spread=-1,
        )
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(5, len(strategy.active_sells))

        first_bid_order = strategy.active_buys[0]
        first_ask_order = strategy.active_sells[0]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("0.5"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.5"), first_ask_order.quantity)

        last_bid_order = strategy.active_buys[-1]
        last_ask_order = strategy.active_sells[-1]
        last_bid_price = Decimal(100 * (1 - 0.01 - (0.01 * 4))).quantize(Decimal("0.001"))
        last_ask_price = Decimal(100 * (1 + 0.01 + (0.01 * 4))).quantize(Decimal("0.001"))
        self.assertAlmostEqual(last_bid_price, last_bid_order.price, 3)
        self.assertAlmostEqual(last_ask_price, last_ask_order.price, 3)
        self.assertEqual(Decimal("1.5"), last_bid_order.quantity)
        self.assertEqual(Decimal("4.5"), last_ask_order.quantity)

        self.simulate_maker_market_trade(True, 5.0, 101.1)
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(4, len(strategy.active_sells))

        self.clock.backtest_til(self.start_timestamp + 3)
        self.assertEqual(1, len(self.order_fill_logger.event_log))

        maker_fill = self.order_fill_logger.event_log[0]
        self.assertEqual(TradeType.SELL, maker_fill.trade_type)
        self.assertAlmostEqual(101, maker_fill.price)
        self.assertAlmostEqual(Decimal("1.5"), Decimal(str(maker_fill.amount)), places=4)

        # The default filled_order_delay is 60, so gotta wait 60 + 2 here.
        self.clock.backtest_til(self.start_timestamp + 7 * self.clock_tick_size + 1)
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(5, len(strategy.active_sells))
        first_bid_order = strategy.active_buys[0]
        first_ask_order = strategy.active_sells[0]
        last_bid_order = strategy.active_buys[-1]
        last_ask_order = strategy.active_sells[-1]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("0.651349"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.34865"), first_ask_order.quantity)
        last_bid_price = Decimal(100 * (1 - 0.01 - (0.01 * 4))).quantize(Decimal("0.001"))
        last_ask_price = Decimal(100 * (1 + 0.01 + (0.01 * 4))).quantize(Decimal("0.001"))
        self.assertAlmostEqual(last_bid_price, last_bid_order.price, 3)
        self.assertAlmostEqual(last_ask_price, last_ask_order.price, 3)
        self.assertEqual(Decimal("1.95404"), last_bid_order.quantity)
        self.assertEqual(Decimal("4.04595"), last_ask_order.quantity)

    def test_inventory_skew_multiple_orders_status(self):
        strategy = PureMarketMakingStrategy()
        strategy.init_params(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=5.0,
            filled_order_delay=5.0,
            order_refresh_tolerance_pct=-1,
            order_levels=5,
            order_level_spread=Decimal("0.01"),
            order_level_amount=Decimal("0.5"),
            inventory_skew_enabled=True,
            inventory_target_base_pct=Decimal("0.9"),
            inventory_range_multiplier=Decimal("0.5"),
            minimum_spread=-1,
        )
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.assertEqual(5, len(strategy.active_buys))
        self.assertEqual(5, len(strategy.active_sells))

        status_df: pd.DataFrame = strategy.inventory_skew_stats_data_frame()
        self.assertEqual("50.0%", status_df.iloc[4, 1])
        self.assertEqual("150.0%", status_df.iloc[4, 2])

    def test_inventory_cost_price_del(self):
        strategy = self.one_level_strategy
        strategy.inventory_cost_price_delegate = self.inventory_cost_price_del
        self.clock.add_iterator(strategy)
        self.market.set_balance("HBOT", 0)
        self.clock.backtest_til(self.start_timestamp + 1)

        # Expecting to have orders set according to mid_price as there is no inventory cost data yet
        first_bid_order = strategy.active_buys[0]
        self.assertEqual(Decimal("99"), first_bid_order.price)

        self.simulate_maker_market_trade(
            is_buy=False, quantity=Decimal("10"), price=Decimal("98.9"),
        )
        new_mid_price = Decimal("96")
        self.market.set_balanced_order_book(
            trading_pair=self.trading_pair,
            mid_price=new_mid_price,
            min_price=1,
            max_price=200,
            price_step_size=1,
            volume_step_size=10,
        )
        self.clock.backtest_til(self.start_timestamp + 7)
        first_bid_order = strategy.active_buys[0]
        first_ask_order = strategy.active_sells[0]
        expected_bid_price = new_mid_price / Decimal(1 + self.bid_spread)
        self.assertAlmostEqual(expected_bid_price, first_bid_order.price, places=1)
        expected_ask_price = Decimal("99") * Decimal(1 + self.ask_spread)
        self.assertAlmostEqual(expected_ask_price, first_ask_order.price)

    def test_order_book_asset_del(self):
        strategy = self.one_level_strategy
        strategy.asset_price_delegate = self.order_book_asset_del
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.simulate_maker_market_trade(
            is_buy=True, quantity=Decimal("1"), price=Decimal("123"), market=self.ext_market,
        )

        bid = self.order_book_asset_del.get_price_by_type(PriceType.BestBid)
        ask = self.order_book_asset_del.get_price_by_type(PriceType.BestAsk)
        mid_price = self.order_book_asset_del.get_price_by_type(PriceType.MidPrice)
        last_trade = self.order_book_asset_del.get_price_by_type(PriceType.LastTrade)

        self.assertEqual((bid + ask) / 2, mid_price)
        self.assertEqual(last_trade, Decimal("123"))
        assert isinstance(bid, Decimal)
        assert isinstance(ask, Decimal)
        assert isinstance(mid_price, Decimal)
        assert isinstance(last_trade, Decimal)

    def test_external_exchange_price_source(self):
        strategy = self.one_level_strategy
        strategy.asset_price_delegate = self.order_book_asset_del
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(1, len(strategy.active_buys))
        # There should be no sell order, since its price will be below first bid order on the order book.
        self.assertEqual(0, len(strategy.active_sells))

        # check price data from external exchange is used for order placement
        bid_order = strategy.active_buys[0]
        self.assertEqual(Decimal("49.5"), bid_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)

    def test_external_exchange_price_source_empty_orderbook(self):
        simulate_order_book_widening(self.market.order_books[self.trading_pair], 0, 10000)
        self.assertEqual(0, len(list(self.market.order_books[self.trading_pair].bid_entries())))
        self.assertEqual(0, len(list(self.market.order_books[self.trading_pair].ask_entries())))
        strategy = self.one_level_strategy
        strategy.asset_price_delegate = self.order_book_asset_del
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        # check price data from external exchange is used for order placement
        bid_order = strategy.active_buys[0]
        self.assertEqual(Decimal("49.5"), bid_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        ask_order = strategy.active_sells[0]
        self.assertEqual(Decimal("50.5"), ask_order.price)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

    def test_multi_order_external_exchange_price_source(self):
        strategy = self.multi_levels_strategy
        strategy.asset_price_delegate = self.order_book_asset_del
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(3, len(strategy.active_buys))
        # There should be no sell order, since its price will be below first bid order on the order book.
        self.assertEqual(0, len(strategy.active_sells))

        # check price data from external exchange is used for order placement
        bid_order = strategy.active_buys[0]
        self.assertEqual(Decimal("49.5"), bid_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)

        last_bid_order = strategy.active_buys[-1]
        last_bid_price = Decimal(50 * (1 - 0.01 - (0.01 * 2))).quantize(Decimal("0.001"))
        self.assertAlmostEqual(last_bid_price, last_bid_order.price, 3)
        self.assertEqual(Decimal("3.0"), last_bid_order.quantity)

    def test_multi_order_external_exchange_price_source_empty_order_book(self):
        simulate_order_book_widening(self.market.order_books[self.trading_pair], 0, 10000)
        self.assertEqual(0, len(list(self.market.order_books[self.trading_pair].bid_entries())))
        self.assertEqual(0, len(list(self.market.order_books[self.trading_pair].ask_entries())))
        strategy = self.multi_levels_strategy
        strategy.asset_price_delegate = self.order_book_asset_del
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)

        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        # check price data from external exchange is used for order placement
        bid_order = strategy.active_buys[0]
        self.assertEqual(Decimal("49.5"), bid_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)

        last_bid_order = strategy.active_buys[-1]
        last_bid_price = Decimal(50 * (1 - 0.01 - (0.01 * 2))).quantize(Decimal("0.001"))
        self.assertAlmostEqual(last_bid_price, last_bid_order.price, 3)
        self.assertEqual(Decimal("3.0"), last_bid_order.quantity)

    def test_config_spread_on_the_fly_multiple_orders(self):
        strategy = self.multi_levels_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + 1)
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(3, len(strategy.active_buys))
        self.assertEqual(3, len(strategy.active_sells))

        first_bid_order = strategy.active_buys[0]
        first_ask_order = strategy.active_sells[0]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)

        last_bid_order = strategy.active_buys[-1]
        last_ask_order = strategy.active_sells[-1]
        self.assertAlmostEqual(Decimal("97"), last_bid_order.price, 2)
        self.assertAlmostEqual(Decimal("103"), last_ask_order.price, 2)

        ConfigCommand.update_running_mm(strategy, "bid_spread", Decimal('2'))
        ConfigCommand.update_running_mm(strategy, "ask_spread", Decimal('2'))
        for order in strategy.active_sells:
            strategy.cancel_order(order.client_order_id)
        for order in strategy.active_buys:
            strategy.cancel_order(order.client_order_id)
        self.clock.backtest_til(self.start_timestamp + 7)
        first_bid_order = strategy.active_buys[0]
        first_ask_order = strategy.active_sells[0]
        self.assertEqual(Decimal("98"), first_bid_order.price)
        self.assertEqual(Decimal("102"), first_ask_order.price)

        last_bid_order = strategy.active_buys[-1]
        last_ask_order = strategy.active_sells[-1]
        self.assertAlmostEqual(Decimal("96"), last_bid_order.price, 2)
        self.assertAlmostEqual(Decimal("104"), last_ask_order.price, 2)

    def test_order_override(self):
        strategy = self.order_override_strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)

        buys = strategy.active_buys
        sells = strategy.active_sells
        self.assertEqual(2, len(buys))
        self.assertEqual(1, len(sells))
        self.assertEqual(Decimal("99.5"), buys[0].price)
        self.assertEqual(Decimal("0.7"), buys[0].quantity)
        self.assertEqual(Decimal("98.7"), buys[1].price)
        self.assertEqual(Decimal("1.1"), buys[1].quantity)
        self.assertEqual(Decimal("101.1"), sells[0].price)
        self.assertEqual(Decimal("2"), sells[0].quantity)

    def test_custom_price_source(self):
        strategy = self.custom_price_source_strategy
        self.clock.add_iterator(strategy)

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        buy = strategy.active_buys[0]
        self.assertEqual(Decimal("99"), buy.price)
        self.assertEqual(1, buy.quantity)
        sell = strategy.active_sells[0]
        self.assertEqual(Decimal("101"), sell.price)
        self.assertEqual(1, sell.quantity)

        self.custom_asset_price_delegate.set_mock_price(mock_price=Decimal("101.0"))

        self.clock.backtest_til(self.start_timestamp + 7)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        buy = strategy.active_buys[0]
        self.assertEqual(Decimal("99.99"), buy.price)
        self.assertEqual(1, buy.quantity)
        sell = strategy.active_sells[0]
        self.assertEqual(Decimal("102.01"), sell.price)
        self.assertEqual(1, sell.quantity)

    def test_no_new_orders_created_until_previous_orders_cancellation_confirmed(self):
        strategy = self.one_level_strategy
        self.clock.add_iterator(strategy)

        refresh_time = strategy.order_refresh_time

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)

        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

        orders_creation_timestamp = strategy.current_timestamp

        # Add a fake in flight cancellation to simulate a confirmation has not arrived
        strategy._sb_order_tracker.in_flight_cancels["OID-99"] = strategy.current_timestamp

        # After refresh time the two real orders should be cancelled, but no new order should be created
        self.clock.backtest_til(orders_creation_timestamp + refresh_time)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        # After a second refresh time no new order should be created
        self.clock.backtest_til(orders_creation_timestamp + (2 * refresh_time))
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))

        del strategy._sb_order_tracker.in_flight_cancels["OID-99"]

        # After removing the pending cancel, in the next tick the new orders should be created
        self.clock.backtest_til(strategy.current_timestamp + 1)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))

    def test_adjusted_available_balance_considers_in_flight_cancel_orders(self):
        base_balance = self.market.get_available_balance(self.base_asset)
        quote_balance = self.market.get_available_balance(self.quote_asset)

        strategy = self.one_level_strategy

        strategy._sb_order_tracker.start_tracking_limit_order(
            market_pair=self.market_info,
            order_id="OID-1",
            is_buy=True,
            price=Decimal(1000),
            quantity=Decimal(1))
        strategy._sb_order_tracker.start_tracking_limit_order(
            market_pair=self.market_info,
            order_id="OID-2",
            is_buy=False,
            price=Decimal(2000),
            quantity=Decimal(2))

        strategy._sb_order_tracker.in_flight_cancels["OID-1"] = strategy.current_timestamp

        available_base_balance, available_quote_balance = strategy.adjusted_available_balance_for_orders_budget_constrain()

        self.assertEqual(available_base_balance, base_balance + Decimal(2))
        self.assertEqual(available_quote_balance, quote_balance + (Decimal(1) * Decimal(1000)))


class PureMarketMakingMinimumSpreadUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    trading_pair = "COINALPHA-WETH"
    maker_trading_pairs: List[str] = ["COINALPHA-WETH", "COINALPHA", "WETH"]

    def setUp(self):
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.market: MockPaperExchange = MockPaperExchange()
        self.mid_price = 100
        self.market.set_balanced_order_book(trading_pair=self.trading_pair,
                                            mid_price=self.mid_price, min_price=1,
                                            max_price=200, price_step_size=1, volume_step_size=10)
        self.market.set_balance("COINALPHA", 500)
        self.market.set_balance("WETH", 5000)
        self.market.set_balance("QETH", 500)
        self.market.set_quantization_param(
            QuantizationParams(
                self.maker_trading_pairs[0], 6, 6, 6, 6
            )
        )
        self.market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            self.market, self.maker_trading_pairs[0],
            self.maker_trading_pairs[1], self.maker_trading_pairs[2]
        )

        self.strategy: PureMarketMakingStrategy = PureMarketMakingStrategy()
        self.strategy.init_params(
            self.market_info,
            bid_spread=Decimal(.05),
            ask_spread=Decimal(.05),
            order_amount=Decimal(1),
            order_refresh_time=30,
            minimum_spread=0,
        )

    def test_minimum_spread_param(self):
        strategy = self.strategy
        self.clock.add_iterator(strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        old_bid = strategy.active_buys[0]
        old_ask = strategy.active_sells[0]
        # t = 2, No Change => orders should stay the same
        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertEqual(old_bid.client_order_id, strategy.active_buys[0].client_order_id)
        self.assertEqual(old_ask.client_order_id, strategy.active_sells[0].client_order_id)
        # Minimum Spread Threshold Cancellation
        # t = 3, Mid Market Price Moves Down - Below Min Spread (Old Bid) => Buy Order Cancelled
        self.market.order_books[self.trading_pair].apply_diffs([OrderBookRow(50, 1000, 2)],
                                                               [OrderBookRow(50, 1000, 2)], 2)
        self.clock.backtest_til(self.start_timestamp + 3 * self.clock_tick_size)
        self.assertEqual(0, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        # t = 30, New Set of Orders
        self.clock.backtest_til(self.start_timestamp + 32 * self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        new_bid = strategy.active_buys[0]
        new_ask = strategy.active_sells[0]
        self.assertNotEqual(old_bid.client_order_id, new_bid.client_order_id)
        self.assertNotEqual(old_ask.client_order_id, new_ask.client_order_id)
        old_ask = new_ask
        old_bid = new_bid
        # t = 35, No Change
        self.clock.backtest_til(self.start_timestamp + 36 * self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertEqual(old_bid.client_order_id, strategy.active_buys[0].client_order_id)
        self.assertEqual(old_ask.client_order_id, strategy.active_sells[0].client_order_id)
        # t = 36, Mid Market Price Moves Up - Below Min Spread (Old Ask) => Sell Order Cancelled
        # Clear Order Book (setting all orders above price 0, to quantity 0)
        simulate_order_book_widening(self.market.order_books[self.trading_pair], 0, 0)
        # New Mid-Market Price
        self.market.order_books[self.trading_pair].apply_diffs([OrderBookRow(99, 1000, 3)],
                                                               [OrderBookRow(101, 1000, 3)], 3)
        # Check That Order Book Manipulations Didn't Affect Strategy Orders Yet
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(1, len(strategy.active_sells))
        self.assertEqual(old_bid.client_order_id, strategy.active_buys[0].client_order_id)
        self.assertEqual(old_ask.client_order_id, strategy.active_sells[0].client_order_id)
        # Simulate Minimum Spread Threshold Cancellation
        self.clock.backtest_til(self.start_timestamp + 40 * self.clock_tick_size)
        self.assertEqual(1, len(strategy.active_buys))
        self.assertEqual(0, len(strategy.active_sells))
