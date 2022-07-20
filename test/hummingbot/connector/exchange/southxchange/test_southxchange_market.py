import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Awaitable, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.southxchange import southxchange_constants as southxchange_utils
from hummingbot.connector.exchange.southxchange.southxchange_api_order_book_data_source import SouthxchangeAPIOrderBookDataSource
from hummingbot.connector.exchange.southxchange.southxchange_exchange import (
    SouthxchangeExchange,
    SouthxchangeOrder,
    SouthXchangeTradingRule,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate
# from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import BuyOrderCompletedEvent, MarketEvent, MarketOrderFailureEvent, OrderFilledEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import RESTMethod

import unittest
# import requests
import json
from decimal import Decimal
from typing import (
    List,
    Optional
)
import re
from aioresponses import aioresponses
from bidict import bidict
import math
import asyncio
import contextlib
import os
import time
import conf

from typing import Awaitable, List, Optional, Dict, Any
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
from hummingbot.core.clock import (
    Clock,
    ClockMode
)


from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import (
    MarketEvent,
    MarketOrderFailureEvent,
    BuyOrderCompletedEvent,
    # SellOrderCompletedEvent,
    OrderFilledEvent,
    # OrderCancelledEvent,
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
# from hummingbot.connector.markets_recorder import MarketsRecorder
# from hummingbot.model.market_state import MarketState
# from hummingbot.model.order import Order
# from hummingbot.model.sql_connection_manager import (
#     SQLConnectionManager,
#     SQLConnectionType
# )
# from hummingbot.model.trade_fill import TradeFill
# from hummingbot.core.mock_api.mock_web_server import MockWebServer
# from unittest import mock
# from test.connector.exchange.southxchange.mock_server_web_socket import MockWebSocketServerFactory
from test.connector.exchange.southxchange.fixture_southxchange import Fixturesouthxchange

API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
API_KEY = "XXX" if API_MOCK_ENABLED else conf.southxchange_api_key
API_SECRET = "YYY" if API_MOCK_ENABLED else conf.southxchange_secret_key
API_BASE_URL = "https://www.southxchange.com"
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
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "LTC2"
        cls.quote_asset = "USD2"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}/{cls.quote_asset}"
        cls.api_key = "someKey"
        cls.api_secret_key = "someSecretKey"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.async_task: Optional[asyncio.Task] = None
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.exchange = SouthxchangeExchange(
            client_config_map=self.client_config_map,
            southxchange_api_key=self.api_key,
            southxchange_secret_key=self.api_secret_key,
            trading_pairs=[self.trading_pair])
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()
        self._initialize_event_loggers()

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._in_flight_order_tracker.logger().setLevel(1)
        self.exchange._in_flight_order_tracker.logger().addHandler(self)

        SouthxchangeAPIOrderBookDataSource._trading_pair_symbol_map = bidict(
            {self.ex_trading_pair: f"{self.base_asset}-{self.quote_asset}"}
        )

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
        SouthxchangeAPIOrderBookDataSource._trading_pair_symbol_map = None
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.order_failure_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.OrderFailure, self.order_failure_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: SouthXchangeTradingRule(
                trading_pair=self.trading_pair,
                min_price_increment= Decimal("0.000000001"),
                min_base_amount_increment= Decimal("0.000000001")
            )
        }

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    async def _iter_user_event_queue_task(self):
        async for event_message in self.exchange._iter_user_event_queue():
            pass

    def test_get_fee(self):
        limit_fee: AddedToCostTradeFee = self.exchange.get_fee("LTC2", "USD2", OrderType.LIMIT_MAKER, TradeType.BUY, 1, 10)
        self.assertGreater(limit_fee.percent, 0)
        self.assertEqual(len(limit_fee.flat_fees), 0)
        market_fee: AddedToCostTradeFee = self.exchange.get_fee("LTC2", "USD2", OrderType.LIMIT, TradeType.BUY, 1)
        self.assertGreater(market_fee.percent, 0)
        self.assertEqual(len(market_fee.flat_fees), 0)
        sell_trade_fee: AddedToCostTradeFee = self.exchange.get_fee("LTC2", "USD2", OrderType.LIMIT_MAKER, TradeType.SELL, 1, 10)
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

    def test_estimate_fee(self):
        maker_fee = self.exchange.estimate_fee_pct(True)
        self.assertAlmostEqual(maker_fee, Decimal("0.001"))
        taker_fee = self.exchange.estimate_fee_pct(False)
        self.assertAlmostEqual(taker_fee, Decimal("0.001"))

    def test_limit_maker_rejections(self):
        if API_MOCK_ENABLED:
            return
        trading_pair = "LTC2-USD2"

        # Try to put a buy limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.exchange.get_price(trading_pair, True) * Decimal('1.02')
        price: Decimal = self.exchange.quantize_order_price(trading_pair, price)
        amount = self.exchange.quantize_order_amount(trading_pair, Decimal(0.01))

        order_id = self.exchange.buy(trading_pair, amount, OrderType.LIMIT_MAKER, price)
        [order_failure_event] = self.run_parallel(self.exchange_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

        self.exchange_logger.clear()

        # Try to put a sell limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.exchange.get_price(trading_pair, True) * Decimal('0.98')
        price: Decimal = self.exchange.quantize_order_price(trading_pair, price)
        amount = self.exchange.quantize_order_amount(trading_pair, Decimal(0.01))

        order_id = self.exchange.sell(trading_pair, amount, OrderType.LIMIT_MAKER, price)
        [order_failure_event] = self.run_parallel(self.exchange_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

    def test_limit_makers_unfilled(self):
        if API_MOCK_ENABLED:
            return
        trading_pair = "LTC2-USD2"
        bid_price = self.exchange.get_price(trading_pair, True) * Decimal("0.8")
        quantized_bid_price = self.exchange.quantize_order_price(trading_pair, bid_price)
        quantized_bid_amount = self.exchange.quantize_order_amount(trading_pair, Decimal(1))
        order_id_buy, exchange_order_id_buy = self.place_order(True, "LTC2-USD2", quantized_bid_amount, OrderType.LIMIT_MAKER, quantized_bid_price)
        [order_created_event] = self.run_parallel(self.exchange_logger.wait_for(BuyOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id_buy, order_created_event.order_id)
        ask_price = self.exchange.get_price(trading_pair, True) * Decimal("1.2")
        quatized_ask_price = self.exchange.quantize_order_price(trading_pair, ask_price)
        quatized_ask_amount = self.exchange.quantize_order_amount(trading_pair, Decimal(1))
        order_id, _ = self.place_order(False, trading_pair, quatized_ask_amount, OrderType.LIMIT_MAKER,
                                       quatized_ask_price)
        [order_created_event] = self.run_parallel(self.exchange_logger.wait_for(SellOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id, order_created_event.order_id)
        [cancellation_results] = self.run_parallel(self.exchange.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)
        [cancellation_results] = self.run_parallel(self.exchange.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def _cancel_order(self, cl_order_id):
        self.exchange.cancel("LTC2-USD2", cl_order_id)
        resp_GET_RESPONSE_BUY_CANCEL = Fixturesouthxchange.GET_ORDER_RESPONSE_BUY_CANCEL.copy()
        resp_GET_RESPONSE_BUY_CANCEL["Code"] = "20001"
        self.web_app.update_response("post", API_BASE_URL, "/api/v4/getOrder", resp_GET_RESPONSE_BUY_CANCEL)

    def place_order(self, is_buy, trading_pair, amount, order_type, price, mock_price, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._account_group = 0
        url = f"{API_BASE_URL}/{'api/v4/placeOrder'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))  
        mock_api.post(regex_url, body=str(EXCHANGE_ORDER_ID))
        resp_GET_ORDER_BUY = Fixturesouthxchange.GET_ORDER_RESPONSE_BUY_BOOKED.copy()
        resp_GET_ORDER_BUY["Code"] = EXCHANGE_ORDER_ID
        url = f"{API_BASE_URL}/{'api/v4/getOrder'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, body=json.dumps(resp_GET_ORDER_BUY))
        mock_price.return_value = Decimal(98.7)
        if is_buy:
            order_result = "BUY_testOrderId1"
        else:
            order_result = "SELL_testOrderId1"
        self.async_run_with_timeout(self.exchange._create_order(
            trade_type= TradeType.BUY if is_buy else TradeType.SELL,
            order_id=order_result,
            trading_pair=trading_pair,
            amount=Decimal(str(amount)),
            order_type= order_type,
            price=Decimal(str(price)),
        ))        
        self.assertIn(order_result, self.exchange.in_flight_orders)
        order_tracker = self.exchange.in_flight_orders[order_result]
        self.assertEqual(EXCHANGE_ORDER_ID, order_tracker.exchange_order_id)
        self.assertEqual(OrderState.OPEN, order_tracker.current_state)
        return order_tracker.client_order_id, order_tracker.exchange_order_id

    @patch("hummingbot.connector.exchange.southxchange.southxchange_exchange.SouthxchangeExchange.get_price")
    @aioresponses()
    def test_create_order(self, mock_price, mock_api):
        order_id_buy, exchange_order_id_buy = self.place_order(True, self.trading_pair,1000,OrderType.LIMIT,99, mock_price, mock_api)
        self.assertEqual(EXCHANGE_ORDER_ID, exchange_order_id_buy)
        self.assertEqual("BUY_testOrderId1", order_id_buy)

    def test_update_last_prices(self):
        # This is basic test to see if order_book last_trade_price is initiated and updated.
        for order_book in self.exchange.order_books.values():
            for _ in range(5):
                self.ev_loop.run_until_complete(asyncio.sleep(1))
                self.assertFalse(math.isnan(order_book.last_trade_price))

    @aioresponses()
    def test_cancel_all_does_not_cancel_orders_without_exchange_id(self, mock_api):


        url = f"{API_BASE_URL}/{'api/v4/cancelOrder'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 

        mock_api.post(regex_url, status=204)

        self.exchange.start_tracking_order(
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
         )
        order = self.exchange.in_flight_orders.get("testOrderId1")
        order.exchange_order_id ="421152"
        order.exchange_order_id_update_event

        self.exchange.start_tracking_order(
            order_id="testOrderId2",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("20000"),
            amount=Decimal("2"),
            order_type=OrderType.LIMIT
        )

        self.async_task = asyncio.get_event_loop().create_task(self.exchange.cancel_all(10))
        result: List[CancellationResult] = self.async_run_with_timeout(self.async_task)

        self.assertEqual(2, len(result))
        self.assertEqual("testOrderId1", result[0].order_id)
        self.assertTrue(result[0].success)
        self.assertEqual("testOrderId2", result[1].order_id)
        self.assertFalse(result[1].success)

    def test_order_without_exchange_id_marked_as_failure_and_removed_during_cancellation(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("20000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT
        )
        order = self.exchange.in_flight_orders["testOrderId1"]
        event_mock = MagicMock()
        event_mock.wait.side_effect = asyncio.TimeoutError()
        order.exchange_order_id_update_event = event_mock

        for i in range(self.exchange.STOP_TRACKING_ORDER_NOT_FOUND_LIMIT):
            self.async_run_with_timeout(
                self.exchange._execute_cancel(trading_pair=self.trading_pair, order_id=order.client_order_id))

        self.assertEqual(0, len(self.exchange.in_flight_orders))
        self.assertEqual(1, len(self.order_failure_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertEqual(1, len(self.log_records))
        self.assertEqual("INFO", self.log_records[0].levelname)
        self.assertTrue(
            self.log_records[0].getMessage().startswith(f"Order {order.client_order_id} has failed. Order Update:"))

    def test_order_without_exchange_id_marked_as_failure_and_removed_during_status_update(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("20000"),
            amount=Decimal("2"),
            order_type=OrderType.LIMIT
        )
        order = self.exchange.in_flight_orders["testOrderId1"]
        event_mock = MagicMock()
        event_mock.wait.side_effect = asyncio.TimeoutError()
        order.exchange_order_id_update_event = event_mock

        for i in range(self.exchange.STOP_TRACKING_ORDER_NOT_FOUND_LIMIT):
            self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertEqual(0, len(self.exchange.in_flight_orders))
        self.assertEqual(1, len(self.order_failure_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertEqual(4, len(self.log_records))
        self.assertEqual("INFO", self.log_records[3].levelname)
        self.assertTrue(
            self.log_records[3].getMessage().startswith(f"Order {order.client_order_id} has failed. Order Update:"))

    @aioresponses()
    def test_order_status_update_successful(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("20000"),
            amount=Decimal("2"),
            order_type=OrderType.LIMIT,
        )

        order = self.exchange.in_flight_orders.get("testOrderId1")
        order.exchange_order_id ="421152"
        order.exchange_order_id_update_event

        o = self.exchange.in_flight_orders["testOrderId1"]
        # Check before
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual(self.exchange.in_flight_orders["testOrderId1"].current_state, OrderState.PENDING_CREATE)

        url = f"{API_BASE_URL}/{'api/v4/getOrder'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 
        resp_GET_ORDER_BUY = Fixturesouthxchange.GET_ORDER_RESPONSE_BUY_BOOKED.copy()
        resp_GET_ORDER_BUY["Code"] = "421152"
        mock_api.post(regex_url, body=json.dumps(resp_GET_ORDER_BUY))

        # status_update = {
        #     "k": "order",
        #         "v": [
        #             {
        #                 "c": "421152",
        #                 "m": 3,
        #                 "d": "2022-07-15T18:24:53.563",
        #                 "get": "LTC2",
        #                 "giv": "USD2",
        #                 "a": 1,
        #                 "oa": 1,
        #                 "p": 20000,
        #                 "b": True
        #             }
        #         ]
        # }

        # mock_response = status_update
        # mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        # Check after
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual(self.exchange.in_flight_orders["testOrderId1"].current_state, OrderState.OPEN)

    @patch("hummingbot.core.data_type.in_flight_order.InFlightOrder.get_exchange_order_id")
    @aioresponses()
    def test_order_status_update_no_exchange_id_error(self, mock_get_ex, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("20000"),
            amount=Decimal("2"),
            order_type=OrderType.LIMIT
        )

        # Check before
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual(self.exchange.in_flight_orders["testOrderId1"].current_state, OrderState.PENDING_CREATE)

        self.exchange._account_group = 0

        url = f"{API_BASE_URL}/{'api/v4/getOrder'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 

        mock_api.post(regex_url, body=json.dumps(Fixturesouthxchange.GET_ORDER_RESPONSE_BUY_BOOKED))

        status_update = {
            "k": "order",
                "v": [
                    {
                        "c": "421152",
                        "m": 3,
                        "d": "2022-07-15T18:24:53.563",
                        "get": "LTC2",
                        "giv": "USD2",
                        "a": 1,
                        "oa": 1,
                        "p": 118.75,
                        "b": True
                    }
                ]
        }

        mock_response = status_update
        mock_api.get(regex_url, body=json.dumps(mock_response))

        mock_get_ex.side_effect = asyncio.TimeoutError()

        self.async_run_with_timeout(self.exchange._update_order_status())

        # Check after
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual(self.exchange.in_flight_orders["testOrderId1"].current_state, OrderState.PENDING_CREATE)

        self.assertTrue(
            self._is_logged(
                "DEBUG",
                "Tracked order testOrderId1 does not have an exchange id. "
                "Attempting fetch in next polling interval."
            )
        )

    @aioresponses()
    def test_order_status_update_api_error(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("20000"),
            amount=Decimal("2"),
            order_type=OrderType.LIMIT            
        )
        order = self.exchange.in_flight_orders.get("testOrderId1")
        order.exchange_order_id ="421152"
        order.exchange_order_id_update_event
        # Check before
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual(self.exchange.in_flight_orders["testOrderId1"].current_state, OrderState.PENDING_CREATE)



        url = f"{API_BASE_URL}/{'api/v4/getOrder'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 

        mock_api.post(regex_url, body=json.dumps(Fixturesouthxchange.GET_ORDER_RESPONSE_BUY_BOOKED), status=401)

        with self.assertRaises(IOError):
            self.async_run_with_timeout(self.exchange._update_order_status())

        # Check after
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual(self.exchange.in_flight_orders["testOrderId1"].current_state, OrderState.PENDING_CREATE)

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "There was an error requesting updates for the active orders ({'421152': 'testOrderId1'})"
            )
        )

    @patch("hummingbot.connector.client_order_tracker.ClientOrderTracker.process_order_update")
    @aioresponses()
    def test_order_status_update_unexpected_error(self, mock_process_order, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("20000"),
            amount=Decimal("2"),
            order_type=OrderType.LIMIT,
        )
        order = self.exchange.in_flight_orders.get("testOrderId1")
        order.exchange_order_id ="421152"
        order.exchange_order_id_update_event

        # Check before
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual(self.exchange.in_flight_orders["testOrderId1"].current_state, OrderState.PENDING_CREATE)

        url = f"{API_BASE_URL}/{'api/v4/getOrder'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 

        mock_api.post(regex_url, body=json.dumps(Fixturesouthxchange.GET_ORDER_RESPONSE_BUY_BOOKED))

        mock_process_order.side_effect = Exception()

        # No exception is passed. If yes -> test failure
        self.async_run_with_timeout(self.exchange._update_order_status())

        # Check after
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual(self.exchange.in_flight_orders["testOrderId1"].current_state, OrderState.PENDING_CREATE)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Unexpected error during processing order status. The Ascend Ex Response: {json.dumps(Fixturesouthxchange.GET_ORDER_RESPONSE_BUY_BOOKED)}".replace("\"", "'")
            )
        )

    def test_restore_tracking_states_only_registers_open_orders(self):
        orders = []
        orders.append(InFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
        ))
        orders.append(InFlightOrder(
            client_order_id="OID2",
            exchange_order_id="EOID2",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.CANCELED
        ))
        orders.append(InFlightOrder(
            client_order_id="OID3",
            exchange_order_id="EOID3",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        ))
        orders.append(InFlightOrder(
            client_order_id="OID4",
            exchange_order_id="EOID4",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FAILED
        ))

        tracking_states = {order.client_order_id: order.to_json() for order in orders}

        self.exchange.restore_tracking_states(tracking_states)

        self.assertIn("OID1", self.exchange.in_flight_orders)
        self.assertNotIn("OID2", self.exchange.in_flight_orders)
        self.assertNotIn("OID3", self.exchange.in_flight_orders)
        self.assertNotIn("OID4", self.exchange.in_flight_orders)

    @aioresponses()
    def test_partial_fill_and_full_fill_generate_fill_events(self, mock_api):


        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("118.75"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT
        )

        order = self.exchange.in_flight_orders.get("testOrderId1")

        order_update: OrderUpdate = OrderUpdate(
            client_order_id="testOrderId1",
            exchange_order_id="421152",
            trading_pair=self.trading_pair,
            update_timestamp=self.exchange.current_timestamp,
            new_state=OrderState.OPEN,
        )
        self.exchange._in_flight_order_tracker.process_order_update(order_update)


        url = f"{API_BASE_URL}/{'api/v4/listTransactions'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, body=json.dumps(Fixturesouthxchange.LIST_TRANSACTIONS))


        url = f"{API_BASE_URL}/{'api/v4/getOrder'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 
        getOrder_partialFill = {"Type": "buy", "Amount": '1.0', "LimitPrice": '118.75', "ListingCurrency": "LTC2", "ReferenceCurrency": "USD2", "Status": "partiallyexecuted", "DateAdded": "2021-10-10T12: 32: 29.167"}
        mock_api.post(regex_url, body=json.dumps(getOrder_partialFill))

        partial_fill = {
            "k": "order",
                "v": [
                    {
                        "c": "421152",
                        "m": 3,
                        "d": "2022-07-15T18:24:53.563",
                        "get": "LTC2",
                        "giv": "USD2",
                        "a": 0.2,
                        "oa": 1,
                        "p": 118.75,
                        "b": True
                    }
                ]
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = [partial_fill, asyncio.CancelledError()]
        self.exchange._user_stream_tracker._user_stream = mock_user_stream
        self.test_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())        
        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            # Ignore cancellation errors, it is the expected signal to cut the background loop
            pass

        self.exchange._set_current_timestamp(1640780001)
        total_fill = {
            "k": "order",
            "v": [
                {
                    "c": "421152",
                    "m": 0,
                    "d": "0001-01-01T00:00:00",
                    "get": "null",
                    "giv": "null",
                    "a": 0.0,
                    "oa": 0.0,
                    "p": 0.0,
                    "b": True
                }
            ]
        }
        url = f"{API_BASE_URL}/{'api/v4/listTransactions'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, body=json.dumps(Fixturesouthxchange.LIST_TRANSACTIONS))
        url = f"{API_BASE_URL}/{'api/v4/getOrder'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 
        getOrder_partialFill = {"Type": "buy", "Amount": '1.0', "LimitPrice": '118.75', "ListingCurrency": "LTC2", "ReferenceCurrency": "USD2", "Status": "executed", "DateAdded": "2021-10-10T12: 32: 29.167"}
        mock_api.post(regex_url, body=json.dumps(getOrder_partialFill))

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = [total_fill, asyncio.CancelledError()]
        self.exchange._user_stream_tracker._user_stream = mock_user_stream
        self.test_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            # Ignore cancellation errors, it is the expected signal to cut the background loop
            pass

        self.assertEqual(2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(1640780000, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(partial_fill["v"][0]["p"]), fill_event.price)
        self.assertEqual(Decimal('0.8'), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(1640780001, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(total_fill["v"][0]["p"]), fill_event.price)
        self.assertEqual(Decimal('0.2'), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)


        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    @aioresponses()
    def test_balance_update_events(self, mock_api):
        self.exchange._account_available_balances[self.base_asset] = Decimal(0)
        self.exchange._account_balances[self.base_asset] = Decimal(99)

        balance_update = {
            "k": "balance",
            "data": {
            }
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = [balance_update, asyncio.CancelledError()]

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        # Check before
        self.assertEqual(Decimal(0), self.exchange._account_available_balances[self.base_asset])
        self.assertEqual(Decimal(99), self.exchange._account_balances[self.base_asset])

        self.test_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        url = f"{API_BASE_URL}/{'api/v4/listBalances'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, body=json.dumps(Fixturesouthxchange.BALANCES))

        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            # Ignore cancellation errors, it is the expected signal to cut the background loop
            pass

        # Check after
        self.assertEqual(Decimal(118.19343), self.exchange._account_available_balances[self.base_asset])
        self.assertEqual(Decimal(118.19343), self.exchange._account_balances[self.base_asset])

    @aioresponses()
    def test_update_balances(self, mock_api):
        self.exchange._account_available_balances[self.base_asset] = Decimal(0)
        self.exchange._account_balances[self.base_asset] = Decimal(99)

        url = f"{API_BASE_URL}/{'api/v4/listBalances'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 

        mock_api.post(regex_url, body=json.dumps(Fixturesouthxchange.BALANCES))

        # Check before
        self.assertEqual(Decimal(0), self.exchange._account_available_balances[self.base_asset])
        self.assertEqual(Decimal(99), self.exchange._account_balances[self.base_asset])

        self.test_task = self.ev_loop.create_task(self.exchange._update_balances())

        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            # Ignore cancellation errors, it is the expected signal to cut the background loop
            pass
        # Check after
        self.assertEqual(Decimal(118.19343), self.exchange._account_available_balances[self.base_asset])
        self.assertEqual(Decimal(118.19343), self.exchange._account_balances[self.base_asset])

    @patch("hummingbot.connector.utils.get_tracking_nonce_low_res")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 6

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True, trading_pair=self.trading_pair, hbot_order_id_prefix=southxchange_utils.HBOT_BROKER_ID
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=False, trading_pair=self.trading_pair, hbot_order_id_prefix=southxchange_utils.HBOT_BROKER_ID
        )

        self.assertEqual(result, expected_client_order_id)

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        url = f"{API_BASE_URL}/{'api/v4/fees'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 

        mock_api.get(regex_url, body=json.dumps(Fixturesouthxchange.FEES))

        self.async_run_with_timeout(self.exchange._update_trading_rules())

        trading_rule = self.exchange._trading_rules[self.trading_pair]
        self.assertEqual(self.trading_pair, trading_rule.trading_pair)
        self.assertEqual(Decimal("0.0001000"),
                         trading_rule.min_price_increment)
        self.assertEqual(Decimal("0.0001000"),
                         trading_rule.min_base_amount_increment)

    @patch("hummingbot.connector.exchange.southxchange.southxchange_exchange.SouthxchangeExchange._sleep")
    @aioresponses()
    def test_trading_rules_polling_loop(self, sleep_mock, mock_api):
        url = f"{API_BASE_URL}/{'api/v4/fees'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 

        mock_api.get(regex_url, body=json.dumps(Fixturesouthxchange.FEES))

        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        try:
            self.async_run_with_timeout(self.exchange._trading_rules_polling_loop())
        except asyncio.exceptions.CancelledError:
            pass

        trading_rule = self.exchange._trading_rules[self.trading_pair]
        self.assertEqual(self.trading_pair, trading_rule.trading_pair)
        self.assertEqual(Decimal("0.0001000"),
                         trading_rule.min_price_increment)
        self.assertEqual(Decimal("0.0001000"),
                         trading_rule.min_base_amount_increment)

    @aioresponses()
    def test_api_request_public(self, mock_api):
        url = f"{API_BASE_URL}/{'api/v4/markets'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 


        mock_api.get(regex_url, body=json.dumps(Fixturesouthxchange.MARKETS))

        response = self.async_run_with_timeout(self.exchange._api_request(
            method=RESTMethod.GET,
            path_url="markets",
            data=None,
            params=None,
            is_auth_required=False))

        self.assertEqual(response, Fixturesouthxchange.MARKETS)

    @aioresponses()
    def test_api_request_private(self, mock_api):
        url = f"{API_BASE_URL}/{'api/v4/getOrder'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 

        mock_api.post(regex_url, body=json.dumps(Fixturesouthxchange.GET_ORDER_RESPONSE_BUY_BOOKED))

        response = self.async_run_with_timeout(self.exchange._api_request(
            method=RESTMethod.POST,
            path_url="getOrder",
            data=None,
            is_auth_required=True,
            force_auth_path_url="order"))

        self.assertEqual(response, Fixturesouthxchange.GET_ORDER_RESPONSE_BUY_BOOKED)

    @aioresponses()
    def test_api_request_error_status(self, mock_api):
        url = f"{API_BASE_URL}/{'api/v4/markets'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 

        mock_response = {"code": 0, "data": "test"}
        mock_api.get(regex_url, body=json.dumps(mock_response), status=401)

        error = None

        try:
            self.async_run_with_timeout(self.exchange._api_request(
                method=RESTMethod.GET,
                path_url="markets",
                data=None,
                params=None,
                is_auth_required=False))
        except IOError as e:
            error = str(e)

        self.assertIsNotNone(error)
        self.assertEqual(error, f"Error calling {url}. " F"Error: Error executing request {RESTMethod.GET} {url}. HTTP status is {401}. " f"Error: {json.dumps(mock_response)}")

    @aioresponses()
    def test_api_request_exception_json(self, mock_api):
        url = f"{API_BASE_URL}/{'api/v4/markets'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 

        mock_response = "wkjqhqw:{"
        mock_api.get(regex_url, body=mock_response)

        error = None

        try:
            self.async_run_with_timeout(self.exchange._api_request(
                method=RESTMethod.GET,
                path_url="markets",
                data=None,
                params=None,
                is_auth_required=False))
        except IOError as e:
            error = str(e)

        self.assertIsNotNone(error)
        self.assertEqual(error, f"Error calling {url}. Error: Expecting value: line 1 column 1 (char 0)")

    @aioresponses()
    def test_update_account_data(self, mock_api):
        url = f"{API_BASE_URL}/{'api/v4/getUserInfo'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 

        mock_response = {"TraderLevel": "test"}
        mock_api.post(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_account_data())

        self.assertEqual(self.exchange._trader_level, "ok")

    @aioresponses()
    def test_update_account_data_error_status(self, mock_api):
        url = f"{API_BASE_URL}/{'api/v4/getUserInfo'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 

        mock_response = {"TraderLevel": "test"}
        mock_api.get(regex_url, body=json.dumps(mock_response), status=401)

        error = None

        try:
            self.async_run_with_timeout(self.exchange._update_account_data())
        except IOError as e:
            error = str(e)

        self.assertIsNotNone(error)
        self.assertEqual(error, f"Error parsing data from getUserInfo.")

    @aioresponses()
    def test_process_order_message(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        # Verify that there's no such order being tracked
        self.assertNotIn("testOrderId1", self.exchange.in_flight_orders)

        self.exchange.start_tracking_order(
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT           
        )
        # Verify that the order is being tracked
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        # Update the order                        
        order_update: OrderUpdate = OrderUpdate(
            client_order_id="testOrderId1",
            exchange_order_id="1617339",
            trading_pair=self.trading_pair,
            update_timestamp=self.exchange.current_timestamp,
            new_state=OrderState.OPEN,
        )
        self.exchange._in_flight_order_tracker.process_order_update(order_update)

        url = f"{API_BASE_URL}/{'api/v4/listTransactions'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, body=json.dumps(Fixturesouthxchange.LIST_TRANSACTIONS))

        self.ev_loop.run_until_complete(
            self.exchange._process_trade_message(SouthxchangeOrder(
                        "1617339",
                        0,
                        "2022-07-13T12:00:00",
                        "LTC2",
                        "USD2",
                        Decimal("4000"),
                        Decimal("10000"),                        
                        Decimal("10000"),
                        TradeType.BUY,
                        "partiallyexecuted"
                    ))
        )

        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertTrue(self.exchange.in_flight_orders["testOrderId1"].executed_amount_base, Decimal("6000"))

    @aioresponses()
    def test_check_network_successful(self, mock_api):
        url = f"{API_BASE_URL}/{'api/v4/markets'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 

        mock_api.get(regex_url, body=json.dumps(Fixturesouthxchange.MARKETS))

        status = self.async_run_with_timeout(self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, status)

    @aioresponses()
    def test_check_network_unsuccessful(self, mock_api):
        url = f"{API_BASE_URL}/{'api/v4/markets'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")) 

        mock_api.get(regex_url, status=404)

        status = self.async_run_with_timeout(self.exchange.check_network())

        self.assertEqual(NetworkStatus.NOT_CONNECTED, status)

    def test_iter_user_event_queue(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.exchange._user_stream_tracker._user_stream = mock_queue

        self.test_task = self.ev_loop.create_task(self._iter_user_event_queue_task())

        is_cancelled = False

        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.exceptions.CancelledError:
            is_cancelled = True

        self.assertTrue(is_cancelled)

    def test_iter_user_event_queue_error(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = Exception()
        self.exchange._user_stream_tracker._user_stream = mock_queue

        self.test_task = self.ev_loop.create_task(self._iter_user_event_queue_task())

        try:
            self.async_run_with_timeout(self.test_task)
        except Exception:
            pass

        self.assertTrue(
            self._is_logged(
                "NETWORK",
                "Unknown error. Retrying after 1 seconds."
            )
        )

    @patch("hummingbot.connector.exchange.southxchange.southxchange_exchange.SouthxchangeExchange.get_price")
    @aioresponses()
    def test_create_order_api_error(self, mock_price, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._account_group = 0

        url = f"{API_BASE_URL}/{'api/v4/placeOrder'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))  

        mock_api.post(regex_url, body="{}", status=400)

        mock_price.return_value = Decimal(98.7)

        self.async_run_with_timeout(self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            amount=Decimal(1000),
            order_type=OrderType.LIMIT,
            price=Decimal(99),
        ))

        self.assertNotIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "The request to create the order testOrderId1 failed"
            )
        )

    @patch("hummingbot.connector.exchange.southxchange.southxchange_exchange.SouthxchangeExchange.get_price")
    def test_create_order_amount_zero(self, mock_price):
        self._simulate_trading_rules_initialized()

        mock_price.return_value = Decimal(98.7)

        is_exception = False
        exception_msg = ""

        try:
            self.async_run_with_timeout(self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id="testOrderId1",
                trading_pair=self.trading_pair,
                amount=Decimal(0),
                order_type=OrderType.LIMIT,
                price=Decimal(99),
            ))
        except ValueError as e:
            is_exception = True
            exception_msg = str(e)

        self.assertNotIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertTrue(is_exception)
        self.assertEqual("Order amount must be greater than zero.", exception_msg)
        
    def test_create_order_unsupported_order(self):
        is_exception = False
        exception_msg = ""

        try:
            self.async_run_with_timeout(self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id="testOrderId1",
                trading_pair=self.trading_pair,
                amount=Decimal(0),
                order_type=OrderType.MARKET,
                price=Decimal(99),
            ))
        except Exception as e:
            is_exception = True
            exception_msg = str(e)

        self.assertNotIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertTrue(is_exception)
        self.assertEqual(f"Unsupported order type: {OrderType.MARKET}", exception_msg)

    @aioresponses()
    def test_cancel_order_successful(self, mock_api):
        self.exchange._account_group = 0
        self.exchange._set_current_timestamp(1640780000)

        # Verify that there's no such order being tracked
        self.assertNotIn("testOrderId1", self.exchange.in_flight_orders)

        self.exchange.start_tracking_order(
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT
        )
        order = self.exchange.in_flight_orders.get("testOrderId1")
        order.exchange_order_id ="421152"
        order.exchange_order_id_update_event
        # Verify that the order is being tracked
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        url = f"{API_BASE_URL}/{'api/v4/cancelOrder'}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))  
        mock_api.post(regex_url, status=204)
        # Cancel the order
        response = self.ev_loop.run_until_complete(
            self.exchange._execute_cancel(
                trading_pair=self.trading_pair,
                order_id="testOrderId1")
        )
        # The order is not removed from in flight orders in this method
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual("testOrderId1", response)

    def test_cancel_order_not_found(self):
        self.exchange._set_current_timestamp(1640780000)

        # Verify that there's no such order being tracked
        self.assertNotIn("testOrderId1", self.exchange.in_flight_orders)

        # Cancel the order
        self.ev_loop.run_until_complete(
            self.exchange._execute_cancel(
                trading_pair=self.trading_pair,
                order_id="testOrderId1")
        )

        self.assertNotIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Failed to cancel order - testOrderId1. Order not found."
            )
        )

    def test_cancel_order_already_cancelled(self):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange._in_flight_order_tracker._cached_orders["testOrderId1"] = "My Order"

        # Verify that there's no such order being tracked
        self.assertNotIn("testOrderId1", self.exchange.in_flight_orders)

        # Cancel the order
        self.ev_loop.run_until_complete(
            self.exchange._execute_cancel(
                trading_pair=self.trading_pair,
                order_id="testOrderId1")
        )

        self.assertNotIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged(
                "INFO",
                "The order testOrderId1 was finished before being canceled"
            )
        )

def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
