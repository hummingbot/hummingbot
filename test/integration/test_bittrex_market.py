#!/usr/bin/env python
import logging
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL

import asyncio
import contextlib
from decimal import Decimal
import os
import time
from typing import (
    List,
    Optional
)
import unittest

import conf
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    MarketWithdrawAssetEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    TradeFee,
    TradeType,
)
from hummingbot.market.bittrex.bittrex_market import BittrexMarket
from hummingbot.market.deposit_info import DepositInfo
from hummingbot.market.market_base import OrderType
from hummingbot.market.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill


logging.basicConfig(level=METRICS_LOG_LEVEL)


class BittrexMarketUnitTest(unittest.TestCase):
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
        MarketEvent.OrderCancelled
    ]

    market: BittrexMarket
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: BittrexMarket = BittrexMarket(
            bittrex_api_key=conf.bittrex_api_key,
            bittrex_secret_key=conf.bittrex_secret_key,
            symbols=["LTC-ETH", "XRP-ETH"]
        )
        print("Initializing Bittrex market... this will take about a minute. ")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.market)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

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
        self.db_path: str = realpath(join(__file__, "../bittrex_test.sqlite"))
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
        future: asyncio.Future = asyncio.ensure_future(asyncio.gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self.clock.run_til(next_iteration)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_get_fee(self):
        limit_fee: TradeFee = self.market.get_fee("LTC", "ETH", OrderType.LIMIT, TradeType.BUY, 1, 1)
        self.assertGreater(limit_fee.percent, 0)
        self.assertEqual(len(limit_fee.flat_fees), 0)
        market_fee: TradeFee = self.market.get_fee("LTC", "ETH", OrderType.MARKET, TradeType.BUY, 1)
        self.assertGreater(market_fee.percent, 0)
        self.assertEqual(len(market_fee.flat_fees), 0)

    def test_limit_buy(self):
        self.assertGreater(self.market.get_balance("ETH"), 0.1)
        symbol = "LTC-ETH"
        amount: Decimal = Decimal(0.02)
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

        current_bid_price: float = self.market.get_price(symbol, True)
        bid_price: Decimal = Decimal(current_bid_price + 0.005 * current_bid_price)
        quantize_bid_price: Decimal = self.market.quantize_order_price(symbol, bid_price)

        order_id = self.market.buy(symbol, quantized_amount, OrderType.LIMIT, quantize_bid_price)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: float = sum(t.amount for t in trade_events)
        quote_amount_traded: float = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(float(quantized_amount), order_completed_event.base_asset_amount)
        self.assertEqual("LTC", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, float(order_completed_event.base_asset_amount))
        self.assertAlmostEqual(quote_amount_traded, float(order_completed_event.quote_asset_amount))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_limit_sell(self):
        symbol = "LTC-ETH"
        amount: Decimal = Decimal(0.02)
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)
        current_ask_price: float = self.market.get_price(symbol, False)
        ask_price: Decimal = Decimal(current_ask_price - 0.005 * current_ask_price)
        quantize_ask_price: Decimal = self.market.quantize_order_price(symbol, ask_price)

        order_id = self.market.sell(symbol, amount, OrderType.LIMIT, quantize_ask_price)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.market_logger.event_log if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(float(quantized_amount), order_completed_event.base_asset_amount)
        self.assertEqual("LTC", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, float(order_completed_event.base_asset_amount))
        self.assertAlmostEqual(quote_amount_traded, float(order_completed_event.quote_asset_amount))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_market_buy(self):
        self.assertGreater(self.market.get_balance("ETH"), 0.1)
        symbol = "LTC-ETH"
        amount: Decimal = Decimal(0.02)
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

        order_id = self.market.buy(symbol, quantized_amount, OrderType.MARKET, 0)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: float = sum(t.amount for t in trade_events)
        quote_amount_traded: float = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(float(quantized_amount), order_completed_event.base_asset_amount)
        self.assertEqual("LTC", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, float(order_completed_event.base_asset_amount))
        self.assertAlmostEqual(quote_amount_traded, float(order_completed_event.quote_asset_amount))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_market_sell(self):
        symbol = "LTC-ETH"
        amount: Decimal = Decimal(0.02)
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

        order_id = self.market.sell(symbol, amount, OrderType.MARKET, 0)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.market_logger.event_log if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(float(quantized_amount), order_completed_event.base_asset_amount)
        self.assertEqual("LTC", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, float(order_completed_event.base_asset_amount))
        self.assertAlmostEqual(quote_amount_traded, float(order_completed_event.quote_asset_amount))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_cancel_order(self):
        self.assertGreater(self.market.get_balance("ETH"), 1)
        symbol = "XRP-ETH"

        current_bid_price: float = self.market.get_price(symbol, True)
        amount: Decimal = Decimal(1 / current_bid_price)

        bid_price: Decimal = Decimal(current_bid_price - 0.1 * current_bid_price)
        quantize_bid_price: Decimal = self.market.quantize_order_price(symbol, bid_price)
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

        client_order_id = self.market.buy(symbol, quantized_amount, OrderType.LIMIT, quantize_bid_price)
        self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        self.market.cancel(symbol, client_order_id)
        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event
        self.assertEqual(order_cancelled_event.order_id, client_order_id)

    def test_cancel_all(self):
        symbol = "XRP-ETH"
        bid_price: float = self.market.get_price(symbol, True) * 0.5
        ask_price: float = self.market.get_price(symbol, False) * 2
        bid_amount: Decimal = Decimal(1 / bid_price)
        ask_amount: Decimal = Decimal('3.64495247')  # Min. trade size in XRP-ETH as of 30 Sep 2019
        quantized_bid_amount: Decimal = self.market.quantize_order_amount(symbol, bid_amount)
        quantized_ask_amount: Decimal = self.market.quantize_order_amount(symbol, ask_amount)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.market.quantize_order_price(symbol, Decimal(bid_price * 0.7))
        quantize_ask_price: Decimal = self.market.quantize_order_price(symbol, Decimal(ask_price * 1.5))

        self.market.buy(symbol, quantized_bid_amount, OrderType.LIMIT, quantize_bid_price)
        self.market.sell(symbol, quantized_ask_amount, OrderType.LIMIT, quantize_ask_price)
        self.run_parallel(asyncio.sleep(1))
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    # @unittest.skipUnless(any("test_list_orders" in arg for arg in sys.argv), "List order test requires manual action.")
    def test_list_orders(self):
        self.assertGreater(self.market.get_balance("ETH"), 0.1)
        symbol = "LTC-ETH"
        amount: Decimal = Decimal(0.02)
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

        current_bid_price: float = self.market.get_price(symbol, True)
        bid_price: Decimal = Decimal(0.7 * current_bid_price)
        quantize_bid_price: Decimal = self.market.quantize_order_price(symbol, bid_price)

        self.market.buy(symbol, quantized_amount, OrderType.LIMIT, quantize_bid_price)
        self.run_parallel(asyncio.sleep(1))
        [order_details] = self.run_parallel(self.market.list_orders())
        self.assertGreaterEqual(len(order_details), 1)

        self.market_logger.clear()

    def test_deposit_info(self):
        [deposit_info] = self.run_parallel(
            self.market.get_deposit_info("ETH")
        )
        deposit_info: DepositInfo = deposit_info
        self.assertIsInstance(deposit_info, DepositInfo)
        self.assertGreater(len(deposit_info.address), 0)

    @unittest.skipUnless(any("test_withdraw" in arg for arg in sys.argv), "Withdraw test requires manual action.")
    def test_withdraw(self):
        # Ensure the market account has enough balance for withdraw testing.
        self.assertGreaterEqual(self.market.get_balance("ZRX"), 1)

        # Withdraw ZRX from Bittrex to test wallet.
        self.market.withdraw(self.wallet.address, "ZRX", 1)
        [withdraw_asset_event] = self.run_parallel(
            self.market_logger.wait_for(MarketWithdrawAssetEvent)
        )
        withdraw_asset_event: MarketWithdrawAssetEvent = withdraw_asset_event
        self.assertEqual(self.wallet.address, withdraw_asset_event.to_address)
        self.assertEqual("ZRX", withdraw_asset_event.asset_name)
        self.assertEqual(1, withdraw_asset_event.amount)
        self.assertEqual(withdraw_asset_event.fee_amount, 0)

    def test_orders_saving_and_restoration(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        symbol: str = "LTC-ETH"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            self.assertEqual(0, len(self.market.tracking_states))

            # Try to put limit buy order for 0.04 ETH, and watch for order creation event.
            current_bid_price: float = self.market.get_price(symbol, True)
            bid_price: Decimal = Decimal(current_bid_price * 0.8)
            quantize_bid_price: Decimal = self.market.quantize_order_price(symbol, bid_price)

            amount: Decimal = Decimal(0.04)
            quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

            order_id = self.market.buy(symbol, quantized_amount, OrderType.LIMIT, quantize_bid_price)
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
            self.market: BittrexMarket = BittrexMarket(
                bittrex_api_key=conf.bittrex_api_key,
                bittrex_secret_key=conf.bittrex_secret_key,
                symbols=["LTC-ETH", "XRP-ETH"]
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
            self.market.cancel(symbol, order_id)
            self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
            order_id = None
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.assertEqual(0, len(saved_market_states.saved_state))
        finally:
            if order_id is not None:
                self.market.cancel(symbol, order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)

    def test_order_fill_record(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        symbol: str = "LTC-ETH"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy 0.04 ETH from the exchange, and watch for completion event.
            amount: Decimal = Decimal(0.04)
            order_id = self.market.buy(symbol, amount)
            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logs
            self.market_logger.clear()

            # Try to sell back the same amount of ETH to the exchange, and watch for completion event.
            amount = Decimal(buy_order_completed_event.base_asset_amount)
            order_id = self.market.sell(symbol, amount)
            [sell_order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))

            # Query the persisted trade logs
            trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
            self.assertEqual(2, len(trade_fills))
            buy_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
            sell_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "SELL"]
            self.assertEqual(1, len(buy_fills))
            self.assertEqual(1, len(sell_fills))

            order_id = None

        finally:
            if order_id is not None:
                self.market.cancel(symbol, order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)


if __name__ == "__main__":
    unittest.main()
