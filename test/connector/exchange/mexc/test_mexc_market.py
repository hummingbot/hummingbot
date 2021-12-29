#!/usr/bin/env python
import logging
from os.path import join, realpath

from test.connector.exchange.mexc.fixture_mexc import FixtureMEXC
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
import math
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
from hummingbot.connector.exchange.mexc.mexc_exchange import MexcExchange
from hummingbot.connector.exchange_base import OrderType
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
from unittest import mock
from hummingbot.connector.exchange.mexc.constants import (
    MEXC_BASE_URL,
    MEXC_PING_URL,
    MEXC_SYMBOL_URL,
    MEXC_DEPTH_URL,
    MEXC_PRICE_URL,
    MEXC_PLACE_ORDER,
    MEXC_ORDER_DETAILS_URL,
    MEXC_ORDER_CANCEL,
    MEXC_BATCH_ORDER_CANCEL,
    MEXC_BALANCE_URL, MEXC_DEAL_DETAIL,
)
import sys

sys.path.insert(0, realpath(join(__file__, "../../../../../")))

# MOCK_API_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
MOCK_API_ENABLED = True

API_KEY = "API_PASSPHRASE_MOCK" if MOCK_API_ENABLED else conf.mexc_api_key
API_SECRET = "API_SECRET_MOCK" if MOCK_API_ENABLED else conf.mexc_secret_key

API_BASE_URL = MEXC_BASE_URL.replace("https://", "").replace("/", "")

EXCHANGE_ORDER_ID = 20001

logging.basicConfig(level=METRICS_LOG_LEVEL)


class MexcExchangeUnitTest(unittest.TestCase):
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

    market: MexcExchange
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def strip_host_from_mexc_url(cls, url):
        HOST = "https://www.mexc.com"
        return url.split(HOST)[-1]

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        if MOCK_API_ENABLED:
            cls.web_app = MockWebServer.get_instance()
            cls.web_app.add_host_to_mock(API_BASE_URL, [])
            cls.web_app.start()
            cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
            cls._patcher = mock.patch("aiohttp.client.URL")
            cls._url_mock = cls._patcher.start()
            cls._url_mock.side_effect = cls.web_app.reroute_local

            cls.web_app.update_response("get", API_BASE_URL, cls.strip_host_from_mexc_url(MEXC_SYMBOL_URL),
                                        FixtureMEXC.MEXC_MARKET_SYMBOL)
            cls.web_app.update_response("get", API_BASE_URL, MEXC_PRICE_URL.split("?")[:1][0], FixtureMEXC.MEXC_TICKERS,
                                        params={"symbol": "ETH-USDT"})
            cls.web_app.update_response("get", API_BASE_URL, MEXC_DEPTH_URL.split("?")[:1][0],
                                        FixtureMEXC.MEXC_ORDER_BOOK, params={"symbol": "ETH-USDT", "depth": 200})
            # cls.web_app.update_response("get", API_BASE_URL, MEXC_TICKERS_URL, FixtureMEXC.MEXC_TICKERS)
            cls.web_app.update_response("get", API_BASE_URL, MEXC_BALANCE_URL, FixtureMEXC.MEXC_BALANCE_URL)
            cls.web_app.update_response("get", API_BASE_URL, MEXC_DEAL_DETAIL, FixtureMEXC.ORDER_DEAL_DETAIL)
            cls.web_app.update_response("get", API_BASE_URL, MEXC_PING_URL, FixtureMEXC.PING_DATA)
            cls._t_nonce_patcher = unittest.mock.patch(
                "hummingbot.connector.exchange.mexc.mexc_exchange.get_tracking_nonce")
            cls._t_nonce_mock = cls._t_nonce_patcher.start()
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: MexcExchange = MexcExchange(
            API_KEY,
            API_SECRET,
            trading_pairs=["ETH-USDT"]
        )
        # Need 2nd instance of market to prevent events mixing up across tests
        cls.market_2: MexcExchange = MexcExchange(
            API_KEY,
            API_SECRET,
            trading_pairs=["ETH-USDT"]
        )
        # a = cls.market
        cls.clock.add_iterator(cls.market)
        cls.clock.add_iterator(cls.market_2)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()
        if MOCK_API_ENABLED:
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
        self.db_path: str = realpath(join(__file__, "../mexc_test.sqlite"))
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

    def test_fee_overrides_config(self):
        fee_overrides_config_map["mexc_taker_fee"].value = None
        taker_fee: AddedToCostTradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.002"), taker_fee.percent)
        fee_overrides_config_map["mexc_taker_fee"].value = Decimal('0.1')
        taker_fee: AddedToCostTradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.001"), taker_fee.percent)
        fee_overrides_config_map["mexc_maker_fee"].value = None
        maker_fee: AddedToCostTradeFee = self.market.get_fee("LINK",
                                                             "ETH",
                                                             OrderType.LIMIT_MAKER,
                                                             TradeType.BUY,
                                                             Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.002"), maker_fee.percent)
        fee_overrides_config_map["mexc_maker_fee"].value = Decimal('0.5')
        maker_fee: AddedToCostTradeFee = self.market.get_fee("LINK",
                                                             "ETH",
                                                             OrderType.LIMIT_MAKER,
                                                             TradeType.BUY,
                                                             Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.005"), maker_fee.percent)

    def place_order(self, is_buy, trading_pair, amount, order_type, price, nonce, get_resp, market_connector=None):
        global EXCHANGE_ORDER_ID
        order_id, exch_order_id = None, None
        if MOCK_API_ENABLED:
            exch_order_id = f"MEXC_{EXCHANGE_ORDER_ID}"
            EXCHANGE_ORDER_ID += 1
            self._t_nonce_mock.return_value = nonce
            resp = FixtureMEXC.ORDER_PLACE.copy()
            resp["data"] = exch_order_id
            side = 'buy' if is_buy else 'sell'
            order_id = f"{side}-{trading_pair}-{nonce}"
            self.web_app.update_response("post", API_BASE_URL, MEXC_PLACE_ORDER, resp)
        market = self.market if market_connector is None else market_connector
        if is_buy:
            order_id = market.buy(trading_pair, amount, order_type, price)
        else:
            order_id = market.sell(trading_pair, amount, order_type, price)
        if MOCK_API_ENABLED:
            resp = get_resp.copy()
            # resp is the response passed by parameter
            resp["data"][0]["id"] = exch_order_id
            resp["data"][0]["client_order_id"] = order_id
            self.web_app.update_response("get", API_BASE_URL,
                                         MEXC_ORDER_DETAILS_URL.format(ordId=exch_order_id, trading_pair="ETH-USDT"),
                                         resp)
        return order_id, exch_order_id

    def cancel_order(self, trading_pair, order_id, exchange_order_id, get_resp):
        if MOCK_API_ENABLED:
            resp = FixtureMEXC.ORDER_CANCEL.copy()
            resp.get('data').clear()
            resp.get('data')[order_id] = 'success'
            self.web_app.update_response("delete", API_BASE_URL, MEXC_ORDER_CANCEL,
                                         resp, params={"order_ids": order_id})
        self.market.cancel(trading_pair, order_id)
        if MOCK_API_ENABLED:
            resp = get_resp.copy()
            resp["data"][0]["id"] = exchange_order_id
            resp["data"][0]["client_order_id"] = order_id
            self.web_app.update_response("get", API_BASE_URL, MEXC_ORDER_DETAILS_URL.format(ordId=exchange_order_id,
                                                                                            trading_pair="ETH-USDT"),
                                         resp)

    def test_limit_maker_rejections(self):
        if MOCK_API_ENABLED:
            return
        trading_pair = "ETH-USDT"

        # Try to put a buy limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.market.get_price(trading_pair, True) * Decimal('1.02')
        price: Decimal = self.market.quantize_order_price(trading_pair, price)
        amount = self.market.quantize_order_amount(trading_pair, Decimal("0.006"))

        order_id = self.market.buy(trading_pair, amount, OrderType.LIMIT_MAKER, price)
        [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

        self.market_logger.clear()

        # Try to put a sell limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.market.get_price(trading_pair, True) * Decimal('0.98')
        price: Decimal = self.market.quantize_order_price(trading_pair, price)
        amount = self.market.quantize_order_amount(trading_pair, Decimal("0.006"))

        order_id = self.market.sell(trading_pair, amount, OrderType.LIMIT_MAKER, price)
        [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

    def test_limit_makers_unfilled(self):
        if MOCK_API_ENABLED:
            return

        trading_pair = "ETH-USDT"

        bid_price: Decimal = self.market.get_price(trading_pair, True) * Decimal("0.5")
        ask_price: Decimal = self.market.get_price(trading_pair, False) * 2
        amount: Decimal = Decimal("0.006")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price * Decimal("0.9"))
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price * Decimal("1.1"))

        order_id1, exch_order_id1 = self.place_order(True, trading_pair, quantized_amount, OrderType.LIMIT_MAKER,
                                                     quantize_bid_price,
                                                     10001, FixtureMEXC.ORDER_GET_LIMIT_BUY_UNFILLED)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id1, order_created_event.order_id)

        order_id2, exch_order_id2 = self.place_order(False, trading_pair, quantized_amount, OrderType.LIMIT_MAKER,
                                                     quantize_ask_price,
                                                     10002, FixtureMEXC.ORDER_GET_LIMIT_SELL_UNFILLED)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id2, order_created_event.order_id)

        self.run_parallel(asyncio.sleep(1))
        if MOCK_API_ENABLED:
            resp = FixtureMEXC.ORDERS_BATCH_CANCELLED.copy()
            resp["data"]["success"] = [exch_order_id1, exch_order_id2]
            self.web_app.update_response("delete", API_BASE_URL, "/open/api/v2/order/cancel_by_symbol", resp)
        [cancellation_results] = self.run_parallel(self.market_2.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

        # Reset the logs
        self.market_logger.clear()

    def test_limit_taker_buy(self):
        trading_pair = "ETH-USDT"
        price: Decimal = self.market.get_price(trading_pair, True)
        amount: Decimal = Decimal("0.06")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id, _ = self.place_order(True, trading_pair, quantized_amount, OrderType.LIMIT, price, 10001,
                                       FixtureMEXC.ORDER_GET_MARKET_BUY)
        [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        buy_order_completed_event: BuyOrderCompletedEvent = buy_order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, buy_order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, buy_order_completed_event.base_asset_amount, places=4)
        self.assertEqual("ETH", buy_order_completed_event.base_asset)
        self.assertEqual("USDT", buy_order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, buy_order_completed_event.base_asset_amount, places=4)
        self.assertAlmostEqual(quote_amount_traded, buy_order_completed_event.quote_asset_amount, places=4)
        self.assertGreater(buy_order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        self.market_logger.clear()

    def test_limit_taker_sell(self):
        trading_pair = "ETH-USDT"
        price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = Decimal("0.06")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id, _ = self.place_order(False, trading_pair, amount, OrderType.LIMIT, price, 10001,
                                       FixtureMEXC.ORDER_GET_MARKET_SELL)
        [sell_order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        sell_order_completed_event: SellOrderCompletedEvent = sell_order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, sell_order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, sell_order_completed_event.base_asset_amount)
        self.assertEqual("ETH", sell_order_completed_event.base_asset)
        self.assertEqual("USDT", sell_order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, sell_order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, sell_order_completed_event.quote_asset_amount)
        self.assertGreater(sell_order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        self.market_logger.clear()

    def test_cancel_order(self):
        trading_pair = "ETH-USDT"

        current_bid_price: Decimal = self.market.get_price(trading_pair, True)
        amount: Decimal = Decimal("0.05")

        bid_price: Decimal = current_bid_price - Decimal("0.1") * current_bid_price
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id, exch_order_id = self.place_order(True, trading_pair, quantized_amount, OrderType.LIMIT_MAKER,
                                                   quantize_bid_price, 10001, FixtureMEXC.ORDER_GET_LIMIT_BUY_UNFILLED)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        self.cancel_order(trading_pair, order_id, exch_order_id, FixtureMEXC.ORDER_GET_CANCELED)
        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event
        self.assertEqual(order_cancelled_event.order_id, order_id)

    def test_cancel_all(self):
        trading_pair = "ETH-USDT"

        bid_price: Decimal = self.market_2.get_price(trading_pair, True) * Decimal("0.5")
        ask_price: Decimal = self.market_2.get_price(trading_pair, False) * 2
        amount: Decimal = Decimal("0.06")
        quantized_amount: Decimal = self.market_2.quantize_order_amount(trading_pair, amount)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.market_2.quantize_order_price(trading_pair, bid_price * Decimal("0.9"))
        quantize_ask_price: Decimal = self.market_2.quantize_order_price(trading_pair, ask_price * Decimal("1.1"))

        _, exch_order_id1 = self.place_order(True, trading_pair, quantized_amount, OrderType.LIMIT_MAKER,
                                             quantize_bid_price,
                                             1001, FixtureMEXC.ORDER_GET_LIMIT_BUY_UNFILLED, self.market_2)
        _, exch_order_id2 = self.place_order(False, trading_pair, quantized_amount, OrderType.LIMIT_MAKER,
                                             quantize_ask_price,
                                             1002, FixtureMEXC.ORDER_GET_LIMIT_BUY_FILLED, self.market_2)
        self.run_parallel(asyncio.sleep(1))
        if MOCK_API_ENABLED:
            resp = FixtureMEXC.ORDERS_BATCH_CANCELLED.copy()
            resp["data"][0]["ordId"] = exch_order_id1
            self.web_app.update_response("delete", API_BASE_URL, '/' + MEXC_BATCH_ORDER_CANCEL, resp)

        [cancellation_results] = self.run_parallel(self.market_2.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, '0')

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
            current_bid_price: Decimal = self.market.get_price(trading_pair, True)
            bid_price: Decimal = current_bid_price * Decimal("0.8")
            quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)

            amount: Decimal = Decimal("0.06")
            quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

            order_id, exch_order_id = self.place_order(True, trading_pair, quantized_amount, OrderType.LIMIT_MAKER,
                                                       quantize_bid_price, 10001,
                                                       FixtureMEXC.ORDER_GET_LIMIT_BUY_UNFILLED)
            [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
            order_created_event: BuyOrderCreatedEvent = order_created_event
            # self.assertEqual(order_id, order_created_event.order_id)

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
            self.market: MexcExchange = MexcExchange(
                API_KEY,
                API_SECRET,
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

            # Cancel the order and verify that the change is saved.
            self.cancel_order(trading_pair, order_id, exch_order_id, FixtureMEXC.ORDER_GET_CANCELED)
            # saved_market_states2 = recorder.get_market_states(config_path, self.market)
            self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
            # saved_market_states3 = recorder.get_market_states(config_path, self.market)
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
            # Try to buy 0.04 ETH from the exchange, and watch for completion event.
            price: Decimal = self.market.get_price(trading_pair, True)
            amount: Decimal = Decimal("0.06")
            order_id, _ = self.place_order(True, trading_pair, amount, OrderType.LIMIT, price, 10001,
                                           FixtureMEXC.ORDER_GET_MARKET_BUY)
            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logs
            self.market_logger.clear()

            # Try to sell back the same amount of ETH to the exchange, and watch for completion event.
            price: Decimal = self.market.get_price(trading_pair, False)
            amount = buy_order_completed_event.base_asset_amount
            order_id, _ = self.place_order(False, trading_pair, amount, OrderType.LIMIT, price, 10002,
                                           FixtureMEXC.ORDER_GET_MARKET_SELL)
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

    def test_update_last_prices(self):
        # This is basic test to see if order_book last_trade_price is initiated and updated.
        for order_book in self.market.order_books.values():
            for _ in range(5):
                self.ev_loop.run_until_complete(asyncio.sleep(1))
                self.assertFalse(math.isnan(order_book.last_trade_price))


if __name__ == "__main__":
    unittest.main()
