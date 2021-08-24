import asyncio
import json
import pandas as pd
import time
from collections import deque
from decimal import Decimal
from unittest import TestCase
from unittest.mock import AsyncMock, patch, PropertyMock

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source import \
    BybitPerpetualAPIOrderBookDataSource
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_derivative import BybitPerpetualDerivative
from hummingbot.connector.trading_rule import TradingRule

from hummingbot.core.event.event_logger import EventLogger

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_in_flight_order import BybitPerpetualInFlightOrder
from hummingbot.core.event.events import OrderType, PositionAction, TradeType, MarketEvent, FundingInfo, PositionMode


class BybitPerpetualDerivativeTests(TestCase):
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.base_asset = "BTC"
        self.quote_asset = "USDT"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"
        self.ex_trading_pair = f"{self.base_asset}{self.quote_asset}"

        self.api_requests_data = asyncio.Queue()
        self.api_responses_json: asyncio.Queue = asyncio.Queue()
        self.api_responses_status = deque()
        self.log_records = []
        self.async_task = None

        self.connector = BybitPerpetualDerivative(bybit_perpetual_api_key='testApiKey',
                                                  bybit_perpetual_secret_key='testSecretKey',
                                                  trading_pairs=[self.trading_pair],
                                                  domain="bybit_perpetual_testnet")

        self.connector.logger().setLevel(1)
        self.connector.logger().addHandler(self)

        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {
            "bybit_perpetual_testnet": {self.ex_trading_pair: self.trading_pair}}

        self.buy_order_created_logger: EventLogger = EventLogger()
        self.sell_order_created_logger: EventLogger = EventLogger()
        self.order_cancelled_logger: EventLogger = EventLogger()
        self.order_failure_logger: EventLogger = EventLogger()
        self.connector.add_listener(MarketEvent.BuyOrderCreated, self.buy_order_created_logger)
        self.connector.add_listener(MarketEvent.SellOrderCreated, self.sell_order_created_logger)
        self.connector.add_listener(MarketEvent.OrderCancelled, self.order_cancelled_logger)
        self.connector.add_listener(MarketEvent.OrderFailure, self.order_failure_logger)

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _get_next_api_response_status(self):
        status = self.api_responses_status.popleft()
        return status

    async def _get_next_api_response_json(self):
        json = await self.api_responses_json.get()
        return json

    def _handle_http_request(self, url, headers, params=None, data=None):
        response = AsyncMock()
        type(response).status = PropertyMock(side_effect=self._get_next_api_response_status)
        response.json.side_effect = self._get_next_api_response_json
        components = params if params else data
        self.api_requests_data.put_nowait((url, headers, components))
        return response

    def _configure_mock_api(self, mock_api: AsyncMock):
        mock_api.side_effect = self._handle_http_request

    def _simulate_trading_rules_initialized(self):
        self.connector._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

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

    @patch('hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils.get_tracking_nonce')
    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_create_buy_order(self, post_mock, nonce_provider_mock):
        nonce_provider_mock.return_value = 1000
        self._configure_mock_api(post_mock)
        self._simulate_trading_rules_initialized()

        self.connector._leverage[self.trading_pair] = 10

        new_order_id = self.connector.buy(trading_pair=self.trading_pair,
                                          amount=Decimal("1"),
                                          order_type=OrderType.LIMIT,
                                          price=Decimal("46000"),
                                          position_action=PositionAction.OPEN)

        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 1,
                "order_id": "335fd977-e5a5-4781-b6d0-c772d5bfb95b",
                "symbol": "BTCUSD",
                "side": "Buy",
                "order_type": "Limit",
                "price": 8800,
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
                "order_link_id": "",
                "created_at": "2019-11-30T11:03:43.452Z",
                "updated_at": "2019-11-30T11:03:43.455Z"
            },
            "time_now": "1575111823.458705",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        })
        buy_request_url, buy_request_headers, buy_request_data = asyncio.get_event_loop().run_until_complete(
            self.api_requests_data.get())

        buy_json = json.loads(buy_request_data)

        self.assertEqual(f"B-{self.trading_pair}-1000", new_order_id)
        self.assertEqual("Buy", buy_json["side"])
        self.assertEqual("BTCUSDT", buy_json["symbol"])
        self.assertEqual("Limit", buy_json["order_type"])
        self.assertEqual(1, buy_json["qty"])
        self.assertEqual(46000, buy_json["price"])
        self.assertEqual("GoodTillCancel", buy_json["time_in_force"])
        self.assertEqual(new_order_id, buy_json["order_link_id"])

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

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_create_buy_order_fails_when_amount_smaller_than_minimum(self, post_mock, app_mock):
        self._configure_mock_api(post_mock)
        self._simulate_trading_rules_initialized()

        self.connector._leverage[self.trading_pair] = 10

        new_order_id = self.connector.buy(trading_pair=self.trading_pair,
                                          amount=Decimal("0.0001"),
                                          order_type=OrderType.LIMIT,
                                          price=Decimal("46000"),
                                          position_action=PositionAction.OPEN)

        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 1,
                "order_id": "335fd977-e5a5-4781-b6d0-c772d5bfb95b",
                "symbol": "BTCUSD",
                "side": "Buy",
                "order_type": "Limit",
                "price": 8800,
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
                "order_link_id": "",
                "created_at": "2019-11-30T11:03:43.452Z",
                "updated_at": "2019-11-30T11:03:43.455Z"
            },
            "time_now": "1575111823.458705",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        })

        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))

        self.assertNotIn(new_order_id, self.connector.in_flight_orders)
        self.assertTrue(self._is_logged("NETWORK",
                                        "Error submitting BUY LIMIT order to Bybit Perpetual for 0.000100"
                                        " BTC-USDT 46000. Error: BUY order amount 0.000100 is lower than the"
                                        " minimum order size 0.01."))

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

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_create_order_fails_and_logs_when_api_response_has_erroneous_return_code(self, post_mock, app_mock):
        self._configure_mock_api(post_mock)
        self._simulate_trading_rules_initialized()

        self.connector._leverage[self.trading_pair] = 10

        new_order_id = self.connector.buy(trading_pair=self.trading_pair,
                                          amount=Decimal("1"),
                                          order_type=OrderType.LIMIT,
                                          price=Decimal("46000"),
                                          position_action=PositionAction.OPEN)

        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
            "ret_code": 1000,
            "ret_msg": "Error",
            "ext_code": "",
            "ext_info": "",
            "result": {"test_key": "test_value"},
            "time_now": "1575111823.458705",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        })

        asyncio.get_event_loop().run_until_complete(
            self.api_requests_data.get())

        self.assertNotIn(new_order_id, self.connector.in_flight_orders)
        self.assertTrue(any(record.levelname == "NETWORK"
                            and ("Error submitting BUY LIMIT order to Bybit Perpetual for 1.000000 BTC-USDT 46000.0000."
                                 " Error: Order is rejected by the API. Parameters:")
                            in record.getMessage()
                            for record in self.log_records))
        failure_events = self.order_failure_logger.event_log
        self.assertEqual(1, len(failure_events))
        self.assertEqual(new_order_id, failure_events[0].order_id)

    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_create_order_raises_cancelled_errors(self, post_mock):
        post_mock.side_effect = asyncio.CancelledError()
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

    @patch('hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils.get_tracking_nonce')
    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_create_sell_order(self, post_mock, nonce_provider_mock):
        nonce_provider_mock.return_value = 1000
        self._configure_mock_api(post_mock)
        self._simulate_trading_rules_initialized()

        self.connector._leverage[self.trading_pair] = 10

        new_order_id = self.connector.sell(trading_pair=self.trading_pair,
                                           amount=Decimal("1"),
                                           order_type=OrderType.MARKET,
                                           price=Decimal("46000"),
                                           position_action=PositionAction.OPEN)

        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": {
                "user_id": 1,
                "order_id": "335fd977-e5a5-4781-b6d0-c772d5bfb95b",
                "symbol": "BTCUSD",
                "side": "Sell",
                "order_type": "Market",
                "price": 8800,
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
                "order_link_id": "",
                "created_at": "2019-11-30T11:03:43.452Z",
                "updated_at": "2019-11-30T11:03:43.455Z"
            },
            "time_now": "1575111823.458705",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        })
        buy_request_url, buy_request_headers, buy_request_data = asyncio.get_event_loop().run_until_complete(
            self.api_requests_data.get())

        sell_json = json.loads(buy_request_data)

        self.assertEqual(f"S-{self.trading_pair}-1000", new_order_id)
        self.assertEqual("Sell", sell_json["side"])
        self.assertEqual("BTCUSDT", sell_json["symbol"])
        self.assertEqual("Market", sell_json["order_type"])
        self.assertEqual(1, sell_json["qty"])
        self.assertNotIn("price", sell_json)
        self.assertEqual("GoodTillCancel", sell_json["time_in_force"])
        self.assertEqual(new_order_id, sell_json["order_link_id"])

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

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_trading_rules_with_polling_loop(self, get_mock):
        self._configure_mock_api(get_mock)

        self.async_task = asyncio.get_event_loop().create_task(self.connector._trading_rules_polling_loop())

        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
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
        })

        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))

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

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_trading_rules_logs_rule_parsing_error(self, get_mock):
        self._configure_mock_api(get_mock)

        self.async_task = asyncio.get_event_loop().create_task(self.connector._trading_rules_polling_loop())

        self.api_responses_status.append(200)
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
        self.api_responses_json.put_nowait({
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [symbol_info],
            "time_now": "1615801223.589808"
        })

        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))

        self.assertTrue(self._is_logged("ERROR", f"Error parsing the trading pair rule: {symbol_info}. Skipping..."))

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_trading_rules_polling_loop_raises_cancelled_error(self, get_mock):
        get_mock.side_effect = asyncio.CancelledError()

        with self.assertRaises(asyncio.CancelledError):
            asyncio.get_event_loop().run_until_complete(self.connector._trading_rules_polling_loop())

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_trading_rules_polling_loop_logs_errors(self, get_mock, app_mock):
        get_mock.side_effect = Exception("Test Error")

        self.async_task = asyncio.get_event_loop().create_task(self.connector._trading_rules_polling_loop())
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))

        self.assertTrue(self._is_logged("NETWORK", "Unexpected error while fetching trading rules. Error: Test Error"))

    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_cancel_tracked_order(self, post_mock):
        self._configure_mock_api(post_mock)

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

        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
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
        })

        request_url, request_headers, request_data = asyncio.get_event_loop().run_until_complete(
            self.api_requests_data.get())

        cancel_json = json.loads(request_data)

        self.assertEqual("BTCUSDT", cancel_json["symbol"])
        self.assertEqual("EO1", cancel_json["order_id"])
        self.assertEqual(cancelled_order_id, cancel_json["order_link_id"])

    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_cancel_tracked_order_logs_error_notified_in_the_response(self, post_mock):
        self._configure_mock_api(post_mock)

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

        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
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
        })

        asyncio.get_event_loop().run_until_complete(self.api_requests_data.get())

        self.assertTrue(self._is_logged(
            "ERROR",
            "Failed to cancel order O1:"
            " Bybit Perpetual encountered a problem cancelling the order (1001 - Test error description)"))

    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_cancel_tracked_order_logs_error_when_cancelling_non_tracked_order(self, post_mock):
        self._configure_mock_api(post_mock)

        self._simulate_trading_rules_initialized()

        self.connector.cancel(trading_pair=self.trading_pair, order_id="O1")
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.4))

        self.assertTrue(self._is_logged(
            "ERROR",
            "Failed to cancel order O1: Order O1 is not being tracked"))

    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_cancel_tracked_order_raises_cancelled(self, post_mock):
        post_mock.side_effect = asyncio.CancelledError()

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

    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_cancel_all_in_flight_orders(self, post_mock):
        self._configure_mock_api(post_mock)

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

        # Emulate first cancellation happening without problems
        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
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
        })
        # Emulate second cancellation failing
        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
            "ret_code": 1001,
            "ret_msg": "Test error description",
            "ext_code": "",
            "ext_info": "",
            "result": {},
            "time_now": "1575112681.814760",
            "rate_limit_status": 98,
            "rate_limit_reset_ms": 1580885703683,
            "rate_limit": 100
        })

        cancellation_results = asyncio.get_event_loop().run_until_complete(self.connector.cancel_all(timeout_seconds=2))

        self.assertEqual(2, len(cancellation_results))
        self.assertTrue(any(map(lambda result: result.order_id == "O1" and result.success, cancellation_results)))
        self.assertTrue(any(map(lambda result: result.order_id == "O2" and not result.success, cancellation_results)))

    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_cancel_all_logs_warning_when_process_times_out(self, post_mock):
        self._configure_mock_api(post_mock)

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

        # We don't register any API response for the process to time out
        self.api_responses_status.append(200)

        cancellation_results = asyncio.get_event_loop().run_until_complete(
            self.connector.cancel_all(timeout_seconds=0.1))

        self.assertTrue(self._is_logged("WARNING", "Cancellation of all active orders for Bybit Perpetual connector"
                                                   " stopped after max wait time"))
        self.assertEqual(1, len(cancellation_results))
        self.assertTrue(cancellation_results[0].order_id == "O1" and not cancellation_results[0].success)

    def test_fee_estimation(self):
        fee = self.connector.get_fee(base_currency="BCT", quote_currency="USDT", order_type=OrderType.LIMIT,
                                     order_side=TradeType.BUY, amount=Decimal(1), price=Decimal(45000))
        self.assertEqual(Decimal("0"), fee.percent)

        fee = self.connector.get_fee(base_currency="BCT", quote_currency="USDT", order_type=OrderType.MARKET,
                                     order_side=TradeType.BUY, amount=Decimal(1), price=Decimal(45000))
        self.assertEqual(Decimal("0.00075"), fee.percent)

    def test_connector_ready_status(self):
        self.assertFalse(self.connector.ready)

        self._simulate_trading_rules_initialized()
        self.connector._order_book_tracker._order_books_initialized.set()
        self.connector._account_balances["USDT"] = Decimal(10000)
        self.connector._funding_info[self.trading_pair] = FundingInfo(
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
        local_connector._funding_info[self.trading_pair] = FundingInfo(
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

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_balances(self, get_mock):
        self._configure_mock_api(get_mock)

        self.connector._account_balances["HBOT"] = Decimal(1000)
        self.connector._account_balances["USDT"] = Decimal(100000)
        self.connector._account_available_balances["HBOT"] = Decimal(1000)
        self.connector._account_available_balances["USDT"] = Decimal(0)

        # Emulate first cancellation happening without problems
        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
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
        })

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

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_order_status_without_created_in_server_in_flight_order_does_not_execute_status_request(self,
                                                                                                           get_mock):
        self._configure_mock_api(get_mock)

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

        # We don't register any API response for the process to time out

        asyncio.get_event_loop().run_until_complete(self.connector._update_order_status())

        self.assertTrue(self._is_logged("DEBUG", "Polling for order status updates of 0 orders."))

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_order_status_for_cancellation(self, get_mock):
        self._configure_mock_api(get_mock)

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

        # Emulate first cancellation happening without problems
        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
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
        })

        asyncio.get_event_loop().run_until_complete(self.connector._update_order_status())
        request_url, request_headers, request_data = asyncio.get_event_loop().run_until_complete(
            self.api_requests_data.get())

        self.assertEqual("BTCUSDT", request_data["symbol"])
        self.assertEqual("EO1", request_data["order_id"])
        self.assertEqual("O1", request_data["order_link_id"])
        self.assertEqual(0, len(self.connector.in_flight_orders))
        self.assertTrue(self._is_logged("INFO", "Successfully cancelled order O1"))
        cancellation_events = self.order_cancelled_logger.event_log
        self.assertEqual(1, len(cancellation_events))
        self.assertEqual("O1", cancellation_events[0].order_id)

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_order_status_for_rejection(self, get_mock):
        self._configure_mock_api(get_mock)

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

        # Emulate first cancellation happening without problems
        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
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
        })

        asyncio.get_event_loop().run_until_complete(self.connector._update_order_status())
        request_url, request_headers, request_data = asyncio.get_event_loop().run_until_complete(
            self.api_requests_data.get())

        self.assertEqual("BTCUSDT", request_data["symbol"])
        self.assertEqual("EO1", request_data["order_id"])
        self.assertEqual("O1", request_data["order_link_id"])
        self.assertEqual(0, len(self.connector.in_flight_orders))
        self.assertTrue(self._is_logged("INFO", "The market order O1 has failed according to order status event. "
                                                "Reason: Out of limits"))
        failure_events = self.order_failure_logger.event_log
        self.assertEqual(1, len(failure_events))
        self.assertEqual("O1", failure_events[0].order_id)

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_order_status_logs_errors_during_status_request(self, get_mock):
        self._configure_mock_api(get_mock)

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

        self.api_responses_status.append(405)
        self.api_responses_json.put_nowait({
            "ret_code": 1001,
            "ret_msg": "Error",
            "ext_code": "",
            "ext_info": "",
            "result": {},
            "time_now": "1597171013.867068",
            "rate_limit_status": 599,
            "rate_limit_reset_ms": 1597171013861,
            "rate_limit": 600
        })

        asyncio.get_event_loop().run_until_complete(self.connector._update_order_status())

        self.assertTrue(any(record.levelname == "ERROR"
                            and ("Error fetching order status. Response: Error fetching data from"
                                 " https://api-testnet.bybit.com/v2/private/order. HTTP status is 405. Message:")
                            in record.getMessage()
                            for record in self.log_records))

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_process_order_event_message_for_creation_confirmation(self, get_mock):
        self._configure_mock_api(get_mock)

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

    def test_supported_position_modes(self):
        expected_result = [PositionMode.ONEWAY, PositionMode.HEDGE]
        self.assertEqual(expected_result, self.connector.supported_position_modes())

    @patch("hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils.get_next_funding_timestamp")
    def test_tick_funding_fee_poll_notifier_set(self, mock_time):
        mock_time.return_value = pd.Timestamp("2021-08-21-01:00:00", tz="UTC").timestamp()

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

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_fetch_funding_fee_supported_trading_pair_receive_funding(self, mock_request):
        self._configure_mock_api(mock_request)

        # Test 2: Support trading pair. Payment > Decimal("0")
        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
            "ret_code": 0,
            "ret_msg": "ok",
            "ext_code": "",
            "result": {
                "symbol": self.ex_trading_pair,
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
        })

        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._fetch_funding_fee(self.trading_pair)
        )
        result = asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertTrue(result)
        self.assertTrue("INFO", f"Funding payment of 0.0001 received on {self.trading_pair} market.")

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_fetch_funding_fee_supported_trading_pair_paid_funding(self, mock_request):
        self._configure_mock_api(mock_request)

        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
            "ret_code": 0,
            "ret_msg": "error",
            "ext_code": "",
            "result": {
                "symbol": self.ex_trading_pair,
                "side": "Buy",
                "size": 1,
                "funding_rate": -0.0001,
                "exec_fee": 0.00000002,
                "exec_timestamp": 1575907200
            },
            "ext_info": None,
            "time_now": "1577446900.717204",
            "rate_limit_status": 119,
            "rate_limit_reset_ms": 1577446900724,
            "rate_limit": 120
        })

        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._fetch_funding_fee(self.trading_pair)
        )
        result = asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertTrue(result)
        self.assertTrue(self._is_logged('INFO', f"Funding payment of -0.0001 paid on {self.trading_pair} market."))

    def test_set_leverage_unsupported_trading_pair(self):
        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._set_leverage("UNSUPPORTED-PAIR")
        )
        asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertTrue(
            self._is_logged("ERROR", "Unable to set leverage for UNSUPPORTED-PAIR. Trading pair not supported.")
        )

    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_set_leverage_not_ok(self, mock_request):
        self._configure_mock_api(mock_request)

        new_leverage: int = 0

        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
            "ret_code": 0,
            "ret_msg": "",
            "ext_code": "20031",
            "result": new_leverage,
            "ext_info": None,
            "time_now": "1577477968.175013",
            "rate_limit_status": 74,
            "rate_limit_reset_ms": 1577477968183,
            "rate_limit": 75
        })

        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._set_leverage(self.trading_pair, new_leverage)
        )
        asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertTrue(
            self._is_logged('ERROR', f"Unable to set leverage for {self.trading_pair}. Leverage: {new_leverage}"))

    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_set_leverage_ok(self, mock_request):
        self._configure_mock_api(mock_request)
        new_leverage: int = 2

        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
            "ret_code": 0,
            "ret_msg": "ok",
            "ext_code": "",
            "result": new_leverage,
            "ext_info": None,
            "time_now": "1577477968.175013",
            "rate_limit_status": 74,
            "rate_limit_reset_ms": 1577477968183,
            "rate_limit": 75
        })

        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._set_leverage(self.trading_pair, new_leverage)
        )
        asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertTrue(
            self._is_logged('INFO', f"Leverage Successfully set to {new_leverage} for {self.trading_pair}."))

    @patch("aiohttp.ClientSession.get", new_callable=AsyncMock)
    def test_update_positions(self, mock_request):
        self._configure_mock_api(mock_request)

        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "is_valid": True,
                    "data": {
                        "id": 0,
                        "position_idx": 0,
                        "mode": 0,
                        "user_id": 118921,
                        "risk_id": 1,
                        "symbol": self.trading_pair,
                        "side": "Buy",
                        "size": 10,
                        "position_value": "0.00076448",
                        "entry_price": "13080.78694014",
                        "is_isolated": False,
                        "auto_add_margin": 1,
                        "leverage": "100",
                        "effective_leverage": "0.01",
                        "position_margin": "0.40111704",
                        "liq_price": "25",
                        "bust_price": "25",
                        "occ_closing_fee": "0.0003",
                        "occ_funding_fee": "0",
                        "take_profit": "0",
                        "stop_loss": "0",
                        "trailing_stop": "0",
                        "position_status": "Normal",
                        "deleverage_indicator": 1,
                        "oc_calc_data": "{\"blq\":0,\"slq\":0,\"bmp\":0,\"smp\":0,\"fq\":-10,\"bv2c\":0.0115075,\"sv2c\":0.0114925}",
                        "order_margin": "0",
                        "wallet_balance": "0.40141704",
                        "realised_pnl": "-0.00000008",
                        "unrealised_pnl": 0.00003797,
                        "cum_realised_pnl": "-0.090626",
                        "cross_seq": 764786721,
                        "position_seq": 581513847,
                        "created_at": "2020-08-10T07:04:32Z",
                        "updated_at": "2020-11-02T00:00:11.943371457Z",
                        "tp_sl_mode": "Partial"
                    }
                },
            ],
            "time_now": "1604302124.031104",
            "rate_limit_status": 118,
            "rate_limit_reset_ms": 1604302124020,
            "rate_limit": 120
        })

        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._update_positions())
        asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertEqual(1, len(self.connector._account_positions))

        self.api_responses_status.append(200)
        self.api_responses_json.put_nowait({
            "ret_code": 0,
            "ret_msg": "OK",
            "ext_code": "",
            "ext_info": "",
            "result": [
                {
                    "is_valid": True,
                    "data": {
                        "id": 0,
                        "position_idx": 0,
                        "mode": 0,
                        "user_id": 118921,
                        "risk_id": 1,
                        "symbol": self.trading_pair,
                        "side": "Buy",
                        "size": 0,
                        "position_value": "0.00076448",
                        "entry_price": "13080.78694014",
                        "is_isolated": False,
                        "auto_add_margin": 1,
                        "leverage": "100",
                        "effective_leverage": "0.01",
                        "position_margin": "0.40111704",
                        "liq_price": "25",
                        "bust_price": "25",
                        "occ_closing_fee": "0.0003",
                        "occ_funding_fee": "0",
                        "take_profit": "0",
                        "stop_loss": "0",
                        "trailing_stop": "0",
                        "position_status": "Normal",
                        "deleverage_indicator": 1,
                        "oc_calc_data": "{\"blq\":0,\"slq\":0,\"bmp\":0,\"smp\":0,\"fq\":-10,\"bv2c\":0.0115075,\"sv2c\":0.0114925}",
                        "order_margin": "0",
                        "wallet_balance": "0.40141704",
                        "realised_pnl": "-0.00000008",
                        "unrealised_pnl": 0.00003797,
                        "cum_realised_pnl": "-0.090626",
                        "cross_seq": 764786721,
                        "position_seq": 581513847,
                        "created_at": "2020-08-10T07:04:32Z",
                        "updated_at": "2020-11-02T00:00:11.943371457Z",
                        "tp_sl_mode": "Partial"
                    }
                },
            ],
            "time_now": "1604302130",
            "rate_limit_status": 118,
            "rate_limit_reset_ms": 1604302124030,
            "rate_limit": 120
        })

        self.connector_task = asyncio.get_event_loop().create_task(
            self.connector._update_positions()
        )
        asyncio.get_event_loop().run_until_complete(self.connector_task)
        self.assertEqual(0, len(self.connector._account_positions))
