import logging
import re
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

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
    MarketOrderFailureEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    TradeFee,
    TradeType,
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.connector.exchange.eterbase.eterbase_exchange import EterbaseExchange
from hummingbot.connector.exchange.eterbase.eterbase_utils import convert_to_exchange_trading_pair
from hummingbot.core.event.events import OrderType
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill


logging.basicConfig(level=METRICS_LOG_LEVEL)


class EterbaseExchangeUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderFilled,
        MarketEvent.OrderCancelled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderFailure
    ]

    market: EterbaseExchange
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: EterbaseExchange = EterbaseExchange(
            conf.eterbase_api_key,
            conf.eterbase_secret_key,
            conf.eterbase_account,
            trading_pairs=["ETH-EUR"]
        )
        print("Initializing Eterbase market... this will take about a minute.")
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
        self.db_path: str = realpath(join(__file__, "../eterbase_test.sqlite"))
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
        limit_fee: TradeFee = self.market.get_fee("ETH", "EUR", OrderType.LIMIT_MAKER, TradeType.BUY, 1, 1)
        self.assertGreaterEqual(limit_fee.percent, 0)
        self.assertEqual(len(limit_fee.flat_fees), 0)
        market_fee: TradeFee = self.market.get_fee("ETH", "EUR", OrderType.LIMIT, TradeType.BUY, 1)
        self.assertGreaterEqual(market_fee.percent, 0)
        self.assertEqual(len(market_fee.flat_fees), 0)

    def test_limit_maker_rejections(self):
        trading_pair = "ETH-EUR"

        # Try to put a buy limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.market.get_price(trading_pair, True) * Decimal('1.02')
        price: Decimal = self.market.quantize_order_price(trading_pair, price)
        amount = self.market.quantize_order_amount(trading_pair, Decimal("0.01"))

        order_id = self.market.buy(trading_pair, amount, OrderType.LIMIT_MAKER, price)
        [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

        self.market_logger.clear()

        # Try to put a sell limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.market.get_price(trading_pair, True) * Decimal('0.98')
        price: Decimal = self.market.quantize_order_price(trading_pair, price)
        amount = self.market.quantize_order_amount(trading_pair, Decimal("0.01"))

        order_id = self.market.sell(trading_pair, amount, OrderType.LIMIT_MAKER, price)
        [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

    def test_limit_makers_unfilled(self):
        trading_pair = "ETH-EUR"
        bid_price: Decimal = self.market.get_price(trading_pair, True) * Decimal("0.5")
        ask_price: Decimal = self.market.get_price(trading_pair, False) * 2
        amount: Decimal = 10 / bid_price
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # Intentionally setting invalid price to prevent getting filled.
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price * Decimal("0.7"))
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price * Decimal("1.5"))

        order_id = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_bid_price)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id, order_created_event.order_id)

        order_id_2 = self.market.sell(trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_ask_price)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id_2, order_created_event.order_id)

        self.run_parallel(asyncio.sleep(1))
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    # NOTE that orders of non-USD pairs (including USDC pairs) are LIMIT only
    def test_limit_taker_buy(self):
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.2"))
        trading_pair = "ETH-EUR"
        amount: Decimal = Decimal("0.02")
        quantize_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        current_ask_price: Decimal = self.market.get_price(trading_pair, False)
        ask_price: Decimal = current_ask_price - Decimal("0.05") * current_ask_price
        quantize_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price)

        order_id = self.market.buy(trading_pair, quantize_amount, OrderType.LIMIT, quantize_price)

        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event

        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        # not possible to exactly defined, as reuest is in COSTS (amount*price)
        self.assertAlmostEqual(quantize_amount * quantize_price, order_completed_event.quote_asset_amount, 1)

        sig_dig = abs((quantize_amount * quantize_price).as_tuple().exponent) - 1

        str_quant_cost = ("{0:." + str(sig_dig) + "g}").format(quantize_amount * quantize_price)
        str_order_cost = ("{0:." + str(sig_dig) + "g}").format(order_completed_event.quote_asset_amount)

        quant_cost = None
        order_cost = None

        if re.search(r'e+', str(quant_cost)):
            quant_cost = Decimal("{:.0f}".format(Decimal(str_quant_cost)))
            order_cost = Decimal("{:.0f}".format(Decimal(str_order_cost)))
        else:
            quant_cost = Decimal(str_quant_cost)
            order_cost = Decimal(str_order_cost)

        self.assertAlmostEqual(quant_cost, order_cost)

        self.assertEqual("ETH", order_completed_event.base_asset)
        self.assertEqual("EUR", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    # NOTE that orders of non-USD pairs (including USDC pairs) are LIMIT only
    def test_limit_taker_sell(self):
        trading_pair = "ETH-EUR"
        price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = Decimal("0.02")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id = self.market.sell(trading_pair, amount, OrderType.LIMIT, price)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.market_logger.event_log if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.price * t.amount for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("ETH", order_completed_event.base_asset)
        self.assertEqual("EUR", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount, 1)
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_cancel_order(self):
        trading_pair = "ETH-EUR"

        current_bid_price: Decimal = self.market.get_price(trading_pair, True)
        amount: Decimal = 10 / current_bid_price
        self.assertGreater(self.market.get_balance("ETH"), amount)

        bid_price: Decimal = current_bid_price - Decimal("0.1") * current_bid_price
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        client_order_id = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_bid_price)
        self.market.cancel(trading_pair, client_order_id)
        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event
        self.assertEqual(order_cancelled_event.order_id, client_order_id)

    def test_cancel_all(self):
        trading_pair = "ETH-EUR"
        bid_price: Decimal = self.market.get_price(trading_pair, True) * Decimal("0.5")
        ask_price: Decimal = self.market.get_price(trading_pair, False) * 2
        amount: Decimal = 10 / bid_price
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price * Decimal("0.7"))
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price * Decimal("1.5"))

        self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_bid_price)
        self.market.sell(trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_ask_price)
        self.run_parallel(asyncio.sleep(1))
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    @unittest.skipUnless(any("test_list_orders" in arg for arg in sys.argv), "List order test requires manual action.")
    def test_list_orders(self):
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.1"))
        trading_pair = "ETH-EUR"
        amount: Decimal = Decimal("0.02")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        current_bid_price: Decimal = self.market.get_price(trading_pair, True)
        bid_price: Decimal = current_bid_price + Decimal("0.05") * current_bid_price
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)

        self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_bid_price)
        self.run_parallel(asyncio.sleep(1))
        [order_details] = self.run_parallel(self.market.list_orders())
        self.assertGreaterEqual(len(order_details), 1)

        self.market_logger.clear()

    def test_orders_saving_and_restoration(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "ETH-EUR"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            self.assertEqual(0, len(self.market.tracking_states))

            # Try to put limit buy order for 0.04 ETH, and watch for order creation event.
            current_bid_price: Decimal = self.market.get_price(trading_pair, True)
            bid_price: Decimal = current_bid_price * Decimal("0.8")
            quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)

            amount: Decimal = Decimal("0.04")
            quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

            order_id = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_bid_price)
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
            print("close out the current market and start another market")
            # Close out the current market and start another market.
            self.clock.remove_iterator(self.market)
            for event_tag in self.events:
                self.market.remove_listener(event_tag, self.market_logger)
            self.market: EterbaseExchange = EterbaseExchange(
                eterbase_api_key=conf.eterbase_api_key,
                eterbase_secret_key=conf.eterbase_secret_key,
                eterbase_account=conf.eterbase_account,
                trading_pairs=["ETHUSDT", "ETH-EUR"]
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
            os.unlink(self.db_path)

    def test_order_fill_record(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "ETH-EUR"

        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy 0.04 ETH from the exchange, and watch for completion event.
            amount: Decimal = Decimal("0.01")

            current_ask_price: Decimal = self.market.get_price(trading_pair, False)
            ask_price: Decimal = current_ask_price - Decimal("0.05") * current_ask_price
            quantize_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price)

            order_id = self.market.buy(trading_pair, amount, OrderType.LIMIT, quantize_price)

            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logger
            self.market_logger.clear()

            # Try to sell back the same amount of ETH to the exchange, and watch for completion event.
            price: Decimal = self.market.get_price(trading_pair, False)
            amount = buy_order_completed_event.base_asset_amount
            order_id = self.market.sell(trading_pair, amount, OrderType.LIMIT, price)
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
                self.market.cancel(trading_pair, order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)

    def test_pair_convesion(self):
        for pair in self.market.trading_rules:
            exchange_pair = convert_to_exchange_trading_pair(pair)
            self.assertTrue(exchange_pair in self.market.order_books)


if __name__ == "__main__":
    unittest.main()
