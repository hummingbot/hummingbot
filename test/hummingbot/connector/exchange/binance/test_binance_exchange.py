import asyncio
import json
import re
from decimal import Decimal
from typing import Awaitable, NamedTuple, Optional
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS
from hummingbot.connector.exchange.binance import binance_utils
from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource
from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.in_flight_order import OrderState, InFlightOrder
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    TradeType,
)
from hummingbot.core.network_iterator import NetworkStatus


class BinanceExchangeTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.exchange_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.test_task: Optional[asyncio.Task] = None

        self.exchange = BinanceExchange(
            binance_api_key="testAPIKey",
            binance_api_secret="testSecret",
            trading_pairs=[self.trading_pair],
        )

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._binance_time_synchronizer.logger().setLevel(1)
        self.exchange._binance_time_synchronizer.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)

        self._initialize_event_loggers()

        BinanceAPIOrderBookDataSource._trading_pair_symbol_map = {
            "com": bidict(
                {f"{self.base_asset}{self.quote_asset}": self.trading_pair})
        }

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        BinanceAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.buy_order_created_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_failure_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.sell_order_created_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.BuyOrderCreated, self.buy_order_created_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFailure, self.order_failure_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.SellOrderCreated, self.sell_order_created_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    def _validate_auth_credentials_for_request(self, request_call_tuple: NamedTuple):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call_tuple,
            params_key="params"
        )

    def _validate_auth_credentials_for_post_request(self, request_call_tuple: NamedTuple):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call_tuple,
            params_key="data"
        )

    def _validate_auth_credentials_taking_parameters_from_argument(self, request_call_tuple: NamedTuple,
                                                                   params_key: str):
        request_params = request_call_tuple.kwargs[params_key]
        self.assertIn("timestamp", request_params)
        self.assertIn("signature", request_params)
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("X-MBX-APIKEY", request_headers)
        self.assertEqual("testAPIKey", request_headers["X-MBX-APIKEY"])

    def test_supported_order_types(self):
        supported_types = self.exchange.supported_order_types()
        self.assertIn(OrderType.LIMIT, supported_types)
        self.assertIn(OrderType.LIMIT_MAKER, supported_types)

    @aioresponses()
    def test_check_network_successful(self, mock_api):
        url = binance_utils.private_rest_url(CONSTANTS.PING_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps({}))

        status = self.async_run_with_timeout(self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, status)

    @aioresponses()
    def test_check_network_unsuccessful(self, mock_api):
        url = binance_utils.private_rest_url(CONSTANTS.PING_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=404)

        status = self.async_run_with_timeout(self.exchange.check_network())

        self.assertEqual(NetworkStatus.NOT_CONNECTED, status)

    @aioresponses()
    def test_check_network_raises_cancel_exception(self, mock_api):
        url = binance_utils.private_rest_url(CONSTANTS.PING_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.exchange.check_network())

    @aioresponses()
    def test_create_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = binance_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        creation_response = {
            "symbol": self.exchange_trading_pair,
            "orderId": 28,
            "orderListId": -1,
            "clientOrderId": "OID1",
            "transactTime": 1507725176595
        }

        mock_api.post(regex_url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_for_post_request(order_request[1][0])
        request_data = order_request[1][0].kwargs["data"]
        self.assertEqual(self.exchange_trading_pair, request_data["symbol"])
        self.assertEqual(CONSTANTS.SIDE_BUY, request_data["side"])
        self.assertEqual(BinanceExchange.binance_order_type(OrderType.LIMIT), request_data["type"])
        self.assertEqual(Decimal("100"), Decimal(request_data["quantity"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))
        self.assertEqual("OID1", request_data["newClientOrderId"])

        self.assertIn("OID1", self.exchange.in_flight_orders)
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(int(self.exchange.current_timestamp * 1e3), create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual("OID1", create_event.order_id)
        self.assertEqual("28", create_event.exchange_order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created LIMIT BUY order OID1 for {Decimal('100.000000')} {self.trading_pair}."
            )
        )

    @aioresponses()
    def test_create_order_fails_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = binance_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_for_post_request(order_request[1][0])

        self.assertNotIn("OID1", self.exchange.in_flight_orders)
        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(int(self.exchange.current_timestamp * 1e3), failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual("OID1", failure_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Order OID1 has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={int(self.exchange.current_timestamp * 1e3)}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='OID1', exchange_order_id=None, trade_id=None, fill_price=None, "
                f"executed_amount_base=None, executed_amount_quote=None, fee_asset=None, cumulative_fee_paid=None, "
                f"trade_fee_percent=None)"
            )
        )

    @aioresponses()
    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = binance_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("0.0001"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("0.0000001")))
        # The second order is used only to have the event triggered and avoid using timeouts for tests
        asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID2",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))

        self.async_run_with_timeout(request_sent_event.wait())

        self.assertNotIn("OID1", self.exchange.in_flight_orders)
        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(int(self.exchange.current_timestamp * 1e3), failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual("OID1", failure_event.order_id)

        self.assertTrue(
            self._is_logged(
                "WARNING",
                "Buy order amount 0 is lower than the minimum order size 0.01. The order will not be created."
            )
        )
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Order OID1 has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={int(self.exchange.current_timestamp * 1e3)}, new_state={repr(OrderState.FAILED)}, "
                "client_order_id='OID1', exchange_order_id=None, trade_id=None, fill_price=None, "
                "executed_amount_base=None, executed_amount_quote=None, fee_asset=None, cumulative_fee_paid=None, "
                "trade_fee_percent=None)"
            )
        )

    @aioresponses()
    def test_cancel_order_successfully(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="4",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders["OID1"]

        url = binance_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "symbol": self.exchange_trading_pair,
            "origClientOrderId": "OID1",
            "orderId": 4,
            "orderListId": -1,
            "clientOrderId": "cancelMyOrder1",
            "price": str(order.price),
            "origQty": str(order.amount),
            "executedQty": str(Decimal("0")),
            "cummulativeQuoteQty": str(Decimal("0")),
            "status": "CANCELED",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "BUY"
        }

        mock_api.delete(regex_url,
                        body=json.dumps(response),
                        callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=self.trading_pair, order_id="OID1")
        self.async_run_with_timeout(request_sent_event.wait())

        cancel_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_for_request(cancel_request[1][0])
        request_params = cancel_request[1][0].kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(order.client_order_id, request_params["origClientOrderId"])

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(int(self.exchange.current_timestamp * 1e3), cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Successfully cancelled order {order.client_order_id}."
            )
        )

    @aioresponses()
    def test_cancel_order_raises_failure_event_when_request_fails(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="4",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders["OID1"]

        url = binance_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.delete(regex_url,
                        status=400,
                        callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=self.trading_pair, order_id="OID1")
        self.async_run_with_timeout(request_sent_event.wait())

        cancel_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_for_request(cancel_request[1][0])

        self.assertEquals(0, len(self.order_cancelled_logger.event_log))

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"There was a an error when requesting cancellation of order {order.client_order_id}"
            )
        )

    @aioresponses()
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="4",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order1 = self.exchange.in_flight_orders["OID1"]

        self.exchange.start_tracking_order(
            order_id="OID2",
            exchange_order_id="5",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("11000"),
            amount=Decimal("90"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID2", self.exchange.in_flight_orders)
        order2 = self.exchange.in_flight_orders["OID2"]

        url = binance_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "symbol": self.exchange_trading_pair,
            "origClientOrderId": "OID1",
            "orderId": 4,
            "orderListId": -1,
            "clientOrderId": "cancelMyOrder1",
            "price": str(order1.price),
            "origQty": str(order1.amount),
            "executedQty": str(Decimal("0")),
            "cummulativeQuoteQty": str(Decimal("0")),
            "status": "CANCELED",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "BUY"
        }

        mock_api.delete(regex_url, body=json.dumps(response))
        mock_api.delete(regex_url, status=400)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(10))

        self.assertEqual(2, len(cancellation_results))
        self.assertEqual(CancellationResult(order1.client_order_id, True), cancellation_results[0])
        self.assertEqual(CancellationResult(order2.client_order_id, False), cancellation_results[1])

        self.assertEqual(1, len(self.order_cancelled_logger.event_log))
        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(int(self.exchange.current_timestamp * 1e3), cancel_event.timestamp)
        self.assertEqual(order1.client_order_id, cancel_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Successfully cancelled order {order1.client_order_id}."
            )
        )

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        request_sent_event = asyncio.Event()
        seconds_counter_mock.side_effect = [0, 0, 0]

        url = binance_utils.private_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"serverTime": 1640000003000}

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertEqual(response["serverTime"] * 1e-3, self.exchange._binance_time_synchronizer.time())

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        request_sent_event = asyncio.Event()

        url = binance_utils.private_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"code": -1121, "msg": "Dummy error"}

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertTrue(self._is_logged("NETWORK", "Error getting server time."))

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        url = binance_utils.private_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url,
                     exception=asyncio.CancelledError)

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout, self.exchange._update_time_synchronizer())

    @aioresponses()
    def test_update_balances(self, mock_api):
        url = binance_utils.private_rest_url(CONSTANTS.ACCOUNTS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "makerCommission": 15,
            "takerCommission": 15,
            "buyerCommission": 0,
            "sellerCommission": 0,
            "canTrade": True,
            "canWithdraw": True,
            "canDeposit": True,
            "updateTime": 123456789,
            "accountType": "SPOT",
            "balances": [
                {
                    "asset": "BTC",
                    "free": "10.0",
                    "locked": "5.0"
                },
                {
                    "asset": "LTC",
                    "free": "2000",
                    "locked": "0.00000000"
                }
            ],
            "permissions": [
                "SPOT"
            ]
        }

        mock_api.get(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("10"), available_balances["BTC"])
        self.assertEqual(Decimal("2000"), available_balances["LTC"])
        self.assertEqual(Decimal("15"), total_balances["BTC"])
        self.assertEqual(Decimal("2000"), total_balances["LTC"])

        response = {
            "makerCommission": 15,
            "takerCommission": 15,
            "buyerCommission": 0,
            "sellerCommission": 0,
            "canTrade": True,
            "canWithdraw": True,
            "canDeposit": True,
            "updateTime": 123456789,
            "accountType": "SPOT",
            "balances": [
                {
                    "asset": "BTC",
                    "free": "10.0",
                    "locked": "5.0"
                },
            ],
            "permissions": [
                "SPOT"
            ]
        }

        mock_api.get(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn("LTC", available_balances)
        self.assertNotIn("LTC", total_balances)
        self.assertEqual(Decimal("10"), available_balances["BTC"])
        self.assertEqual(Decimal("15"), total_balances["BTC"])

    @aioresponses()
    def test_update_balances_logs_errors(self, mock_api):
        url = binance_utils.private_rest_url(CONSTANTS.ACCOUNTS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=401)
        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertTrue(
            self._is_logged("ERROR", "Error getting account balances from server")
        )

    @aioresponses()
    def test_update_order_fills_from_trades_triggers_filled_event(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = binance_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill = {
            "symbol": self.exchange_trading_pair,
            "id": 28457,
            "orderId": int(order.exchange_order_id),
            "orderListId": -1,
            "price": "9999",
            "qty": "1",
            "quoteQty": "48.000012",
            "commission": "10.10000000",
            "commissionAsset": "BNB",
            "time": 1499865549590,
            "isBuyer": True,
            "isMaker": False,
            "isBestMatch": True
        }

        trade_fill_non_tracked_order = {
            "symbol": self.exchange_trading_pair,
            "id": 30000,
            "orderId": 99999,
            "orderListId": -1,
            "price": "4.00000100",
            "qty": "12.00000000",
            "quoteQty": "48.000012",
            "commission": "10.10000000",
            "commissionAsset": "BNB",
            "time": 1499865549590,
            "isBuyer": True,
            "isMaker": False,
            "isBestMatch": True
        }

        mock_response = [trade_fill, trade_fill_non_tracked_order]
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.exchange.add_exchange_order_ids_from_market_recorder(
            {str(trade_fill_non_tracked_order["orderId"]): "OID99"})

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        trades_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        request_params = trades_request[1][0].kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self._validate_auth_credentials_for_request(trades_request[1][0])

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(int(self.exchange.current_timestamp * 1e3), fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill["qty"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(trade_fill["commissionAsset"], Decimal(trade_fill["commission"]))],
                         fill_event.trade_fee.flat_fees)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(float(trade_fill_non_tracked_order["time"]) * 1e-3, fill_event.timestamp)
        self.assertEqual("OID99", fill_event.order_id)
        self.assertEqual(self.trading_pair, fill_event.trading_pair)
        self.assertEqual(TradeType.BUY, fill_event.trade_type)
        self.assertEqual(OrderType.LIMIT, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["qty"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(
                trade_fill_non_tracked_order["commissionAsset"],
                Decimal(trade_fill_non_tracked_order["commission"]))],
            fill_event.trade_fee.flat_fees)
        self.assertTrue(self._is_logged(
            "INFO",
            f"Recreating missing trade in TradeFill: {trade_fill_non_tracked_order}"
        ))

    @aioresponses()
    def test_update_order_fills_request_parameters(self, mock_api):
        self.exchange._set_current_timestamp(0)
        self.exchange._last_poll_timestamp = -1

        url = binance_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = []
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        trades_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        request_params = trades_request[1][0].kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertNotIn("startTime", request_params)
        self._validate_auth_credentials_for_request(trades_request[1][0])

        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        self.exchange._last_trades_poll_binance_timestamp = 10
        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        trades_request = [(key, value) for key, value in mock_api.requests.items()
                          if key[1].human_repr().startswith(url)][1]
        request_params = trades_request[1][0].kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(10 * 1e3, request_params["startTime"])
        self._validate_auth_credentials_for_request(trades_request[1][0])

    @aioresponses()
    def test_update_order_fills_from_trades_with_repeated_fill_triggers_only_one_event(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        url = binance_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade_fill_non_tracked_order = {
            "symbol": self.exchange_trading_pair,
            "id": 30000,
            "orderId": 99999,
            "orderListId": -1,
            "price": "4.00000100",
            "qty": "12.00000000",
            "quoteQty": "48.000012",
            "commission": "10.10000000",
            "commissionAsset": "BNB",
            "time": 1499865549590,
            "isBuyer": True,
            "isMaker": False,
            "isBestMatch": True
        }

        mock_response = [trade_fill_non_tracked_order, trade_fill_non_tracked_order]
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.exchange.add_exchange_order_ids_from_market_recorder(
            {str(trade_fill_non_tracked_order["orderId"]): "OID99"})

        self.async_run_with_timeout(self.exchange._update_order_fills_from_trades())

        trades_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        request_params = trades_request[1][0].kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self._validate_auth_credentials_for_request(trades_request[1][0])

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(float(trade_fill_non_tracked_order["time"]) * 1e-3, fill_event.timestamp)
        self.assertEqual("OID99", fill_event.order_id)
        self.assertEqual(self.trading_pair, fill_event.trading_pair)
        self.assertEqual(TradeType.BUY, fill_event.trade_type)
        self.assertEqual(OrderType.LIMIT, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["qty"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(trade_fill_non_tracked_order["commissionAsset"],
                        Decimal(trade_fill_non_tracked_order["commission"]))],
            fill_event.trade_fee.flat_fees)
        self.assertTrue(self._is_logged(
            "INFO",
            f"Recreating missing trade in TradeFill: {trade_fill_non_tracked_order}"
        ))

    @aioresponses()
    def test_update_order_status_when_filled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

        url = binance_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "symbol": self.exchange_trading_pair,
            "orderId": int(order.exchange_order_id),
            "orderListId": -1,
            "clientOrderId": order.client_order_id,
            "price": "10000.0",
            "origQty": "1.0",
            "executedQty": "1.0",
            "cummulativeQuoteQty": "10000.0",
            "status": "FILLED",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "BUY",
            "stopPrice": "0.0",
            "icebergQty": "0.0",
            "time": 1499827319559,
            "updateTime": 1499827319559,
            "isWorking": True,
            "origQuoteOrderQty": "10000.000000"
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(order.client_order_id, request_params["origClientOrderId"])
        self._validate_auth_credentials_for_request(order_request[1][0])

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(int(self.exchange.current_timestamp * 1e3), buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertIsNone(buy_event.fee_asset)
        self.assertEqual(Decimal(0), buy_event.base_asset_amount)
        self.assertEqual(Decimal(0), buy_event.quote_asset_amount)
        self.assertEqual(order.cumulative_fee_paid, buy_event.fee_amount)
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
    def test_update_order_status_when_cancelled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = binance_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "symbol": self.exchange_trading_pair,
            "orderId": int(order.exchange_order_id),
            "orderListId": -1,
            "clientOrderId": order.client_order_id,
            "price": "10000.0",
            "origQty": "1.0",
            "executedQty": "1.0",
            "cummulativeQuoteQty": "10000.0",
            "status": "CANCELED",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "BUY",
            "stopPrice": "0.0",
            "icebergQty": "0.0",
            "time": 1499827319559,
            "updateTime": 1499827319559,
            "isWorking": True,
            "origQuoteOrderQty": "10000.000000"
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(order.client_order_id, request_params["origClientOrderId"])
        self._validate_auth_credentials_for_request(order_request[1][0])

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(int(self.exchange.current_timestamp * 1e3), cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged("INFO", f"Successfully cancelled order {order.client_order_id}.")
        )

    @aioresponses()
    def test_update_order_status_when_failed(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = binance_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "symbol": self.exchange_trading_pair,
            "orderId": int(order.exchange_order_id),
            "orderListId": -1,
            "clientOrderId": order.client_order_id,
            "price": "10000.0",
            "origQty": "1.0",
            "executedQty": "0.0",
            "cummulativeQuoteQty": "0.0",
            "status": "REJECTED",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "BUY",
            "stopPrice": "0.0",
            "icebergQty": "0.0",
            "time": 1499827319559,
            "updateTime": 1499827319559,
            "isWorking": True,
            "origQuoteOrderQty": "10000.000000"
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_params = order_request[1][0].kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self.assertEqual(order.client_order_id, request_params["origClientOrderId"])
        self._validate_auth_credentials_for_request(order_request[1][0])

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(int(self.exchange.current_timestamp * 1e3), failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Order {order.client_order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}',"
                f" update_timestamp={int(order_status['updateTime'])}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order.client_order_id}', exchange_order_id='{order.exchange_order_id}', "
                f"trade_id=None, fill_price=None, executed_amount_base=None, executed_amount_quote=None, "
                f"fee_asset=None, cumulative_fee_paid=None, trade_fee_percent=None)")
        )

    @aioresponses()
    def test_update_order_status_marks_order_as_failure_after_three_errors(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        url = binance_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=401)

        for i in range(self.exchange.MAX_ORDER_UPDATE_RETRIEVAL_RETRIES_WITH_FAILURES):
            self.async_run_with_timeout(self.exchange._update_order_status())

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(int(self.exchange.current_timestamp * 1e3), failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        url = binance_utils.private_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "timezone": "UTC",
            "serverTime": 1565246363776,
            "rateLimits": [{}],
            "exchangeFilters": [],
            "symbols": [
                {
                    "symbol": self.exchange_trading_pair,
                    "status": "TRADING",
                    "baseAsset": "ETH",
                    "baseAssetPrecision": 8,
                    "quoteAsset": "BTC",
                    "quotePrecision": 8,
                    "quoteAssetPrecision": 8,
                    "orderTypes": ["LIMIT", "LIMIT_MAKER"],
                    "icebergAllowed": True,
                    "ocoAllowed": True,
                    "isSpotTradingAllowed": True,
                    "isMarginTradingAllowed": True,
                    "filters": [
                        {
                            "filterType": "PRICE_FILTER",
                            "minPrice": "0.00000100",
                            "maxPrice": "100000.00000000",
                            "tickSize": "0.00000100"
                        }, {
                            "filterType": "LOT_SIZE",
                            "minQty": "0.00100000",
                            "maxQty": "200000.00000000",
                            "stepSize": "0.00100000"
                        }, {
                            "filterType": "MIN_NOTIONAL",
                            "minNotional": "0.00100000"
                        }
                    ],
                    "permissions": [
                        "SPOT",
                        "MARGIN"
                    ]
                }
            ]
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_trading_rules())

        trading_rule = self.exchange.trading_rules[self.trading_pair]
        self.assertEqual(self.trading_pair, trading_rule.trading_pair)
        self.assertEqual(Decimal(order_status["symbols"][0]["filters"][1]["minQty"]),
                         trading_rule.min_order_size)
        self.assertEqual(Decimal(order_status["symbols"][0]["filters"][0]["tickSize"]),
                         trading_rule.min_price_increment)
        self.assertEqual(Decimal(order_status["symbols"][0]["filters"][1]["stepSize"]),
                         trading_rule.min_base_amount_increment)
        self.assertEqual(Decimal(order_status["symbols"][0]["filters"][2]["minNotional"]),
                         trading_rule.min_notional_size)

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        url = binance_utils.private_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "timezone": "UTC",
            "serverTime": 1565246363776,
            "rateLimits": [{}],
            "exchangeFilters": [],
            "symbols": [
                {
                    "symbol": self.exchange_trading_pair,
                    "status": "TRADING",
                    "baseAsset": "ETH",
                    "baseAssetPrecision": 8,
                    "quoteAsset": "BTC",
                    "quotePrecision": 8,
                    "quoteAssetPrecision": 8,
                    "orderTypes": ["LIMIT", "LIMIT_MAKER"],
                    "icebergAllowed": True,
                    "ocoAllowed": True,
                    "isSpotTradingAllowed": True,
                    "isMarginTradingAllowed": True,
                    "filters": [],
                    "permissions": [
                        "SPOT",
                        "MARGIN"
                    ]
                }
            ]
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_trading_rules())

        self.assertEqual(0, len(self.exchange.trading_rules))
        self.assertTrue(
            self._is_logged("ERROR", f"Error parsing the trading pair rule {order_status['symbols'][0]}. Skipping.")
        )

    def test_user_stream_update_for_new_order(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        event_message = {
            "e": "executionReport",
            "E": 1499405658658,
            "s": self.exchange_trading_pair,
            "c": order.client_order_id,
            "S": "BUY",
            "o": "LIMIT",
            "f": "GTC",
            "q": "1.00000000",
            "p": "1000.00000000",
            "P": "0.00000000",
            "F": "0.00000000",
            "g": -1,
            "C": "",
            "x": "NEW",
            "X": "NEW",
            "r": "NONE",
            "i": int(order.exchange_order_id),
            "l": "0.00000000",
            "z": "0.00000000",
            "L": "0.00000000",
            "n": "0",
            "N": None,
            "T": 1499405658657,
            "t": -1,
            "I": 8641984,
            "w": True,
            "m": False,
            "M": False,
            "O": 1499405658657,
            "Z": "0.00000000",
            "Y": "0.00000000",
            "Q": "0.00000000"
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(int(self.exchange.current_timestamp * 1e3), event.timestamp)
        self.assertEqual(order.order_type, event.type)
        self.assertEqual(order.trading_pair, event.trading_pair)
        self.assertEqual(order.amount, event.amount)
        self.assertEqual(order.price, event.price)
        self.assertEqual(order.client_order_id, event.order_id)
        self.assertEqual(order.exchange_order_id, event.exchange_order_id)
        self.assertTrue(order.is_open)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created {order.order_type.name.upper()} {order.trade_type.name.upper()} order "
                f"{order.client_order_id} for {order.amount} {order.trading_pair}."
            )
        )

    def test_user_stream_update_for_cancelled_order(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        event_message = {
            "e": "executionReport",
            "E": 1499405658658,
            "s": self.exchange_trading_pair,
            "c": "dummyText",
            "S": "BUY",
            "o": "LIMIT",
            "f": "GTC",
            "q": "1.00000000",
            "p": "1000.00000000",
            "P": "0.00000000",
            "F": "0.00000000",
            "g": -1,
            "C": order.client_order_id,
            "x": "CANCELED",
            "X": "CANCELED",
            "r": "NONE",
            "i": int(order.exchange_order_id),
            "l": "0.00000000",
            "z": "0.00000000",
            "L": "0.00000000",
            "n": "0",
            "N": None,
            "T": 1499405658657,
            "t": -1,
            "I": 8641984,
            "w": True,
            "m": False,
            "M": False,
            "O": 1499405658657,
            "Z": "0.00000000",
            "Y": "0.00000000",
            "Q": "0.00000000"
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(int(self.exchange.current_timestamp * 1e3), cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_cancelled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self._is_logged("INFO", f"Successfully cancelled order {order.client_order_id}.")
        )

    def test_user_stream_update_for_order_fill(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        event_message = {
            "e": "executionReport",
            "E": 1499405658658,
            "s": self.exchange_trading_pair,
            "c": order.client_order_id,
            "S": "BUY",
            "o": "LIMIT",
            "f": "GTC",
            "q": "1.00000000",
            "p": "1000.00000000",
            "P": "0.00000000",
            "F": "0.00000000",
            "g": -1,
            "C": "",
            "x": "TRADE",
            "X": "FILLED",
            "r": "NONE",
            "i": int(order.exchange_order_id),
            "l": "1.00000000",
            "z": "1.00000000",
            "L": "10050.00000000",
            "n": "50",
            "N": "BNB",
            "T": 1499405658657,
            "t": 1,
            "I": 8641984,
            "w": True,
            "m": False,
            "M": False,
            "O": 1499405658657,
            "Z": "10050.00000000",
            "Y": "10050.00000000",
            "Q": "10000.00000000"
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(int(self.exchange.current_timestamp * 1e3), fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(event_message["L"]), fill_event.price)
        self.assertEqual(Decimal(event_message["l"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(event_message["N"], Decimal(event_message["n"]))],
            fill_event.trade_fee.flat_fees)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(int(self.exchange.current_timestamp * 1e3), buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(event_message["N"], buy_event.fee_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        self.assertEqual(Decimal(event_message["Z"]), buy_event.quote_asset_amount)
        self.assertEqual(order.cumulative_fee_paid, buy_event.fee_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    def test_user_stream_update_for_order_failure(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        event_message = {
            "e": "executionReport",
            "E": 1499405658658,
            "s": self.exchange_trading_pair,
            "c": order.client_order_id,
            "S": "BUY",
            "o": "LIMIT",
            "f": "GTC",
            "q": "1.00000000",
            "p": "1000.00000000",
            "P": "0.00000000",
            "F": "0.00000000",
            "g": -1,
            "C": "",
            "x": "REJECTED",
            "X": "REJECTED",
            "r": "NONE",
            "i": int(order.exchange_order_id),
            "l": "0.00000000",
            "z": "0.00000000",
            "L": "0.00000000",
            "n": "0",
            "N": None,
            "T": 1499405658657,
            "t": 1,
            "I": 8641984,
            "w": True,
            "m": False,
            "M": False,
            "O": 1499405658657,
            "Z": "0.00000000",
            "Y": "0.00000000",
            "Q": "0.00000000"
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(int(self.exchange.current_timestamp * 1e3), failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_failure)
        self.assertTrue(order.is_done)

    def test_user_stream_balance_update(self):
        self.exchange._set_current_timestamp(1640780000)

        event_message = {
            "e": "outboundAccountPosition",
            "E": 1564034571105,
            "u": 1564034571073,
            "B": [
                {
                    "a": "COINALPHA",
                    "f": "10000.000000",
                    "l": "500.000000"
                }
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10000"), self.exchange.available_balances["COINALPHA"])
        self.assertEqual(Decimal("10500"), self.exchange.get_balance("COINALPHA"))
