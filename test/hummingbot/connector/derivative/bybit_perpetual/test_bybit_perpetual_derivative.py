import asyncio
import json
from collections import deque
from decimal import Decimal
from unittest import TestCase
from unittest.mock import AsyncMock, patch, PropertyMock

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source import \
    BybitPerpetualAPIOrderBookDataSource
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_derivative import BybitPerpetualDerivative
from hummingbot.connector.trading_rule import TradingRule

from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import OrderType, PositionAction, TradeType, MarketEvent


class BybitPerpetualDerivativeTests(TestCase):
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.base_asset = "BTC"
        self.quote_asset = "USDT"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"

        self.api_requests_data = asyncio.Queue()
        self.api_responses_json: asyncio.Queue = asyncio.Queue()
        self.api_responses_status = deque()
        self.log_records = []
        self.listening_task = None

        self.connector = BybitPerpetualDerivative(bybit_perpetual_api_key='testApiKey',
                                                  bybit_perpetual_secret_key='testSecretKey',
                                                  trading_pairs=[self.trading_pair])

        self.connector.logger().setLevel(1)
        self.connector.logger().addHandler(self)

        self.market_order_failure_logger: EventLogger = EventLogger()
        self.connector.add_listener(MarketEvent.OrderFailure, self.market_order_failure_logger)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
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

    def _handle_http_request(self, url, headers, data):
        response = AsyncMock()
        type(response).status = PropertyMock(side_effect=self._get_next_api_response_status)
        response.json.side_effect = self._get_next_api_response_json

        self.api_requests_data.put_nowait((url, headers, data))
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
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSDT": "BTC-USDT"}}

        self.connector.set_leverage(self.trading_pair, 10)

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

    def test_create_order_with_invalid_position_action_raises_value_error(self):
        self._simulate_trading_rules_initialized()
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSDT": "BTC-USDT"}}

        self.connector.set_leverage(self.trading_pair, 10)

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
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSDT": "BTC-USDT"}}

        self.connector.set_leverage(self.trading_pair, 10)

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
        failure_events = self.market_order_failure_logger.event_log
        self.assertEqual(1, len(failure_events))
        self.assertEqual(new_order_id, failure_events[0].order_id)

    @patch('hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils.get_tracking_nonce')
    @patch("aiohttp.ClientSession.post", new_callable=AsyncMock)
    def test_create_sell_order(self, post_mock, nonce_provider_mock):
        nonce_provider_mock.return_value = 1000
        self._configure_mock_api(post_mock)
        self._simulate_trading_rules_initialized()
        BybitPerpetualAPIOrderBookDataSource._trading_pair_symbol_map = {None: {"BTCUSDT": "BTC-USDT"}}

        self.connector.set_leverage(self.trading_pair, 10)

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
