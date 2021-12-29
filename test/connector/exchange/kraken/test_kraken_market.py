#!/usr/bin/env python
import time
from os import unlink
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

from hummingbot.connector.exchange.kraken.kraken_exchange import KrakenExchange
from hummingbot.connector.exchange.kraken.kraken_utils import convert_to_exchange_trading_pair
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.trade_fill import TradeFill
from hummingbot.core.event.events import (
    OrderType
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    TradeType,
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
import asyncio
import contextlib
import logging
from typing import (
    Optional,
    List,
)
from decimal import Decimal
import unittest
import conf

PAIR = "ETH-USDC"
BASE = "ETH"
QUOTE = "USDC"


class KrakenExchangeUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderFilled,
        MarketEvent.OrderCancelled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled
    ]

    market: KrakenExchange
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()

        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: KrakenExchange = KrakenExchange(
            conf.kraken_api_key,
            conf.kraken_secret_key,
            trading_pairs=[PAIR]
        )

        cls.count = 0

        print("Initializing Kraken market... this will take about a minute. ")
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
            cls.count += 1
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../kraken_test.sqlite"))
        try:
            unlink(self.db_path)
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
        return self.run_async(self.run_parallel_async(*tasks))

    def run_async(self, task):
        return self.ev_loop.run_until_complete(task)

    def sleep(self, t=1.0):
        self.run_parallel(asyncio.sleep(t))

    def test_get_fee(self):
        limit_fee: AddedToCostTradeFee = self.market.get_fee(BASE, QUOTE, OrderType.LIMIT_MAKER, TradeType.BUY, 1, 1)
        self.assertGreater(limit_fee.percent, 0)
        self.assertEqual(len(limit_fee.flat_fees), 0)
        market_fee: AddedToCostTradeFee = self.market.get_fee(BASE, QUOTE, OrderType.LIMIT, TradeType.BUY, 1)
        self.assertGreater(market_fee.percent, 0)
        self.assertEqual(len(market_fee.flat_fees), 0)

    def test_fee_overrides_config(self):
        fee_overrides_config_map["kraken_taker_fee"].value = None
        taker_fee: AddedToCostTradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.0026"), taker_fee.percent)
        fee_overrides_config_map["kraken_taker_fee"].value = Decimal('0.2')
        taker_fee: AddedToCostTradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.002"), taker_fee.percent)
        fee_overrides_config_map["kraken_maker_fee"].value = None
        maker_fee: AddedToCostTradeFee = self.market.get_fee("LINK",
                                                             "ETH",
                                                             OrderType.LIMIT_MAKER,
                                                             TradeType.BUY,
                                                             Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.0016"), maker_fee.percent)
        fee_overrides_config_map["kraken_maker_fee"].value = Decimal('0.5')
        maker_fee: AddedToCostTradeFee = self.market.get_fee("LINK",
                                                             "ETH",
                                                             OrderType.LIMIT_MAKER,
                                                             TradeType.BUY,
                                                             Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.005"), maker_fee.percent)

    def place_order(self, is_buy, trading_pair, amount, order_type, price):
        order_id = None
        if is_buy:
            order_id = self.market.buy(trading_pair, amount, order_type, price)
        else:
            order_id = self.market.sell(trading_pair, amount, order_type, price)
        return order_id

    def cancel_order(self, trading_pair, order_id):
        self.market.cancel(trading_pair, order_id)

    def test_limit_taker_buy(self):
        self.assertGreater(self.market.get_balance(QUOTE), 6)
        trading_pair = PAIR

        self.sleep(3)
        price: Decimal = self.market.get_price(trading_pair, True)
        amount: Decimal = Decimal("0.02")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id = self.place_order(
            True,
            trading_pair,
            quantized_amount,
            OrderType.LIMIT,
            price
        )
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent) and t.amount is not None]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual(BASE, order_completed_event.base_asset)
        self.assertEqual(QUOTE, order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_limit_sell(self):
        self.assertGreater(self.market.get_balance(BASE), 0.02)
        trading_pair = PAIR

        self.sleep(3)
        price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = Decimal("0.02")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id = self.place_order(
            False,
            trading_pair,
            quantized_amount,
            OrderType.LIMIT,
            price
        )
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent) and t.amount is not None]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual(BASE, order_completed_event.base_asset)
        self.assertEqual(QUOTE, order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def underpriced_limit_buy(self):
        self.assertGreater(self.market.get_balance(QUOTE), 4)
        trading_pair = PAIR

        current_bid_price: Decimal = self.market.get_price(trading_pair, True)
        bid_price: Decimal = current_bid_price * Decimal('0.005')
        quantized_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)

        amount: Decimal = Decimal("0.02")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id = self.place_order(
            True,
            trading_pair,
            quantized_amount,
            OrderType.LIMIT_MAKER,
            quantized_bid_price
        )

        return order_id

    def underpriced_limit_buy_multiple(self, num):
        order_ids = []
        for _ in range(num):
            order_ids.append(self.underpriced_limit_buy())
            self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        return order_ids

    def test_cancel_order(self):
        order_id = self.underpriced_limit_buy()
        self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))

        self.cancel_order(PAIR, order_id)

        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event
        self.assertEqual(order_cancelled_event.order_id, order_id)

    def test_cancel_all(self):
        order_ids = self.underpriced_limit_buy_multiple(2)

        cancelled_orders = self.run_async(self.market.cancel_all(10.))
        self.assertEqual([order.order_id for order in cancelled_orders], order_ids)
        self.assertTrue([order.success for order in cancelled_orders])

    def test_order_saving_and_restoration(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            self.assertEqual(0, len(self.market.tracking_states))

            # Try to put limit buy order for 0.02 ETH at fraction of USDC market price, and watch for order creation event.
            order_id = self.underpriced_limit_buy()
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
            self.market: KrakenExchange = KrakenExchange(
                conf.kraken_api_key,
                conf.kraken_secret_key,
                trading_pairs=[PAIR]
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
            self.market.cancel(PAIR, order_id)
            self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
            order_id = None
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.assertEqual(0, len(saved_market_states.saved_state))
        finally:
            if order_id is not None:
                self.market.cancel(PAIR, order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            unlink(self.db_path)

    def test_order_fill_record(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy 0.02 ETH from the exchange, and watch for completion event.
            price: Decimal = self.market.get_price(PAIR, True)
            amount: Decimal = Decimal("0.02")
            quantized_amount: Decimal = self.market.quantize_order_amount(PAIR, amount)
            order_id = self.place_order(
                True,
                PAIR,
                quantized_amount,
                OrderType.LIMIT,
                price
            )
            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logs
            self.market_logger.clear()

            # Try to sell back the same amount of ETH to the exchange, and watch for completion event.
            price: Decimal = self.market.get_price(PAIR, False)
            amount = buy_order_completed_event.base_asset_amount
            quantized_amount: Decimal = self.market.quantize_order_amount(PAIR, amount)
            order_id = self.place_order(
                False,
                PAIR,
                quantized_amount,
                OrderType.LIMIT,
                price
            )
            [sell_order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))

            # Query the persisted trade logs
            trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
            self.assertGreaterEqual(len(trade_fills), 2)
            buy_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
            sell_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "SELL"]
            self.assertGreaterEqual(len(buy_fills), 1)
            self.assertGreaterEqual(len(sell_fills), 1)

            order_id = None

        finally:
            if order_id is not None:
                self.market.cancel(PAIR, order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            unlink(self.db_path)

    def test_pair_convesion(self):
        for pair in self.market.trading_rules:
            exchange_pair = convert_to_exchange_trading_pair(pair)
            self.assertTrue(exchange_pair in self.market.order_books)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
