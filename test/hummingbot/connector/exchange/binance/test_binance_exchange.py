import asyncio
import json
import re
import time
from decimal import Decimal
from typing import Awaitable, List, NamedTuple, Optional
from unittest import TestCase
from unittest.mock import patch

from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS
from hummingbot.connector.exchange.binance import binance_utils
from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource
from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OpenOrder
from hummingbot.core.data_type.trade import Trade
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

    def _validate_auth_credentials_taking_parameters_from_argument(self, request_call_tuple: NamedTuple, params_key: str):
        request_params = request_call_tuple.kwargs[params_key]
        self.assertIn("timestamp", request_params)
        self.assertIn("signature", request_params)
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("X-MBX-APIKEY", request_headers)
        self.assertEqual("testAPIKey", request_headers["X-MBX-APIKEY"])

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
            self.exchange.execute_buy(order_id="OID1",
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
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
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

    # TODO: test the sell order case
    # TODO: test that create order raises CancelledError exception
    # TODO: test that create order handles request exceptions and removes inflight order

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
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Successfully cancelled order {order.client_order_id}."
            )
        )

    # TODO: Add unit test for expected error during cancellation
    # TODO: Add unit test for unexpected error during cancellation
    # TODO: Add unit test to check cancellation raises CancelledError

    @aioresponses()
    @patch("hummingbot.connector.exchange.binance.binance_time.BinanceTime._current_seconds_counter")
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
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill["qty"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([(trade_fill["commissionAsset"], Decimal(trade_fill["commission"]))],
                         fill_event.trade_fee.flat_fees)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(float(trade_fill["time"]) * 1e-3, fill_event.timestamp)
        self.assertEqual("OID99", fill_event.order_id)
        self.assertEqual(self.trading_pair, fill_event.trading_pair)
        self.assertEqual(TradeType.BUY, fill_event.trade_type)
        self.assertEqual(OrderType.LIMIT, fill_event.order_type)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["price"]), fill_event.price)
        self.assertEqual(Decimal(trade_fill_non_tracked_order["qty"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([(trade_fill_non_tracked_order["commissionAsset"],
                           Decimal(trade_fill_non_tracked_order["commission"]))],
                         fill_event.trade_fee.flat_fees)
        self.assertTrue(self._is_logged(
            "INFO",
            f"Recreating missing trade in TradeFill: {trade_fill_non_tracked_order}"
        ))

    # TODO: Test the history reconciliation failing case

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
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.base_asset, buy_event.fee_asset)
        self.assertEqual(Decimal(order_status["executedQty"]), buy_event.base_asset_amount)
        self.assertEqual(Decimal(order_status["cummulativeQuoteQty"]), buy_event.quote_asset_amount)
        self.assertEqual(order.fee_paid, buy_event.fee_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"The market {order.trade_type.name.lower()} order {order.client_order_id} has completed according to "
                f"order status API."
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
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
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
            "executedQty": "1.0",
            "cummulativeQuoteQty": "10000.0",
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
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"The market order {order.client_order_id} has failed according to order status API.")
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
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
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

    @aioresponses()
    def test_get_my_trades(self, mock_api):
        url = binance_utils.private_rest_url(CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        trade1 = {
            "symbol": self.exchange_trading_pair,
            "id": 28457,
            "orderId": 100234,
            "orderListId": -1,
            "price": "4.00000100",
            "qty": "12.00000000",
            "quoteQty": "48.000012",
            "commission": "10.10000000",
            "commissionAsset": "BNB",
            "time": (time.time() - 100) * 1e3,
            "isBuyer": True,
            "isMaker": False,
            "isBestMatch": True
        }

        trade2 = {
            "symbol": self.exchange_trading_pair,
            "id": 28458,
            "orderId": 100235,
            "orderListId": -1,
            "price": "4.00000100",
            "qty": "12.00000000",
            "quoteQty": "48.000012",
            "commission": "10.10000000",
            "commissionAsset": "BNB",
            "time": (time.time() - 10) * 1e3,
            "isBuyer": False,
            "isMaker": True,
            "isBestMatch": True
        }

        mock_response = [trade1, trade2]
        mock_api.get(regex_url, body=json.dumps(mock_response))

        trades: List[Trade] = self.async_run_with_timeout(
            self.exchange.get_my_trades(trading_pair=self.trading_pair, days_ago=30))

        trades_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        request_params = trades_request[1][0].kwargs["params"]
        self.assertEqual(self.exchange_trading_pair, request_params["symbol"])
        self._validate_auth_credentials_for_request(trades_request[1][0])

        self.assertEqual(self.trading_pair, trades[0].trading_pair)
        self.assertEqual(TradeType.BUY, trades[0].side)
        self.assertEqual(Decimal(trade1["price"]), trades[0].price)
        self.assertEqual(Decimal(trade1["qty"]), trades[0].amount)
        self.assertIsNone(trades[0].order_type)
        self.assertEqual(self.trading_pair, trades[0].market)
        self.assertEqual(int(trade1["time"]), trades[0].timestamp)
        self.assertEqual(0.0, trades[0].trade_fee.percent)
        self.assertEqual([(trade1["commissionAsset"],
                           Decimal(trade1["commission"]))], trades[0].trade_fee.flat_fees)

        self.assertEqual(self.trading_pair, trades[1].trading_pair)
        self.assertEqual(TradeType.SELL, trades[1].side)
        self.assertEqual(Decimal(trade2["price"]), trades[1].price)
        self.assertEqual(Decimal(trade2["qty"]), trades[1].amount)
        self.assertIsNone(trades[1].order_type)
        self.assertEqual(self.trading_pair, trades[1].market)
        self.assertEqual(int(trade2["time"]), trades[1].timestamp)
        self.assertEqual(0.0, trades[1].trade_fee.percent)
        self.assertEqual([(trade2["commissionAsset"],
                           Decimal(trade2["commission"]))], trades[1].trade_fee.flat_fees)

    @aioresponses()
    def test_get_open_orders(self, mock_api):
        url = binance_utils.private_rest_url(CONSTANTS.OPEN_ORDERS_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order1 = {
            "symbol": self.exchange_trading_pair,
            "orderId": 1,
            "orderListId": -1,
            "clientOrderId": f"{CONSTANTS.HBOT_ORDER_ID_PREFIX}-OID1",
            "price": "0.1",
            "origQty": "1.0",
            "executedQty": "0.0",
            "cummulativeQuoteQty": "0.0",
            "status": "NEW",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "BUY",
            "stopPrice": "0.0",
            "icebergQty": "0.0",
            "time": 1499827319559,
            "updateTime": 1499827319559,
            "isWorking": True,
            "origQuoteOrderQty": "0.000000"
        }

        order2 = {
            "symbol": self.exchange_trading_pair,
            "orderId": 2,
            "orderListId": -1,
            "clientOrderId": f"{CONSTANTS.HBOT_ORDER_ID_PREFIX}-OID2",
            "price": "0.2",
            "origQty": "2.0",
            "executedQty": "2.0",
            "cummulativeQuoteQty": "0.0",
            "status": "FILLED",
            "timeInForce": "GTC",
            "type": "LIMIT",
            "side": "SELL",
            "stopPrice": "0.0",
            "icebergQty": "0.0",
            "time": 1499827320000,
            "updateTime": 1499827319559,
            "isWorking": True,
            "origQuoteOrderQty": "0.4"
        }

        mock_response = [order1, order2]
        mock_api.get(regex_url, body=json.dumps(mock_response))

        orders: List[OpenOrder] = self.async_run_with_timeout(self.exchange.get_open_orders())

        orders_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_for_request(orders_request[1][0])

        self.assertEqual(order1["clientOrderId"], orders[0].client_order_id)
        self.assertEqual(self.trading_pair, orders[0].trading_pair)
        self.assertTrue(orders[0].is_buy)
        self.assertEqual(Decimal(order1["price"]), orders[0].price)
        self.assertEqual(Decimal(order1["origQty"]), orders[0].amount)
        self.assertEqual(Decimal(order1["executedQty"]), orders[0].executed_amount)
        self.assertEqual(order1["status"], orders[0].status)
        self.assertEqual(OrderType.LIMIT, orders[0].order_type)
        self.assertEqual(int(order1["time"]), orders[0].time)
        self.assertEqual(str(order1["orderId"]), orders[0].exchange_order_id)

        self.assertEqual(order2["clientOrderId"], orders[1].client_order_id)
        self.assertEqual(self.trading_pair, orders[1].trading_pair)
        self.assertFalse(orders[1].is_buy)
        self.assertEqual(Decimal(order2["price"]), orders[1].price)
        self.assertEqual(Decimal(order2["origQty"]), orders[1].amount)
        self.assertEqual(Decimal(order2["executedQty"]), orders[1].executed_amount)
        self.assertEqual(order2["status"], orders[1].status)
        self.assertEqual(OrderType.LIMIT, orders[1].order_type)
        self.assertEqual(int(order2["time"]), orders[1].time)
        self.assertEqual(str(order2["orderId"]), orders[1].exchange_order_id)
