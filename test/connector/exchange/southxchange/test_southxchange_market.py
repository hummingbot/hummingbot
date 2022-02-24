#!/usr/bin/env python
import unittest
import requests
from decimal import Decimal
from typing import (
    List,
    Optional
)
import math
import asyncio
import contextlib
import os
import time
import conf
import logging
from typing import Dict, Any
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import (
    MarketEvent,
    MarketOrderFailureEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    # TradeFee,
    TradeType,
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.connector.exchange.southxchange.southxchange_exchange import SouthxchangeExchange
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
from unittest import mock
from test.connector.exchange.southxchange.mock_server_web_socket import MockWebSocketServerFactory
from test.connector.exchange.southxchange.fixture_southxchange import Fixturesouthxchange
logging.basicConfig(level=METRICS_LOG_LEVEL)
API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
API_KEY = "XXX" if API_MOCK_ENABLED else conf.southxchange_api_key
API_SECRET = "YYY" if API_MOCK_ENABLED else conf.southxchange_secret_key
API_BASE_URL = "www.southxchange.com"
EXCHANGE_ORDER_ID = 20001


class TestSouthXchangeExchange(unittest.TestCase):
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
    market: SouthxchangeExchange
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        if API_MOCK_ENABLED:
            cls.web_app = MockWebServer.get_instance()
            cls.web_app.add_host_to_mock(API_BASE_URL, ["/api/v1/ticker/24hr", "api/v4/connect", "api/v4/connect?token="])
            cls.web_app.start()
            cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
            cls._patcher = mock.patch("aiohttp.client.URL")
            cls._url_mock = cls._patcher.start()
            cls._url_mock.side_effect = cls.web_app.reroute_local
            cls._req_patcher = unittest.mock.patch.object(requests.Session, "request", autospec=True)
            cls._req_url_mock = cls._req_patcher.start()
            cls._req_url_mock.side_effect = MockWebServer.reroute_request
            cls.web_app.update_response("get", API_BASE_URL, "/api/v4/markets", Fixturesouthxchange.MARKETS)
            cls.web_app.update_response("get", API_BASE_URL, "/api/v4/book/LTC2/USD2", Fixturesouthxchange.ORDERS_BOOK)
            cls.web_app.update_response("get", API_BASE_URL, "/api/v4/trades/LTC2/USD2", Fixturesouthxchange.TRADES)
            cls.web_app.update_response("get", API_BASE_URL, "/api/v4/fees", Fixturesouthxchange.FEES)
            cls.web_app.update_response("post", API_BASE_URL, "/api/v4/listTransactions", Fixturesouthxchange.LIST_TRANSACTIONS)
            cls.web_app.update_response("post", API_BASE_URL, "/api/v4/getUserInfo", {"TraderLevel": "Test"})
            cls.web_app.update_response("post", API_BASE_URL, "/api/v4/cancelOrder", None)
            cls.web_app.update_response("post", API_BASE_URL, "/api/v4/listBalances", Fixturesouthxchange.BALANCES)
            cls.web_app.update_response("post", API_BASE_URL, "/api/v4/GetWebSocketToken", "tokenTest")

            ws_base_url = "wss://www.southxchange.com/api/v4/connect?token=tokenTest"
            cls._ws_user_url = f"{ws_base_url}"
            MockWebSocketServerFactory.start_new_server(cls._ws_user_url)
            cls._ws_patcher = unittest.mock.patch("websockets.connect",
                                                  autospec=True)
            cls._ws_mock = cls._ws_patcher.start()
            cls._ws_mock.side_effect = MockWebSocketServerFactory.reroute_ws_connect

            cls._t_nonce_patcher = unittest.mock.patch("hummingbot.core.utils.tracking_nonce.get_tracking_nonce")
            cls._t_nonce_mock = cls._t_nonce_patcher.start()
            cls._exch_order_id = 20001
            cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: SouthxchangeExchange = SouthxchangeExchange(
            southxchange_api_key=API_KEY,
            southxchange_secret_key=API_SECRET,
            trading_pairs=["LTC2-USD2"],
            trading_required = True
        )
        cls.clock.add_iterator(cls.market)
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
    async def wait_til_ready(cls, connector = None):
        if connector is None:
            connector = cls.market
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if connector.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../southxchange_test.sqlite"))
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
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(0.5)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_get_fee(self):
        limit_fee: AddedToCostTradeFee = self.market.get_fee("LTC2", "USD2", OrderType.LIMIT_MAKER, TradeType.BUY, 1, 10)
        self.assertGreater(limit_fee.percent, 0)
        self.assertEqual(len(limit_fee.flat_fees), 0)
        market_fee: AddedToCostTradeFee = self.market.get_fee("LTC2", "USD2", OrderType.LIMIT, TradeType.BUY, 1)
        self.assertGreater(market_fee.percent, 0)
        self.assertEqual(len(market_fee.flat_fees), 0)
        sell_trade_fee: AddedToCostTradeFee = self.market.get_fee("LTC2", "USD2", OrderType.LIMIT_MAKER, TradeType.SELL, 1, 10)
        self.assertGreater(sell_trade_fee.percent, 0)
        self.assertEqual(len(sell_trade_fee.flat_fees), 0)

    @classmethod
    def get_current_nonce(cls):
        cls.current_nonce += 1
        return cls.current_nonce

    def test_rest_auth(self) -> Dict[Any, Any]:
        api_response = {
            "Code": "dummyOrderId",
            "Type": "sell",
            "Amount": 123,
            "LimitPrice": 123,
            "ListingCurrency": "BTC2",
            "ReferenceCurrency": "USD2",
            "Status": "executed",
            "DateAdded": "2021-07-29T15:26:42.120Z"
        }
        return api_response

    def test_place_order(self):
        order_id_buy, exchange_order_id_buy = self.place_order(True, "LTC2-USD2", 1, OrderType.LIMIT_MAKER, 66)
        order_id_sell, exchange_order_id_sell = self.place_order(False, "LTC2-USD2", 1, OrderType.LIMIT_MAKER, 66)
        return "ok"

    def test_estimate_fee(self):
        maker_fee = self.market.estimate_fee_pct(True)
        self.assertAlmostEqual(maker_fee, Decimal("0.001"))
        taker_fee = self.market.estimate_fee_pct(False)
        self.assertAlmostEqual(taker_fee, Decimal("0.001"))

    def test_limit_maker_rejections(self):
        if API_MOCK_ENABLED:
            return
        trading_pair = "LTC2-USD2"

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
        trading_pair = "LTC2-USD2"
        bid_price = self.market.get_price(trading_pair, True) * Decimal("0.8")
        quantized_bid_price = self.market.quantize_order_price(trading_pair, bid_price)
        quantized_bid_amount = self.market.quantize_order_amount(trading_pair, Decimal(1))
        order_id_buy, exchange_order_id_buy = self.place_order(True, "LTC2-USD2", quantized_bid_amount, OrderType.LIMIT_MAKER, quantized_bid_price)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id_buy, order_created_event.order_id)
        ask_price = self.market.get_price(trading_pair, True) * Decimal("1.2")
        quatized_ask_price = self.market.quantize_order_price(trading_pair, ask_price)
        quatized_ask_amount = self.market.quantize_order_amount(trading_pair, Decimal(1))
        order_id, _ = self.place_order(False, trading_pair, quatized_ask_amount, OrderType.LIMIT_MAKER,
                                       quatized_ask_price)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id, order_created_event.order_id)
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def _cancel_order(self, cl_order_id):
        self.market.cancel("LTC2-USD2", cl_order_id)
        resp_GET_RESPONSE_BUY_CANCEL = Fixturesouthxchange.GET_ORDER_RESPONSE_BUY_CANCEL.copy()
        resp_GET_RESPONSE_BUY_CANCEL["Code"] = "20001"
        self.web_app.update_response("post", API_BASE_URL, "/api/v4/getOrder", resp_GET_RESPONSE_BUY_CANCEL)

    def test_cancel_all(self):
        trading_pair = "LTC2-USD2"
        bid_price = self.market.get_price(trading_pair, True)
        ask_price = self.market.get_price(trading_pair, False)
        bid_price = self.market.quantize_order_price(trading_pair, bid_price * Decimal("0.9"))
        ask_price = self.market.quantize_order_price(trading_pair, ask_price * Decimal("1.1"))
        amount = self.market.quantize_order_amount(trading_pair, Decimal("0.0002"))

        list_orders_exchange = Fixturesouthxchange.OPEN_ORDERS.copy()
        sell_id = self.place_order(False, trading_pair, amount, OrderType.LIMIT, ask_price)
        resp_LIST_ORDER_SELL = Fixturesouthxchange.OPEN_ORDERS_SELL.copy()
        resp_LIST_ORDER_SELL["Code"] = str(sell_id[1])
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        buy_id = self.place_order(True, trading_pair, amount, OrderType.LIMIT, bid_price)
        resp_LIST_ORDER_BUY = Fixturesouthxchange.OPEN_ORDERS_BUY.copy()
        resp_LIST_ORDER_BUY["Code"] = str(buy_id[1])
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        list_orders_exchange = []
        self.web_app.update_response("post", API_BASE_URL, "/api/v4/listOrders", list_orders_exchange)
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def place_order(self, is_buy, trading_pair, amount, order_type, price):
        # , post_resp, get_resp):
        global EXCHANGE_ORDER_ID
        order_id, exch_order_id = None, None
        if API_MOCK_ENABLED:
            exch_order_id = EXCHANGE_ORDER_ID
            EXCHANGE_ORDER_ID += 1
            self.web_app.update_response("post", API_BASE_URL, "/api/v4/placeOrder", str(exch_order_id))
        if is_buy:
            order_id = self.market.buy(trading_pair, amount, order_type, price)
        else:
            order_id = self.market.sell(trading_pair, amount, order_type, price)
        if API_MOCK_ENABLED:
            if is_buy:
                resp_GET_ORDER_BUY = Fixturesouthxchange.GET_ORDER_RESPONSE_BUY_CREATE.copy()
                resp_GET_ORDER_BUY["Code"] = exch_order_id
                self.web_app.update_response("post", API_BASE_URL, "/api/v4/getOrder", resp_GET_ORDER_BUY)
            else:
                resp_GET_ORDER_SELL = Fixturesouthxchange.GET_ORDER_RESPONSE_SELL_CREATE.copy()
                resp_GET_ORDER_SELL["Code"] = exch_order_id
                self.web_app.update_response("post", API_BASE_URL, "/api/v4/getOrder", resp_GET_ORDER_SELL)
        return order_id, exch_order_id

    def test_limit_buy(self):
        self.assertGreater(self.market.get_balance("LTC2"), Decimal("0.05"))
        trading_pair = "LTC2-USD2"
        price = self.market.get_price(trading_pair, True)
        price = self.market.quantize_order_price(trading_pair, Decimal("86.24000"))
        amount = self.market.quantize_order_amount(trading_pair, Decimal("1"))
        order_id, exchange_order_code = self.place_order(True, trading_pair, amount, OrderType.LIMIT, price)
        fixture_ws = Fixturesouthxchange.WS_AFTER_BUY.get("v").copy()
        aux = fixture_ws[0]
        aux["c"] = str(exchange_order_code)
        ws_message = []
        ws_message.append(aux)
        final = {"k": "order", "v": ws_message}
        MockWebSocketServerFactory.send_json_threadsafe(self._ws_user_url,
                                                        final,
                                                        delay=1)
        resp_GET_ORDER_BUY = Fixturesouthxchange.GET_ORDER_RESPONSE_BUY_EXECUTED.copy()
        resp_GET_ORDER_BUY["Code"] = exchange_order_code
        self.web_app.update_response("post", API_BASE_URL, "/api/v4/getOrder", resp_GET_ORDER_BUY)

        [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        buy_order_completed_event: BuyOrderCompletedEvent = buy_order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: float = sum(t.amount for t in trade_events)
        quote_amount_traded: float = sum(t.amount * t.price for t in trade_events)
        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, buy_order_completed_event.order_id)
        self.assertAlmostEqual(amount, buy_order_completed_event.base_asset_amount, places=4)
        self.assertEqual("LTC2", buy_order_completed_event.base_asset)
        self.assertEqual("USD2", buy_order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, float(buy_order_completed_event.base_asset_amount), places=4)
        self.assertAlmostEqual(quote_amount_traded, float(buy_order_completed_event.quote_asset_amount), places=4)
        self.assertGreater(buy_order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_limit_sell(self):
        self.assertGreater(self.market.get_balance("LTC2"), Decimal("0.05"))
        trading_pair = "LTC2-USD2"
        price = self.market.get_price(trading_pair, True)
        price = self.market.quantize_order_price(trading_pair, Decimal("86.24000"))
        amount = self.market.quantize_order_amount(trading_pair, Decimal("1"))
        order_id, exchange_order_code = self.place_order(False, trading_pair, amount, OrderType.LIMIT, price)

        fixture_ws = Fixturesouthxchange.WS_AFTER_SELL.get("v").copy()
        aux = fixture_ws[0]
        aux["c"] = str(exchange_order_code)
        ws_message = []
        ws_message.append(aux)
        final = {"k": "order", "v": ws_message}
        MockWebSocketServerFactory.send_json_threadsafe(self._ws_user_url,
                                                        final,
                                                        delay=1)
        resp_GET_ORDER_SELL = Fixturesouthxchange.GET_ORDER_RESPONSE_SELL_EXECUTED.copy()
        resp_GET_ORDER_SELL["Code"] = exchange_order_code
        self.web_app.update_response("post", API_BASE_URL, "/api/v4/getOrder", resp_GET_ORDER_SELL)

        [sell_order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        sell_order_completed_event: SellOrderCompletedEvent = sell_order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, sell_order_completed_event.order_id)
        self.assertAlmostEqual(float(amount), sell_order_completed_event.base_asset_amount)
        self.assertEqual("LTC2", sell_order_completed_event.base_asset)
        self.assertEqual("USD2", sell_order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, float(sell_order_completed_event.base_asset_amount))
        self.assertAlmostEqual(quote_amount_traded, float(sell_order_completed_event.quote_asset_amount))
        self.assertGreater(sell_order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_cancel_order(self):
        self.assertGreater(self.market.get_balance("LTC2"), Decimal("0.05"))
        trading_pair = "LTC2-USD2"
        price = self.market.get_price(trading_pair, True)
        price = self.market.quantize_order_price(trading_pair, Decimal("86.24000"))
        amount = self.market.quantize_order_amount(trading_pair, Decimal("1"))
        order_id, exchange_order_code = self.place_order(True, trading_pair, amount, OrderType.LIMIT_MAKER, price)
        self.run_parallel(asyncio.sleep(1.0))
        self.market.cancel(trading_pair, order_id)
        if API_MOCK_ENABLED:
            resp_GET_RESPONSE_BUY_CANCEL = Fixturesouthxchange.GET_ORDER_RESPONSE_BUY_CANCEL.copy()
            resp_GET_RESPONSE_BUY_CANCEL["Code"] = str(exchange_order_code)
            self.web_app.update_response("post", API_BASE_URL, "/api/v4/getOrder", resp_GET_RESPONSE_BUY_CANCEL)
            fixture_ws = Fixturesouthxchange.WS_AFTER_CANCEL_BUY.get("v").copy()
            aux = fixture_ws[0]
            aux["c"] = str(exchange_order_code)
            ws_message = []
            ws_message.append(aux)
            final = {"k": "order", "v": ws_message}
            MockWebSocketServerFactory.send_json_threadsafe(self._ws_user_url, final, delay=0.1)
        [order_cancelled_event] = self.run_parallel(
            self.market_logger.wait_for(OrderCancelledEvent))

        order_cancelled_event: OrderCancelledEvent = order_cancelled_event

        self.run_parallel(asyncio.sleep(6.0))
        self.assertEqual(0, len(self.market.limit_orders))
        self.assertEqual(str(exchange_order_code), order_cancelled_event.exchange_order_id)

    def test_update_last_prices(self):
        # This is basic test to see if order_book last_trade_price is initiated and updated.
        for order_book in self.market.order_books.values():
            for _ in range(5):
                self.ev_loop.run_until_complete(asyncio.sleep(1))
                self.assertFalse(math.isnan(order_book.last_trade_price))

    def test_order_fill_record(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "LTC2-USD2"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy 0.01 ETH from the exchange, and watch for completion event.
            price: Decimal = self.market.get_price(trading_pair, True)
            amount: Decimal = Decimal('0.01')
            order_id, exchange_order_code = self.place_order(True, trading_pair, amount, OrderType.LIMIT, price)

            fixture_ws = Fixturesouthxchange.WS_AFTER_BUY.get("v").copy()
            aux = fixture_ws[0]
            aux["c"] = str(exchange_order_code)
            ws_message = []
            ws_message.append(aux)
            final = {"k": "order", "v": ws_message}
            MockWebSocketServerFactory.send_json_threadsafe(self._ws_user_url, final, delay=1)
            resp_GET_ORDER_BUY = Fixturesouthxchange.GET_ORDER_RESPONSE_BUY_EXECUTED.copy()
            resp_GET_ORDER_BUY["Code"] = exchange_order_code
            self.web_app.update_response("post", API_BASE_URL, "/api/v4/getOrder", resp_GET_ORDER_BUY)

            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logs
            self.market_logger.clear()

            # Try to sell back the same amount of ETH to the exchange, and watch for completion event.
            price: Decimal = self.market.get_price(trading_pair, False)
            amount: Decimal = Decimal(str(buy_order_completed_event.base_asset_amount))
            order_id, exchange_order_code = self.place_order(False, trading_pair, amount, OrderType.LIMIT, price)

            fixture_ws = Fixturesouthxchange.WS_AFTER_SELL.get("v").copy()
            aux = fixture_ws[0]
            aux["c"] = str(exchange_order_code)
            ws_message = []
            ws_message.append(aux)
            final = {"k": "order", "v": ws_message}
            MockWebSocketServerFactory.send_json_threadsafe(self._ws_user_url, final, delay=1)
            resp_GET_ORDER_SELL = Fixturesouthxchange.GET_ORDER_RESPONSE_SELL_EXECUTED.copy()
            resp_GET_ORDER_SELL["Code"] = exchange_order_code
            self.web_app.update_response("post", API_BASE_URL, "/api/v4/getOrder", resp_GET_ORDER_SELL)

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

    def test_orders_saving_and_restoration(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "LTC2-USD2"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()
        try:
            self.market._in_flight_orders.clear()
            self.assertEqual(0, len(self.market.tracking_states))

            # Try to put limit buy order for 0.02 ETH worth of ZRX, and watch for order creation event.
            current_bid_price: Decimal = self.market.get_price(trading_pair, True)
            price: Decimal = current_bid_price * Decimal("0.8")
            price = self.market.quantize_order_price(trading_pair, price)

            amount: Decimal = Decimal("0.0002")
            amount = self.market.quantize_order_amount(trading_pair, amount)

            order_id, exch_order_id = self.place_order(True, trading_pair, amount, OrderType.LIMIT_MAKER, price)
            order_created_event = self.ev_loop.run_until_complete(self.market_logger.wait_for(BuyOrderCreatedEvent))
            self.assertEqual(order_id, order_created_event.order_id)

            # Verify tracking states
            self.assertEqual(1, len(self.market.tracking_states))
            self.assertEqual(order_id, list(self.market.tracking_states.keys())[0])

            # Verify orders from recorder
            recorded_orders: List[Order] = recorder.get_orders_for_config_and_market(config_path, self.market)
            self.assertEqual(1, len(recorded_orders))
            self.assertEqual(order_id, recorded_orders[0].id)

            sess = recorder._sql_manager.get_new_session()
            # Verify saved market states
            saved_market_states: MarketState = recorder.get_market_states(config_path, self.market, sess)
            self.assertIsNotNone(saved_market_states)
            self.assertIsInstance(saved_market_states.saved_state, dict)
            self.assertGreater(len(saved_market_states.saved_state), 0)

            # Close out the current market and start another market.
            self.market.stop(self._clock)
            self.ev_loop.run_until_complete(asyncio.sleep(5))
            self.clock.remove_iterator(self.market)
            for event_tag in self.events:
                self.market.remove_listener(event_tag, self.market_logger)
            new_connector = SouthxchangeExchange(
                southxchange_api_key=API_KEY,
                southxchange_secret_key=API_SECRET,
                trading_pairs=["LTC2-USD2"],
                trading_required = True
            )
            for event_tag in self.events:
                new_connector.add_listener(event_tag, self.market_logger)
            recorder.stop()
            recorder = MarketsRecorder(sql, [new_connector], config_path, strategy_name)
            recorder.start()
            saved_market_states = recorder.get_market_states(config_path, new_connector, sess)
            self.clock.add_iterator(new_connector)
            self.ev_loop.run_until_complete(self.wait_til_ready(new_connector))
            self.assertEqual(0, len(new_connector.limit_orders))
            self.assertEqual(0, len(new_connector.tracking_states))
            new_connector.restore_tracking_states(saved_market_states.saved_state)
            self.assertEqual(1, len(new_connector.limit_orders))
            self.assertEqual(1, len(new_connector.tracking_states))

            # Cancel the order and verify that the change is saved.
            if API_MOCK_ENABLED:
                resp_GET_RESPONSE_BUY_CANCEL = Fixturesouthxchange.GET_ORDER_RESPONSE_BUY_CANCEL.copy()
                resp_GET_RESPONSE_BUY_CANCEL["Code"] = str(exch_order_id)
                self.web_app.update_response("post", API_BASE_URL, "/api/v4/getOrder", resp_GET_RESPONSE_BUY_CANCEL)
            new_connector.cancel(trading_pair, order_id)
            if API_MOCK_ENABLED:
                fixture_ws = Fixturesouthxchange.WS_AFTER_CANCEL_BUY.get("v").copy()
                aux = fixture_ws[0]
                aux["c"] = str(exch_order_id)
                ws_message = []
                ws_message.append(aux)
                final = {"k": "order", "v": ws_message}
                MockWebSocketServerFactory.send_json_threadsafe(self._ws_user_url, final, delay=5)
            self.ev_loop.run_until_complete(self.market_logger.wait_for(OrderCancelledEvent))
            recorder.save_market_states(config_path, new_connector, sess)
            order_id = None
            self.assertEqual(0, len(new_connector.limit_orders))
            self.assertEqual(0, len(new_connector.tracking_states))
            saved_market_states = recorder.get_market_states(config_path, new_connector, sess)
            self.assertEqual(0, len(saved_market_states.saved_state))
        finally:
            if order_id is not None:
                self.market.cancel(trading_pair, order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
