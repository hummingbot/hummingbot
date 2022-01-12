#!/usr/bin/env python
import logging
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
import math
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
    TradeType,
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.connector.exchange.kucoin.kucoin_exchange import KucoinExchange
from hummingbot.core.event.events import OrderType
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.core.mock_api.mock_web_server import MockWebServer
from test.connector.exchange.kucoin.fixture_kucoin import FixtureKucoin
from unittest import mock
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map


logging.basicConfig(level=METRICS_LOG_LEVEL)
API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
API_KEY = "XXX" if API_MOCK_ENABLED else conf.kucoin_api_key
API_SECRET = "YYY" if API_MOCK_ENABLED else conf.kucoin_secret_key
API_PASSPHRASE = "ZZZ" if API_MOCK_ENABLED else conf.kucoin_passphrase
API_BASE_URL = "api.kucoin.com"
EXCHANGE_ORDER_ID = 20001


class KucoinExchangeUnitTest(unittest.TestCase):
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

    market: KucoinExchange
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        if API_MOCK_ENABLED:
            cls.web_app = MockWebServer.get_instance()
            cls.web_app.add_host_to_mock(API_BASE_URL, ["/api/v1/timestamp", "/api/v1/symbols",
                                                        "/api/v1/bullet-public",
                                                        "/api/v2/market/orderbook/level2"])
            cls.web_app.start()
            cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
            cls._patcher = mock.patch("aiohttp.client.URL")
            cls._url_mock = cls._patcher.start()
            cls._url_mock.side_effect = cls.web_app.reroute_local
            cls.web_app.update_response("get", API_BASE_URL, "/api/v1/accounts", FixtureKucoin.BALANCES)

            cls._t_nonce_patcher = unittest.mock.patch(
                "hummingbot.connector.exchange.kucoin.kucoin_exchange.get_tracking_nonce")
            cls._t_nonce_mock = cls._t_nonce_patcher.start()
            cls._exch_order_id = 20001
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: KucoinExchange = KucoinExchange(
            kucoin_api_key=API_KEY,
            kucoin_passphrase=API_PASSPHRASE,
            kucoin_secret_key=API_SECRET,
            trading_pairs=["ETH-USDT"]
        )
        # Need 2nd instance of market to prevent events mixing up across tests
        cls.market_2: KucoinExchange = KucoinExchange(
            kucoin_api_key=API_KEY,
            kucoin_passphrase=API_PASSPHRASE,
            kucoin_secret_key=API_SECRET,
            trading_pairs=["ETH-USDT"]
        )
        cls.clock.add_iterator(cls.market)
        cls.clock.add_iterator(cls.market_2)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()
        if API_MOCK_ENABLED:
            cls.web_app.stop()
            cls._patcher.stop()
            cls._t_nonce_patcher.stop()

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if cls.market.ready and cls.market_2.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../kucoin_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        self.market_2_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)
            self.market_2.add_listener(event_tag, self.market_2_logger)

    def tearDown(self):
        for event_tag in self.events:
            self.market.remove_listener(event_tag, self.market_logger)
            self.market_2.remove_listener(event_tag, self.market_2_logger)
        self.market_logger = None
        self.market_2_logger = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(0.5)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_get_fee(self):
        limit_fee: AddedToCostTradeFee = self.market.get_fee("ETH", "USDT", OrderType.LIMIT_MAKER, TradeType.BUY, 1, 10)
        self.assertGreater(limit_fee.percent, 0)
        self.assertEqual(len(limit_fee.flat_fees), 0)
        market_fee: AddedToCostTradeFee = self.market.get_fee("ETH", "USDT", OrderType.LIMIT, TradeType.BUY, 1)
        self.assertGreater(market_fee.percent, 0)
        self.assertEqual(len(market_fee.flat_fees), 0)
        sell_trade_fee: AddedToCostTradeFee = self.market.get_fee(
            "ETH", "USDT", OrderType.LIMIT_MAKER, TradeType.SELL, 1, 10
        )
        self.assertGreater(sell_trade_fee.percent, 0)
        self.assertEqual(len(sell_trade_fee.flat_fees), 0)

    def order_response(self, fixture_data, nonce):
        self._t_nonce_mock.return_value = nonce
        order_resp = fixture_data.copy()
        return order_resp

    def place_order(self, is_buy, trading_pair, amount, order_type, price, nonce, post_resp, get_resp):
        global EXCHANGE_ORDER_ID
        order_id, exch_order_id = None, None
        if API_MOCK_ENABLED:
            exch_order_id = f"KUCOIN_{EXCHANGE_ORDER_ID}"
            EXCHANGE_ORDER_ID += 1
            resp = self.order_response(post_resp, nonce)
            resp["data"]["orderId"] = exch_order_id
            self.web_app.update_response("post", API_BASE_URL, "/api/v1/orders", resp)
        if is_buy:
            order_id = self.market.buy(trading_pair, amount, order_type, price)
        else:
            order_id = self.market.sell(trading_pair, amount, order_type, price)
        if API_MOCK_ENABLED:
            resp = get_resp.copy()
            resp["data"]["id"] = exch_order_id
            resp["data"]["clientOid"] = order_id
            self.web_app.update_response("get", API_BASE_URL, f"/api/v1/orders/{exch_order_id}", resp)
        return order_id, exch_order_id

    def test_fee_overrides_config(self):
        fee_overrides_config_map["kucoin_taker_fee"].value = None
        taker_fee: AddedToCostTradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.001"), taker_fee.percent)
        fee_overrides_config_map["kucoin_taker_fee"].value = Decimal('0.2')
        taker_fee: AddedToCostTradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.002"), taker_fee.percent)
        fee_overrides_config_map["kucoin_maker_fee"].value = None
        maker_fee: AddedToCostTradeFee = self.market.get_fee("LINK",
                                                             "ETH",
                                                             OrderType.LIMIT_MAKER,
                                                             TradeType.BUY,
                                                             Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.001"), maker_fee.percent)
        fee_overrides_config_map["kucoin_maker_fee"].value = Decimal('0.5')
        maker_fee: AddedToCostTradeFee = self.market.get_fee("LINK",
                                                             "ETH",
                                                             OrderType.LIMIT_MAKER,
                                                             TradeType.BUY,
                                                             Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.005"), maker_fee.percent)

    def test_limit_maker_rejections(self):
        if API_MOCK_ENABLED:
            return
        trading_pair = "ETH-USDT"

        # Try to put a buy limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.market.get_price(trading_pair, True) * Decimal('1.02')
        price: Decimal = self.market.quantize_order_price(trading_pair, price)
        amount = self.market.quantize_order_amount(trading_pair, Decimal(0.01))

        order_id = self.market.buy(trading_pair, amount, OrderType.LIMIT_MAKER, price)
        [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

        self.market_logger.clear()

        # Try to put a sell limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.market.get_price(trading_pair, True) * Decimal('0.98')
        price: Decimal = self.market.quantize_order_price(trading_pair, price)
        amount = self.market.quantize_order_amount(trading_pair, Decimal(0.01))

        order_id = self.market.sell(trading_pair, amount, OrderType.LIMIT_MAKER, price)
        [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

    def test_limit_makers_unfilled(self):
        if API_MOCK_ENABLED:
            return
        trading_pair = "ETH-USDT"
        bid_price = self.market.get_price(trading_pair, True) * Decimal("0.8")
        quantized_bid_price = self.market.quantize_order_price(trading_pair, bid_price)
        quantized_bid_amount = self.market.quantize_order_amount(trading_pair, Decimal(0.01))

        order_id, _ = self.place_order(True, trading_pair, quantized_bid_amount, OrderType.LIMIT_MAKER,
                                       quantized_bid_price, 10001,
                                       FixtureKucoin.ORDER_PLACE, FixtureKucoin.ORDER_GET_BUY_UNMATCHED)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id, order_created_event.order_id)

        ask_price = self.market.get_price(trading_pair, True) * Decimal("1.2")
        quatized_ask_price = self.market.quantize_order_price(trading_pair, ask_price)
        quatized_ask_amount = self.market.quantize_order_amount(trading_pair, Decimal(0.01))

        order_id, _ = self.place_order(False, trading_pair, quatized_ask_amount, OrderType.LIMIT_MAKER,
                                       quatized_ask_price, 10002,
                                       FixtureKucoin.ORDER_PLACE, FixtureKucoin.ORDER_GET_SELL_UNMATCHED)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id, order_created_event.order_id)

        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_limit_taker_buy(self):
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.05"))
        trading_pair = "ETH-USDT"
        price: Decimal = self.market.get_price(trading_pair, True)
        amount: Decimal = Decimal(0.01)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id, _ = self.place_order(True, trading_pair, quantized_amount, OrderType.LIMIT, price, 10001,
                                       FixtureKucoin.ORDER_PLACE, FixtureKucoin.BUY_MARKET_ORDER)
        [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        buy_order_completed_event: BuyOrderCompletedEvent = buy_order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: float = sum(t.amount for t in trade_events)
        quote_amount_traded: float = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, buy_order_completed_event.order_id)
        self.assertAlmostEqual(float(quantized_amount), buy_order_completed_event.base_asset_amount, places=4)
        self.assertEqual("ETH", buy_order_completed_event.base_asset)
        self.assertEqual("USDT", buy_order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, float(buy_order_completed_event.base_asset_amount), places=4)
        self.assertAlmostEqual(quote_amount_traded, float(buy_order_completed_event.quote_asset_amount), places=4)
        self.assertGreater(buy_order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_limit_taker_sell(self):
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.05"))
        trading_pair = "ETH-USDT"
        price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = Decimal(0.011)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)
        order_id, _ = self.place_order(False, trading_pair, amount, OrderType.LIMIT, price, 10001,
                                       FixtureKucoin.ORDER_PLACE, FixtureKucoin.SELL_MARKET_ORDER)
        [sell_order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        sell_order_completed_event: SellOrderCompletedEvent = sell_order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, sell_order_completed_event.order_id)
        self.assertAlmostEqual(float(quantized_amount), sell_order_completed_event.base_asset_amount)
        self.assertEqual("ETH", sell_order_completed_event.base_asset)
        self.assertEqual("USDT", sell_order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, float(sell_order_completed_event.base_asset_amount))
        self.assertAlmostEqual(quote_amount_traded, float(sell_order_completed_event.quote_asset_amount))
        self.assertGreater(sell_order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_cancel(self):
        trading_pair = "ETH-USDT"

        current_price: float = self.market.get_price(trading_pair, False)
        amount: Decimal = Decimal(0.01)

        price: Decimal = Decimal(current_price) * Decimal(1.1)
        quantized_price: Decimal = self.market.quantize_order_price(trading_pair, price)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id, exch_order_id = self.place_order(False, trading_pair, quantized_amount, OrderType.LIMIT_MAKER,
                                                   quantized_price, 10001,
                                                   FixtureKucoin.ORDER_PLACE_2, FixtureKucoin.OPEN_SELL_LIMIT_ORDER)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        if API_MOCK_ENABLED:
            resp = FixtureKucoin.CANCEL_ORDER.copy()
            resp["data"]["cancelledOrderIds"] = [exch_order_id]
            self.web_app.update_response("delete", API_BASE_URL, f"/api/v1/orders/{exch_order_id}", resp)
        self.market.cancel(trading_pair, order_id)
        if API_MOCK_ENABLED:
            resp = FixtureKucoin.GET_CANCELLED_ORDER.copy()
            resp["data"]["id"] = exch_order_id
            resp["data"]["clientOid"] = order_id
            self.web_app.update_response("get", API_BASE_URL, f"/api/v1/orders/{exch_order_id}", resp)
        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event
        self.assertEqual(order_cancelled_event.order_id, order_id)
        self.market_logger.clear()

    def test_cancel_all(self):
        trading_pair = "ETH-USDT"

        bid_price: Decimal = Decimal(self.market_2.get_price(trading_pair, True))
        ask_price: Decimal = Decimal(self.market_2.get_price(trading_pair, False))
        amount: Decimal = Decimal(0.01)
        quantized_amount: Decimal = self.market_2.quantize_order_amount(trading_pair, amount)

        # Intentionally setting high price to prevent getting filled
        quantize_bid_price: Decimal = self.market_2.quantize_order_price(trading_pair, bid_price * Decimal(0.8))
        quantize_ask_price: Decimal = self.market_2.quantize_order_price(trading_pair, ask_price * Decimal(1.2))

        _, exch_order_id = self.place_order(True, trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_bid_price,
                                            10001, FixtureKucoin.ORDER_PLACE, FixtureKucoin.OPEN_BUY_LIMIT_ORDER)

        _, exch_order_id2 = self.place_order(False, trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_ask_price,
                                             10002, FixtureKucoin.ORDER_PLACE, FixtureKucoin.OPEN_SELL_LIMIT_ORDER)

        self.run_parallel(asyncio.sleep(1))
        if API_MOCK_ENABLED:
            resp = FixtureKucoin.ORDERS_BATCH_CANCELLED.copy()
            resp["data"]["cancelledOrderIds"] = [exch_order_id, exch_order_id2]
            self.web_app.update_response("delete", API_BASE_URL, "/api/v1/orders", resp)
        [cancellation_results] = self.run_parallel(self.market_2.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)
        self.market_2_logger.clear()

    def test_orders_saving_and_restoration(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "ETH-USDT"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            self.assertEqual(0, len(self.market.tracking_states))

            # Try to put limit buy order for 0.04 ETH, and watch for order creation event.
            current_bid_price: float = self.market.get_price(trading_pair, True)
            bid_price: Decimal = Decimal(current_bid_price * Decimal(0.8))
            quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)

            amount: Decimal = Decimal(0.04)
            quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

            order_id, exch_order_id = self.place_order(True, trading_pair, quantized_amount, OrderType.LIMIT_MAKER,
                                                       quantize_bid_price,
                                                       10001, FixtureKucoin.ORDER_PLACE,
                                                       FixtureKucoin.OPEN_BUY_LIMIT_ORDER)
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
            self.market: KucoinExchange = KucoinExchange(
                kucoin_api_key=API_KEY,
                kucoin_passphrase=API_PASSPHRASE,
                kucoin_secret_key=API_SECRET,
                trading_pairs=["ETH-USDT"]
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

            if API_MOCK_ENABLED:
                resp = FixtureKucoin.CANCEL_ORDER.copy()
                resp["data"]["cancelledOrderIds"] = exch_order_id
                self.web_app.update_response("delete", API_BASE_URL, f"/api/v1/orders/{exch_order_id}", resp)
            # Cancel the order and verify that the change is saved.
            self.market.cancel(trading_pair, order_id)
            if API_MOCK_ENABLED:
                resp = FixtureKucoin.GET_CANCELLED_ORDER.copy()
                resp["data"]["id"] = exch_order_id
                resp["data"]["clientOid"] = order_id
                self.web_app.update_response("get", API_BASE_URL, f"/api/v1/orders/{exch_order_id}", resp)
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
            self.market_logger.clear()

    def test_order_fill_record(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "ETH-USDT"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy 0.01 ETH from the exchange, and watch for completion event.
            price: Decimal = self.market.get_price(trading_pair, True)
            amount: Decimal = Decimal(0.01)
            order_id, _ = self.place_order(True, trading_pair, amount, OrderType.LIMIT, price, 10001,
                                           FixtureKucoin.ORDER_PLACE, FixtureKucoin.BUY_MARKET_ORDER)
            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logs
            self.market_logger.clear()

            # Try to sell back the same amount of ETH to the exchange, and watch for completion event.
            price: Decimal = self.market.get_price(trading_pair, False)
            amount: Decimal = Decimal(buy_order_completed_event.base_asset_amount)
            order_id, _ = self.place_order(False, trading_pair, amount, OrderType.LIMIT, price, 10002,
                                           FixtureKucoin.ORDER_PLACE, FixtureKucoin.SELL_MARKET_ORDER)
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
            self.market_logger.clear()

    def test_update_last_prices(self):
        # This is basic test to see if order_book last_trade_price is initiated and updated.
        for order_book in self.market.order_books.values():
            for _ in range(5):
                self.ev_loop.run_until_complete(asyncio.sleep(1))
                self.assertFalse(math.isnan(order_book.last_trade_price))


if __name__ == "__main__":
    unittest.main()
