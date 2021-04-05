from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
import asyncio
import logging
from decimal import Decimal
import unittest
import contextlib
import time
import os
from typing import List
import conf
import math

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.core.utils.async_utils import safe_gather, safe_ensure_future
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
    OrderCancelledEvent
)
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.trade_fill import TradeFill
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.connector.exchange.hitbtc.hitbtc_exchange import HitbtcExchange

logging.basicConfig(level=METRICS_LOG_LEVEL)

API_KEY = conf.hitbtc_api_key
API_SECRET = conf.hitbtc_secret_key


class HitbtcExchangeUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderFailure
    ]
    connector: HitbtcExchange
    event_logger: EventLogger
    trading_pair = "BTC-USDT"
    base_token, quote_token = trading_pair.split("-")
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        global MAINNET_RPC_URL

        cls.ev_loop = asyncio.get_event_loop()

        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.connector: HitbtcExchange = HitbtcExchange(
            hitbtc_api_key=API_KEY,
            hitbtc_secret_key=API_SECRET,
            trading_pairs=[cls.trading_pair],
            trading_required=True
        )
        print("Initializing Hitbtc market... this will take about a minute.")
        cls.clock.add_iterator(cls.connector)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()

    @classmethod
    async def wait_til_ready(cls, connector = None):
        if connector is None:
            connector = cls.connector
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if connector.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../connector_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.event_logger = EventLogger()
        for event_tag in self.events:
            self.connector.add_listener(event_tag, self.event_logger)

    def tearDown(self):
        for event_tag in self.events:
            self.connector.remove_listener(event_tag, self.event_logger)
        self.event_logger = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def _place_order(self, is_buy, amount, order_type, price, ex_order_id) -> str:
        if is_buy:
            cl_order_id = self.connector.buy(self.trading_pair, amount, order_type, price)
        else:
            cl_order_id = self.connector.sell(self.trading_pair, amount, order_type, price)
        return cl_order_id

    def _cancel_order(self, cl_order_id, connector=None):
        if connector is None:
            connector = self.connector
        return connector.cancel(self.trading_pair, cl_order_id)

    def test_estimate_fee(self):
        maker_fee = self.connector.estimate_fee_pct(True)
        self.assertAlmostEqual(maker_fee, Decimal("0.001"))
        taker_fee = self.connector.estimate_fee_pct(False)
        self.assertAlmostEqual(taker_fee, Decimal("0.0025"))

    def test_buy_and_sell(self):
        price = self.connector.get_price(self.trading_pair, True) * Decimal("1.02")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0002"))
        quote_bal = self.connector.get_available_balance(self.quote_token)
        base_bal = self.connector.get_available_balance(self.base_token)

        order_id = self._place_order(True, amount, OrderType.LIMIT, price, 1)
        order_completed_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCompletedEvent))
        self.ev_loop.run_until_complete(asyncio.sleep(5))
        trade_events = [t for t in self.event_logger.event_log if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(amount, order_completed_event.base_asset_amount)
        self.assertEqual("BTC", order_completed_event.base_asset)
        self.assertEqual("USDT", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and str(event.order_id) == str(order_id)
                             for event in self.event_logger.event_log]))

        # check available quote balance gets updated, we need to wait a bit for the balance message to arrive
        expected_quote_bal = quote_bal - quote_amount_traded
        # self.ev_loop.run_until_complete(asyncio.sleep(1))
        self.ev_loop.run_until_complete(self.connector._update_balances())
        self.assertAlmostEqual(expected_quote_bal, self.connector.get_available_balance(self.quote_token), 1)

        # Reset the logs
        self.event_logger.clear()

        # Try to sell back the same amount to the exchange, and watch for completion event.
        price = self.connector.get_price(self.trading_pair, True) * Decimal("0.98")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0002"))
        order_id = self._place_order(False, amount, OrderType.LIMIT, price, 2)
        order_completed_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCompletedEvent))
        trade_events = [t for t in self.event_logger.event_log if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(amount, order_completed_event.base_asset_amount)
        self.assertEqual("BTC", order_completed_event.base_asset)
        self.assertEqual("USDT", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.event_logger.event_log]))

        # check available base balance gets updated, we need to wait a bit for the balance message to arrive
        expected_base_bal = base_bal
        self.ev_loop.run_until_complete(asyncio.sleep(1))
        self.ev_loop.run_until_complete(self.connector._update_balances())
        self.ev_loop.run_until_complete(asyncio.sleep(5))
        self.assertAlmostEqual(expected_base_bal, self.connector.get_available_balance(self.base_token), 5)

    def test_limit_makers_unfilled(self):
        price = self.connector.get_price(self.trading_pair, True) * Decimal("0.8")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0002"))
        self.ev_loop.run_until_complete(asyncio.sleep(1))
        self.ev_loop.run_until_complete(self.connector._update_balances())
        self.ev_loop.run_until_complete(asyncio.sleep(2))
        quote_bal = self.connector.get_available_balance(self.quote_token)

        cl_order_id = self._place_order(True, amount, OrderType.LIMIT_MAKER, price, 1)
        order_created_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCreatedEvent))
        self.assertEqual(cl_order_id, order_created_event.order_id)
        # check available quote balance gets updated, we need to wait a bit for the balance message to arrive
        taker_fee = self.connector.estimate_fee_pct(False)
        quote_amount = ((price * amount))
        quote_amount = ((price * amount) * (Decimal("1") + taker_fee))
        expected_quote_bal = quote_bal - quote_amount
        self.ev_loop.run_until_complete(asyncio.sleep(1))
        self.ev_loop.run_until_complete(self.connector._update_balances())
        self.ev_loop.run_until_complete(asyncio.sleep(2))

        self.assertAlmostEqual(expected_quote_bal, self.connector.get_available_balance(self.quote_token), 5)
        self._cancel_order(cl_order_id)
        event = self.ev_loop.run_until_complete(self.event_logger.wait_for(OrderCancelledEvent))
        self.assertEqual(cl_order_id, event.order_id)

        price = self.connector.get_price(self.trading_pair, True) * Decimal("1.2")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0002"))

        cl_order_id = self._place_order(False, amount, OrderType.LIMIT_MAKER, price, 2)
        order_created_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCreatedEvent))
        self.assertEqual(cl_order_id, order_created_event.order_id)
        self._cancel_order(cl_order_id)
        event = self.ev_loop.run_until_complete(self.event_logger.wait_for(OrderCancelledEvent))
        self.assertEqual(cl_order_id, event.order_id)

    # # @TODO: find a way to create "rejected"
    # def test_limit_maker_rejections(self):
    #     price = self.connector.get_price(self.trading_pair, True) * Decimal("1.2")
    #     price = self.connector.quantize_order_price(self.trading_pair, price)
    #     amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.000001"))
    #     cl_order_id = self._place_order(True, amount, OrderType.LIMIT_MAKER, price, 1)
    #     event = self.ev_loop.run_until_complete(self.event_logger.wait_for(OrderCancelledEvent))
    #     self.assertEqual(cl_order_id, event.order_id)

    #     price = self.connector.get_price(self.trading_pair, False) * Decimal("0.8")
    #     price = self.connector.quantize_order_price(self.trading_pair, price)
    #     amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.000001"))
    #     cl_order_id = self._place_order(False, amount, OrderType.LIMIT_MAKER, price, 2)
    #     event = self.ev_loop.run_until_complete(self.event_logger.wait_for(OrderCancelledEvent))
    #     self.assertEqual(cl_order_id, event.order_id)

    def test_cancel_all(self):
        bid_price = self.connector.get_price(self.trading_pair, True)
        ask_price = self.connector.get_price(self.trading_pair, False)
        bid_price = self.connector.quantize_order_price(self.trading_pair, bid_price * Decimal("0.9"))
        ask_price = self.connector.quantize_order_price(self.trading_pair, ask_price * Decimal("1.1"))
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0002"))

        buy_id = self._place_order(True, amount, OrderType.LIMIT, bid_price, 1)
        sell_id = self._place_order(False, amount, OrderType.LIMIT, ask_price, 2)

        self.ev_loop.run_until_complete(asyncio.sleep(1))
        asyncio.ensure_future(self.connector.cancel_all(5))
        self.ev_loop.run_until_complete(self.event_logger.wait_for(OrderCancelledEvent))
        self.ev_loop.run_until_complete(asyncio.sleep(1))
        cancel_events = [t for t in self.event_logger.event_log if isinstance(t, OrderCancelledEvent)]
        self.assertEqual({buy_id, sell_id}, {o.order_id for o in cancel_events})

    def test_order_quantized_values(self):
        bid_price: Decimal = self.connector.get_price(self.trading_pair, True)
        ask_price: Decimal = self.connector.get_price(self.trading_pair, False)
        mid_price: Decimal = (bid_price + ask_price) / 2

        # Make sure there's enough balance to make the limit orders.
        self.assertGreater(self.connector.get_balance("BTC"), Decimal("0.0005"))
        self.assertGreater(self.connector.get_balance("USDT"), Decimal("10"))

        # Intentionally set some prices with too many decimal places s.t. they
        # need to be quantized. Also, place them far away from the mid-price s.t. they won't
        # get filled during the test.
        bid_price = self.connector.quantize_order_price(self.trading_pair, mid_price * Decimal("0.9333192292111341"))
        ask_price = self.connector.quantize_order_price(self.trading_pair, mid_price * Decimal("1.1492431474884933"))
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.000223456"))

        # Test bid order
        cl_order_id_1 = self._place_order(True, amount, OrderType.LIMIT, bid_price, 1)
        # Wait for the order created event and examine the order made
        self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCreatedEvent))

        # Test ask order
        cl_order_id_2 = self._place_order(False, amount, OrderType.LIMIT, ask_price, 1)
        # Wait for the order created event and examine and order made
        self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCreatedEvent))

        self._cancel_order(cl_order_id_1)
        self.ev_loop.run_until_complete(self.event_logger.wait_for(OrderCancelledEvent))
        self._cancel_order(cl_order_id_2)
        self.ev_loop.run_until_complete(self.event_logger.wait_for(OrderCancelledEvent))

    def test_orders_saving_and_restoration(self):
        config_path = "test_config"
        strategy_name = "test_strategy"
        sql = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id = None
        recorder = MarketsRecorder(sql, [self.connector], config_path, strategy_name)
        recorder.start()

        try:
            self.connector._in_flight_orders.clear()
            self.assertEqual(0, len(self.connector.tracking_states))

            # Try to put limit buy order for 0.02 ETH worth of ZRX, and watch for order creation event.
            current_bid_price: Decimal = self.connector.get_price(self.trading_pair, True)
            price: Decimal = current_bid_price * Decimal("0.8")
            price = self.connector.quantize_order_price(self.trading_pair, price)

            amount: Decimal = Decimal("0.0002")
            amount = self.connector.quantize_order_amount(self.trading_pair, amount)

            cl_order_id = self._place_order(True, amount, OrderType.LIMIT_MAKER, price, 1)
            order_created_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCreatedEvent))
            self.assertEqual(cl_order_id, order_created_event.order_id)

            # Verify tracking states
            self.assertEqual(1, len(self.connector.tracking_states))
            self.assertEqual(cl_order_id, list(self.connector.tracking_states.keys())[0])

            # Verify orders from recorder
            recorded_orders: List[Order] = recorder.get_orders_for_config_and_market(config_path, self.connector)
            self.assertEqual(1, len(recorded_orders))
            self.assertEqual(cl_order_id, recorded_orders[0].id)

            # Verify saved market states
            saved_market_states: MarketState = recorder.get_market_states(config_path, self.connector)
            self.assertIsNotNone(saved_market_states)
            self.assertIsInstance(saved_market_states.saved_state, dict)
            self.assertGreater(len(saved_market_states.saved_state), 0)

            # Close out the current market and start another market.
            self.connector.stop(self._clock)
            self.ev_loop.run_until_complete(asyncio.sleep(5))
            self.clock.remove_iterator(self.connector)
            for event_tag in self.events:
                self.connector.remove_listener(event_tag, self.event_logger)
            # Clear the event loop
            self.event_logger.clear()
            new_connector = HitbtcExchange(API_KEY, API_SECRET, [self.trading_pair], True)
            for event_tag in self.events:
                new_connector.add_listener(event_tag, self.event_logger)
            recorder.stop()
            recorder = MarketsRecorder(sql, [new_connector], config_path, strategy_name)
            recorder.start()
            saved_market_states = recorder.get_market_states(config_path, new_connector)
            self.clock.add_iterator(new_connector)
            self.ev_loop.run_until_complete(self.wait_til_ready(new_connector))
            self.assertEqual(0, len(new_connector.limit_orders))
            self.assertEqual(0, len(new_connector.tracking_states))
            new_connector.restore_tracking_states(saved_market_states.saved_state)
            self.assertEqual(1, len(new_connector.limit_orders))
            self.assertEqual(1, len(new_connector.tracking_states))

            # Cancel the order and verify that the change is saved.
            self._cancel_order(cl_order_id, new_connector)
            self.ev_loop.run_until_complete(self.event_logger.wait_for(OrderCancelledEvent))
            recorder.save_market_states(config_path, new_connector)
            order_id = None
            self.assertEqual(0, len(new_connector.limit_orders))
            self.assertEqual(0, len(new_connector.tracking_states))
            saved_market_states = recorder.get_market_states(config_path, new_connector)
            self.assertEqual(0, len(saved_market_states.saved_state))
        finally:
            if order_id is not None:
                self.connector.cancel(self.trading_pair, cl_order_id)
                self.run_parallel(self.event_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)

    def test_update_last_prices(self):
        # This is basic test to see if order_book last_trade_price is initiated and updated.
        for order_book in self.connector.order_books.values():
            for _ in range(5):
                self.ev_loop.run_until_complete(asyncio.sleep(1))
                self.assertFalse(math.isnan(order_book.last_trade_price))

    def test_filled_orders_recorded(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id = None
        recorder = MarketsRecorder(sql, [self.connector], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy some token from the exchange, and watch for completion event.
            price = self.connector.get_price(self.trading_pair, True) * Decimal("1.05")
            price = self.connector.quantize_order_price(self.trading_pair, price)
            amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0002"))

            order_id = self._place_order(True, amount, OrderType.LIMIT, price, 1)
            self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCompletedEvent))
            self.ev_loop.run_until_complete(asyncio.sleep(1))

            # Reset the logs
            self.event_logger.clear()

            # Try to sell back the same amount to the exchange, and watch for completion event.
            price = self.connector.get_price(self.trading_pair, True) * Decimal("0.95")
            price = self.connector.quantize_order_price(self.trading_pair, price)
            amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0002"))
            order_id = self._place_order(False, amount, OrderType.LIMIT, price, 2)
            self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCompletedEvent))
            self.ev_loop.run_until_complete(asyncio.sleep(1))

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
                self.connector.cancel(self.trading_pair, order_id)
                self.run_parallel(self.event_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)
