import asyncio
import json
from typing import Dict

import pandas as pd
import re
import time

import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils as bybit_utils
import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_constants as CONSTANTS

from aioresponses import aioresponses
from decimal import Decimal
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source import \
    BybitPerpetualAPIOrderBookDataSource
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_derivative import BybitPerpetualDerivative
from hummingbot.connector.trading_rule import TradingRule

from hummingbot.core.event.event_logger import EventLogger

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_in_flight_order import BybitPerpetualInFlightOrder
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_order_book import BybitPerpetualOrderBook
from hummingbot.core.event.events import (
    OrderType,
    PositionAction,
    PositionSide,
    TradeType,
    MarketEvent,
    FundingInfo,
    PositionMode,
)
from hummingbot.core.network_iterator import NetworkStatus

from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class BybitPerpetualDerivativeTests(TestCase):
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.base_asset = "BTC"
        self.quote_asset = "USDT"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"
        self.ex_trading_pair = f"{self.base_asset}{self.quote_asset}"
        self.non_linear_base = "BTC"
        self.non_linear_quote = "USD"
        self.non_linear_trading_pair = f"{self.non_linear_base}-{self.non_linear_quote}"
        self.non_linear_ex_trading_pair = f"{self.non_linear_base}{self.non_linear_quote}"
        self.domain = "bybit_perpetual_testnet"

        self.log_records = []
        self._finalMessage = 'FinalDummyMessage'
        self.async_task = None

        self.connector = BybitPerpetualDerivative(bybit_perpetual_api_key='testApiKey',
                                                  bybit_perpetual_secret_key='testSecretKey',
                                                  trading_pairs=[self.trading_pair, self.non_linear_trading_pair],
                                                  domain=self.domain)

        self.connector.logger().setLevel(1)
        self.connector.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.mock_done_event = asyncio.Event()

        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            self.domain: {
                self.ex_trading_pair: self.trading_pair,
                self.non_linear_ex_trading_pair: self.non_linear_trading_pair
            }
        }

        self.buy_order_created_logger: EventLogger = EventLogger()
        self.sell_order_created_logger: EventLogger = EventLogger()
        self.buy_order_completed_logger: EventLogger = EventLogger()
        self.order_cancelled_logger: EventLogger = EventLogger()
        self.order_failure_logger: EventLogger = EventLogger()
        self.order_filled_logger: EventLogger = EventLogger()
        self.connector.add_listener(MarketEvent.BuyOrderCreated, self.buy_order_created_logger)
        self.connector.add_listener(MarketEvent.SellOrderCreated, self.sell_order_created_logger)
        self.connector.add_listener(MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger)
        self.connector.add_listener(MarketEvent.OrderCancelled, self.order_cancelled_logger)
        self.connector.add_listener(MarketEvent.OrderFailure, self.order_failure_logger)
        self.connector.add_listener(MarketEvent.OrderFilled, self.order_filled_logger)

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _simulate_trading_rules_initialized(self):
        self.connector._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            ),
            self.non_linear_trading_pair: TradingRule(
                trading_pair=self.non_linear_trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
                buy_order_collateral_token=self.non_linear_base,
                sell_order_collateral_token=self.non_linear_base,
            ),
        }

    def _authentication_response(self, authenticated: bool) -> str:
        request = {"op": "auth",
                   "args": ['testAPIKey', 'testExpires', 'testSignature']}
        message = {"success": authenticated,
                   "ret_msg": "",
                   "conn_id": "testConnectionID",
                   "request": request}

        return message

    def _get_symbols_mock_response(
        self,
        linear: bool = True,
        min_order_size: float = 1,
        max_order_size: float = 2,
        min_price_increment: float = 3,
        min_base_amount_increment: float = 4,
    ) -> Dict:
        base, quote = (
            (self.base_asset, self.quote_asset)
            if linear
            else (self.non_linear_base, self.non_linear_quote)
        )
        symbols_mock = {  # irrelevant fields removed
            "result": [
                {
                    "name": f"{base}{quote}",
                    "alias": f"{base}{quote}",
                    "status": "Trading",
                    "base_currency": base,
                    "quote_currency": quote,
                    "price_scale": 2,
                    "taker_fee": "0.00075",
                    "maker_fee": "-0.00025",
                    "leverage_filter": {
                        "min_leverage": 1,
                        "max_leverage": 100,
                        "leverage_step": "0.01"
                    },
                    "price_filter": {
                        "min_price": "0.5",
                        "max_price": "999999.5",
                        "tick_size": min_price_increment,
                    },
                    "lot_size_filter": {
                        "max_trading_qty": max_order_size,
                        "min_trading_qty": min_order_size,
                        "qty_step": min_base_amount_increment,
                    }
                },
            ],
            "time_now": "1615801223.589808"
        }
        return symbols_mock

    def test_supported_order_types(self):
        self.assertEqual(2, len(self.connector.supported_order_types()))
        self.assertIn(OrderType.LIMIT, self.connector.supported_order_types())
        self.assertIn(OrderType.MARKET, self.connector.supported_order_types())

    def test_get_order_price_quantum(self):
        self._simulate_trading_rules_initialized()
        self.assertEqual(Decimal("0.0001"), self.connector.get_order_price_quantum(self.trading_pair, Decimal(100)))

    def test_get_order_size_quantum(self):
        self._simulate_trading_rules_initialized()
        self.assertEqual(Decimal("0.000001"), self.connector.get_order_size_quantum(self.trading_pair, Decimal(100)))

    def _mock_responses_done_callback(self, *_, **__):
        self.mock_done_event.set()

    @aioresponses()
    @patch('hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils.get_tracking_nonce')
    def test_create_buy_order(self, post_mock, nonce_provider_mock):
        nonce_provider_mock.return_value = 1000
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 1,
                "order_id": "335fd977-e5a5-4781-b6d0-c772d5bfb95b",
                "symbol": self.ex_trading_pair,
                "side": "Buy",
                "order_type": "Limit",
                "price": 46000,
                "qty": 1,
                "time_in_force": "GoodTillCancel",
                "order_status": "Created",
                "last_exec_time": 0,
                "last_exec_price": 0,
                "leaves_qty": 1,
                "cum_exec_qty": 0,
                "cum_exec_value": 0,
                "cum_exec_fee": 0,
                "reject_reason": "",
                "order_link_id": bybit_utils.get_new_client_order_id(True, self.trading_pair),
                "created_at": "2019-11-30T11:03:43.452Z",
                "updated_at": "2019-11-30T11:03:43.455Z"
            },
            "time_now": "1575111823.458705",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        }
        post_mock.post(regex_url, body=json.dumps(mock_response), callback=self._mock_responses_done_callback)

        self._simulate_trading_rules_initialized()
        self.connector._leverage[self.trading_pair] = 10

        new_order_id = self.connector.buy(trading_pair=self.trading_pair,
                                          amount=Decimal("1"),
                                          order_type=OrderType.LIMIT,
                                          price=Decimal("46000"),
                                          position_action=PositionAction.OPEN)

        asyncio.get_event_loop().run_until_complete(self.mock_done_event.wait())

        result = mock_response["result"]

        self.assertEqual(f"HBOT-B-{self.trading_pair}-1000", new_order_id)
        self.assertEqual("Buy", result["side"])
        self.assertEqual(self.ex_trading_pair, result["symbol"])
        self.assertEqual("Limit", result["order_type"])
        self.assertEqual(1, result["qty"])
        self.assertEqual(46000, result["price"])
        self.assertEqual("GoodTillCancel", result["time_in_force"])
        self.assertEqual(new_order_id, result["order_link_id"])

        self.assertIn(new_order_id, self.connector.in_flight_orders)
        in_flight_order = self.connector.in_flight_orders[new_order_id]
        self.assertEqual("335fd977-e5a5-4781-b6d0-c772d5bfb95b", in_flight_order.exchange_order_id)
        self.assertEqual(new_order_id, in_flight_order.client_order_id)
        self.assertEqual(Decimal(1), in_flight_order.amount)
        self.assertEqual(Decimal("46000"), in_flight_order.price)
        self.assertEqual(self.trading_pair, in_flight_order.trading_pair)
        self.assertEqual(OrderType.LIMIT, in_flight_order.order_type)
        self.assertEqual(TradeType.BUY, in_flight_order.trade_type)
        self.assertEqual(10, in_flight_order.leverage)
        self.assertEqual(PositionAction.OPEN.name, in_flight_order.position)

    @aioresponses()
    def test_create_buy_order_fails_when_amount_smaller_than_minimum(self, post_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 1,
                "order_id": "335fd977-e5a5-4781-b6d0-c772d5bfb95b",
                "symbol": self.ex_trading_pair,
                "side": "Buy",
                "order_type": "Limit",
                "price": 46000,
                "qty": 1,
                "time_in_force": "GoodTillCancel",
                "order_status": "Created",
                "last_exec_time": 0,
                "last_exec_price": 0,
                "leaves_qty": 1,
                "cum_exec_qty": 0,
                "cum_exec_value": 0,
                "cum_exec_fee": 0,
                "reject_reason": "",
                "order_link_id": f"B-{self.trading_pair}-1000",
                "created_at": "2019-11-30T11:03:43.452Z",
                "updated_at": "2019-11-30T11:03:43.455Z"
            },
            "time_now": "1575111823.458705",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        }
        post_mock.post(regex_url, body=json.dumps(mock_response), callback=self._mock_responses_done_callback)
        self._simulate_trading_rules_initialized()

        self.connector._leverage[self.trading_pair] = 10

        new_order_id = self.connector.buy(trading_pair=self.trading_pair,
                                          amount=Decimal("0.0001"),
                                          order_type=OrderType.LIMIT,
                                          price=Decimal("46000"),
                                          position_action=PositionAction.OPEN)

        # Request does not get called.
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))

        self.assertFalse(self.mock_done_event.is_set())
        self.assertNotIn(new_order_id, self.connector.in_flight_orders)
        self.assertTrue(self._is_logged("NETWORK",
                                        "Error submitting BUY LIMIT order to Bybit Perpetual for 0.000100 BTC-USDT 46000."
                                        " Error: BUY order amount 0.000100 is lower than the minimum order size 0.01."
                                        " Parameters: None"))

    def test_create_order_with_invalid_position_action_raises_value_error(self):
        self._simulate_trading_rules_initialized()

        self.connector._leverage[self.trading_pair] = 10

        with self.assertRaises(ValueError) as exception_context:
            asyncio.get_event_loop().run_until_complete(
                self.connector._create_order(
                    trade_type=TradeType.BUY,
                    order_id="C1",
                    trading_pair=self.trading_pair,
                    amount=Decimal("1"),
                    order_type=OrderType.LIMIT,
                    price=Decimal("46000"),
                    position_action=None))

        self.assertEqual("Specify either OPEN_POSITION or CLOSE_POSITION position_action to create an order",
                         str(exception_context.exception))

    @aioresponses()
    def test_create_order_fails_and_logs_when_api_response_has_erroneous_return_code(self, post_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 130006,
            "ret_msg": "order qty is out of permissible range",
            "ext_code": "",
            "ext_info": "",
            "result": {},
            "time_now": "1575111823.458705",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        }
        post_mock.post(regex_url, body=json.dumps(mock_response), callback=self._mock_responses_done_callback)
        self._simulate_trading_rules_initialized()

        self.connector._leverage[self.trading_pair] = 10

        new_order_id = self.connector.buy(trading_pair=self.trading_pair,
                                          amount=Decimal("1"),
                                          order_type=OrderType.LIMIT,
                                          price=Decimal("46000"),
                                          position_action=PositionAction.OPEN)

        asyncio.get_event_loop().run_until_complete(self.mock_done_event.wait())

        self.assertNotIn(new_order_id, self.connector.in_flight_orders)
        self.assertTrue(any(record.levelname == "NETWORK"
                            and "Error submitting BUY LIMIT order to Bybit Perpetual for 1.000000 BTC-USDT 46000.0000."
                            in record.getMessage()
                            for record in self.log_records))
        failure_events = self.order_failure_logger.event_log
        self.assertEqual(1, len(failure_events))
        self.assertEqual(new_order_id, failure_events[0].order_id)

    @aioresponses()
    def test_create_order_raises_cancelled_errors(self, post_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")
        post_mock.post(regex_url, exception=asyncio.CancelledError)
        self._simulate_trading_rules_initialized()

        self.connector._leverage[self.trading_pair] = 10

        with self.assertRaises(asyncio.CancelledError):
            asyncio.get_event_loop().run_until_complete(
                self.connector._create_order(
                    trade_type=TradeType.BUY,
                    order_id="C1",
                    trading_pair=self.trading_pair,
                    amount=Decimal("1"),
                    order_type=OrderType.LIMIT,
                    price=Decimal("46000"),
                    position_action=PositionAction.OPEN))

    @aioresponses()
    def test_create_order_close_position_action(self, post_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 1,
                "order_id": "335fd977-e5a5-4781-b6d0-c772d5bfb95b",
                "symbol": self.ex_trading_pair,
                "side": "Buy",
                "order_type": "Limit",
                "price": 46000,
                "qty": 1,
                "time_in_force": "GoodTillCancel",
                "order_status": "Created",
                "last_exec_time": 0,
                "last_exec_price": 0,
                "leaves_qty": 1,
                "cum_exec_qty": 0,
                "cum_exec_value": 0,
                "cum_exec_fee": 0,
                "reject_reason": "",
                "order_link_id": f"B-{self.trading_pair}-1000",
                "created_at": "2019-11-30T11:03:43.452Z",
                "updated_at": "2019-11-30T11:03:43.455Z"
            },
            "time_now": "1575111823.458705",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        }
        post_mock.post(regex_url, body=json.dumps(mock_response))

        self.connector.set_position_mode(PositionMode.HEDGE)

        self._simulate_trading_rules_initialized()

        self.connector._leverage[self.trading_pair] = 10

        asyncio.get_event_loop().run_until_complete(
            self.connector._create_order(
                trade_type=TradeType.BUY,
                order_id="C1",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.LIMIT,
                price=Decimal("46000"),
                position_action=PositionAction.CLOSE)
        )

        self.assertEqual(1, len(self.connector.in_flight_orders))
        self.assertTrue("C1" in self.connector.in_flight_orders)
        in_flight_order: BybitPerpetualInFlightOrder = self.connector.in_flight_orders["C1"]
        self.assertEqual(in_flight_order.position, PositionAction.CLOSE.name)
        self.assertTrue(self._is_logged("INFO", "Created LIMIT BUY order C1 for BTC-USDT. Amount: 1 Price: 46000."))

    @aioresponses()
    def test_create_order_open_position_action(self, post_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 1,
                "order_id": "335fd977-e5a5-4781-b6d0-c772d5bfb95b",
                "symbol": self.ex_trading_pair,
                "side": "Buy",
                "order_type": "Limit",
                "price": 46000,
                "qty": 1,
                "time_in_force": "GoodTillCancel",
                "order_status": "Created",
                "last_exec_time": 0,
                "last_exec_price": 0,
                "leaves_qty": 1,
                "cum_exec_qty": 0,
                "cum_exec_value": 0,
                "cum_exec_fee": 0,
                "reject_reason": "",
                "order_link_id": f"HBOT-B-{self.trading_pair}-1000",
                "created_at": "2019-11-30T11:03:43.452Z",
                "updated_at": "2019-11-30T11:03:43.455Z"
            },
            "time_now": "1575111823.458705",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        }
        post_mock.post(regex_url, body=json.dumps(mock_response))
        self.connector.set_position_mode(PositionMode.HEDGE)

        self._simulate_trading_rules_initialized()

        self.connector._leverage[self.trading_pair] = 10

        asyncio.get_event_loop().run_until_complete(
            self.connector._create_order(
                trade_type=TradeType.BUY,
                order_id="C1",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.LIMIT,
                price=Decimal("46000"),
                position_action=PositionAction.OPEN)
        )

        self.assertEqual(1, len(self.connector.in_flight_orders))
        self.assertTrue("C1" in self.connector.in_flight_orders)
        in_flight_order: BybitPerpetualInFlightOrder = self.connector.in_flight_orders["C1"]
        self.assertEqual(in_flight_order.position, PositionAction.OPEN.name)
        self.assertTrue(self._is_logged("INFO", "Created LIMIT BUY order C1 for BTC-USDT. Amount: 1 Price: 46000."))

    @aioresponses()
    @patch('hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils.get_tracking_nonce')
    def test_create_sell_order(self, post_mock, nonce_provider_mock):
        nonce_provider_mock.return_value = 1000
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 1,
                "order_id": "335fd977-e5a5-4781-b6d0-c772d5bfb95b",
                "symbol": self.ex_trading_pair,
                "side": "Sell",
                "order_type": "Market",
                "qty": 1,
                "time_in_force": "GoodTillCancel",
                "order_status": "Created",
                "last_exec_time": 0,
                "last_exec_price": 0,
                "leaves_qty": 1,
                "cum_exec_qty": 0,
                "cum_exec_value": 0,
                "cum_exec_fee": 0,
                "reject_reason": "",
                "order_link_id": bybit_utils.get_new_client_order_id(False, self.trading_pair),
                "created_at": "2019-11-30T11:03:43.452Z",
                "updated_at": "2019-11-30T11:03:43.455Z"
            },
            "time_now": "1575111823.458705",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        }
        post_mock.post(regex_url, body=json.dumps(mock_response), callback=self._mock_responses_done_callback)
        self._simulate_trading_rules_initialized()

        self.connector._leverage[self.trading_pair] = 10

        new_order_id = self.connector.sell(trading_pair=self.trading_pair,
                                           amount=Decimal("1"),
                                           order_type=OrderType.MARKET,
                                           price=Decimal("46000"),
                                           position_action=PositionAction.OPEN)

        asyncio.get_event_loop().run_until_complete(self.mock_done_event.wait())

        result = mock_response["result"]

        self.assertEqual(f"HBOT-S-{self.trading_pair}-1000", new_order_id)
        self.assertEqual("Sell", result["side"])
        self.assertEqual("BTCUSDT", result["symbol"])
        self.assertEqual("Market", result["order_type"])
        self.assertEqual(1, result["qty"])
        self.assertNotIn("price", result)
        self.assertEqual("GoodTillCancel", result["time_in_force"])
        self.assertEqual(new_order_id, result["order_link_id"])

        self.assertIn(new_order_id, self.connector.in_flight_orders)
        in_flight_order = self.connector.in_flight_orders[new_order_id]
        self.assertEqual("335fd977-e5a5-4781-b6d0-c772d5bfb95b", in_flight_order.exchange_order_id)
        self.assertEqual(new_order_id, in_flight_order.client_order_id)
        self.assertEqual(Decimal(1), in_flight_order.amount)
        self.assertEqual(Decimal("46000"), in_flight_order.price)
        self.assertEqual(self.trading_pair, in_flight_order.trading_pair)
        self.assertEqual(OrderType.MARKET, in_flight_order.order_type)
        self.assertEqual(TradeType.SELL, in_flight_order.trade_type)
        self.assertEqual(10, in_flight_order.leverage)
        self.assertEqual(PositionAction.OPEN.name, in_flight_order.position)

    @aioresponses()
    def test_update_trading_rules_with_polling_loop(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.QUERY_SYMBOL_ENDPOINT, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "name": "BTCUSD",
                    "alias": "BTCUSD",
                    "status": "Trading",
                    "base_currency": "BTC",
                    "quote_currency": "USD",
                    "price_scale": 2,
                    "taker_fee": "0.00075",
                    "maker_fee": "-0.00025",
                    "leverage_filter": {
                        "min_leverage": 1,
                        "max_leverage": 100,
                        "leverage_step": "0.01"
                    },
                    "price_filter": {
                        "min_price": "0.5",
                        "max_price": "999999.5",
                        "tick_size": "0.5"
                    },
                    "lot_size_filter": {
                        "max_trading_qty": 1000000,
                        "min_trading_qty": 1,
                        "qty_step": 1
                    }
                },
                {
                    "name": "BTCUSDT",
                    "alias": "BTCUSDT",
                    "status": "Trading",
                    "base_currency": "BTC",
                    "quote_currency": "USDT",
                    "price_scale": 2,
                    "taker_fee": "0.00075",
                    "maker_fee": "-0.00025",
                    "leverage_filter": {
                        "min_leverage": 1,
                        "max_leverage": 100,
                        "leverage_step": "0.01"
                    },
                    "price_filter": {
                        "min_price": "0.4",
                        "max_price": "999999.5",
                        "tick_size": "0.4"
                    },
                    "lot_size_filter": {
                        "max_trading_qty": 100,
                        "min_trading_qty": 0.001,
                        "qty_step": 0.001
                    }
                }
            ],
            "time_now": "1615801223.589808"
        }
        get_mock.get(regex_url, body=json.dumps(mock_response), callback=self._mock_responses_done_callback)

        self.async_task = asyncio.get_event_loop().create_task(self.connector._trading_rules_polling_loop())

        asyncio.get_event_loop().run_until_complete(self.mock_done_event.wait())

        self.assertIn("BTC-USD", self.connector.trading_rules)
        trading_rule = self.connector.trading_rules["BTC-USD"]
        self.assertEqual("BTC-USD", trading_rule.trading_pair)
        self.assertEqual(Decimal(1), trading_rule.min_order_size)
        self.assertEqual(Decimal(1000000), trading_rule.max_order_size)
        self.assertEqual(Decimal("0.5"), trading_rule.min_price_increment)
        self.assertEqual(Decimal(1), trading_rule.min_base_amount_increment)
        self.assertTrue(trading_rule.supports_limit_orders)
        self.assertTrue(trading_rule.supports_market_orders)

        self.assertIn("BTC-USDT", self.connector.trading_rules)
        trading_rule = self.connector.trading_rules["BTC-USDT"]
        self.assertEqual("BTC-USDT", trading_rule.trading_pair)
        self.assertEqual(Decimal("0.001"), trading_rule.min_order_size)
        self.assertEqual(Decimal(100), trading_rule.max_order_size)
        self.assertEqual(Decimal("0.4"), trading_rule.min_price_increment)
        self.assertEqual(Decimal("0.001"), trading_rule.min_base_amount_increment)
        self.assertTrue(trading_rule.supports_limit_orders)
        self.assertTrue(trading_rule.supports_market_orders)

    @aioresponses()
    def test_update_trading_rules_logs_rule_parsing_error(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.QUERY_SYMBOL_ENDPOINT, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        symbol_info = {
            "name": "BTCUSD",
            "alias": "BTCUSD",
            "status": "Trading",
            "base_currency": "BTC",
            "quote_currency": "USD",
            "price_scale": 2,
            "taker_fee": "0.00075",
            "maker_fee": "-0.00025",
            "leverage_filter": {
                "min_leverage": 1,
                "max_leverage": 100,
                "leverage_step": "0.01"
            }
        }
        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [symbol_info],
            "time_now": "1615801223.589808"
        }

        get_mock.get(regex_url, body=json.dumps(mock_response), callback=self._mock_responses_done_callback)

        self.async_task = asyncio.get_event_loop().create_task(self.connector._trading_rules_polling_loop())
        asyncio.get_event_loop().run_until_complete(self.mock_done_event.wait())

        self.assertTrue(self._is_logged("ERROR", f"Error parsing the trading pair rule: {symbol_info}. Skipping..."))

    @aioresponses()
    def test_update_trading_rules_polling_loop_raises_cancelled_error(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.QUERY_SYMBOL_ENDPOINT, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")
        get_mock.get(regex_url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            asyncio.get_event_loop().run_until_complete(self.connector._trading_rules_polling_loop())

    @aioresponses()
    def test_update_trading_rules_polling_loop_logs_errors(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.QUERY_SYMBOL_ENDPOINT, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")
        get_mock.get(regex_url, exception=Exception("Test Error"))

        self.async_task = asyncio.get_event_loop().create_task(self.connector._trading_rules_polling_loop())
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))

        self.assertTrue(self._is_logged("NETWORK", "Unexpected error while fetching trading rules. Error: Test Error"))

    @aioresponses()
    def test_cancel_tracked_order(self, post_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 1,
                "order_id": "EO1",
                "symbol": "BTCUSDT",
                "side": "Buy",
                "order_type": "Limit",
                "price": 44000,
                "qty": 1,
                "time_in_force": "GoodTillCancel",
                "order_status": "New",
                "last_exec_time": 0,
                "last_exec_price": 0,
                "leaves_qty": 1,
                "cum_exec_qty": 0,
                "cum_exec_value": 0,
                "cum_exec_fee": 0,
                "reject_reason": "",
                "order_link_id": "O1",
                "created_at": "2019-11-30T11:17:18.396Z",
                "updated_at": "2019-11-30T11:18:01.811Z"
            },
            "time_now": "1575112681.814760",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        }
        post_mock.post(regex_url, body=json.dumps(mock_response))

        self._simulate_trading_rules_initialized()

        self.connector.start_tracking_order(
            order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name
        )

        cancelled_order_id = self.connector.cancel(trading_pair=self.trading_pair, order_id="O1")

        cancel_json = mock_response["result"]

        self.assertEqual("BTCUSDT", cancel_json["symbol"])
        self.assertEqual("EO1", cancel_json["order_id"])
        self.assertEqual(cancelled_order_id, cancel_json["order_link_id"])

    @aioresponses()
    def test_cancel_tracked_order_logs_error_notified_in_the_response(self, post_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 1001,
            "ret_msg": "Test error description",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 1,
                "order_id": "EO1",
                "symbol": "BTCUSDT",
                "side": "Buy",
                "order_type": "Limit",
                "price": 44000,
                "qty": 1,
                "time_in_force": "GoodTillCancel",
                "order_status": "New",
                "last_exec_time": 0,
                "last_exec_price": 0,
                "leaves_qty": 1,
                "cum_exec_qty": 0,
                "cum_exec_value": 0,
                "cum_exec_fee": 0,
                "reject_reason": "",
                "order_link_id": "O1",
                "created_at": "2019-11-30T11:17:18.396Z",
                "updated_at": "2019-11-30T11:18:01.811Z"
            },
            "time_now": "1575112681.814760",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        }
        post_mock.post(regex_url, body=json.dumps(mock_response), callback=self._mock_responses_done_callback)

        self._simulate_trading_rules_initialized()

        self.connector.start_tracking_order(
            order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name
        )

        self.connector.cancel(trading_pair=self.trading_pair, order_id="O1")

        asyncio.get_event_loop().run_until_complete(self.mock_done_event.wait())

        self.assertTrue(self._is_logged(
            "ERROR",
            "Failed to cancel order O1:"
            " Bybit Perpetual encountered a problem cancelling the order (1001 - Test error description)"))

    @aioresponses()
    def test_order_marked_as_cancelled_if_cancellation_status_error_is_not_found(self, post_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)

        mock_response = {
            "ret_code": CONSTANTS.ORDER_NOT_EXISTS_ERROR_CODE,
            "ret_msg": "order not exists",
            "ext_code": "",
            "ext_info": "",
            "result": {},
            "time_now": "1575112681.814760",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        }
        post_mock.post(url, body=json.dumps(mock_response), callback=self._mock_responses_done_callback)

        self._simulate_trading_rules_initialized()

        self.connector.start_tracking_order(
            order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name
        )

        self.connector.cancel(trading_pair=self.trading_pair, order_id="O1")

        asyncio.get_event_loop().run_until_complete(self.mock_done_event.wait())

        self.assertNotIn("O1", self.connector.in_flight_orders)
        self.assertTrue(self._is_logged(
            "WARNING",
            "Failed to cancel order O1: order not found (130010 - order not exists)"))

    def test_cancel_tracked_order_logs_error_when_cancelling_non_tracked_order(self):
        self._simulate_trading_rules_initialized()

        self.connector.cancel(trading_pair=self.trading_pair, order_id="O1")
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.4))

        self.assertTrue(self._is_logged(
            "ERROR",
            "Failed to cancel order O1: Order O1 is not being tracked"))

    @aioresponses()
    def test_cancel_tracked_order_raises_cancelled(self, post_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")
        post_mock.post(regex_url, exception=asyncio.CancelledError)

        self._simulate_trading_rules_initialized()

        self.connector.start_tracking_order(
            order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trading_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name
        )

        with self.assertRaises(asyncio.CancelledError):
            asyncio.get_event_loop().run_until_complete(
                self.connector._execute_cancel(trading_pair=self.trading_pair, order_id="O1"))

    @aioresponses()
    def test_cancel_all_in_flight_orders(self, post_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        # Emulate first cancellation happening without problems
        mock_response_first_cancellation = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 1,
                "order_id": "EO1",
                "symbol": "BTCUSDT",
                "side": "Buy",
                "order_type": "Limit",
                "price": 44000,
                "qty": 1,
                "time_in_force": "GoodTillCancel",
                "order_status": "New",
                "last_exec_time": 0,
                "last_exec_price": 0,
                "leaves_qty": 1,
                "cum_exec_qty": 0,
                "cum_exec_value": 0,
                "cum_exec_fee": 0,
                "reject_reason": "",
                "order_link_id": "O1",
                "created_at": "2019-11-30T11:17:18.396Z",
                "updated_at": "2019-11-30T11:18:01.811Z"
            },
            "time_now": "1575112681.814760",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        }
        # Emulate second cancellation failing
        mock_response_second_cancellation = {
            "ret_code": 1001,
            "ret_msg": "Test error description",
            "ext_code": "",
            "ext_info": "",
            "result": {},
            "time_now": "1575112681.814760",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        }

        post_mock.post(regex_url, body=json.dumps(mock_response_first_cancellation))
        post_mock.post(regex_url, body=json.dumps(mock_response_second_cancellation))

        self._simulate_trading_rules_initialized()

        self.connector._in_flight_orders["O1"] = BybitPerpetualInFlightOrder(
            client_order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name)
        self.connector._in_flight_orders["O2"] = BybitPerpetualInFlightOrder(
            client_order_id="O2",
            exchange_order_id="EO2",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name,
            initial_state="New")
        # Add also an order already done, that should not be cancelled
        self.connector._in_flight_orders["O3"] = BybitPerpetualInFlightOrder(
            client_order_id="O3",
            exchange_order_id="EO3",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name,
            initial_state="Filled")

        cancellation_results = asyncio.get_event_loop().run_until_complete(self.connector.cancel_all(timeout_seconds=10))

        self.assertEqual(2, len(cancellation_results))
        self.assertTrue(any(map(lambda result: result.order_id == "O1" and result.success, cancellation_results)))
        self.assertTrue(any(map(lambda result: result.order_id == "O2" and not result.success, cancellation_results)))

    def test_cancel_all_logs_warning_when_process_times_out(self):

        self._simulate_trading_rules_initialized()

        self.connector._in_flight_orders["O1"] = BybitPerpetualInFlightOrder(
            client_order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name)

        cancellation_results = asyncio.get_event_loop().run_until_complete(
            self.connector.cancel_all(timeout_seconds=0.1))

        self.assertTrue(self._is_logged("WARNING", "Cancellation of all active orders for Bybit Perpetual connector"
                                                   " stopped after max wait time"))
        self.assertEqual(1, len(cancellation_results))
        self.assertTrue(cancellation_results[0].order_id == "O1" and not cancellation_results[0].success)

    def test_fee_estimation(self):
        with self.assertRaises(DeprecationWarning):
            self.connector.get_fee(base_currency="BCT", quote_currency="USDT", order_type=OrderType.LIMIT,
                                   order_side=TradeType.BUY, amount=Decimal(1), price=Decimal(45000))

    def test_connector_ready_status(self):
        self.assertFalse(self.connector.ready)

        self._simulate_trading_rules_initialized()
        self.connector._order_book_tracker._order_books_initialized.set()
        self.connector._user_stream_tracker.data_source._last_recv_time = 1
        self.connector._account_balances["USDT"] = Decimal(10000)
        self.connector._order_book_tracker.data_source._funding_info[self.trading_pair] = FundingInfo(
            trading_pair=self.trading_pair,
            index_price=Decimal(1),
            mark_price=Decimal(1),
            next_funding_utc_timestamp=time.time(),
            rate=Decimal(1))
        self.connector._order_book_tracker.data_source._funding_info[self.non_linear_trading_pair] = FundingInfo(
            trading_pair=self.trading_pair,
            index_price=Decimal(1),
            mark_price=Decimal(1),
            next_funding_utc_timestamp=time.time(),
            rate=Decimal(1))

        self.assertTrue(self.connector.ready)

    def test_connector_ready_status_when_trading_not_required(self):
        local_connector = BybitPerpetualDerivative(bybit_perpetual_api_key='testApiKey',
                                                   bybit_perpetual_secret_key='testSecretKey',
                                                   trading_pairs=[self.trading_pair],
                                                   trading_required=False)

        self.assertFalse(local_connector.ready)

        local_connector._order_book_tracker._order_books_initialized.set()
        local_connector._order_book_tracker.data_source._funding_info[self.trading_pair] = FundingInfo(
            trading_pair=self.trading_pair,
            index_price=Decimal(1),
            mark_price=Decimal(1),
            next_funding_utc_timestamp=time.time(),
            rate=Decimal(1))
        local_connector._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

        self.assertTrue(local_connector.ready)

    def test_limit_orders(self):
        self.connector._in_flight_orders["O1"] = BybitPerpetualInFlightOrder(
            client_order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name)
        self.connector._in_flight_orders["O2"] = BybitPerpetualInFlightOrder(
            client_order_id="O2",
            exchange_order_id="EO2",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.MARKET,
            leverage=10,
            position=PositionAction.OPEN.name,
            initial_state="New")

        limit_orders = self.connector.limit_orders

        self.assertEqual(2, len(limit_orders))
        self.assertEqual("O1", limit_orders[0].client_order_id)
        self.assertEqual("O2", limit_orders[1].client_order_id)

    def test_generate_tracking_states(self):
        self.connector._in_flight_orders["O1"] = BybitPerpetualInFlightOrder(
            client_order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name)
        self.connector._in_flight_orders["O2"] = BybitPerpetualInFlightOrder(
            client_order_id="O2",
            exchange_order_id="EO2",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.MARKET,
            leverage=10,
            position=PositionAction.OPEN.name,
            initial_state="New")

        tracking_states = self.connector.tracking_states

        expected_first_order_json = {'client_order_id': 'O1', 'exchange_order_id': 'EO1', 'trading_pair': 'BTC-USDT',
                                     'order_type': 'LIMIT', 'trade_type': 'BUY', 'price': '44000', 'amount': '1',
                                     'executed_amount_base': '0', 'executed_amount_quote': '0', 'fee_asset': 'USDT',
                                     'fee_paid': '0', 'last_state': 'Created', 'leverage': '10', 'position': 'OPEN'}
        expected_second_order_json = {'client_order_id': 'O2', 'exchange_order_id': 'EO2', 'trading_pair': 'BTC-USDT',
                                      'order_type': 'MARKET', 'trade_type': 'SELL', 'price': '44000', 'amount': '1',
                                      'executed_amount_base': '0', 'executed_amount_quote': '0', 'fee_asset': 'USDT',
                                      'fee_paid': '0', 'last_state': 'New', 'leverage': '10', 'position': 'OPEN'}
        self.assertEqual(2, len(tracking_states))
        self.assertEqual(expected_first_order_json, tracking_states["O1"])
        self.assertEqual(expected_second_order_json, tracking_states["O2"])

    def test_restore_tracking_states(self):
        order = BybitPerpetualInFlightOrder(
            client_order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name)
        order_json = {'client_order_id': 'O1', 'exchange_order_id': 'EO1', 'trading_pair': 'BTC-USDT',
                      'order_type': 'LIMIT', 'trade_type': 'BUY', 'price': '44000', 'amount': '1',
                      'executed_amount_base': '0', 'executed_amount_quote': '0', 'fee_asset': 'USDT',
                      'fee_paid': '0', 'last_state': 'Created', 'leverage': '10', 'position': 'OPEN'}

        self.connector.restore_tracking_states({order.client_order_id: order_json})

        self.assertIn(order.client_order_id, self.connector.in_flight_orders)
        self.assertEqual(order_json, self.connector.in_flight_orders[order.client_order_id].to_json())

    @aioresponses()
    @patch("hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_order_book_tracker"
           ".BybitPerpetualOrderBookTracker.trading_pair_symbol")
    def test_throttler_rebuilt_on_tracking_states_restored(self, post_mock, trading_pair_symbol_mock):
        trading_pair_symbol_mock.side_effect = lambda tp: tp.replace("-", "")

        alt_pair = "BTC-USDC"

        client_order_id = "01"
        order_json = {'client_order_id': 'O1', 'exchange_order_id': 'EO1', 'trading_pair': alt_pair,
                      'order_type': 'LIMIT', 'trade_type': 'BUY', 'price': '44000', 'amount': '1',
                      'executed_amount_base': '0', 'executed_amount_quote': '0', 'fee_asset': 'USDC',
                      'fee_paid': '0', 'last_state': 'Created', 'leverage': '10', 'position': 'OPEN'}

        self.connector.restore_tracking_states({client_order_id: order_json})

        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 1,
                "order_id": "EO1",
                "symbol": alt_pair.replace("-", ""),
                "side": "Buy",
                "order_type": "Limit",
                "price": 44000,
                "qty": 1,
                "time_in_force": "GoodTillCancel",
                "order_status": "New",
                "last_exec_time": 0,
                "last_exec_price": 0,
                "leaves_qty": 1,
                "cum_exec_qty": 0,
                "cum_exec_value": 0,
                "cum_exec_fee": 0,
                "reject_reason": "",
                "order_link_id": "O1",
                "created_at": "2019-11-30T11:17:18.396Z",
                "updated_at": "2019-11-30T11:18:01.811Z"
            },
            "time_now": "1575112681.814760",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        }
        post_mock.post(regex_url, body=json.dumps(mock_response))

        cancel_future = self.connector._execute_cancel(trading_pair=alt_pair, order_id=client_order_id)
        asyncio.get_event_loop().run_until_complete(cancel_future)

        cancel_json = mock_response["result"]

        self.assertEqual(alt_pair.replace("-", ""), cancel_json["symbol"])

    @aioresponses()
    def test_update_balances(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.GET_WALLET_BALANCE_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "BTC": {
                    "equity": 1002,
                    "available_balance": 999.99987471,
                    "used_margin": 0.00012529,
                    "order_margin": 0.00012529,
                    "position_margin": 0,
                    "occ_closing_fee": 0,
                    "occ_funding_fee": 0,
                    "wallet_balance": 1000,
                    "realised_pnl": 0,
                    "unrealised_pnl": 2,
                    "cum_realised_pnl": 0,
                    "given_cash": 0,
                    "service_cash": 0
                },
                "USDT": {
                    "equity": 80000,
                    "available_balance": 30500,
                    "used_margin": 49500,
                    "order_margin": 49500,
                    "position_margin": 0,
                    "occ_closing_fee": 0,
                    "occ_funding_fee": 0,
                    "wallet_balance": 80000,
                    "realised_pnl": 0,
                    "unrealised_pnl": 0,
                    "cum_realised_pnl": 0,
                    "given_cash": 0,
                    "service_cash": 0
                }
            },
            "time_now": "1578284274.816029",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        }
        get_mock.get(regex_url, body=json.dumps(mock_response))
        self.connector._account_balances["HBOT"] = Decimal(1000)
        self.connector._account_balances["USDT"] = Decimal(100000)
        self.connector._account_available_balances["HBOT"] = Decimal(1000)
        self.connector._account_available_balances["USDT"] = Decimal(0)

        asyncio.get_event_loop().run_until_complete(self.connector._update_balances())

        balances = self.connector.get_all_balances()
        available_balances = self.connector.available_balances
        self.assertEqual(2, len(balances))
        self.assertEqual(2, len(available_balances))
        self.assertNotIn("HBOT", balances)
        self.assertNotIn("HBOT", available_balances)
        self.assertEqual(Decimal(1000), balances["BTC"])
        self.assertEqual(Decimal("999.99987471"), available_balances["BTC"])
        self.assertEqual(Decimal(80000), balances["USDT"])
        self.assertEqual(Decimal(30500), available_balances["USDT"])

    @aioresponses()
    def test_update_order_status_for_cancellation(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 106958,
                "symbol": "BTCUSDT",
                "side": "Buy",
                "order_type": "Limit",
                "price": "44000",
                "qty": 1,
                "time_in_force": "PostOnly",
                "order_status": "Cancelled",
                "ext_fields": {
                    "o_req_num": -68948112492,
                    "xreq_type": "x_create"
                },
                "last_exec_time": "1596304897.847944",
                "last_exec_price": "43900",
                "leaves_qty": 0,
                "leaves_value": "0",
                "cum_exec_qty": 1,
                "cum_exec_value": "0.00008505",
                "cum_exec_fee": "-0.00000002",
                "reject_reason": "",
                "cancel_type": "",
                "order_link_id": "O1",
                "created_at": "2020-08-01T18:00:26Z",
                "updated_at": "2020-08-01T18:01:37Z",
                "order_id": "EO1"
            },
            "time_now": "1597171013.867068",
            "rate_limit_status": 599,
            "rate_limit_reset_ms": 1597171013861,
            "rate_limit": 600
        }

        get_mock.get(regex_url, body=json.dumps(mock_response))

        self._simulate_trading_rules_initialized()

        self.connector._in_flight_orders["O1"] = BybitPerpetualInFlightOrder(
            client_order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name,
            initial_state="New")

        asyncio.get_event_loop().run_until_complete(self.connector._update_order_status())

        request_data = mock_response["result"]

        self.assertEqual("BTCUSDT", request_data["symbol"])
        self.assertEqual("EO1", request_data["order_id"])
        self.assertEqual("O1", request_data["order_link_id"])
        self.assertEqual(0, len(self.connector.in_flight_orders))
        self.assertTrue(self._is_logged("INFO", "Successfully cancelled order O1"))
        cancellation_events = self.order_cancelled_logger.event_log
        self.assertEqual(1, len(cancellation_events))
        self.assertEqual("O1", cancellation_events[0].order_id)

    @aioresponses()
    def test_update_order_status_for_rejection(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 106958,
                "symbol": "BTCUSDT",
                "side": "Buy",
                "order_type": "Limit",
                "price": "44000",
                "qty": 1,
                "time_in_force": "PostOnly",
                "order_status": "Rejected",
                "ext_fields": {
                    "o_req_num": -68948112492,
                    "xreq_type": "x_create"
                },
                "last_exec_time": "1596304897.847944",
                "last_exec_price": "43900",
                "leaves_qty": 0,
                "leaves_value": "0",
                "cum_exec_qty": 1,
                "cum_exec_value": "0.00008505",
                "cum_exec_fee": "-0.00000002",
                "reject_reason": "Out of limits",
                "cancel_type": "",
                "order_link_id": "O1",
                "created_at": "2020-08-01T18:00:26Z",
                "updated_at": "2020-08-01T18:01:37Z",
                "order_id": "EO1"
            },
            "time_now": "1597171013.867068",
            "rate_limit_status": 599,
            "rate_limit_reset_ms": 1597171013861,
            "rate_limit": 600
        }
        get_mock.get(regex_url, body=json.dumps(mock_response))
        self._simulate_trading_rules_initialized()

        self.connector._in_flight_orders["O1"] = BybitPerpetualInFlightOrder(
            client_order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name,
            initial_state="New")

        asyncio.get_event_loop().run_until_complete(self.connector._update_order_status())
        request_data = mock_response["result"]

        self.assertEqual("BTCUSDT", request_data["symbol"])
        self.assertEqual("EO1", request_data["order_id"])
        self.assertEqual("O1", request_data["order_link_id"])
        self.assertEqual(0, len(self.connector.in_flight_orders))
        self.assertTrue(self._is_logged("INFO", "The market order O1 has failed according to order status event. "
                                                "Reason: Out of limits"))
        failure_events = self.order_failure_logger.event_log
        self.assertEqual(1, len(failure_events))
        self.assertEqual("O1", failure_events[0].order_id)

    @aioresponses()
    def test_update_order_status_logs_errors_during_status_request(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 1001,
            "ret_msg": "Error",
            "ext_code": "",
            "ext_info": "",
            "result": {},
            "time_now": "1597171013.867068",
            "rate_limit_status": 599,
            "rate_limit_reset_ms": 1597171013861,
            "rate_limit": 600
        }
        get_mock.get(regex_url, status=405, body=json.dumps(mock_response))

        self._simulate_trading_rules_initialized()

        self.connector._in_flight_orders["O1"] = BybitPerpetualInFlightOrder(
            client_order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name,
            initial_state="New")

        asyncio.get_event_loop().run_until_complete(self.connector._update_order_status())

        self.assertTrue(any(record.levelname == "ERROR"
                            and ("Error fetching order status. Response: Error fetching data from"
                                 " https://api-testnet.bybit.com/private/linear/order/search. "
                                 "HTTP status is 405. Message:")
                            in record.getMessage()
                            for record in self.log_records))

    def test_process_order_event_message_for_creation_confirmation(self):
        self._simulate_trading_rules_initialized()
        self.connector._leverage[self.trading_pair] = 10

        self.connector._in_flight_orders["O1"] = BybitPerpetualInFlightOrder(
            client_order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name,
            initial_state="Created")

        status_request_result = {
            "user_id": 106958,
            "symbol": "BTCUSDT",
            "side": "Buy",
            "order_type": "Limit",
            "price": "44000",
            "qty": 1,
            "time_in_force": "PostOnly",
            "order_status": "New",
            "ext_fields": {
                "o_req_num": -68948112492,
                "xreq_type": "x_create"
            },
            "last_exec_time": "1596304897.847944",
            "last_exec_price": "43900",
            "leaves_qty": 0,
            "leaves_value": "0",
            "cum_exec_qty": 1,
            "cum_exec_value": "0.00008505",
            "cum_exec_fee": "-0.00000002",
            "reject_reason": "Out of limits",
            "cancel_type": "",
            "order_link_id": "O1",
            "created_at": "2020-08-01T18:00:26Z",
            "updated_at": "2020-08-01T18:01:37Z",
            "order_id": "EO1"}

        self.connector._process_order_event_message(status_request_result)

        self.assertTrue(self.connector.in_flight_orders["O1"].is_new)
        buy_events = self.buy_order_created_logger.event_log
        self.assertEqual(1, len(buy_events))
        self.assertEqual("O1", buy_events[0].order_id)

        self.connector._in_flight_orders["O2"] = BybitPerpetualInFlightOrder(
            client_order_id="O2",
            exchange_order_id="EO2",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name,
            initial_state="Created")

        status_request_result = {
            "user_id": 106958,
            "symbol": "BTCUSDT",
            "side": "Sell",
            "order_type": "Limit",
            "price": "44000",
            "qty": 1,
            "time_in_force": "PostOnly",
            "order_status": "New",
            "ext_fields": {
                "o_req_num": -68948112492,
                "xreq_type": "x_create"
            },
            "last_exec_time": "1596304897.847944",
            "last_exec_price": "43900",
            "leaves_qty": 0,
            "leaves_value": "0",
            "cum_exec_qty": 1,
            "cum_exec_value": "0.00008505",
            "cum_exec_fee": "-0.00000002",
            "reject_reason": "Out of limits",
            "cancel_type": "",
            "order_link_id": "O2",
            "created_at": "2020-08-01T18:00:26Z",
            "updated_at": "2020-08-01T18:01:37Z",
            "order_id": "EO2"}

        self.connector._process_order_event_message(status_request_result)

        self.assertTrue(self.connector.in_flight_orders["O2"].is_new)
        sell_events = self.sell_order_created_logger.event_log
        self.assertEqual(1, len(sell_events))
        self.assertEqual("O2", sell_events[0].order_id)

    def test_status_update_with_filled_status_marks_inflight_order_as_completed(self):
        """ If for any reason the connector does not receive the fully filled event, it should mark the order
            as completed as soon as a status poll is executed.
        """
        self._simulate_trading_rules_initialized()
        self.connector._leverage[self.trading_pair] = 10

        order = BybitPerpetualInFlightOrder(
            client_order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name,
            initial_state="Created")
        self.connector._in_flight_orders["O1"] = order

        status_request_result = {
            "user_id": 106958,
            "symbol": "BTCUSDT",
            "side": "Buy",
            "order_type": "Limit",
            "price": "44000",
            "qty": 1,
            "time_in_force": "PostOnly",
            "order_status": "Filled",
            "ext_fields": {
                "o_req_num": -68948112492,
                "xreq_type": "x_create"
            },
            "last_exec_time": "1596304897.847944",
            "last_exec_price": "43900",
            "leaves_qty": 0,
            "leaves_value": "0",
            "cum_exec_qty": 1,
            "cum_exec_value": "0.00008505",
            "cum_exec_fee": "-0.00000002",
            "reject_reason": "Out of limits",
            "cancel_type": "",
            "order_link_id": "O1",
            "created_at": "2020-08-01T18:00:26Z",
            "updated_at": "2020-08-01T18:01:37Z",
            "order_id": "EO1"}

        self.connector._process_order_event_message(status_request_result)

        self.assertNotIn("O1", self.connector.in_flight_orders)

        order_completed_events = self.buy_order_completed_logger.event_log
        self.assertEqual(order.client_order_id, order_completed_events[0].order_id)
        self.assertEqual(order.base_asset, order_completed_events[0].base_asset)
        self.assertEqual(order.quote_asset, order_completed_events[0].quote_asset)
        self.assertEqual(order.quote_asset, order_completed_events[0].fee_asset)
        self.assertEqual(order.order_type, order_completed_events[0].order_type)
        self.assertEqual(order.exchange_order_id, order_completed_events[0].exchange_order_id)

    @aioresponses()
    def test_update_trade_history_for_not_existent_order_does_not_fail(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.USER_TRADE_RECORDS_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "order_id": "Abandoned!!",
                "trade_list": [
                    {
                        "closed_size": 0,
                        "cross_seq": 277136382,
                        "exec_fee": "0.0000001",
                        "exec_id": "256e5ef8-abfe-5772-971b-f944e15e0d68",
                        "exec_price": "8178.5",
                        "exec_qty": 1,
                        "exec_time": "1571676941.70682",
                        "exec_type": "Trade",
                        "exec_value": "0.00012227",
                        "fee_rate": "0.00075",
                        "last_liquidity_ind": "RemovedLiquidity",
                        "leaves_qty": 0,
                        "nth_fill": 2,
                        "order_id": "7ad50cb1-9ad0-4f74-804b-d82a516e1029",
                        "order_link_id": "",
                        "order_price": "8178",
                        "order_qty": 1,
                        "order_type": "Market",
                        "side": "Buy",
                        "symbol": "BTCUSD",
                        "user_id": 1,
                        "trade_time_ms": 1577480599000
                    }
                ]
            },
            "time_now": "1577483699.281488",
            "rate_limit_status": 118,
            "rate_limit_reset_ms": 1577483699244737,
            "rate_limit": 120
        }
        get_mock.get(regex_url, body=json.dumps(mock_response))
        self._simulate_trading_rules_initialized()

        order = BybitPerpetualInFlightOrder(
            client_order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name)
        self.connector._in_flight_orders["O1"] = order

        asyncio.get_event_loop().run_until_complete(self.connector._update_trade_history())

        self.assertEqual(Decimal(0), order.executed_amount_base)
        self.assertEqual(Decimal(0), order.executed_amount_quote)

    @aioresponses()
    def test_update_trade_history_with_partial_fill_and_complete_fill(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.USER_TRADE_RECORDS_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        # First trade, with partial fill
        mock_response_partial_fill = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "order_id": "Abandoned!!",
                "trade_list": [
                    {
                        "closed_size": 0,
                        "cross_seq": 277136382,
                        "exec_fee": "0.0000001",
                        "exec_id": "256e5ef8-abfe-5772-971b-f944e15e0d68",
                        "exec_price": "44000",
                        "exec_qty": 0.8,
                        "exec_time": "1571676941.70682",
                        "exec_type": "Trade",
                        "exec_value": "35200",
                        "fee_rate": "0.00075",
                        "last_liquidity_ind": "RemovedLiquidity",
                        "leaves_qty": 0.2,
                        "nth_fill": 2,
                        "order_id": "EO1",
                        "order_link_id": "O1",
                        "order_price": "44000",
                        "order_qty": 1,
                        "order_type": "Market",
                        "side": "Buy",
                        "symbol": "BTCUSDT",
                        "user_id": 1,
                        "trade_time_ms": 1577480599000
                    }
                ]
            },
            "time_now": "1577483699.281488",
            "rate_limit_status": 118,
            "rate_limit_reset_ms": 1577483699244737,
            "rate_limit": 120
        }
        # Second trade, completes the fill
        mock_response_complete_fill = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "order_id": "Abandoned!!",
                "trade_list": [
                    {
                        "closed_size": 0,
                        "cross_seq": 277136382,
                        "exec_fee": "0.0000001",
                        "exec_id": "256e5ef8-abfe-5772-971b-f944e15e0d69",
                        "exec_price": "44000",
                        "exec_qty": 0.2,
                        "exec_time": "1571676942.70682",
                        "exec_type": "Trade",
                        "exec_value": "7800",
                        "fee_rate": "0.00075",
                        "last_liquidity_ind": "RemovedLiquidity",
                        "leaves_qty": 0,
                        "nth_fill": 2,
                        "order_id": "EO1",
                        "order_link_id": "O1",
                        "order_price": "44000",
                        "order_qty": 1,
                        "order_type": "Market",
                        "side": "Buy",
                        "symbol": "BTCUSDT",
                        "user_id": 1,
                        "trade_time_ms": 1577480599000
                    }
                ]
            },
            "time_now": "1577483799.281488",
            "rate_limit_status": 118,
            "rate_limit_reset_ms": 1577483699244737,
            "rate_limit": 120
        }

        self._simulate_trading_rules_initialized()
        self.connector._leverage[self.trading_pair] = 10

        order = BybitPerpetualInFlightOrder(
            client_order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name)
        self.connector._in_flight_orders["O1"] = order

        get_mock.get(regex_url, body=json.dumps(mock_response_partial_fill))
        asyncio.get_event_loop().run_until_complete(self.connector._update_trade_history())

        self.assertEqual(Decimal("0.8"), order.executed_amount_base)
        self.assertEqual(Decimal(35200), order.executed_amount_quote)
        order_filled_events = self.order_filled_logger.event_log
        self.assertEqual(order.client_order_id, order_filled_events[0].order_id)
        self.assertEqual(order.trading_pair, order_filled_events[0].trading_pair)
        self.assertEqual(order.trade_type, order_filled_events[0].trade_type)
        self.assertEqual(order.order_type, order_filled_events[0].order_type)
        self.assertEqual(Decimal(44000), order_filled_events[0].price)
        self.assertEqual(Decimal(0.8), order_filled_events[0].amount)
        self.assertEqual("256e5ef8-abfe-5772-971b-f944e15e0d68", order_filled_events[0].exchange_trade_id)

        get_mock.get(regex_url, body=json.dumps(mock_response_complete_fill))
        asyncio.get_event_loop().run_until_complete(self.connector._update_trade_history())

        self.assertEqual(Decimal(1), order.executed_amount_base)
        self.assertEqual(Decimal(44000), order.executed_amount_quote)
        order_filled_events = self.order_filled_logger.event_log
        self.assertEqual(order.client_order_id, order_filled_events[1].order_id)
        self.assertEqual(order.trading_pair, order_filled_events[1].trading_pair)
        self.assertEqual(order.trade_type, order_filled_events[1].trade_type)
        self.assertEqual(order.order_type, order_filled_events[1].order_type)
        self.assertEqual(Decimal(44000), order_filled_events[1].price)
        self.assertEqual(Decimal(0.2), order_filled_events[1].amount)
        self.assertEqual(Decimal("0"), order_filled_events[1].trade_fee.percent)
        self.assertEqual(self.quote_asset, order_filled_events[1].trade_fee.flat_fees[0].token)
        self.assertEqual(Decimal("0.0000001"), order_filled_events[1].trade_fee.flat_fees[0].amount)
        self.assertEqual("256e5ef8-abfe-5772-971b-f944e15e0d69", order_filled_events[1].exchange_trade_id)

        self.assertTrue(self._is_logged("INFO", "The BUY order O1 has completed according to order status API"))
        order_completed_events = self.buy_order_completed_logger.event_log
        self.assertEqual(order.client_order_id, order_completed_events[0].order_id)
        self.assertEqual(order.base_asset, order_completed_events[0].base_asset)
        self.assertEqual(order.quote_asset, order_completed_events[0].quote_asset)
        self.assertEqual(order.quote_asset, order_completed_events[0].fee_asset)
        self.assertEqual(order.order_type, order_completed_events[0].order_type)
        self.assertEqual(Decimal(44000), order_completed_events[0].quote_asset_amount)
        self.assertEqual(Decimal(1), order_completed_events[0].base_asset_amount)
        self.assertEqual(order.exchange_order_id, order_completed_events[0].exchange_order_id)

    @aioresponses()
    def test_update_trade_history_when_api_call_raises_exception(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.USER_TRADE_RECORDS_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 1001,
            "ret_msg": "Error",
            "ext_code": "",
            "ext_info": "",
            "result": {},
            "time_now": "1597171013.867068",
            "rate_limit_status": 599,
            "rate_limit_reset_ms": 1597171013861,
            "rate_limit": 600
        }
        get_mock.get(regex_url, status=405, body=json.dumps(mock_response))

        self._simulate_trading_rules_initialized()

        order = BybitPerpetualInFlightOrder(
            client_order_id="O1",
            exchange_order_id="EO1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(44000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            leverage=10,
            position=PositionAction.OPEN.name)
        self.connector._in_flight_orders["O1"] = order

        asyncio.get_event_loop().run_until_complete(self.connector._update_trade_history())

        self.assertTrue(any(record.levelname == "ERROR"
                            and ("Error fetching trades history. Response: Error fetching data from"
                                 " https://api-testnet.bybit.com/private/linear/trade/execution/list. "
                                 "HTTP status is 405. Message:")
                            in record.getMessage()
                            for record in self.log_records))

    @aioresponses()
    def test_check_network_succeeds_when_server_time_response_is_ok(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.SERVER_TIME_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {},
            "time_now": "1577444332.192859"
        }
        get_mock.get(regex_url, body=json.dumps(mock_response))

        result = asyncio.get_event_loop().run_until_complete(self.connector.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, result)

    @aioresponses()
    def test_check_network_fails_when_server_time_response_is_not_ok(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.SERVER_TIME_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 1001,
            "ret_msg": "Not OK",
            "ext_code": "",
            "ext_info": "",
            "result": {},
            "time_now": "1577444332.192859"
        }
        get_mock.get(regex_url, body=json.dumps(mock_response))

        result = asyncio.get_event_loop().run_until_complete(self.connector.check_network())
        self.assertEqual(NetworkStatus.NOT_CONNECTED, result)

    @aioresponses()
    def test_check_network_fails_when_server_time_returns_error_code(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.SERVER_TIME_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {},
            "time_now": "1577444332.192859"
        }
        get_mock.get(regex_url, status=405, body=json.dumps(mock_response))

        result = asyncio.get_event_loop().run_until_complete(self.connector.check_network())

        self.assertEqual(NetworkStatus.NOT_CONNECTED, result)

    def test_get_order_book_for_valid_trading_pair(self):
        dummy_order_book = BybitPerpetualOrderBook()
        self.connector._order_book_tracker.order_books["BTC-USDT"] = dummy_order_book
        self.assertEqual(dummy_order_book, self.connector.get_order_book("BTC-USDT"))

    def test_get_order_book_for_invalid_trading_pair_raises_error(self):
        self.assertRaisesRegex(ValueError,
                               "No order book exists for 'BTC-USDT'",
                               self.connector.get_order_book,
                               "BTC-USDT")

    def test_supported_position_modes(self):
        testnet_linear_connector = BybitPerpetualDerivative(bybit_perpetual_api_key='testApiKey',
                                                            bybit_perpetual_secret_key='testSecretKey',
                                                            trading_pairs=[self.trading_pair],
                                                            domain="bybit_perpetual_testnet")
        testnet_non_linear_connector = BybitPerpetualDerivative(bybit_perpetual_api_key='testApiKey',
                                                                bybit_perpetual_secret_key='testSecretKey',
                                                                trading_pairs=[self.non_linear_trading_pair],
                                                                domain="bybit_perpetual_testnet")

        # Case 1: Linear Perpetual
        expected_result = [PositionMode.HEDGE]
        self.assertEqual(expected_result, testnet_linear_connector.supported_position_modes())

        # Case 2: Non-Linear Perpetual
        expected_result = [PositionMode.ONEWAY]
        self.assertEqual(expected_result, testnet_non_linear_connector.supported_position_modes())

    def test_tick_funding_fee_poll_notifier_not_set(self):
        self.assertFalse(self.connector._funding_fee_poll_notifier.is_set())
        self.connector.tick(int(time.time()))
        self.assertFalse(self.connector._funding_fee_poll_notifier.is_set())

    def test_tick_funding_fee_poll_notifier_set(self):
        self.connector._next_funding_fee_timestamp = 0

        self.assertFalse(self.connector._funding_fee_poll_notifier.is_set())
        self.connector.tick(int(time.time()))
        self.assertTrue(self.connector._funding_fee_poll_notifier.is_set())

    def test_fetch_funding_fee_unsupported_trading_pair(self):
        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._fetch_funding_fee("UNSUPPORTED-PAIR")
        )
        result = asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertFalse(result)
        self.assertTrue(
            self._is_logged("ERROR", "Unable to fetch funding fee for UNSUPPORTED-PAIR. Trading pair not supported.")
        )

    @aioresponses()
    def test_fetch_funding_fee_supported_linear_trading_pair_receive_funding(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "symbol": self.ex_trading_pair,
                "side": "Buy",
                "size": 1,
                "funding_rate": 0.0001,
                "exec_fee": 0.00000002,
                "exec_time": "2020-04-13T08:00:00.000Z"
            },
            "time_now": "1586780352.867171",
            "rate_limit_status": 119,
            "rate_limit_reset_ms": 1586780352864,
            "rate_limit": 120
        }
        get_mock.get(regex_url, body=json.dumps(mock_response))

        # Test 2: Support trading pair. Payment > Decimal("0")
        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._fetch_funding_fee(self.trading_pair)
        )
        result = asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertTrue(result)
        self.assertTrue("INFO", f"Funding payment of 0.0001 received on {self.trading_pair} market.")

    @aioresponses()
    def test_fetch_funding_fee_supported_non_linear_trading_pair_receive_funding(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL, self.non_linear_trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        # Notice the Last Funding API response for Non-linear and Linear Perpetuals are slightly different.
        # Mainly in the `exec_time` and `exec_timestamp` data.
        mock_response = {
            "ret_code": 0,
            "ret_msg": "ok",
            "ext_code": "",
            "result": {
                "symbol": self.non_linear_ex_trading_pair,
                "side": "Buy",
                "size": 1,
                "funding_rate": 0.0001,
                "exec_fee": 0.00000002,
                "exec_timestamp": 1575907200
            },
            "ext_info": None,
            "time_now": "1577446900.717204",
            "rate_limit_status": 119,
            "rate_limit_reset_ms": 1577446900724,
            "rate_limit": 120
        }
        get_mock.get(regex_url, body=json.dumps(mock_response))

        # Test 2: Support trading pair. Payment > Decimal("0")
        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._fetch_funding_fee(self.non_linear_trading_pair)
        )
        result = asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertTrue(result)
        self.assertTrue("INFO", f"Funding payment of 0.0001 received on {self.non_linear_trading_pair} market.")

    @aioresponses()
    def test_fetch_funding_fee_supported_trading_pair_paid_funding(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "error",
            "ext_code": "",
            "result": {
                "symbol": self.ex_trading_pair,
                "side": "Buy",
                "size": 1,
                "funding_rate": -0.0001,
                "exec_fee": 0.00000002,
                "exec_time": "2020-04-13T08:00:00.000Z"
            },
            "ext_info": None,
            "time_now": "1577446900.717204",
            "rate_limit_status": 119,
            "rate_limit_reset_ms": 1577446900724,
            "rate_limit": 120
        }
        get_mock.get(regex_url, body=json.dumps(mock_response))

        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._fetch_funding_fee(self.trading_pair)
        )
        result = asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertTrue(result)
        self.assertTrue(self._is_logged('INFO', f"Funding payment of -0.0001 paid on {self.trading_pair} market."))

    @aioresponses()
    def test_user_funding_fee_polling_loop(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        linear_mock_response = {
            "ret_code": 0,
            "ret_msg": "ok",
            "ext_code": "",
            "result": {
                "symbol": self.ex_trading_pair,
                "side": "Buy",
                "size": 1,
                "funding_rate": 0.0001,
                "exec_fee": 0.00000002,
                "exec_time": "2020-04-13T08:00:00.000Z"
            },
            "ext_info": None,
            "time_now": "1577446900.717204",
            "rate_limit_status": 119,
            "rate_limit_reset_ms": 1577446900724,
            "rate_limit": 120
        }
        get_mock.get(regex_url, body=json.dumps(linear_mock_response))

        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL, self.non_linear_trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")
        non_linear_mock_response = {
            "ret_code": 0,
            "ret_msg": "ok",
            "ext_code": "",
            "result": {
                "symbol": self.non_linear_ex_trading_pair,
                "side": "Buy",
                "size": 1,
                "funding_rate": 0.0001,
                "exec_fee": 0.00000002,
                "exec_timestamp": 1575907200
            },
            "ext_info": None,
            "time_now": "1577446900.717204",
            "rate_limit_status": 119,
            "rate_limit_reset_ms": 1577446900724,
            "rate_limit": 120
        }
        get_mock.get(regex_url, body=json.dumps(non_linear_mock_response), callback=self._mock_responses_done_callback)

        # Mock tick() ready to fetch funding fee
        initial_funding_fee_ts = 0
        self.connector._next_funding_fee_timestamp = initial_funding_fee_ts
        self.connector._funding_fee_poll_notifier.set()

        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._user_funding_fee_polling_loop()
        )

        asyncio.get_event_loop().run_until_complete(self.mock_done_event.wait())

        self.assertFalse(self.connector._funding_fee_poll_notifier.is_set())
        self.assertGreater(self.connector._next_funding_fee_timestamp, initial_funding_fee_ts)
        self.assertTrue(self._is_logged("INFO", f"Funding payment of 0.0001 received on {self.trading_pair} market."))
        self.assertTrue(self._is_logged("INFO", f"Funding payment of 0.0001 received on {self.non_linear_trading_pair} market."))

    def test_set_leverage_unsupported_trading_pair(self):
        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._set_leverage("UNSUPPORTED-PAIR")
        )
        asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertTrue(
            self._is_logged("ERROR", "Unable to set leverage for UNSUPPORTED-PAIR. Trading pair not supported.")
        )

    @aioresponses()
    def test_set_leverage_not_ok(self, post_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.SET_LEVERAGE_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        new_leverage: int = 0
        mock_response = {
            "ret_code": 1001,
            "ret_msg": "",
            "ext_code": "20031",
            "result": new_leverage,
            "ext_info": None,
            "time_now": "1577477968.175013",
            "rate_limit_status": 74,
            "rate_limit_reset_ms": 1577477968183,
            "rate_limit": 75
        }
        post_mock.post(regex_url, body=json.dumps(mock_response))

        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._set_leverage(self.trading_pair, new_leverage)
        )
        asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertTrue(
            self._is_logged('ERROR', f"Unable to set leverage for {self.trading_pair}. Leverage: {new_leverage}"))

    @aioresponses()
    def test_set_leverage_ok(self, post_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.SET_LEVERAGE_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        new_leverage: int = 2
        mock_response = {
            "ret_code": 0,
            "ret_msg": "ok",
            "ext_code": "",
            "result": new_leverage,
            "ext_info": None,
            "time_now": "1577477968.175013",
            "rate_limit_status": 74,
            "rate_limit_reset_ms": 1577477968183,
            "rate_limit": 75
        }
        post_mock.post(regex_url, body=json.dumps(mock_response))

        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._set_leverage(self.trading_pair, new_leverage)
        )
        asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertTrue(
            self._is_logged('INFO', f"Leverage Successfully set to {new_leverage} for {self.trading_pair}."))

    @aioresponses()
    def test_update_positions(self, get_mock):
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.GET_POSITIONS_PATH_URL, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response_two_entries = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "user_id": 100004,
                    "symbol": self.ex_trading_pair,
                    "side": "Buy",
                    "size": 10,
                    "position_value": "0.00076448",
                    "entry_price": "13080.78694014",
                    "liq_price": "25",
                    "bust_price": "25",
                    "leverage": 100,
                    "is_isolated": False,
                    "auto_add_margin": 1,
                    "position_margin": "0.40111704",
                    "occ_closing_fee": "0.0003",
                    "realised_pnl": 0,
                    "cum_realised_pnl": 0,
                    "free_qty": 30,
                    "tp_sl_mode": "Full",
                    "unrealised_pnl": 0.00003797,
                    "deleverage_indicator": 0,
                    "risk_id": 1,
                    "stop_loss": 0,
                    "take_profit": 0,
                    "trailing_stop": 0
                },
                {
                    "user_id": 100004,
                    "symbol": self.ex_trading_pair,
                    "side": "Sell",
                    "size": 10,
                    "position_value": "0.00076448",
                    "entry_price": "13080.78694014",
                    "liq_price": "25",
                    "bust_price": "25",
                    "leverage": 100,
                    "is_isolated": False,
                    "auto_add_margin": 1,
                    "position_margin": "0.40111704",
                    "occ_closing_fee": "0.0003",
                    "realised_pnl": 0,
                    "cum_realised_pnl": 0,
                    "free_qty": 30,
                    "tp_sl_mode": "Full",
                    "unrealised_pnl": 0.00003797,
                    "deleverage_indicator": 0,
                    "risk_id": 1,
                    "stop_loss": 0,
                    "take_profit": 0,
                    "trailing_stop": 0
                }
            ],
            "time_now": "1577480599.097287",
            "rate_limit_status": 119,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 120
        }
        mock_response_remove_long_position = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "user_id": 100004,
                    "symbol": self.ex_trading_pair,
                    "side": "Buy",
                    "size": 0,
                    "position_value": "0.00076448",
                    "entry_price": "13080.78694014",
                    "liq_price": "25",
                    "bust_price": "25",
                    "leverage": 100,
                    "is_isolated": False,
                    "auto_add_margin": 1,
                    "position_margin": "0.40111704",
                    "occ_closing_fee": "0.0003",
                    "realised_pnl": 0,
                    "cum_realised_pnl": 0,
                    "free_qty": 30,
                    "tp_sl_mode": "Full",
                    "unrealised_pnl": 0.00003797,
                    "deleverage_indicator": 0,
                    "risk_id": 1,
                    "stop_loss": 0,
                    "take_profit": 0,
                    "trailing_stop": 0
                }
            ],
            "time_now": "1577480599.097287",
            "rate_limit_status": 119,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 120
        }
        get_mock.get(regex_url, body=json.dumps(mock_response_two_entries))
        get_mock.get(regex_url, body=json.dumps(mock_response_remove_long_position))

        self.connector._position_mode = PositionMode.HEDGE
        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._update_positions())
        asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertEqual(2, len(self.connector._account_positions))

        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._update_positions()
        )
        asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertEqual(1, len(self.connector._account_positions))

        # Checks that amount for SHORT positions are negative
        short_position = self.connector._account_positions[f"{self.trading_pair}{PositionSide.SHORT.name}"]
        self.assertEqual(Decimal("-10.0"), short_position.amount)

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_receives_updates_position(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_task = asyncio.get_event_loop().create_task(
            self.connector._user_stream_event_listener())
        self.tracker_task = asyncio.get_event_loop().create_task(
            self.connector._user_stream_tracker.start())

        # Add the authentication response for the websocket
        self.mocking_assistant.add_websocket_json_message(ws_connect_mock.return_value, self._authentication_response(True))

        self.mocking_assistant.add_websocket_json_message(
            ws_connect_mock.return_value,
            {
                "topic": "position",
                "action": "update",
                "data": [
                    {
                        "user_id": 1,
                        "symbol": "BTCUSDT",
                        "size": 11,
                        "side": "Sell",
                        "position_value": "0.00159252",
                        "entry_price": "6907.291588174717",
                        "liq_price": "7100.234",
                        "bust_price": "7088.1234",
                        "leverage": "1",
                        "order_margin": "1",
                        "position_margin": "1",
                        "available_balance": "2",
                        "take_profit": "0",
                        "tp_trigger_by": "LastPrice",
                        "stop_loss": "0",
                        "sl_trigger_by": "",
                        "realised_pnl": "0.10",
                        "trailing_stop": "0",
                        "trailing_active": "0",
                        "wallet_balance": "4.12",
                        "risk_id": 1,
                        "occ_closing_fee": "0.1",
                        "occ_funding_fee": "0.1",
                        "auto_add_margin": 0,
                        "cum_realised_pnl": "0.12",
                        "position_status": "Normal",
                        "position_seq": 14
                    }
                ]
            })

        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.mocking_assistant.add_websocket_json_message(ws_connect_mock.return_value, self._finalMessage)

        # Force execution of queued tasks by stopping current execution with a short sleep
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.3))

        for key in self.connector._account_positions:
            position = self.connector._account_positions[key]
            self.assertEqual(position.position_side, PositionSide.SHORT)
            self.assertEqual(position.amount, Decimal("-11.0"))
            self.assertEqual(position.leverage, 1)
            self.assertEqual(position.entry_price, Decimal('6907.291588174717'))

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_receives_updates_order(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_task = asyncio.get_event_loop().create_task(
            self.connector._user_stream_event_listener())
        self.tracker_task = asyncio.get_event_loop().create_task(
            self.connector._user_stream_tracker.start())

        # Prepare inflight order
        self.connector.start_tracking_order("xxxxxxxx-xxxx-xxxx-9a8f-4a973eb5c418",
                                            "xxxxxxxx-xxxx-xxxx-9a8f-4a973eb5c418", "BTC-USDT", "Sell", "8579.5", 1,
                                            "Market", 1, "")

        # Add the authentication response for the websocket
        self.mocking_assistant.add_websocket_json_message(ws_connect_mock.return_value, self._authentication_response(True))

        self.mocking_assistant.add_websocket_json_message(
            ws_connect_mock.return_value,
            {
                "topic": "order",
                "data": [
                    {
                        "order_id": "xxxxxxxx-xxxx-xxxx-9a8f-4a973eb5c418",
                        "order_link_id": "xxxxxxxx-xxxx-xxxx-9a8f-4a973eb5c418",
                        "symbol": "BTCUSDT",
                        "side": "Sell",
                        "order_type": "Market",
                        "price": "8579.5",
                        "qty": 1,
                        "time_in_force": "ImmediateOrCancel",
                        "create_type": "CreateByClosing",
                        "cancel_type": "",
                        "order_status": "Cancelled",
                        "leaves_qty": 0,
                        "cum_exec_qty": 1,
                        "cum_exec_value": "0.00011655",
                        "cum_exec_fee": "0.00000009",
                        "timestamp": "2020-01-14T14:09:31.778Z",
                        "take_profit": "0",
                        "stop_loss": "0",
                        "trailing_stop": "0",
                        "trailing_active": "0",
                        "last_exec_price": "8580",
                        "reduce_only": False,
                        "close_on_trigger": False
                    }
                ]
            })

        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.mocking_assistant.add_websocket_json_message(ws_connect_mock.return_value, self._finalMessage)

        # Wait until the connector finishes processing the message queue
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.3))

        self.assertTrue(self._is_logged('INFO', 'Successfully cancelled order xxxxxxxx-xxxx-xxxx-9a8f-4a973eb5c418'))

    @patch('aiohttp.ClientSession.ws_connect', new_callable=AsyncMock)
    def test_listening_process_receives_updates_execution(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_task = asyncio.get_event_loop().create_task(
            self.connector._user_stream_event_listener())
        self.tracker_task = asyncio.get_event_loop().create_task(
            self.connector._user_stream_tracker.start())

        # Prepare inflight order
        self.connector.start_tracking_order("xxxxxxxx-xxxx-xxxx-9a8f-4a973eb5c419",
                                            "xxxxxxxx-xxxx-xxxx-9a8f-4a973eb5c419", "BTC-USDT", "Buy", "8300", 1,
                                            "Market", 1, "")

        # Add the authentication response for the websocket
        self.mocking_assistant.add_websocket_json_message(ws_connect_mock.return_value, self._authentication_response(True))

        self.mocking_assistant.add_websocket_json_message(
            ws_connect_mock.return_value,
            {
                "topic": "execution",
                "data": [
                    {
                        "symbol": "BTCUSDT",
                        "side": "Buy",
                        "order_id": "xxxxxxxx-xxxx-xxxx-9a8f-4a973eb5c419",
                        "exec_id": "xxxxxxxx-xxxx-xxxx-8b66-c3d2fcd352f6",
                        "order_link_id": "xxxxxxxx-xxxx-xxxx-9a8f-4a973eb5c419",
                        "price": "8300",
                        "order_qty": 1,
                        "exec_type": "Trade",
                        "exec_qty": 1,
                        "exec_fee": "0.00000009",
                        "leaves_qty": 0,
                        "is_maker": False,
                        "trade_time": "2020-01-14T14:07:23.629Z"
                    }
                ]
            })

        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.mocking_assistant.add_websocket_json_message(ws_connect_mock.return_value, self._finalMessage)

        # Wait until the connector finishes processing the message queue
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.3))

        self.assertTrue("xxxxxxxx-xxxx-xxxx-8b66-c3d2fcd352f6" in self.connector.in_flight_orders[
            "xxxxxxxx-xxxx-xxxx-9a8f-4a973eb5c419"].trade_id_set)

    def test_get_funding_info_trading_pair_exist(self):
        expected_funding_info: FundingInfo = FundingInfo(
            trading_pair="BTC-USD",
            index_price=Decimal("50000"),
            mark_price=Decimal("50000"),
            next_funding_utc_timestamp=int(pd.Timestamp('2021-08-23T08:00:00Z', tz="UTC").timestamp()),
            rate=(Decimal('-15') * Decimal(1e-6)),
        )
        self.connector._order_book_tracker.data_source._funding_info = {
            "BTC-USD": expected_funding_info
        }

        result = self.connector.get_funding_info("BTC-USD")

        self.assertEqual(expected_funding_info.trading_pair, result.trading_pair)
        self.assertEqual(expected_funding_info.index_price, result.index_price)
        self.assertEqual(expected_funding_info.mark_price, result.mark_price)
        self.assertEqual(expected_funding_info.next_funding_utc_timestamp, result.next_funding_utc_timestamp)
        self.assertEqual(expected_funding_info.rate, result.rate)

    @aioresponses()
    def test_get_funding_info_trading_pair_does_not_exist(self, get_mock):
        expected_funding_info: FundingInfo = FundingInfo(
            trading_pair=self.trading_pair,
            index_price=Decimal("50000"),
            mark_price=Decimal("50000"),
            next_funding_utc_timestamp=int(pd.Timestamp('2021-08-23T08:00:00Z', tz="UTC").timestamp()),
            rate=(Decimal('-15')),
        )
        path_url = bybit_utils.rest_api_path_for_endpoint(CONSTANTS.LATEST_SYMBOL_INFORMATION_ENDPOINT, self.trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self.domain)
        regex_url = re.compile(f"^{url}")

        mock_response = {
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                # Truncated Response
                {
                    "symbol": self.ex_trading_pair,
                    "mark_price": "50000",
                    "index_price": "50000",
                    "funding_rate": "-15",
                    "predicted_funding_rate": "-15",
                    "next_funding_time": "2021-08-23T08:00:00Z",
                }
            ],
            "time_now": "1577484619.817968"
        }
        get_mock.get(regex_url, body=json.dumps(mock_response), callback=self._mock_responses_done_callback)

        result = self.connector.get_funding_info(self.trading_pair)
        self.assertIsNone(result)

        self.connector.get_funding_info(self.trading_pair)

        asyncio.get_event_loop().run_until_complete(self.mock_done_event.wait())
        self.assertIsNotNone(self.connector.get_funding_info(self.trading_pair))
        funding_info = self.connector.get_funding_info(self.trading_pair)
        self.assertEqual(expected_funding_info.trading_pair, funding_info.trading_pair)
        self.assertEqual(expected_funding_info.index_price, funding_info.index_price)
        self.assertEqual(expected_funding_info.mark_price, funding_info.mark_price)
        self.assertEqual(expected_funding_info.next_funding_utc_timestamp, funding_info.next_funding_utc_timestamp)
        self.assertEqual(expected_funding_info.rate, funding_info.rate)

    def test_format_trading_rules_linear(self):
        collateral_token = self.quote_asset
        min_order_size = 1
        max_order_size = 2
        min_price_increment = 3
        min_base_amount_increment = 4
        mocked_response = self._get_symbols_mock_response(
            linear=True,
            min_order_size=min_order_size,
            max_order_size=max_order_size,
            min_price_increment=min_price_increment,
            min_base_amount_increment=min_base_amount_increment,
        )

        trading_rules = self.connector._format_trading_rules(mocked_response["result"])

        self.assertEqual(1, len(trading_rules))

        trading_rule = trading_rules[self.trading_pair]

        self.assertEqual(min_order_size, trading_rule.min_order_size)
        self.assertEqual(max_order_size, trading_rule.max_order_size)
        self.assertEqual(min_price_increment, trading_rule.min_price_increment)
        self.assertEqual(min_base_amount_increment, trading_rule.min_base_amount_increment)
        self.assertEqual(collateral_token, trading_rule.buy_order_collateral_token)
        self.assertEqual(collateral_token, trading_rule.sell_order_collateral_token)

    def test_format_trading_rules_non_linear(self):
        collateral_token = self.non_linear_base
        mocked_response = self._get_symbols_mock_response(linear=False)

        trading_rules = self.connector._format_trading_rules(mocked_response["result"])

        self.assertEqual(1, len(trading_rules))

        trading_rule = trading_rules[self.non_linear_trading_pair]

        self.assertEqual(collateral_token, trading_rule.buy_order_collateral_token)
        self.assertEqual(collateral_token, trading_rule.sell_order_collateral_token)

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()

        linear_buy_collateral_token = self.connector.get_buy_collateral_token(self.trading_pair)
        linear_sell_collateral_token = self.connector.get_sell_collateral_token(self.trading_pair)

        self.assertEqual(self.quote_asset, linear_buy_collateral_token)
        self.assertEqual(self.quote_asset, linear_sell_collateral_token)

        non_linear_buy_collateral_token = self.connector.get_buy_collateral_token(self.non_linear_trading_pair)
        non_linear_sell_collateral_token = self.connector.get_sell_collateral_token(self.non_linear_trading_pair)

        self.assertEqual(self.non_linear_base, non_linear_buy_collateral_token)
        self.assertEqual(self.non_linear_base, non_linear_sell_collateral_token)
