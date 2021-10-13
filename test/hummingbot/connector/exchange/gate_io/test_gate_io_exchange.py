import asyncio
import json
import re
import time
import unittest
from decimal import Decimal
from typing import Awaitable, List, Dict
from unittest.mock import patch

from aioresponses import aioresponses

from hummingbot.connector.exchange.gate_io.gate_io_exchange import GateIoExchange
from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.core.network_iterator import NetworkStatus

from hummingbot.connector.exchange.gate_io.gate_io_in_flight_order import GateIoInFlightOrder
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, TradeType, OrderType
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class TestGateIoExchange(unittest.TestCase):
    # logging.Level required to receive logs from the exchange
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.api_key = "someKey"
        cls.api_secret = "someSecret"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.mocking_assistant = NetworkMockingAssistant()
        self.exchange = GateIoExchange(self.api_key, self.api_secret, trading_pairs=[self.trading_pair])
        self.event_listener = EventLogger()

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    def get_currency_data_mock() -> List:
        currency_data = [
            {
                "currency": "GT",
                "delisted": False,
                "withdraw_disabled": False,
                "withdraw_delayed": False,
                "deposit_disabled": False,
                "trade_disabled": False,
            }
        ]
        return currency_data

    def get_trading_rules_mock(self) -> List:
        trading_rules = [
            {
                "id": f"{self.base_asset}_{self.quote_asset}",
                "base": self.base_asset,
                "quote": self.quote_asset,
                "fee": "0.2",
                "min_base_amount": "0.001",
                "min_quote_amount": "1.0",
                "amount_precision": 3,
                "precision": 6,
                "trade_status": "tradable",
                "sell_start": 1516378650,
                "buy_start": 1516378650
            }
        ]
        return trading_rules

    def get_order_create_response_mock(self, cancelled: bool = False, exchange_order_id: str = "someExchId") -> Dict:
        order_create_resp_mock = {
            "id": exchange_order_id,
            "text": "t-123456",
            "create_time": "1548000000",
            "update_time": "1548000100",
            "create_time_ms": 1548000000123,
            "update_time_ms": 1548000100123,
            "currency_pair": f"{self.base_asset}_{self.quote_asset}",
            "status": "cancelled" if cancelled else "open",
            "type": "limit",
            "account": "spot",
            "side": "buy",
            "iceberg": "0",
            "amount": "1",
            "price": "5.00032",
            "time_in_force": "gtc",
            "left": "0.5",
            "filled_total": "2.50016",
            "fee": "0.005",
            "fee_currency": "ETH",
            "point_fee": "0",
            "gt_fee": "0",
            "gt_discount": False,
            "rebated_fee": "0",
            "rebated_fee_currency": "BTC"
        }
        return order_create_resp_mock

    def get_in_flight_order(self, client_order_id: str, exchange_order_id: str = "someExchId") -> GateIoInFlightOrder:
        order = GateIoInFlightOrder(
            client_order_id,
            exchange_order_id,
            self.trading_pair,
            OrderType.LIMIT,
            TradeType.BUY,
            price=Decimal("5.1"),
            amount=Decimal("1"),
        )
        return order

    def get_user_balances_mock(self) -> List:
        user_balances = [
            {
                "currency": self.base_asset,
                "available": "968.8",
                "locked": "0",
            },
            {
                "currency": self.quote_asset,
                "available": "543.9",
                "locked": "0",
            }
        ]
        return user_balances

    def get_open_order_mock(self, exchange_order_id: str = "someExchId") -> List:
        open_orders = [
            {
                "currency_pair": f"{self.base_asset}_{self.quote_asset}",
                "total": 1,
                "orders": [
                    {
                        "id": exchange_order_id,
                        "text": f"{CONSTANTS.HBOT_ORDER_ID}-{exchange_order_id}",
                        "create_time": "1548000000",
                        "update_time": "1548000100",
                        "currency_pair": f"{self.base_asset}_{self.quote_asset}",
                        "status": "open",
                        "type": "limit",
                        "account": "spot",
                        "side": "buy",
                        "amount": "1",
                        "price": "5.00032",
                        "time_in_force": "gtc",
                        "left": "0.5",
                        "filled_total": "2.50016",
                        "fee": "0.005",
                        "fee_currency": "ETH",
                        "point_fee": "0",
                        "gt_fee": "0",
                        "gt_discount": False,
                        "rebated_fee": "0",
                        "rebated_fee_currency": "BTC"
                    }
                ]
            }
        ]
        return open_orders

    @patch("hummingbot.connector.exchange.gate_io.gate_io_exchange.retry_sleep_time")
    @aioresponses()
    def test_check_network_not_connected(self, retry_sleep_time_mock, mock_api):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.NETWORK_CHECK_PATH_URL}"
        resp = ""
        for i in range(CONSTANTS.API_MAX_RETRIES):
            mock_api.get(url, status=500, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED)

    @aioresponses()
    def test_check_network(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.NETWORK_CHECK_PATH_URL}"
        resp = self.get_currency_data_mock()
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.CONNECTED)

    @aioresponses()
    def test_update_trading_rules_polling_loop(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.SYMBOL_PATH_URL}"
        resp = self.get_trading_rules_mock()
        called_event = asyncio.Event()
        mock_api.get(url, body=json.dumps(resp), callback=lambda *args, **kwargs: called_event.set())

        self.ev_loop.create_task(self.exchange._trading_rules_polling_loop())
        self.async_run_with_timeout(called_event.wait())

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)

    @aioresponses()
    def test_create_order(self, mock_api):
        trading_rules = self.get_trading_rules_mock()
        self.exchange._trading_rules = self.exchange._format_trading_rules(trading_rules)

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_CREATE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_create_response_mock()
        mock_api.post(regex_url, body=json.dumps(resp))

        self.exchange.add_listener(MarketEvent.BuyOrderCreated, self.event_listener)

        order_id = "someId"
        self.async_run_with_timeout(
            coroutine=self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.LIMIT,
                price=Decimal("5.1"),
            )
        )

        self.assertEqual(1, len(self.event_listener.event_log))

        event = self.event_listener.event_log[0]

        self.assertEqual(order_id, event.order_id)
        self.assertTrue(order_id in self.exchange.in_flight_orders)

    @aioresponses()
    def test_create_order_when_order_is_instantly_closed(self, mock_api):
        trading_rules = self.get_trading_rules_mock()
        self.exchange._trading_rules = self.exchange._format_trading_rules(trading_rules)

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_CREATE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_create_response_mock()
        resp["status"] = "closed"
        mock_api.post(regex_url, body=json.dumps(resp))

        event_logger = EventLogger()
        self.exchange.add_listener(MarketEvent.BuyOrderCreated, event_logger)

        order_id = "someId"
        self.async_run_with_timeout(
            coroutine=self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.LIMIT,
                price=Decimal("5.1"),
            )
        )

        self.assertEqual(1, len(event_logger.event_log))
        self.assertEqual(order_id, event_logger.event_log[0].order_id)
        self.assertTrue(order_id in self.exchange.in_flight_orders)

    @aioresponses()
    def test_order_with_less_amount_than_allowed_is_not_created(self, mock_api):
        trading_rules = self.get_trading_rules_mock()
        self.exchange._trading_rules = self.exchange._format_trading_rules(trading_rules)

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_CREATE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, exception=Exception("The request should never happen"))

        self.exchange.add_listener(MarketEvent.BuyOrderCreated, self.event_listener)

        order_id = "someId"
        self.async_run_with_timeout(
            coroutine=self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("0.0001"),
                order_type=OrderType.LIMIT,
                price=Decimal("5.1"),
            )
        )

        self.assertEqual(0, len(self.event_listener.event_log))
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertTrue(self._is_logged(
            "WARNING",
            "Buy order amount 0.000 is lower than the minimum order size 0.001."
        ))

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    @aioresponses()
    def test_create_order_fails(self, _, mock_api):
        trading_rules = self.get_trading_rules_mock()
        self.exchange._trading_rules = self.exchange._format_trading_rules(trading_rules)

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_CREATE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_create_response_mock(cancelled=True)
        mock_api.post(regex_url, body=json.dumps(resp))

        self.exchange.add_listener(MarketEvent.BuyOrderCreated, self.event_listener)

        order_id = "someId"
        self.async_run_with_timeout(
            coroutine=self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                order_type=OrderType.LIMIT,
                price=Decimal("5.1"),
            )
        )

        self.assertEqual(0, len(self.event_listener.event_log))
        self.assertTrue(order_id not in self.exchange.in_flight_orders)

    @aioresponses()
    def test_execute_cancel(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_CREATE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_create_response_mock(cancelled=True)
        mock_api.delete(regex_url, body=json.dumps(resp))

        client_order_id = "someId"
        exchange_order_id = "someExchId"
        self.exchange._in_flight_orders[client_order_id] = self.get_in_flight_order(client_order_id, exchange_order_id)

        self.exchange.add_listener(MarketEvent.OrderCancelled, self.event_listener)

        self.async_run_with_timeout(
            coroutine=self.exchange._execute_cancel(self.trading_pair, client_order_id)
        )

        self.assertEqual(1, len(self.event_listener.event_log))

        event = self.event_listener.event_log[0]

        self.assertEqual(client_order_id, event.order_id)
        self.assertTrue(client_order_id not in self.exchange.in_flight_orders)

    def test_cancel_order_not_present_in_inflight_orders(self):
        client_order_id = "test-id"
        event_logger = EventLogger()
        self.exchange.add_listener(MarketEvent.OrderCancelled, event_logger)

        result = self.async_run_with_timeout(
            coroutine=self.exchange._execute_cancel(self.trading_pair, client_order_id)
        )

        self.assertEqual(0, len(event_logger.event_log))
        self.assertTrue(self._is_logged(
            "WARNING",
            f"Failed to cancel order {client_order_id}. Order not found in inflight orders."))
        self.assertFalse(result.success)

    @patch("hummingbot.connector.exchange.gate_io.gate_io_exchange.GateIoExchange.current_timestamp")
    @aioresponses()
    def test_status_polling_loop(self, current_ts_mock, mock_api):
        balances_url = f"{CONSTANTS.REST_URL}/{CONSTANTS.USER_BALANCES_PATH_URL}"
        balances_resp = self.get_user_balances_mock()
        balances_called_event = asyncio.Event()
        mock_api.get(
            balances_url, body=json.dumps(balances_resp), callback=lambda *args, **kwargs: balances_called_event.set()
        )

        client_order_id = "someId"
        exchange_order_id = "someExchId"
        self.exchange._in_flight_orders[client_order_id] = self.get_in_flight_order(client_order_id, exchange_order_id)

        order_status_url = f"{CONSTANTS.REST_URL}/{CONSTANTS.ORDER_STATUS_PATH_URL}"
        regex_order_status_url = re.compile(f"^{order_status_url[:-4]}".replace(".", r"\.").replace("?", r"\?"))
        order_status_resp = self.get_order_create_response_mock(cancelled=True, exchange_order_id=exchange_order_id)
        order_status_called_event = asyncio.Event()
        mock_api.get(
            regex_order_status_url,
            body=json.dumps(order_status_resp),
            callback=lambda *args, **kwargs: order_status_called_event.set(),
        )

        current_ts_mock.return_value = time.time()

        self.ev_loop.create_task(self.exchange._status_polling_loop())
        self.exchange._poll_notifier.set()
        self.async_run_with_timeout(balances_called_event.wait())
        self.async_run_with_timeout(order_status_called_event.wait())

        self.assertEqual(self.exchange.available_balances[self.base_asset], Decimal("968.8"))
        self.assertTrue(client_order_id not in self.exchange.in_flight_orders)

    @aioresponses()
    def test_get_open_orders(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.USER_ORDERS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_open_order_mock()
        mock_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.get_open_orders())

        self.assertTrue(len(ret) == 1)

    def test_process_trade_message_matching_order_by_internal_order_id(self):
        self.exchange.start_tracking_order(
            order_id='OID-1',
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT)

        trade_message = {
            "id": 5736713,
            "user_id": 1000001,
            "order_id": "EOID-1",
            "currency_pair": "BTC_USDT",
            "create_time": 1605176741,
            "create_time_ms": "1605176741123.456",
            "side": "buy",
            "amount": "1.00000000",
            "role": "maker",
            "price": "10000.00000000",
            "fee": "0.00200000000000",
            "point_fee": "0",
            "gt_fee": "0",
            "text": "OID-1"
        }

        asyncio.get_event_loop().run_until_complete(self.exchange._process_trade_message(trade_message))
        order = self.exchange.in_flight_orders["OID-1"]

        self.assertIn(str(trade_message["id"]), order.trade_update_id_set)
        self.assertEqual(Decimal(1), order.executed_amount_base)
        self.assertEqual(Decimal(10000), order.executed_amount_quote)
        self.assertEqual(Decimal("0.002"), order.fee_paid)
