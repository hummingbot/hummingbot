import asyncio
import contextlib
import logging
import os
import sys
import time
import unittest
from decimal import Decimal
from os.path import join, realpath
from typing import (
    List,
    Optional,
)

import conf
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    OrderType,
    TradeType,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    OrderCancelledEvent,
    BuyOrderCompletedEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.connector.exchange.bitfinex.bitfinex_exchange import BitfinexExchange
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import SQLConnectionManager, SQLConnectionType

sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)
API_KEY = conf.bitfinex_api_key
API_SECRET = conf.bitfinex_secret_key
trading_pair = "ETH-USD"
base_asset = trading_pair.split("-")[0]
quote_asset = trading_pair.split("-")[1]


class BitfinexExchangeUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.OrderCancelled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
    ]

    market: BitfinexExchange
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: BitfinexExchange = BitfinexExchange(
            API_KEY,
            API_SECRET,
            trading_pairs=[trading_pair]
        )
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.market)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if cls.market.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../bitfinex_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)

    def tearDown(self):
        for event_tag in self.events:
            self.market.remove_listener(event_tag, self.market_logger)
        self.market_logger = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self.clock.run_til(next_iteration)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_get_fee(self):
        limit_fee: AddedToCostTradeFee = self.market.get_fee(base_asset, quote_asset, OrderType.LIMIT,
                                                             TradeType.BUY, 1, 1)
        self.assertGreater(limit_fee.percent, 0)
        self.assertEqual(len(limit_fee.flat_fees), 0)
        market_fee: AddedToCostTradeFee = self.market.get_fee(base_asset, quote_asset, OrderType.MARKET,
                                                              TradeType.BUY, 1)
        self.assertGreater(market_fee.percent, 0)
        self.assertEqual(len(market_fee.flat_fees), 0)

    def test_minimum_order_size(self):
        amount = Decimal("0.001")
        quantized_amount = self.market.quantize_order_amount(trading_pair, amount)
        self.assertEqual(quantized_amount, 0)

    def test_get_balance(self):
        balance = self.market.get_balance(quote_asset)
        self.assertGreater(balance, 10)

    def test_limit_buy(self):
        amount: Decimal = Decimal("0.04")
        current_ask_price: Decimal = self.market.get_price(trading_pair, False)
        # no fill
        bid_price: Decimal = Decimal("0.9") * current_ask_price
        quantize_ask_price: Decimal = self.market.quantize_order_price(
            trading_pair,
            bid_price
        )

        order_id = self.market.buy(
            trading_pair,
            amount,
            OrderType.LIMIT,
            quantize_ask_price
        )

        # Wait for order creation event
        self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))

        # Cancel order. Automatically asserts that order is tracked
        self.market.cancel(trading_pair, order_id)

        [order_cancelled_event] = self.run_parallel(
            self.market_logger.wait_for(OrderCancelledEvent))
        self.assertEqual(order_cancelled_event.order_id, order_id)
        # # Reset the logs
        self.market_logger.clear()

    def test_limit_sell(self):
        amount: Decimal = Decimal("0.02")
        current_ask_price: Decimal = self.market.get_price(trading_pair, False)
        # for no fill
        ask_price: Decimal = Decimal("1.1") * current_ask_price
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair,
                                                                       ask_price)

        order_id = self.market.sell(trading_pair, amount, OrderType.LIMIT,
                                    quantize_ask_price)
        # Wait for order creation event
        self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))

        # Cancel order. Automatically asserts that order is tracked
        self.market.cancel(trading_pair, order_id)

        [order_cancelled_event] = self.run_parallel(
            self.market_logger.wait_for(OrderCancelledEvent))

        self.assertEqual(order_cancelled_event.order_id, order_id)

        # Reset the logs
        self.market_logger.clear()

    def test_execute_limit_buy(self):
        amount: Decimal = Decimal("0.04")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair,
                                                                      amount)

        bid_entries = self.market.order_books[trading_pair].bid_entries()

        most_top_bid = next(bid_entries)
        bid_price: Decimal = Decimal(most_top_bid.price)
        quantize_bid_price: Decimal = \
            self.market.quantize_order_price(trading_pair, bid_price)
        quantize_bid_price = quantize_bid_price * Decimal("1.1")

        order_id = self.market.buy(trading_pair,
                                   quantized_amount,
                                   OrderType.LIMIT,
                                   quantize_bid_price,
                                   )

        [order_completed_event] = self.run_parallel(
            self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount,
                               order_completed_event.base_asset_amount)
        self.assertEqual(base_asset, order_completed_event.base_asset)
        self.assertEqual(quote_asset, order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded,
                               order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded,
                               order_completed_event.quote_asset_amount)
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_execute_limit_sell(self):
        amount: Decimal = Decimal(0.02)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair,
                                                                      amount)
        ask_entries = self.market.order_books[trading_pair].ask_entries()
        most_top_ask = next(ask_entries)
        ask_price: Decimal = Decimal(most_top_ask.price)
        quantize_ask_price: Decimal = \
            self.market.quantize_order_price(trading_pair, ask_price)
        quantize_ask_price = quantize_ask_price * Decimal("0.9")

        order_id = self.market.sell(trading_pair,
                                    quantized_amount,
                                    OrderType.LIMIT,
                                    quantize_ask_price,
                                    )
        [order_completed_event] = self.run_parallel(
            self.market_logger.wait_for(SellOrderCompletedEvent))

        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount,
                               order_completed_event.base_asset_amount)
        self.assertEqual(base_asset, order_completed_event.base_asset)
        self.assertEqual(quote_asset, order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded,
                               order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded,
                               order_completed_event.quote_asset_amount)
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_orders_saving_and_restoration(self):
        self.tearDownClass()
        self.setUpClass()
        self.setUp()

        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None

        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            self.assertEqual(0, len(self.market.tracking_states))

            amount: Decimal = Decimal("0.04")
            current_ask_price: Decimal = self.market.get_price(trading_pair, False)
            bid_price: Decimal = Decimal("0.9") * current_ask_price
            quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)
            order_id = self.market.buy(trading_pair, amount, OrderType.LIMIT, quantize_ask_price)

            [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
            order_created_event: BuyOrderCreatedEvent = order_created_event
            self.assertEqual(order_id, order_created_event.order_id)

            # Verify tracking states
            self.assertEqual(1, len(self.market.tracking_states))
            self.assertEqual(order_id, list(self.market.tracking_states.keys())[0])

            # Verify orders from recorder
            recorded_orders: List[Order] = recorder.get_orders_for_config_and_market(config_path, self.market)
            self.assertEqual(1, len(recorded_orders))
            self.assertEqual(order_id, recorded_orders[0].id)

            # Verify saved market states
            saved_market_states: MarketState = recorder.get_market_states(config_path, self.market)
            self.assertIsNotNone(saved_market_states)
            self.assertIsInstance(saved_market_states.saved_state, dict)
            self.assertGreater(len(saved_market_states.saved_state), 0)

            # Close out the current market and start another market.
            self.clock.remove_iterator(self.market)
            for event_tag in self.events:
                self.market.remove_listener(event_tag, self.market_logger)
            self.market: BitfinexExchange = BitfinexExchange(
                API_KEY,
                API_SECRET,
                trading_pairs=[trading_pair]
            )
            for event_tag in self.events:
                self.market.add_listener(event_tag, self.market_logger)
            recorder.stop()
            recorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
            recorder.start()
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.clock.add_iterator(self.market)
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            self.market.restore_tracking_states(saved_market_states.saved_state)
            self.assertEqual(1, len(self.market.limit_orders))
            self.assertEqual(1, len(self.market.tracking_states))

            # Cancel the order and verify that the change is saved.
            self.run_parallel(asyncio.sleep(5.0))
            self.market.cancel(trading_pair, order_id)
            self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
            order_id = None
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.assertEqual(0, len(saved_market_states.saved_state))
        finally:
            if order_id is not None:
                self.market.cancel(trading_pair, order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            self.setUpClass()

    def test_cancel_all(self):
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        ask_price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = Decimal("0.04")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price * Decimal("0.9"))
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price * Decimal("1.1"))

        self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price)
        self.market.sell(trading_pair, quantized_amount, OrderType.LIMIT, quantize_ask_price)
        self.run_parallel(asyncio.sleep(5))
        [cancellation_results] = self.run_parallel(self.market.cancel_all(45))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)
