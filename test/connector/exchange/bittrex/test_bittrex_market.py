#!/usr/bin/env python
import logging
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
    TradeType,
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.connector.exchange.bittrex.bittrex_exchange import BittrexExchange
from hummingbot.core.event.events import OrderType
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
from hummingbot.core.mock_api.mock_web_server import MockWebServer
from hummingbot.core.mock_api.mock_web_socket_server import MockWebSocketServerFactory
from test.connector.exchange.bittrex.fixture_bittrex import FixtureBittrex
from unittest import mock
import json

API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
API_KEY = "XXXX" if API_MOCK_ENABLED else conf.bittrex_api_key
API_SECRET = "YYYY" if API_MOCK_ENABLED else conf.bittrex_secret_key
API_BASE_URL = "api.bittrex.com"
WS_BASE_URL = "https://socket.bittrex.com/signalr"
EXCHANGE_ORDER_ID = 20001
logging.basicConfig(level=METRICS_LOG_LEVEL)


def _transform_raw_message_patch(self, msg):
    return json.loads(msg)


class BittrexExchangeUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
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

    market: BittrexExchange
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        if API_MOCK_ENABLED:
            cls.web_app = MockWebServer.get_instance()
            cls.web_app.add_host_to_mock(API_BASE_URL, [])
            cls.web_app.start()
            cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
            cls._patcher = mock.patch("aiohttp.client.URL")
            cls._url_mock = cls._patcher.start()
            cls._url_mock.side_effect = cls.web_app.reroute_local
            cls.web_app.update_response("get", API_BASE_URL, "/v3/ping", FixtureBittrex.PING)
            cls.web_app.update_response("get", API_BASE_URL, "/v3/markets", FixtureBittrex.MARKETS)
            cls.web_app.update_response("get", API_BASE_URL, "/v3/markets/tickers", FixtureBittrex.MARKETS_TICKERS)
            cls.web_app.update_response("get", API_BASE_URL, "/v3/balances", FixtureBittrex.BALANCES)
            cls.web_app.update_response("get", API_BASE_URL, "/v3/orders/open", FixtureBittrex.ORDERS_OPEN)
            cls._t_nonce_patcher = unittest.mock.patch(
                "hummingbot.connector.exchange.bittrex.bittrex_exchange.get_tracking_nonce")
            cls._t_nonce_mock = cls._t_nonce_patcher.start()

            cls._us_patcher = unittest.mock.patch(
                "hummingbot.connector.exchange.bittrex.bittrex_api_user_stream_data_source."
                "BittrexAPIUserStreamDataSource._transform_raw_message",
                autospec=True)
            cls._us_mock = cls._us_patcher.start()
            cls._us_mock.side_effect = _transform_raw_message_patch

            cls._ob_patcher = unittest.mock.patch(
                "hummingbot.connector.exchange.bittrex.bittrex_api_order_book_data_source."
                "BittrexAPIOrderBookDataSource._transform_raw_message",
                autospec=True)
            cls._ob_mock = cls._ob_patcher.start()
            cls._ob_mock.side_effect = _transform_raw_message_patch

            MockWebSocketServerFactory.url_host_only = True
            ws_server = MockWebSocketServerFactory.start_new_server(WS_BASE_URL)
            cls._ws_patcher = unittest.mock.patch("websockets.connect", autospec=True)
            cls._ws_mock = cls._ws_patcher.start()
            cls._ws_mock.side_effect = MockWebSocketServerFactory.reroute_ws_connect
            ws_server.add_stock_response("queryExchangeState", FixtureBittrex.WS_ORDER_BOOK_SNAPSHOT.copy())

        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: BittrexExchange = BittrexExchange(
            bittrex_api_key=API_KEY,
            bittrex_secret_key=API_SECRET,
            trading_pairs=["ETH-USDT"]
        )

        print("Initializing Bittrex market... this will take about a minute. ")
        cls.clock.add_iterator(cls.market)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()
        if API_MOCK_ENABLED:
            cls.web_app.stop()
            cls._patcher.stop()
            cls._t_nonce_patcher.stop()
            cls._ob_patcher.stop()
            cls._us_patcher.stop()
            cls._ws_patcher.stop()

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
        limit_fee: AddedToCostTradeFee = self.market.get_fee("ETH", "USDT", OrderType.LIMIT_MAKER, TradeType.BUY, 1, 1)
        self.assertGreater(limit_fee.percent, 0)
        self.assertEqual(len(limit_fee.flat_fees), 0)
        market_fee: AddedToCostTradeFee = self.market.get_fee("ETH", "USDT", OrderType.LIMIT, TradeType.BUY, 1)
        self.assertGreater(market_fee.percent, 0)
        self.assertEqual(len(market_fee.flat_fees), 0)

    def test_fee_overrides_config(self):
        fee_overrides_config_map["bittrex_taker_fee"].value = None
        taker_fee: AddedToCostTradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.0025"), taker_fee.percent)
        fee_overrides_config_map["bittrex_taker_fee"].value = Decimal('0.2')
        taker_fee: AddedToCostTradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.002"), taker_fee.percent)
        fee_overrides_config_map["bittrex_maker_fee"].value = None
        maker_fee: AddedToCostTradeFee = self.market.get_fee("LINK",
                                                             "ETH",
                                                             OrderType.LIMIT_MAKER,
                                                             TradeType.BUY,
                                                             Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.0025"), maker_fee.percent)
        fee_overrides_config_map["bittrex_maker_fee"].value = Decimal('0.5')
        maker_fee: AddedToCostTradeFee = self.market.get_fee("LINK",
                                                             "ETH",
                                                             OrderType.LIMIT_MAKER,
                                                             TradeType.BUY,
                                                             Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.005"), maker_fee.percent)

    def place_order(self, is_buy, trading_pair, amount, order_type, price, nonce, post_resp, ws_resp):
        global EXCHANGE_ORDER_ID
        order_id, exch_order_id = None, None
        if API_MOCK_ENABLED:
            exch_order_id = f"BITTREX_{EXCHANGE_ORDER_ID}"
            EXCHANGE_ORDER_ID += 1
            self._t_nonce_mock.return_value = nonce
            resp = post_resp.copy()
            resp["id"] = exch_order_id
            side = 'buy' if is_buy else 'sell'
            resp["direction"] = side.upper()
            resp["type"] = order_type.name.upper()
            if order_type == OrderType.LIMIT:
                del resp["limit"]
            self.web_app.update_response("post", API_BASE_URL, "/v3/orders", resp)
        if is_buy:
            order_id = self.market.buy(trading_pair, amount, order_type, price)
        else:
            order_id = self.market.sell(trading_pair, amount, order_type, price)
        if API_MOCK_ENABLED:
            resp = ws_resp.copy()
            resp["content"]["o"]["OU"] = exch_order_id
            MockWebSocketServerFactory.send_json_threadsafe(WS_BASE_URL, resp, delay=1.0)
        return order_id, exch_order_id

    def cancel_order(self, trading_pair, order_id, exch_order_id):
        if API_MOCK_ENABLED:
            resp = FixtureBittrex.CANCEL_ORDER.copy()
            resp["id"] = exch_order_id
            self.web_app.update_response("delete", API_BASE_URL, f"/v3/orders/{exch_order_id}", resp)
        self.market.cancel(trading_pair, order_id)

    def test_limit_maker_rejections(self):
        if API_MOCK_ENABLED:
            return
        trading_pair = "ETH-USDT"

        # Try to put a buy limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.market.get_price(trading_pair, True) * Decimal('1.02')
        price: Decimal = self.market.quantize_order_price(trading_pair, price)
        amount = self.market.quantize_order_amount(trading_pair, 1)
        order_id = self.market.buy(trading_pair, amount, OrderType.LIMIT_MAKER, price)
        [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

        self.market_logger.clear()

        # Try to put a sell limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.market.get_price(trading_pair, True) * Decimal('0.98')
        price: Decimal = self.market.quantize_order_price(trading_pair, price)
        amount = self.market.quantize_order_amount(trading_pair, 1)

        order_id = self.market.sell(trading_pair, amount, OrderType.LIMIT_MAKER, price)
        [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

    def test_limit_makers_unfilled(self):
        self.assertGreater(self.market.get_balance("USDT"), 20)
        trading_pair = "ETH-USDT"
        current_bid_price: Decimal = self.market.get_price(trading_pair, True) * Decimal('0.80')
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, current_bid_price)
        bid_amount: Decimal = Decimal('0.06')
        quantized_bid_amount: Decimal = self.market.quantize_order_amount(trading_pair, bid_amount)

        current_ask_price: Decimal = self.market.get_price(trading_pair, False)
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, current_ask_price)
        ask_amount: Decimal = Decimal('0.06')
        quantized_ask_amount: Decimal = self.market.quantize_order_amount(trading_pair, ask_amount)

        order_id, exch_order_id_1 = self.place_order(True, trading_pair, quantized_bid_amount, OrderType.LIMIT_MAKER,
                                                     quantize_bid_price, 10001,
                                                     FixtureBittrex.FILLED_BUY_LIMIT_ORDER,
                                                     FixtureBittrex.WS_AFTER_BUY_2)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id, order_created_event.order_id)

        order_id2, exch_order_id_2 = self.place_order(False, trading_pair, quantized_ask_amount, OrderType.LIMIT_MAKER,
                                                      quantize_ask_price, 10002,
                                                      FixtureBittrex.ORDER_PLACE_OPEN, FixtureBittrex.WS_ORDER_OPEN)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id2, order_created_event.order_id)

        self.run_parallel(asyncio.sleep(1))
        if API_MOCK_ENABLED:
            resp = FixtureBittrex.ORDER_CANCEL.copy()
            resp["id"] = exch_order_id_1
            self.web_app.update_response("delete", API_BASE_URL, f"/v3/orders/{exch_order_id_1}", resp)
            resp = FixtureBittrex.ORDER_CANCEL.copy()
            resp["id"] = exch_order_id_2
            self.web_app.update_response("delete", API_BASE_URL, f"/v3/orders/{exch_order_id_2}", resp)
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_limit_taker_buy(self):
        self.assertGreater(self.market.get_balance("USDT"), 20)
        trading_pair = "ETH-USDT"

        price: Decimal = self.market.get_price(trading_pair, True)
        amount: Decimal = Decimal("0.06")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id, _ = self.place_order(True, trading_pair, quantized_amount, OrderType.LIMIT, price, 10001,
                                       FixtureBittrex.FILLED_BUY_LIMIT_ORDER, FixtureBittrex.WS_AFTER_BUY_2)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("ETH", order_completed_event.base_asset)
        self.assertEqual("USDT", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_limit_taker_sell(self):
        trading_pair = "ETH-USDT"
        self.assertGreater(self.market.get_balance("ETH"), 0.06)

        price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = Decimal("0.06")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id, _ = self.place_order(False, trading_pair, quantized_amount, OrderType.LIMIT, price, 10001,
                                       FixtureBittrex.FILLED_BUY_LIMIT_ORDER, FixtureBittrex.WS_AFTER_BUY_2)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.market_logger.event_log if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("ETH", order_completed_event.base_asset)
        self.assertEqual("USDT", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_cancel_order(self):
        trading_pair = "ETH-USDT"

        current_bid_price: Decimal = self.market.get_price(trading_pair, True) * Decimal('0.80')
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, current_bid_price)

        amount: Decimal = Decimal("0.06")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id, exch_order_id = self.place_order(True, trading_pair, quantized_amount, OrderType.LIMIT_MAKER,
                                                   quantize_bid_price, 10001, FixtureBittrex.OPEN_BUY_LIMIT_ORDER,
                                                   FixtureBittrex.WS_AFTER_BUY_1)
        self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        self.cancel_order(trading_pair, order_id, exch_order_id)
        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event
        self.assertEqual(order_cancelled_event.order_id, order_id)

    def test_cancel_all(self):
        self.assertGreater(self.market.get_balance("USDT"), 20)
        trading_pair = "ETH-USDT"

        current_bid_price: Decimal = self.market.get_price(trading_pair, True) * Decimal('0.80')
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, current_bid_price)
        bid_amount: Decimal = Decimal('0.06')
        quantized_bid_amount: Decimal = self.market.quantize_order_amount(trading_pair, bid_amount)

        current_ask_price: Decimal = self.market.get_price(trading_pair, False)
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, current_ask_price)
        ask_amount: Decimal = Decimal('0.06')
        quantized_ask_amount: Decimal = self.market.quantize_order_amount(trading_pair, ask_amount)

        _, exch_order_id_1 = self.place_order(True, trading_pair, quantized_bid_amount, OrderType.LIMIT_MAKER,
                                              quantize_bid_price, 10001,
                                              FixtureBittrex.OPEN_BUY_LIMIT_ORDER, FixtureBittrex.WS_AFTER_BUY_1)
        _, exch_order_id_2 = self.place_order(False, trading_pair, quantized_ask_amount, OrderType.LIMIT_MAKER,
                                              quantize_ask_price, 10002,
                                              FixtureBittrex.OPEN_BUY_LIMIT_ORDER, FixtureBittrex.WS_AFTER_BUY_1)
        self.run_parallel(asyncio.sleep(1))
        if API_MOCK_ENABLED:
            resp = FixtureBittrex.CANCEL_ORDER.copy()
            resp["id"] = exch_order_id_1
            self.web_app.update_response("delete", API_BASE_URL, f"/v3/orders/{exch_order_id_1}", resp)
            resp = FixtureBittrex.CANCEL_ORDER.copy()
            resp["id"] = exch_order_id_2
            self.web_app.update_response("delete", API_BASE_URL, f"/v3/orders/{exch_order_id_2}", resp)
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

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
            current_bid_price: Decimal = self.market.get_price(trading_pair, True) * Decimal('0.80')
            quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, current_bid_price)
            bid_amount: Decimal = Decimal('0.06')
            quantized_bid_amount: Decimal = self.market.quantize_order_amount(trading_pair, bid_amount)

            order_id, exch_order_id = self.place_order(True, trading_pair, quantized_bid_amount, OrderType.LIMIT,
                                                       quantize_bid_price, 10001,
                                                       FixtureBittrex.OPEN_BUY_LIMIT_ORDER,
                                                       FixtureBittrex.WS_AFTER_BUY_1)
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
            self.market: BittrexExchange = BittrexExchange(
                bittrex_api_key=API_KEY,
                bittrex_secret_key=API_SECRET,
                trading_pairs=["XRP-BTC"]
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
            self.cancel_order(trading_pair, order_id, exch_order_id)
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
        trading_pair: str = "ETH-USDT"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:

            price: Decimal = self.market.get_price(trading_pair, True)
            amount: Decimal = Decimal("0.06")
            quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)
            order_id, _ = self.place_order(True, trading_pair, quantized_amount, OrderType.LIMIT, price, 10001,
                                           FixtureBittrex.FILLED_BUY_LIMIT_ORDER, FixtureBittrex.WS_AFTER_BUY_2)
            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logs
            self.market_logger.clear()

            amount = Decimal(buy_order_completed_event.base_asset_amount)
            price: Decimal = self.market.get_price(trading_pair, False)
            order_id, _ = self.place_order(False, trading_pair, amount, OrderType.LIMIT, price, 10001,
                                           FixtureBittrex.FILLED_BUY_LIMIT_ORDER, FixtureBittrex.WS_AFTER_BUY_2)
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


if __name__ == "__main__":
    unittest.main()
