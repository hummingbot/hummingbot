#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from decimal import Decimal
import logging; logging.basicConfig(level=logging.ERROR)
import pandas as pd
from typing import List
import unittest
import time
import asyncio

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
    SellOrderCompletedEvent,
    TradeFee
)
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.strategy.pure_market_making.pure_market_making_v2 import PureMarketMakingStrategyV2
from hummingbot.strategy.pure_market_making import (
    ConstantSpreadPricingDelegate,
    PassThroughFilterDelegate,
    ConstantMultipleSpreadPricingDelegate,
    ConstantSizeSizingDelegate,
    StaggeredMultipleSizeSizingDelegate,
    InventorySkewSingleSizeSizingDelegate,
    InventorySkewMultipleSizeSizingDelegate,
    OrderBookAssetPriceDelegate,
    DataFeedAssetPriceDelegate,
    APIAssetPriceDelegate
)
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingbot.core.network_base import NetworkStatus


class MockDataFeed(DataFeedBase):

    @property
    def name(self):
        return self._name

    def __init__(self, name, coin_prices):
        super().__init__()
        self._name = name
        self._mock_price_dict = coin_prices
        self._network_status = NetworkStatus.CONNECTED

    async def check_network(self) -> NetworkStatus:
        return NetworkStatus.CONNECTED

    @property
    def price_dict(self):
        return self._mock_price_dict

    def get_price(self, trading_pair):
        return self._mock_price_dict.get(trading_pair.upper())

    def start(self):
        pass

    def stop(self):
        pass


class PureMarketMakingV2UnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    maker_trading_pairs: List[str] = ["COINALPHA-WETH", "COINALPHA", "WETH"]

    def setUp(self):
        self.clock: Clock = Clock(ClockMode.BACKTEST, 60.0, self.start_timestamp, self.end_timestamp)
        self.clock_tick_size = 60
        self.maker_market: BacktestMarket = BacktestMarket()
        self.maker_data: MockOrderBookLoader = MockOrderBookLoader(*self.maker_trading_pairs)
        self.mid_price = 100
        self.bid_threshold = 0.01
        self.ask_threshold = 0.01
        self.cancel_order_wait_time = 45
        self.maker_data.set_balanced_order_book(mid_price=self.mid_price, min_price=1,
                                                max_price=200, price_step_size=1, volume_step_size=10)

        self.constant_pricing_delegate = ConstantSpreadPricingDelegate(Decimal(self.bid_threshold),
                                                                       Decimal(self.ask_threshold))
        self.constant_sizing_delegate = ConstantSizeSizingDelegate(Decimal("1.0"))
        self.filter_delegate = PassThroughFilterDelegate()
        self.equal_strategy_sizing_delegate = StaggeredMultipleSizeSizingDelegate(
            order_start_size=Decimal("1.0"),
            order_step_size=Decimal("0"),
            number_of_orders=Decimal("5")
        )
        self.staggered_strategy_sizing_delegate = StaggeredMultipleSizeSizingDelegate(
            order_start_size=Decimal("1.0"),
            order_step_size=Decimal("0.5"),
            number_of_orders=Decimal("5")
        )
        self.multiple_order_strategy_pricing_delegate = ConstantMultipleSpreadPricingDelegate(
            bid_spread=Decimal(self.bid_threshold),
            ask_spread=Decimal(self.ask_threshold),
            order_interval_size=Decimal("0.01"),
            number_of_orders=Decimal("5")
        )

        self.maker_market.add_data(self.maker_data)
        self.maker_market.set_balance("COINALPHA", 500)
        self.maker_market.set_balance("WETH", 5000)
        self.maker_market.set_balance("QETH", 500)
        self.maker_market.set_quantization_param(
            QuantizationParams(
                self.maker_trading_pairs[0], 6, 6, 6, 6
            )
        )

        self.market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            *(
                [self.maker_market] + self.maker_trading_pairs
            )
        )

        logging_options: int = (PureMarketMakingStrategyV2.OPTION_LOG_ALL &
                                (~PureMarketMakingStrategyV2.OPTION_LOG_NULL_ORDER_SIZE))
        self.strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filled_order_replenish_wait_time=self.cancel_order_wait_time,
            filter_delegate=self.filter_delegate,
            sizing_delegate=self.constant_sizing_delegate,
            pricing_delegate=self.constant_pricing_delegate,
            cancel_order_wait_time=45,
            logging_options=logging_options
        )

        self.multi_order_equal_strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filter_delegate=self.filter_delegate,
            pricing_delegate=self.multiple_order_strategy_pricing_delegate,
            sizing_delegate=self.equal_strategy_sizing_delegate,
            cancel_order_wait_time=45,
            logging_options=logging_options
        )

        self.multi_order_staggered_strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filter_delegate=self.filter_delegate,
            pricing_delegate=self.multiple_order_strategy_pricing_delegate,
            sizing_delegate=self.staggered_strategy_sizing_delegate,
            cancel_order_wait_time=45,
            logging_options=logging_options
        )

        self.delayed_placement_strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filter_delegate=self.filter_delegate,
            pricing_delegate=self.constant_pricing_delegate,
            sizing_delegate=self.constant_sizing_delegate,
            cancel_order_wait_time=900,
            filled_order_replenish_wait_time=80,
            logging_options=logging_options
        )

        self.prevent_cancel_strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filter_delegate=self.filter_delegate,
            pricing_delegate=self.constant_pricing_delegate,
            sizing_delegate=self.constant_sizing_delegate,
            cancel_order_wait_time=900,
            filled_order_replenish_wait_time=80,
            enable_order_filled_stop_cancellation=True,
            logging_options=logging_options
        )

        self.penny_jumping_strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filter_delegate=self.filter_delegate,
            pricing_delegate=self.constant_pricing_delegate,
            sizing_delegate=self.constant_sizing_delegate,
            best_bid_ask_jump_mode=True,
            cancel_order_wait_time=900,
            filled_order_replenish_wait_time=80,
            enable_order_filled_stop_cancellation=True,
            logging_options=logging_options
        )

        self.ext_market: BacktestMarket = BacktestMarket()
        self.ext_data: MockOrderBookLoader = MockOrderBookLoader(*self.maker_trading_pairs)
        self.ext_market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            self.ext_market, *self.maker_trading_pairs
        )
        self.ext_data.set_balanced_order_book(mid_price=50, min_price=1, max_price=400,
                                         price_step_size=1, volume_step_size=10)
        self.ext_market.add_data(self.ext_data)
        self.asset_del = OrderBookAssetPriceDelegate(self.ext_market, self.maker_trading_pairs[0])
        self.ext_exc_price_strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filled_order_replenish_wait_time=self.cancel_order_wait_time,
            filter_delegate=self.filter_delegate,
            sizing_delegate=self.constant_sizing_delegate,
            pricing_delegate=self.constant_pricing_delegate,
            cancel_order_wait_time=45,
            logging_options=logging_options,
            asset_price_delegate=self.asset_del
        )

        self.multi_orders_ext_exc_price_strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filled_order_replenish_wait_time=self.cancel_order_wait_time,
            filter_delegate=self.filter_delegate,
            sizing_delegate=self.equal_strategy_sizing_delegate,
            pricing_delegate=self.multiple_order_strategy_pricing_delegate,
            cancel_order_wait_time=45,
            logging_options=logging_options,
            asset_price_delegate=self.asset_del
        )

        ExchangeRateConversion.set_global_exchange_rate_config({
            "global_config": {
                self.maker_trading_pairs[1]: {"default": 200, "source": "mock_data_feed"},
                self.maker_trading_pairs[2]: {"default": 1, "source": "mock_data_feed"}
            },
            "default_data_feed": "mock_data_feed"
        })
        mock_feed = MockDataFeed("mock_data_feed", {self.maker_trading_pairs[1]:200, self.maker_trading_pairs[2]:1})
        ExchangeRateConversion.set_data_feeds([
            mock_feed
        ])
        ExchangeRateConversion.set_update_interval(0.1)
        ExchangeRateConversion.get_instance().start()
        time.sleep(1)
        self.feed_asset_del = DataFeedAssetPriceDelegate(self.maker_trading_pairs[1], self.maker_trading_pairs[2])

        self.ext_feed_price_strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filled_order_replenish_wait_time=self.cancel_order_wait_time,
            filter_delegate=self.filter_delegate,
            sizing_delegate=self.constant_sizing_delegate,
            pricing_delegate=self.constant_pricing_delegate,
            cancel_order_wait_time=45,
            logging_options=logging_options,
            asset_price_delegate=self.feed_asset_del
        )

        self.multi_orders_ext_feed_price_strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filled_order_replenish_wait_time=self.cancel_order_wait_time,
            filter_delegate=self.filter_delegate,
            sizing_delegate=self.equal_strategy_sizing_delegate,
            pricing_delegate=self.multiple_order_strategy_pricing_delegate,
            cancel_order_wait_time=45,
            logging_options=logging_options,
            asset_price_delegate=self.feed_asset_del
        )

        self.logging_options = logging_options
        self.clock.add_iterator(self.maker_market)
        self.clock.add_iterator(self.strategy)
        self.maker_order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.maker_market.add_listener(MarketEvent.OrderFilled, self.maker_order_fill_logger)
        self.maker_market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

    def simulate_maker_market_trade(self, is_buy: bool, quantity: float):
        maker_trading_pair: str = self.maker_trading_pairs[0]
        order_book: OrderBook = self.maker_market.get_order_book(maker_trading_pair)
        trade_event: OrderBookTradeEvent = OrderBookTradeEvent(
            maker_trading_pair,
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
        quote_currency_traded: Decimal = limit_order.price * limit_order.quantity
        base_currency_traded: Decimal = limit_order.quantity
        quote_currency: str = limit_order.quote_currency
        base_currency: str = limit_order.base_currency
        config: MarketConfig = market.config

        if limit_order.is_buy:
            market.set_balance(quote_currency, market.get_balance(quote_currency) - quote_currency_traded)
            market.set_balance(base_currency, market.get_balance(base_currency) + base_currency_traded)
            market.trigger_event(MarketEvent.OrderFilled, OrderFilledEvent(
                market.current_timestamp,
                limit_order.client_order_id,
                limit_order.trading_pair,
                TradeType.BUY,
                OrderType.LIMIT,
                limit_order.price,
                limit_order.quantity,
                TradeFee(Decimal("0.0"))
            ))
            market.trigger_event(MarketEvent.BuyOrderCompleted, BuyOrderCompletedEvent(
                market.current_timestamp,
                limit_order.client_order_id,
                base_currency,
                quote_currency,
                base_currency if config.buy_fees_asset is AssetType.BASE_CURRENCY else quote_currency,
                base_currency_traded,
                quote_currency_traded,
                Decimal("0.0"),
                OrderType.LIMIT
            ))
        else:
            market.set_balance(quote_currency, market.get_balance(quote_currency) + quote_currency_traded)
            market.set_balance(base_currency, market.get_balance(base_currency) - base_currency_traded)
            market.trigger_event(MarketEvent.OrderFilled, OrderFilledEvent(
                market.current_timestamp,
                limit_order.client_order_id,
                limit_order.trading_pair,
                TradeType.SELL,
                OrderType.LIMIT,
                limit_order.price,
                limit_order.quantity,
                TradeFee(Decimal("0.0"))
            ))
            market.trigger_event(MarketEvent.SellOrderCompleted, SellOrderCompletedEvent(
                market.current_timestamp,
                limit_order.client_order_id,
                base_currency,
                quote_currency,
                base_currency if config.sell_fees_asset is AssetType.BASE_CURRENCY else quote_currency,
                base_currency_traded,
                quote_currency_traded,
                Decimal("0.0"),
                OrderType.LIMIT
            ))

    def test_confirm_active_bids_asks(self):
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

    def test_correct_price_correct_size(self):
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(self.mid_price * (1 + self.ask_threshold),
                         self.strategy.active_asks[0][1].price)
        self.assertEqual(self.mid_price * (1 - self.bid_threshold),
                         self.strategy.active_bids[0][1].price)
        self.assertEqual(1, self.strategy.active_bids[0][1].quantity)
        self.assertEqual(1, self.strategy.active_asks[0][1].quantity)

    def test_check_sufficient_balance(self):
        self.maker_market.set_balance("WETH", 0)
        end_ts = self.start_timestamp + self.clock_tick_size
        self.clock.backtest_til(end_ts)
        self.assertEqual(0, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

        self.maker_market.set_balance("COINALPHA", 0)
        end_ts += self.clock_tick_size
        self.clock.backtest_til(end_ts)
        self.assertEqual(0, len(self.strategy.active_bids))
        self.assertEqual(0, len(self.strategy.active_asks))

        self.maker_market.set_balance("COINALPHA", 500)
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

        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size + 1)
        self.assertEqual(1, len(self.maker_order_fill_logger.event_log))

        maker_fill: OrderFilledEvent = self.maker_order_fill_logger.event_log[0]
        self.assertEqual(TradeType.SELL, maker_fill.trade_type)
        self.assertAlmostEqual(101, maker_fill.price)
        self.assertAlmostEqual(1.0, maker_fill.amount)
        self.maker_order_fill_logger.clear()

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
        self.maker_order_fill_logger.clear()

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

        self.strategy.cancel_order(self.market_info, bid_order.client_order_id)
        self.strategy.cancel_order(self.market_info, ask_order.client_order_id)

        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size + 1)
        self.assertEqual(0, len(self.strategy.active_bids))
        self.assertEqual(0, len(self.strategy.active_asks))

    def test_strategy_with_transaction_costs(self):
        self.clock.remove_iterator(self.strategy)
        logging_options: int = (PureMarketMakingStrategyV2.OPTION_LOG_ALL &
                                (~PureMarketMakingStrategyV2.OPTION_LOG_NULL_ORDER_SIZE))
        self.strategy_with_tx_costs: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filled_order_replenish_wait_time=self.cancel_order_wait_time,
            add_transaction_costs_to_orders=True,
            filter_delegate=self.filter_delegate,
            sizing_delegate=self.constant_sizing_delegate,
            pricing_delegate=self.constant_pricing_delegate,
            cancel_order_wait_time=45,
            logging_options=logging_options
        )
        self.clock.add_iterator(self.strategy_with_tx_costs)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.strategy_with_tx_costs.active_bids))
        self.assertEqual(1, len(self.strategy_with_tx_costs.active_asks))

        # Fees are zero here, check whether order placements are working
        bid_order: LimitOrder = self.strategy_with_tx_costs.active_bids[0][1]
        ask_order: LimitOrder = self.strategy_with_tx_costs.active_asks[0][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

        # Check if orders are placed after cancel_order_wait_time
        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size + 1)
        self.assertEqual(2, len(self.cancel_order_logger.event_log))
        bid_order: LimitOrder = self.strategy_with_tx_costs.active_bids[0][1]
        ask_order: LimitOrder = self.strategy_with_tx_costs.active_asks[0][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

        # Check if order fills are working
        self.simulate_limit_order_fill(self.maker_market, bid_order)
        self.simulate_limit_order_fill(self.maker_market, ask_order)

        fill_events = self.maker_order_fill_logger.event_log
        self.assertEqual(2, len(fill_events))
        bid_fills: List[OrderFilledEvent] = [evt for evt in fill_events if evt.trade_type is TradeType.SELL]
        ask_fills: List[OrderFilledEvent] = [evt for evt in fill_events if evt.trade_type is TradeType.BUY]
        self.assertEqual(1, len(bid_fills))
        self.assertEqual(1, len(ask_fills))
        self.maker_order_fill_logger.clear()

    def test_external_exchange_price_source(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(self.ext_exc_price_strategy)
        end_ts = self.start_timestamp + self.clock_tick_size
        self.clock.backtest_til(end_ts)

        self.assertEqual(1, len(self.ext_exc_price_strategy.active_bids))
        # There should be no sell order, since its price will be below first bid order on the order book.
        self.assertEqual(0, len(self.ext_exc_price_strategy.active_asks))

        # check price data from external exchange is used for order placement
        bid_order: LimitOrder = self.ext_exc_price_strategy.active_bids[0][1]
        self.assertEqual(Decimal("49.5"), bid_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)

    def test_external_exchange_price_source_empty_orderbook(self):
        self.simulate_order_book_widening(self.maker_data.order_book, 0, 10000)
        self.assertEqual(0, len(list(self.maker_data.order_book.bid_entries())))
        self.assertEqual(0, len(list(self.maker_data.order_book.ask_entries())))
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(self.ext_exc_price_strategy)
        end_ts = self.start_timestamp + self.clock_tick_size
        self.clock.backtest_til(end_ts)

        self.assertEqual(1, len(self.ext_exc_price_strategy.active_bids))
        self.assertEqual(1, len(self.ext_exc_price_strategy.active_asks))

        # check price data from external exchange is used for order placement
        bid_order: LimitOrder = self.ext_exc_price_strategy.active_bids[0][1]
        self.assertEqual(Decimal("49.5"), bid_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        ask_order: LimitOrder = self.ext_exc_price_strategy.active_asks[0][1]
        self.assertEqual(Decimal("50.5"), ask_order.price)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

    def test_multi_order_external_exchange_price_source(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(self.multi_orders_ext_exc_price_strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(5, len(self.multi_orders_ext_exc_price_strategy.active_bids))
        self.assertEqual(0, len(self.multi_orders_ext_exc_price_strategy.active_asks))

        first_bid_order: LimitOrder = self.multi_orders_ext_exc_price_strategy.active_bids[0][1]
        self.assertEqual(Decimal("49.5"), first_bid_order.price)
        self.assertEqual(Decimal("1.0"), first_bid_order.quantity)

        last_bid_order: LimitOrder = self.multi_orders_ext_exc_price_strategy.active_bids[-1][1]
        last_bid_price = Decimal(49.5 * (1 - 0.01) ** 4).quantize(Decimal("0.001"))
        self.assertAlmostEqual(last_bid_price, last_bid_order.price, 3)
        self.assertEqual(Decimal("1.0"), last_bid_order.quantity)

    def test_multi_order_external_exchange_price_source_empty_order_book(self):
        self.simulate_order_book_widening(self.maker_data.order_book, 0, 10000)
        self.assertEqual(0, len(list(self.maker_data.order_book.bid_entries())))
        self.assertEqual(0, len(list(self.maker_data.order_book.ask_entries())))
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(self.multi_orders_ext_exc_price_strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(5, len(self.multi_orders_ext_exc_price_strategy.active_bids))
        self.assertEqual(5, len(self.multi_orders_ext_exc_price_strategy.active_asks))

        first_bid_order: LimitOrder = self.multi_orders_ext_exc_price_strategy.active_bids[0][1]
        self.assertEqual(Decimal("49.5"), first_bid_order.price)
        self.assertEqual(Decimal("1.0"), first_bid_order.quantity)
        first_ask_order: LimitOrder = self.multi_orders_ext_exc_price_strategy.active_asks[0][1]
        self.assertEqual(Decimal("50.5"), first_ask_order.price)
        self.assertEqual(Decimal("1.0"), first_ask_order.quantity)

        last_bid_order: LimitOrder = self.multi_orders_ext_exc_price_strategy.active_bids[-1][1]
        last_bid_price = Decimal(49.5 * (1 - 0.01) ** 4).quantize(Decimal("0.001"))
        self.assertAlmostEqual(last_bid_price, last_bid_order.price, 3)
        self.assertEqual(Decimal("1.0"), last_bid_order.quantity)
        last_ask_order: LimitOrder = self.multi_orders_ext_exc_price_strategy.active_asks[-1][1]
        last_ask_price = Decimal(50.5 * (1 + 0.01) ** 4).quantize(Decimal("0.001"))
        self.assertAlmostEqual(last_ask_price, last_ask_order.price, 3)
        self.assertEqual(Decimal("1.0"), last_ask_order.quantity)

    def test_external_feed_price_source(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(self.ext_feed_price_strategy)
        end_ts = self.start_timestamp + self.clock_tick_size
        self.clock.backtest_til(end_ts)

        self.assertEqual(0, len(self.ext_feed_price_strategy.active_bids))
        self.assertEqual(1, len(self.ext_feed_price_strategy.active_asks))

        # check price data from external exchange is used for order placement
        ask_order: LimitOrder = self.ext_feed_price_strategy.active_asks[0][1]
        self.assertEqual(Decimal("202"), ask_order.price)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

    def test_external_feed_price_source_empty_orderbook(self):
        self.simulate_order_book_widening(self.maker_data.order_book, 0, 10000)
        self.assertEqual(0, len(list(self.maker_data.order_book.bid_entries())))
        self.assertEqual(0, len(list(self.maker_data.order_book.ask_entries())))
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(self.ext_feed_price_strategy)
        end_ts = self.start_timestamp + self.clock_tick_size
        self.clock.backtest_til(end_ts)

        self.assertEqual(1, len(self.ext_feed_price_strategy.active_bids))
        self.assertEqual(1, len(self.ext_feed_price_strategy.active_asks))

        # check price data from external exchange is used for order placement
        bid_order: LimitOrder = self.ext_feed_price_strategy.active_bids[0][1]
        self.assertEqual(Decimal("198"), bid_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        ask_order: LimitOrder = self.ext_feed_price_strategy.active_asks[0][1]
        self.assertEqual(Decimal("202"), ask_order.price)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)

    def test_multiple_orders_equal_sizes(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(self.multi_order_equal_strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(5, len(self.multi_order_equal_strategy.active_bids))
        self.assertEqual(5, len(self.multi_order_equal_strategy.active_asks))

        first_bid_order: LimitOrder = self.multi_order_equal_strategy.active_bids[0][1]
        first_ask_order: LimitOrder = self.multi_order_equal_strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("1.0"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.0"), first_ask_order.quantity)

        last_bid_order: LimitOrder = self.multi_order_equal_strategy.active_bids[-1][1]
        last_ask_order: LimitOrder = self.multi_order_equal_strategy.active_asks[-1][1]
        last_bid_price = Decimal(99 * (1 - 0.01) ** 4).quantize(Decimal("0.001"))
        last_ask_price = Decimal(101 * (1 + 0.01) ** 4).quantize(Decimal("0.001"))
        self.assertAlmostEqual(last_bid_price, last_bid_order.price, 3)
        self.assertAlmostEqual(last_ask_price, last_ask_order.price, 3)
        self.assertEqual(Decimal("1.0"), last_bid_order.quantity)
        self.assertEqual(Decimal("1.0"), last_ask_order.quantity)

        self.simulate_maker_market_trade(True, 5.0)
        self.assertEqual(5, len(self.multi_order_equal_strategy.active_bids))
        self.assertEqual(4, len(self.multi_order_equal_strategy.active_asks))

        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size + 1)
        self.assertEqual(1, len(self.maker_order_fill_logger.event_log))

        maker_fill: OrderFilledEvent = self.maker_order_fill_logger.event_log[0]
        self.assertEqual(TradeType.SELL, maker_fill.trade_type)
        self.assertAlmostEqual(101, maker_fill.price)
        self.assertAlmostEqual(1.0, maker_fill.amount)

        self.strategy.cancel_order(self.market_info, first_bid_order.client_order_id)
        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size + 1)
        self.assertEqual(0, len(self.strategy.active_bids))
        self.assertEqual(0, len(self.strategy.active_asks))

    def test_multiple_orders_staggered_sizes(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(self.multi_order_staggered_strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(5, len(self.multi_order_staggered_strategy.active_bids))
        self.assertEqual(5, len(self.multi_order_staggered_strategy.active_asks))

        first_bid_order: LimitOrder = self.multi_order_staggered_strategy.active_bids[0][1]
        first_ask_order: LimitOrder = self.multi_order_staggered_strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("1.0"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.0"), first_ask_order.quantity)

        last_bid_order: LimitOrder = self.multi_order_staggered_strategy.active_bids[-1][1]
        last_ask_order: LimitOrder = self.multi_order_staggered_strategy.active_asks[-1][1]
        last_bid_price = Decimal(99 * (1 - 0.01) ** 4).quantize(Decimal("0.001"))
        last_ask_price = Decimal(101 * (1 + 0.01) ** 4).quantize(Decimal("0.001"))

        last_bid_order_size = Decimal(1 + (0.5 * 4)).quantize(Decimal("0.001"))
        last_ask_order_size = Decimal(1 + (0.5 * 4)).quantize(Decimal("0.001"))
        self.assertAlmostEqual(last_bid_price, last_bid_order.price, 3)
        self.assertAlmostEqual(last_ask_price, last_ask_order.price, 3)
        self.assertAlmostEqual(last_bid_order_size, last_bid_order.quantity)
        self.assertAlmostEqual(last_ask_order_size, last_ask_order.quantity)

        self.simulate_maker_market_trade(True, 5.0)

        self.assertEqual(5, len(self.multi_order_staggered_strategy.active_bids))
        self.assertEqual(4, len(self.multi_order_staggered_strategy.active_asks))

        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size + 1)
        self.assertEqual(1, len(self.maker_order_fill_logger.event_log))

        maker_fill: OrderFilledEvent = self.maker_order_fill_logger.event_log[0]
        self.assertEqual(TradeType.SELL, maker_fill.trade_type)
        self.assertAlmostEqual(101, maker_fill.price)
        self.assertAlmostEqual(1.0, maker_fill.amount)

        self.strategy.cancel_order(self.market_info, first_bid_order.client_order_id)
        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size + 1)
        self.assertEqual(0, len(self.strategy.active_bids))
        self.assertEqual(0, len(self.strategy.active_asks))
        self.maker_order_fill_logger.clear()

    def test_balance_for_multiple_equal_orders(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(self.multi_order_equal_strategy)
        self.maker_market.set_balance("WETH", 0)
        end_ts = self.start_timestamp + self.clock_tick_size
        self.clock.backtest_til(end_ts)

        self.assertEqual(0, len(self.multi_order_equal_strategy.active_bids))
        self.assertEqual(5, len(self.multi_order_equal_strategy.active_asks))

        self.maker_market.set_balance("COINALPHA", 0)
        end_ts += self.clock_tick_size
        self.clock.backtest_til(end_ts)
        self.assertEqual(0, len(self.multi_order_equal_strategy.active_bids))
        self.assertEqual(0, len(self.multi_order_equal_strategy.active_asks))

        self.maker_market.set_balance("COINALPHA", 500)
        self.maker_market.set_balance("WETH", 5000)
        end_ts += self.clock_tick_size
        self.clock.backtest_til(end_ts)
        self.assertEqual(5, len(self.multi_order_equal_strategy.active_bids))
        self.assertEqual(5, len(self.multi_order_equal_strategy.active_asks))

    def test_balance_for_multiple_staggered_orders(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(self.multi_order_staggered_strategy)
        self.maker_market.set_balance("WETH", 0)
        end_ts = self.start_timestamp + self.clock_tick_size
        self.clock.backtest_til(end_ts)

        self.assertEqual(0, len(self.multi_order_staggered_strategy.active_bids))
        self.assertEqual(5, len(self.multi_order_staggered_strategy.active_asks))

        self.maker_market.set_balance("COINALPHA", 0)
        end_ts += self.clock_tick_size
        self.clock.backtest_til(end_ts)
        self.assertEqual(0, len(self.multi_order_staggered_strategy.active_bids))
        self.assertEqual(0, len(self.multi_order_staggered_strategy.active_asks))

        self.maker_market.set_balance("COINALPHA", 500)
        self.maker_market.set_balance("WETH", 5000)
        end_ts += self.clock_tick_size
        self.clock.backtest_til(end_ts)
        self.assertEqual(5, len(self.multi_order_staggered_strategy.active_bids))
        self.assertEqual(5, len(self.multi_order_staggered_strategy.active_asks))

    def test_replenish_delay(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(self.delayed_placement_strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.delayed_placement_strategy.active_bids))
        self.assertEqual(1, len(self.delayed_placement_strategy.active_asks))
        ask_order: LimitOrder = self.delayed_placement_strategy.active_asks[0][1]

        self.simulate_limit_order_fill(self.maker_market, ask_order)

        # Ask is filled and due to delay is not replenished immediately
        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size)
        self.assertEqual(1, len(self.maker_order_fill_logger.event_log))
        self.assertEqual(1, len(self.delayed_placement_strategy.active_bids))
        self.assertEqual(0, len(self.delayed_placement_strategy.active_asks))

        # Orders are placed after replenish delay
        self.clock.backtest_til(self.start_timestamp + 4 * self.clock_tick_size)
        self.assertEqual(1, len(self.delayed_placement_strategy.active_bids))
        self.assertEqual(1, len(self.delayed_placement_strategy.active_asks))

        # Prices are not adjusted according to filled price as per settings
        bid_order: LimitOrder = self.delayed_placement_strategy.active_bids[0][1]
        ask_order: LimitOrder = self.delayed_placement_strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)
        self.maker_order_fill_logger.clear()

    def test_replenish_delay_multiple_fills(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(self.delayed_placement_strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.delayed_placement_strategy.active_bids))
        self.assertEqual(1, len(self.delayed_placement_strategy.active_asks))
        ask_order: LimitOrder = self.delayed_placement_strategy.active_asks[0][1]
        bid_order: LimitOrder = self.delayed_placement_strategy.active_bids[0][1]

        self.simulate_limit_order_fill(self.maker_market, ask_order)

        # Ask is filled and due to delay is not replenished immediately
        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size)
        self.assertEqual(1, len(self.maker_order_fill_logger.event_log))
        self.assertEqual(1, len(self.delayed_placement_strategy.active_bids))
        self.assertEqual(0, len(self.delayed_placement_strategy.active_asks))
        self.simulate_limit_order_fill(self.maker_market, bid_order)

        # Even if both orders are filled, orders are not placed due to delay
        self.clock.backtest_til(self.start_timestamp + 3 * self.clock_tick_size)
        self.assertEqual(0, len(self.delayed_placement_strategy.active_bids))
        self.assertEqual(0, len(self.delayed_placement_strategy.active_asks))

        # Orders are placed after replenish delay
        self.clock.backtest_til(self.start_timestamp + 4 * self.clock_tick_size)
        self.assertEqual(1, len(self.delayed_placement_strategy.active_bids))
        self.assertEqual(1, len(self.delayed_placement_strategy.active_asks))

        # Prices are not adjusted according to filled price as per settings
        bid_order: LimitOrder = self.delayed_placement_strategy.active_bids[0][1]
        ask_order: LimitOrder = self.delayed_placement_strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)
        self.maker_order_fill_logger.clear()

    def test_prevent_cancellation_feature(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(self.prevent_cancel_strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.prevent_cancel_strategy.active_bids))
        self.assertEqual(1, len(self.prevent_cancel_strategy.active_asks))
        ask_order: LimitOrder = self.prevent_cancel_strategy.active_asks[0][1]

        self.simulate_limit_order_fill(self.maker_market, ask_order)

        # Ask is filled and due to delay is not replenished immediately
        # Bid order is no longer tracked and is not in active bids
        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size)
        self.assertEqual(1, len(self.maker_order_fill_logger.event_log))
        self.assertEqual(0, len(self.prevent_cancel_strategy.active_bids))
        self.assertEqual(0, len(self.prevent_cancel_strategy.active_asks))

        # Orders are placed after replenish delay
        self.clock.backtest_til(self.start_timestamp + 4 * self.clock_tick_size)
        self.assertEqual(1, len(self.prevent_cancel_strategy.active_bids))
        self.assertEqual(1, len(self.prevent_cancel_strategy.active_asks))

        # Prices are not adjusted according to filled price as per settings
        bid_order: LimitOrder = self.prevent_cancel_strategy.active_bids[0][1]
        ask_order: LimitOrder = self.prevent_cancel_strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), bid_order.price)
        self.assertEqual(Decimal("101"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)
        self.maker_order_fill_logger.clear()

    def test_penny_jumping_feature(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.remove_iterator(self.maker_market)
        self.maker_market_2: BacktestMarket = BacktestMarket()
        self.maker_data_2: MockOrderBookLoader = MockOrderBookLoader(*self.maker_trading_pairs)
        self.maker_data_2.set_balanced_order_book(mid_price=self.mid_price,
                                                  min_price=1,
                                                  max_price=200,
                                                  price_step_size=4,
                                                  volume_step_size=10)
        self.maker_market_2.add_data(self.maker_data_2)
        self.maker_market_2.set_balance("COINALPHA", 500)
        self.maker_market_2.set_balance("WETH", 5000)
        self.maker_market_2.set_balance("QETH", 500)
        self.maker_market_2.set_quantization_param(
            QuantizationParams(
                self.maker_trading_pairs[0], 6, 6, 6, 6
            )
        )

        self.market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            *([self.maker_market_2] + self.maker_trading_pairs)
        )
        logging_options: int = (PureMarketMakingStrategyV2.OPTION_LOG_ALL &
                                (~PureMarketMakingStrategyV2.OPTION_LOG_NULL_ORDER_SIZE))
        self.penny_jumping_strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filter_delegate=self.filter_delegate,
            pricing_delegate=self.constant_pricing_delegate,
            sizing_delegate=self.constant_sizing_delegate,
            best_bid_ask_jump_mode=True,
            cancel_order_wait_time=900,
            filled_order_replenish_wait_time=80,
            enable_order_filled_stop_cancellation=True,
            logging_options=logging_options
        )
        self.clock.add_iterator(self.penny_jumping_strategy)
        self.clock.add_iterator(self.maker_market_2)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.penny_jumping_strategy.active_bids))
        self.assertEqual(1, len(self.penny_jumping_strategy.active_asks))
        bid_order: LimitOrder = self.penny_jumping_strategy.active_bids[0][1]
        ask_order: LimitOrder = self.penny_jumping_strategy.active_asks[0][1]
        # Top bid is 98 and suggested price is 99 from pricing proposal
        # With penny jumping, bid price is just one above top bid
        self.assertEqual(Decimal("98.0001"), bid_order.price)
        # Top ask is 102 and suggested price is 101 from pricing proposal
        # With penny jumping, ask price is just one below top ask
        self.assertEqual(Decimal("101.999"), ask_order.price)
        self.assertEqual(Decimal("1.0"), bid_order.quantity)
        self.assertEqual(Decimal("1.0"), ask_order.quantity)


class PureMarketMakingV2InventorySkewUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    maker_trading_pairs: List[str] = ["COINALPHA-WETH", "COINALPHA", "WETH"]

    def setUp(self):
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.maker_market: BacktestMarket = BacktestMarket()
        self.maker_data: MockOrderBookLoader = MockOrderBookLoader(*self.maker_trading_pairs)
        self.mid_price = 100
        self.bid_threshold = 0.01
        self.ask_threshold = 0.01
        self.cancel_order_wait_time = 30
        self.maker_data.set_balanced_order_book(mid_price=self.mid_price, min_price=1,
                                                max_price=200, price_step_size=1, volume_step_size=10)
        self.filter_delegate = PassThroughFilterDelegate()
        self.constant_pricing_delegate = ConstantSpreadPricingDelegate(Decimal(self.bid_threshold),
                                                                       Decimal(self.ask_threshold))
        self.multiple_order_strategy_pricing_delegate = ConstantMultipleSpreadPricingDelegate(
            bid_spread=Decimal(self.bid_threshold),
            ask_spread=Decimal(self.ask_threshold),
            order_interval_size=Decimal("0.01"),
            number_of_orders=5
        )
        self.inventory_skew_single_size_sizing_delegate = InventorySkewSingleSizeSizingDelegate(
            order_size=1,
            inventory_target_base_percent=Decimal("0.5")
        )
        self.inventory_skew_multiple_size_sizing_delegate = InventorySkewMultipleSizeSizingDelegate(
            order_start_size=Decimal("1.0"),
            order_step_size=Decimal("0.5"),
            number_of_orders=5,
            inventory_target_base_percent=Decimal("0.5")
        )

        self.maker_market.add_data(self.maker_data)
        self.maker_market.set_balance("COINALPHA", 500)
        self.maker_market.set_balance("WETH", 5000)
        self.maker_market.set_balance("QETH", 500)
        self.maker_market.set_quantization_param(
            QuantizationParams(
                self.maker_trading_pairs[0], 6, 6, 6, 6
            )
        )

        self.market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            *(
                [self.maker_market] + self.maker_trading_pairs
            )
        )

        logging_options: int = (PureMarketMakingStrategyV2.OPTION_LOG_ALL &
                                (~PureMarketMakingStrategyV2.OPTION_LOG_NULL_ORDER_SIZE))

        self.inventory_skew_single_order_strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filter_delegate=self.filter_delegate,
            sizing_delegate=self.inventory_skew_single_size_sizing_delegate,
            pricing_delegate=self.constant_pricing_delegate,
            cancel_order_wait_time=45,
            filled_order_replenish_wait_time=0,
            logging_options=logging_options
        )

        self.inventory_skew_single_order_strategy_delayed_fill: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filter_delegate=self.filter_delegate,
            sizing_delegate=self.inventory_skew_single_size_sizing_delegate,
            pricing_delegate=self.constant_pricing_delegate,
            cancel_order_wait_time=45,
            filled_order_replenish_wait_time=15,
            logging_options=logging_options
        )

        self.inventory_skew_multiple_order_strategy: PureMarketMakingStrategyV2 = PureMarketMakingStrategyV2(
            [self.market_info],
            filter_delegate=self.filter_delegate,
            sizing_delegate=self.inventory_skew_multiple_size_sizing_delegate,
            pricing_delegate=self.multiple_order_strategy_pricing_delegate,
            cancel_order_wait_time=45,
            logging_options=logging_options
        )

        self.logging_options = logging_options
        self.clock.add_iterator(self.maker_market)
        self.maker_order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.maker_market.add_listener(MarketEvent.OrderFilled, self.maker_order_fill_logger)
        self.maker_market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

    def simulate_maker_market_trade(self, is_buy: bool, quantity: float):
        maker_trading_pair: str = self.maker_trading_pairs[0]
        order_book: OrderBook = self.maker_market.get_order_book(maker_trading_pair)
        trade_event: OrderBookTradeEvent = OrderBookTradeEvent(
            maker_trading_pair,
            self.clock.current_timestamp,
            TradeType.BUY if is_buy else TradeType.SELL,
            (self.mid_price * (1 - self.bid_threshold - 0.01)
             if not is_buy
             else self.mid_price * (1 + self.ask_threshold + 0.01)),
            quantity
        )
        order_book.apply_trade(trade_event)

    def test_inventory_skew_single_order_strategy(self):
        self.clock.add_iterator(self.inventory_skew_single_order_strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(1, len(self.inventory_skew_single_order_strategy.active_bids))
        self.assertEqual(1, len(self.inventory_skew_single_order_strategy.active_asks))
        first_bid_order: LimitOrder = self.inventory_skew_single_order_strategy.active_bids[0][1]
        first_ask_order: LimitOrder = self.inventory_skew_single_order_strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("0.181818"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.81818"), first_ask_order.quantity)

        self.simulate_maker_market_trade(True, 5.0)
        self.assertEqual(1, len(self.inventory_skew_single_order_strategy.active_bids))
        self.assertEqual(0, len(self.inventory_skew_single_order_strategy.active_asks))

        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size + 1)
        self.assertEqual(1, len(self.maker_order_fill_logger.event_log))

        maker_fill: OrderFilledEvent = self.maker_order_fill_logger.event_log[0]
        self.assertEqual(TradeType.SELL, maker_fill.trade_type)
        self.assertAlmostEqual(101, maker_fill.price)
        self.assertAlmostEqual(Decimal("1.81818"), Decimal(str(maker_fill.amount)), places=4)

        self.clock.backtest_til(self.start_timestamp + 3 * self.clock_tick_size + 1)
        self.assertEqual(1, len(self.inventory_skew_single_order_strategy.active_bids))
        self.assertEqual(1, len(self.inventory_skew_single_order_strategy.active_asks))
        first_bid_order: LimitOrder = self.inventory_skew_single_order_strategy.active_bids[0][1]
        first_ask_order: LimitOrder = self.inventory_skew_single_order_strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("0.188489"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.81151"), first_ask_order.quantity)

    def test_inventory_skew_single_order_strategy_delayed_fill(self):
        self.clock.add_iterator(self.inventory_skew_single_order_strategy_delayed_fill)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size + 1)
        self.assertEqual(1, len(self.inventory_skew_single_order_strategy_delayed_fill.active_bids))
        self.assertEqual(1, len(self.inventory_skew_single_order_strategy_delayed_fill.active_asks))
        first_bid_order: LimitOrder = self.inventory_skew_single_order_strategy_delayed_fill.active_bids[0][1]
        first_ask_order: LimitOrder = self.inventory_skew_single_order_strategy_delayed_fill.active_asks[0][1]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("0.181818"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.81818"), first_ask_order.quantity)

        self.simulate_maker_market_trade(True, 5.0)
        self.assertEqual(1, len(self.inventory_skew_single_order_strategy_delayed_fill.active_bids))
        self.assertEqual(0, len(self.inventory_skew_single_order_strategy_delayed_fill.active_asks))

        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size + 1)
        self.assertEqual(1, len(self.maker_order_fill_logger.event_log))

        maker_fill: OrderFilledEvent = self.maker_order_fill_logger.event_log[0]
        self.assertEqual(TradeType.SELL, maker_fill.trade_type)
        self.assertAlmostEqual(101, maker_fill.price)
        self.assertAlmostEqual(Decimal("1.81818"), Decimal(str(maker_fill.amount)), places=4)

        self.clock.backtest_til(self.start_timestamp + 3 * self.clock_tick_size + 1)
        # Order is not replenished till replenish time
        self.assertEqual(1, len(self.inventory_skew_single_order_strategy_delayed_fill.active_bids))
        self.assertEqual(0, len(self.inventory_skew_single_order_strategy_delayed_fill.active_asks))
        first_bid_order: LimitOrder = self.inventory_skew_single_order_strategy_delayed_fill.active_bids[0][1]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("0.181818"), first_bid_order.quantity)

        self.clock.backtest_til(self.start_timestamp + 60 * self.clock_tick_size + 1)
        self.assertEqual(1, len(self.inventory_skew_single_order_strategy_delayed_fill.active_bids))
        self.assertEqual(1, len(self.inventory_skew_single_order_strategy_delayed_fill.active_asks))
        first_bid_order: LimitOrder = self.inventory_skew_single_order_strategy_delayed_fill.active_bids[0][1]
        first_ask_order: LimitOrder = self.inventory_skew_single_order_strategy_delayed_fill.active_asks[0][1]
        # Price does not change based on filled price
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("0.188489"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.81151"), first_ask_order.quantity)

    def test_inventory_skew_multiple_order_strategy(self):
        self.clock.add_iterator(self.inventory_skew_multiple_order_strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(5, len(self.inventory_skew_multiple_order_strategy.active_bids))
        self.assertEqual(5, len(self.inventory_skew_multiple_order_strategy.active_asks))

        first_bid_order: LimitOrder = self.inventory_skew_multiple_order_strategy.active_bids[0][1]
        first_ask_order: LimitOrder = self.inventory_skew_multiple_order_strategy.active_asks[0][1]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("0.181818"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.81818"), first_ask_order.quantity)

        last_bid_order: LimitOrder = self.inventory_skew_multiple_order_strategy.active_bids[-1][1]
        last_ask_order: LimitOrder = self.inventory_skew_multiple_order_strategy.active_asks[-1][1]
        last_bid_price = Decimal(99 * (1 - 0.01) ** 4).quantize(Decimal("0.001"))
        last_ask_price = Decimal(101 * (1 + 0.01) ** 4).quantize(Decimal("0.001"))
        self.assertAlmostEqual(last_bid_price, last_bid_order.price, 3)
        self.assertAlmostEqual(last_ask_price, last_ask_order.price, 3)
        self.assertEqual(Decimal("0.545454"), last_bid_order.quantity)
        self.assertEqual(Decimal("5.45454"), last_ask_order.quantity)

        self.simulate_maker_market_trade(True, 5.0)
        self.assertEqual(5, len(self.inventory_skew_multiple_order_strategy.active_bids))
        self.assertEqual(4, len(self.inventory_skew_multiple_order_strategy.active_asks))

        self.clock.backtest_til(self.start_timestamp + 2 * self.clock_tick_size + 1)
        self.assertEqual(1, len(self.maker_order_fill_logger.event_log))

        maker_fill: OrderFilledEvent = self.maker_order_fill_logger.event_log[0]
        self.assertEqual(TradeType.SELL, maker_fill.trade_type)
        self.assertAlmostEqual(101, maker_fill.price)
        self.assertAlmostEqual(Decimal("1.81818"), Decimal(str(maker_fill.amount)), places=4)

        self.clock.backtest_til(self.start_timestamp + 60 * self.clock_tick_size + 1)
        self.assertEqual(5, len(self.inventory_skew_multiple_order_strategy.active_bids))
        self.assertEqual(5, len(self.inventory_skew_multiple_order_strategy.active_asks))
        first_bid_order: LimitOrder = self.inventory_skew_multiple_order_strategy.active_bids[0][1]
        first_ask_order: LimitOrder = self.inventory_skew_multiple_order_strategy.active_asks[0][1]
        last_bid_order: LimitOrder = self.inventory_skew_multiple_order_strategy.active_bids[-1][1]
        last_ask_order: LimitOrder = self.inventory_skew_multiple_order_strategy.active_asks[-1][1]
        self.assertEqual(Decimal("99"), first_bid_order.price)
        self.assertEqual(Decimal("101"), first_ask_order.price)
        self.assertEqual(Decimal("0.188489"), first_bid_order.quantity)
        self.assertEqual(Decimal("1.81151"), first_ask_order.quantity)
        last_bid_price = Decimal(99 * (1 - 0.01) ** 4).quantize(Decimal("0.001"))
        last_ask_price = Decimal(101 * (1 + 0.01) ** 4).quantize(Decimal("0.001"))
        self.assertAlmostEqual(last_bid_price, last_bid_order.price, 3)
        self.assertAlmostEqual(last_ask_price, last_ask_order.price, 3)
        self.assertEqual(Decimal("0.565468"), last_bid_order.quantity)
        self.assertEqual(Decimal("5.43453"), last_ask_order.quantity)
