import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Dict, Awaitable, List
from unittest.mock import AsyncMock, patch, MagicMock

from aioresponses import aioresponses

from hummingbot.connector.exchange.bitmart.bitmart_exchange import BitmartExchange
from hummingbot.connector.exchange.bitmart import bitmart_constants as CONSTANTS
from hummingbot.core.event.event_logger import EventLogger

from hummingbot.connector.trading_rule import TradingRule

from hummingbot.connector.exchange.bitmart.bitmart_utils import HBOT_BROKER_ID
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.events import TradeType, OrderType, MarketEvent
from hummingbot.core.network_iterator import NetworkStatus

from hummingbot.core.time_iterator import TimeIterator
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class BitmartExchangeTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.exchange_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()

        self.tracker_task = None
        self.exchange_task = None
        self.log_records = []
        self.return_values_queue = asyncio.Queue()
        self.resume_test_event = asyncio.Event()

        self.exchange = BitmartExchange(
            bitmart_api_key="someKey",
            bitmart_secret_key="someSecret",
            bitmart_memo="someMemo",
            trading_pairs=[self.trading_pair],
        )

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.ev_loop = asyncio.get_event_loop()

        self.buy_order_created_logger: EventLogger = EventLogger()
        self.sell_order_created_logger: EventLogger = EventLogger()
        self.buy_order_completed_logger: EventLogger = EventLogger()
        self.order_cancelled_logger: EventLogger = EventLogger()
        self.order_failure_logger: EventLogger = EventLogger()
        self.order_filled_logger: EventLogger = EventLogger()
        self.exchange.add_listener(MarketEvent.BuyOrderCreated, self.buy_order_created_logger)
        self.exchange.add_listener(MarketEvent.SellOrderCreated, self.sell_order_created_logger)
        self.exchange.add_listener(MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger)
        self.exchange.add_listener(MarketEvent.OrderCancelled, self.order_cancelled_logger)
        self.exchange.add_listener(MarketEvent.OrderFailure, self.order_failure_logger)
        self.exchange.add_listener(MarketEvent.OrderFilled, self.order_filled_logger)

    def tearDown(self) -> None:
        self.tracker_task and self.tracker_task.cancel()
        self.exchange_task and self.exchange_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def is_logged(self, log_level: str, message: str) -> bool:
        logged = any(
            record.levelname == log_level and record.getMessage() == message
            for record in self.log_records
        )
        return logged

    async def return_queued_values_and_unlock_with_event(self):
        val = await self.return_values_queue.get()
        self.resume_test_event.set()
        return val

    def create_exception_and_unlock_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal("0.01"),
                min_price_increment=Decimal("0.0001"),
                min_base_amount_increment=Decimal("0.000001"),
            )
        }

    @staticmethod
    def authentication_response(authenticated: bool) -> str:
        if authenticated:
            resp = {"event": "login"}
        else:
            resp = {"event": "login", "errorMessage": "", "errorCode": "91002"}
        return json.dumps(resp)

    @staticmethod
    def get_system_status_reply_mock() -> Dict:
        status_reply = {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "service": [
                    {
                        "title": "Spot API Stop",
                        "service_type": "spot",
                        "status": "2",
                        "start_time": 1527777538000,
                        "end_time": 1527777538000
                    },
                ]
            }
        }
        return status_reply

    def get_symbols_details_reply_mock(self, min_order_size: str) -> Dict:
        details = {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "symbols": [
                    {
                        "symbol": self.exchange_trading_pair,
                        "symbol_id": 1024,
                        "base_currency": self.base_asset,
                        "quote_currency": self.quote_asset,
                        "quote_increment": "1.00000000",
                        "base_min_size": min_order_size,
                        "base_max_size": "10000000.00000000",
                        "price_min_precision": 6,
                        "price_max_precision": 8,
                        "expiration": "NA",
                        "min_buy_amount": "0.00010000",
                        "min_sell_amount": "0.00010000"
                    },
                ]
            }
        }
        return details

    @staticmethod
    def get_order_placed_response_mock(exchange_order_id: int) -> Dict:
        response = {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "order_id": exchange_order_id
            }
        }
        return response

    @staticmethod
    def get_order_cancelled_response_mock(success: bool) -> Dict:
        response = {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "result": success
            }
        }
        return response

    @staticmethod
    def get_account_balances_response_mock(wallet: List[Dict[str, str]]) -> Dict:
        response = {
            "code": 1000,
            "trace": "886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "wallet": wallet
            }
        }
        return response

    @aioresponses()
    def test_check_network_succeeds_on_reply(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.CHECK_NETWORK_PATH_URL}"
        resp = self.get_system_status_reply_mock()
        mocked_api.get(url, body=json.dumps(resp))

        result = self.async_run_with_timeout(self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, result)

    @aioresponses()
    def test_check_network_fails_on_error(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.CHECK_NETWORK_PATH_URL}"
        mocked_api.get(url, body="", status=501)

        result = self.async_run_with_timeout(self.exchange.check_network())

        self.assertEqual(NetworkStatus.NOT_CONNECTED, result)

    @aioresponses()
    def test_trading_rules_polling_loop(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_TRADING_RULES_PATH_URL}"
        min_order_size = "1.10000000"
        resp = self.get_symbols_details_reply_mock(min_order_size)
        mocked_api.get(
            url, body=json.dumps(resp), callback=lambda *args, **kwargs: self.resume_test_event.set()
        )

        self.exchange_task = self.ev_loop.create_task(self.exchange._trading_rules_polling_loop())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertIn(self.trading_pair, self.exchange.trading_rules)

        trading_rules = self.exchange.trading_rules[self.trading_pair]

        self.assertTrue(isinstance(trading_rules, TradingRule))
        self.assertEqual(Decimal(min_order_size), trading_rules.min_order_size)

    @aioresponses()
    def test_trading_rules_polling_loop_stops_on_asyncio_cancelled_error(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_TRADING_RULES_PATH_URL}"
        mocked_api.get(url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.exchange._trading_rules_polling_loop())

    @patch("hummingbot.connector.exchange.bitmart.bitmart_exchange.BitmartExchange._update_trading_rules")
    def test_trading_rules_polling_loop_logs_other_exceptions(self, update_trading_rules_mock: AsyncMock):
        update_trading_rules_mock.side_effect = lambda: self.create_exception_and_unlock_with_event(
            Exception("Dummy test error")
        )
        self.exchange_task = self.ev_loop.create_task(self.exchange._trading_rules_polling_loop())
        self.async_run_with_timeout(self.resume_test_event.wait())
        self.resume_test_event.clear()

        self.assertTrue(
            self.is_logged("NETWORK", "Unexpected error while fetching trading rules. Error: Dummy test error")
        )

    def test_get_order_price_quantum(self):
        self.simulate_trading_rules_initialized()
        price_quantum = self.exchange.get_order_price_quantum(self.trading_pair, price=Decimal("1"))

        self.assertEqual(Decimal("0.0001"), price_quantum)

    def test_get_order_size_quantum(self):
        self.simulate_trading_rules_initialized()
        size_quantum = self.exchange.get_order_size_quantum(self.trading_pair, order_size=Decimal("1"))

        self.assertEqual(Decimal("0.000001"), size_quantum)

    @patch("hummingbot.connector.exchange.bitmart.bitmart_exchange.BitmartExchange._create_order")
    @patch("hummingbot.connector.exchange.bitmart.bitmart_utils.get_tracking_nonce")
    def test_buy(self, get_tracking_nonce_mock: MagicMock, create_order_mock: AsyncMock):
        nonce = "1234"
        amount = Decimal("1")
        price = Decimal("1000")
        get_tracking_nonce_mock.return_value = nonce
        order_id = self.exchange.buy(self.trading_pair, amount, OrderType.LIMIT, price)

        create_order_mock.assert_called_with(
            TradeType.BUY, order_id, self.trading_pair, amount, OrderType.LIMIT, price
        )
        self.assertEqual(f"{HBOT_BROKER_ID}B-{self.trading_pair}-{nonce}", order_id)

    @patch("hummingbot.connector.exchange.bitmart.bitmart_exchange.BitmartExchange._create_order")
    @patch("hummingbot.connector.exchange.bitmart.bitmart_utils.get_tracking_nonce")
    def test_sell(self, get_tracking_nonce_mock: MagicMock, create_order_mock: AsyncMock):
        nonce = "1234"
        amount = Decimal("1")
        price = Decimal("1000")
        get_tracking_nonce_mock.return_value = nonce
        order_id = self.exchange.sell(self.trading_pair, amount, OrderType.LIMIT, price)

        create_order_mock.assert_called_with(
            TradeType.SELL, order_id, self.trading_pair, amount, OrderType.LIMIT, price
        )
        self.assertEqual(f"{HBOT_BROKER_ID}S-{self.trading_pair}-{nonce}", order_id)

    @patch("hummingbot.connector.exchange.bitmart.bitmart_exchange.BitmartExchange._execute_cancel")
    def test_cancel(self, execute_cancel_mock: AsyncMock):
        order_id = "someId"
        ret = self.exchange.cancel(self.trading_pair, order_id)

        execute_cancel_mock.assert_called_with(self.trading_pair, order_id)
        self.assertEqual(order_id, ret)

    @aioresponses()
    def test_create_buy_order(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.CREATE_ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        exchange_id = 1234
        resp = self.get_order_placed_response_mock(exchange_id)
        mocked_api.post(regex_url, body=json.dumps(resp))

        self.simulate_trading_rules_initialized()

        order_id = "someId"
        amount = Decimal("1")
        price = Decimal("1000")
        self.async_run_with_timeout(
            self.exchange._create_order(
                TradeType.BUY, order_id, self.trading_pair, amount, OrderType.LIMIT, price
            )
        )

        self.assertEqual(1, len(self.exchange.in_flight_orders))

        order = self.exchange.in_flight_orders[order_id]

        self.assertEqual(amount, order.amount)
        self.assertEqual(TradeType.BUY, order.trade_type)

        created_orders_events = self.buy_order_created_logger.event_log

        self.assertEqual(1, len(created_orders_events))

        event = created_orders_events[0]

        self.assertEqual(order_id, event.order_id)

    @aioresponses()
    def test_create_sell_order(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.CREATE_ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        exchange_id = 1234
        resp = self.get_order_placed_response_mock(exchange_id)
        mocked_api.post(regex_url, body=json.dumps(resp))

        self.simulate_trading_rules_initialized()

        order_id = "someId"
        amount = Decimal("1")
        price = Decimal("1000")
        self.async_run_with_timeout(
            self.exchange._create_order(
                TradeType.SELL, order_id, self.trading_pair, amount, OrderType.LIMIT, price
            )
        )

        self.assertEqual(1, len(self.exchange.in_flight_orders))

        order = self.exchange.in_flight_orders[order_id]

        self.assertEqual(amount, order.amount)
        self.assertEqual(TradeType.SELL, order.trade_type)

        created_orders_events = self.sell_order_created_logger.event_log

        self.assertEqual(1, len(created_orders_events))

        event = created_orders_events[0]

        self.assertEqual(order_id, event.order_id)

    @aioresponses()
    def test_create_order_raises_on_asyncio_cancelled_error(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.CREATE_ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        mocked_api.post(regex_url, exception=asyncio.CancelledError)

        self.simulate_trading_rules_initialized()

        order_id = "someId"
        amount = Decimal("1")
        price = Decimal("1000")

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.exchange._create_order(
                    TradeType.SELL, order_id, self.trading_pair, amount, OrderType.LIMIT, price
                )
            )

    @aioresponses()
    def test_create_order_handles_other_exceptions(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.CREATE_ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        mocked_api.post(regex_url, exception=Exception("Dummy test error"))

        self.simulate_trading_rules_initialized()

        trade_type = TradeType.BUY
        order_id = "someId"
        amount = Decimal("1")
        order_type = OrderType.LIMIT
        price = Decimal("1000")
        self.async_run_with_timeout(
            self.exchange._create_order(
                trade_type, order_id, self.trading_pair, amount, order_type, price
            )
        )

        self.assertEqual(0, len(self.exchange.in_flight_orders))

        error_msg = (
            f"Error submitting {trade_type.name} {order_type.name} order to BitMart for"
            f" {self.exchange.quantize_order_amount(self.trading_pair, amount)} {self.trading_pair}"
            f" {self.exchange.quantize_order_price(self.trading_pair, price)}."
        )

        self.assertTrue(self.is_logged("NETWORK", error_msg))

    def test_start_tracking_order(self):
        order_id = "someId"
        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id="1234",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
        )

        self.assertEqual(1, len(self.exchange.in_flight_orders))

        order = self.exchange.in_flight_orders[order_id]

        self.assertEqual(order_id, order.client_order_id)

    def test_stop_tracking_order(self):
        order_id = "someId"
        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id="1234",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
        )

        self.exchange.stop_tracking_order("anotherId")  # should be ignored

        self.assertEqual(1, len(self.exchange.in_flight_orders))

        self.exchange.stop_tracking_order(order_id)

        self.assertEqual(0, len(self.exchange.in_flight_orders))

    @aioresponses()
    def test_execute_cancel(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.CANCEL_ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        resp = self.get_order_cancelled_response_mock(success=True)
        mocked_api.post(regex_url, body=json.dumps(resp))

        order_id = "someId"
        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id="1234",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
        )

        ret = self.async_run_with_timeout(self.exchange._execute_cancel(self.trading_pair, order_id))

        self.assertEqual(order_id, ret)

    @aioresponses()
    def test_execute_cancel_failed_is_logged(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.CANCEL_ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        resp = self.get_order_cancelled_response_mock(success=False)
        mocked_api.post(regex_url, body=json.dumps(resp))

        order_id = "someId"
        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id="1234",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
        )

        self.async_run_with_timeout(self.exchange._execute_cancel(self.trading_pair, order_id))

        logged_msg = (
            f"Failed to cancel order {order_id}:"
            f" Failed to cancel order - {order_id}. Order was already matched or cancelled on the exchange."
        )
        self.assertTrue(self.is_logged("NETWORK", logged_msg))

    @aioresponses()
    def test_execute_cancel_raises_on_asyncio_cancelled_error(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.CANCEL_ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        mocked_api.post(regex_url, exception=asyncio.CancelledError)

        order_id = "someId"
        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id="1234",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
        )

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.exchange._execute_cancel(self.trading_pair, order_id))

    @aioresponses()
    def test_execute_cancel_other_exceptions_are_logged(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.CANCEL_ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        mocked_api.post(regex_url, exception=Exception("Dummy test error"))

        order_id = "someId"
        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id="1234",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
        )

        self.async_run_with_timeout(self.exchange._execute_cancel(self.trading_pair, order_id))

        logged_msg = f"Failed to cancel order {order_id}: Dummy test error"
        self.assertTrue(self.is_logged("NETWORK", logged_msg))

    @patch("hummingbot.connector.exchange.bitmart.bitmart_exchange.BitmartExchange._update_balances")
    @patch("hummingbot.connector.exchange.bitmart.bitmart_exchange.BitmartExchange._update_order_status")
    def test_status_polling_loop(self, update_order_status_mock: AsyncMock, update_balances_mock: AsyncMock):
        update_order_status_mock.side_effect = self.return_queued_values_and_unlock_with_event
        self.return_values_queue.put_nowait("")

        self.exchange_task = self.ev_loop.create_task(self.exchange._status_polling_loop())
        self.exchange._poll_notifier.set()

        self.async_run_with_timeout(self.resume_test_event.wait())

        update_balances_mock.assert_called()
        update_order_status_mock.assert_called()

    @patch("hummingbot.connector.exchange.bitmart.bitmart_exchange.BitmartExchange._update_balances")
    def test_status_polling_loop_raises_on_asyncio_cancelled_error(self, update_balances_mock: AsyncMock):
        update_balances_mock.side_effect = lambda: self.create_exception_and_unlock_with_event(
            exception=asyncio.CancelledError
        )

        self.exchange._poll_notifier.set()

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.exchange._status_polling_loop())

    @patch("hummingbot.connector.exchange.bitmart.bitmart_exchange.BitmartExchange._update_balances")
    def test_status_polling_loop_logs_other_exceptions(self, update_balances_mock: AsyncMock):
        update_balances_mock.side_effect = lambda: self.create_exception_and_unlock_with_event(
            exception=Exception("Dummy test error")
        )

        self.exchange._poll_notifier.set()

        self.exchange_task = self.ev_loop.create_task(self.exchange._status_polling_loop())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(self.is_logged("ERROR", "Dummy test error"))
        self.assertTrue(
            self.is_logged("NETWORK", "Unexpected error while fetching account updates.")
        )

    @aioresponses()
    def test_update_balances_adds_new_balances(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ACCOUNT_SUMMARY_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        wallet = [
            {
                "id": self.base_asset,
                "available": "10.000000",
                "name": "CoinAlpha",
                "frozen": "5.000000",
            },
        ]
        resp = self.get_account_balances_response_mock(wallet)
        mocked_api.get(regex_url, body=json.dumps(resp))

        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertIn(self.base_asset, self.exchange.available_balances)
        self.assertEqual(Decimal("10"), self.exchange.available_balances[self.base_asset])
        self.assertEqual(Decimal("15"), self.exchange.get_balance(self.base_asset))

    @aioresponses()
    def test_update_balances_updates_balances(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ACCOUNT_SUMMARY_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        wallet = [
            {
                "id": self.base_asset,
                "available": "10.000000",
                "name": "CoinAlpha",
                "frozen": "5.000000",
            },
        ]
        resp = self.get_account_balances_response_mock(wallet)
        mocked_api.get(regex_url, body=json.dumps(resp))

        self.exchange.available_balances[self.base_asset] = Decimal("1")
        self.exchange._account_balances[self.base_asset] = Decimal("2")

        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertIn(self.base_asset, self.exchange.available_balances)
        self.assertEqual(Decimal("10"), self.exchange.available_balances[self.base_asset])
        self.assertEqual(Decimal("15"), self.exchange.get_balance(self.base_asset))

    @aioresponses()
    def test_update_balances_removes_balances(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ACCOUNT_SUMMARY_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        wallet = [
            {
                "id": self.base_asset,
                "available": "10.000000",
                "name": "CoinAlpha",
                "frozen": "5.000000",
            },
        ]
        resp = self.get_account_balances_response_mock(wallet)
        mocked_api.get(regex_url, body=json.dumps(resp))

        self.exchange.available_balances[self.quote_asset] = Decimal("1")
        self.exchange._account_balances[self.quote_asset] = Decimal("2")

        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertNotIn(self.quote_asset, self.exchange.available_balances)

    @aioresponses()
    def test_update_order_status_logs_missing_data_in_response(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ORDER_DETAIL_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        resp = {
            "message": "OK",
            "code": 1000,
            "trace": "a27c2cb5-ead4-471d-8455-1cfeda054ea6",
        }
        mocked_api.get(regex_url, body=json.dumps(resp))

        clock = Clock(
            ClockMode.BACKTEST,
            start_time=self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL,
            end_time=self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL * 2,
        )
        TimeIterator.start(self.exchange, clock)
        order_id = "someId"
        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id="1234",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
        )

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertTrue(
            self.is_logged("INFO", f"_update_order_status data not in resp: {resp}")
        )

    @aioresponses()
    def test_update_order_status_order_fill(self, mocked_api):
        exchange_order_id = "2147857398"
        order_id = "someId"
        price = "46100.0000000000"
        amount = "1.0000000000"

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ORDER_DETAIL_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        resp = {
            "message": "OK",
            "code": 1000,
            "trace": "a27c2cb5-ead4-471d-8455-1cfeda054ea6",
            "data": {
                "order_id": int(exchange_order_id),
                "symbol": self.exchange_trading_pair,
                "create_time": 1591096004000,
                "side": "buy",
                "type": "limit",
                "price": price,
                "price_avg": price,
                "size": amount,
                "notional": "0.00000000",
                "filled_notional": str(Decimal(price) / 2),
                "filled_size": str(Decimal(amount) / 2),
                "status": "5",  # partially filled
            }
        }
        mocked_api.get(regex_url, body=json.dumps(resp))

        clock = Clock(
            ClockMode.BACKTEST,
            start_time=self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL,
            end_time=self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL * 2,
        )
        TimeIterator.start(self.exchange, clock)
        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
            order_type=OrderType.LIMIT,
        )

        self.async_run_with_timeout(self.exchange._update_order_status())

        order = self.exchange.in_flight_orders[order_id]
        order_completed_events = self.buy_order_completed_logger.event_log
        orders_filled_events = self.order_filled_logger.event_log

        self.assertFalse(order.is_done or order.is_failure or order.is_cancelled)
        self.assertEqual(0, len(order_completed_events))
        self.assertEqual(1, len(orders_filled_events))
        self.assertEqual(order_id, orders_filled_events[0].order_id)

    @aioresponses()
    def test_update_order_status_order_filled(self, mocked_api):
        exchange_order_id = "2147857398"
        order_id = "someId"
        price = "46100.0000000000"
        amount = "1.0000000000"

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ORDER_DETAIL_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        resp = {
            "message": "OK",
            "code": 1000,
            "trace": "a27c2cb5-ead4-471d-8455-1cfeda054ea6",
            "data": {
                "order_id": int(exchange_order_id),
                "symbol": self.exchange_trading_pair,
                "create_time": 1591096004000,
                "side": "buy",
                "type": "limit",
                "price": price,
                "price_avg": price,
                "size": amount,
                "notional": "0.00000000",
                "filled_notional": price,
                "filled_size": amount,
                "status": "6",  # filled
            }
        }
        mocked_api.get(regex_url, body=json.dumps(resp))

        clock = Clock(
            ClockMode.BACKTEST,
            start_time=self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL,
            end_time=self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL * 2,
        )
        TimeIterator.start(self.exchange, clock)
        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
            order_type=OrderType.LIMIT,
        )
        order = self.exchange.in_flight_orders[order_id]

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_completed_events = self.buy_order_completed_logger.event_log
        orders_filled_events = self.order_filled_logger.event_log

        self.assertTrue(order.is_done)
        self.assertFalse(order.is_failure or order.is_cancelled)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(1, len(order_completed_events))
        self.assertEqual(order_id, order_completed_events[0].order_id)
        self.assertEqual(1, len(orders_filled_events))
        self.assertEqual(order_id, orders_filled_events[0].order_id)

    @aioresponses()
    def test_update_order_status_cancelled_event(self, mocked_api):
        exchange_order_id = "2147857398"
        order_id = "someId"
        price = "46100.0000000000"
        amount = "1.0000000000"

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ORDER_DETAIL_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        resp = {
            "message": "OK",
            "code": 1000,
            "trace": "a27c2cb5-ead4-471d-8455-1cfeda054ea6",
            "data": {
                "order_id": int(exchange_order_id),
                "symbol": self.exchange_trading_pair,
                "create_time": 1591096004000,
                "side": "buy",
                "type": "limit",
                "price": price,
                "price_avg": "0",
                "size": amount,
                "notional": "0.00000000",
                "filled_notional": "0",
                "filled_size": "0",
                "status": "8",  # cancelled
            }
        }
        mocked_api.get(regex_url, body=json.dumps(resp))

        clock = Clock(
            ClockMode.BACKTEST,
            start_time=self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL,
            end_time=self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL * 2,
        )
        TimeIterator.start(self.exchange, clock)
        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
            order_type=OrderType.LIMIT,
        )
        order = self.exchange.in_flight_orders[order_id]

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_completed_events = self.buy_order_completed_logger.event_log
        order_cancelled_events = self.order_cancelled_logger.event_log

        self.assertTrue(order.is_cancelled and order.is_done)
        self.assertFalse(order.is_failure)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(0, len(order_completed_events))
        self.assertEqual(1, len(order_cancelled_events))
        self.assertEqual(order_id, order_cancelled_events[0].order_id)

    @aioresponses()
    def test_update_order_status_order_failed_event(self, mocked_api):
        exchange_order_id = "2147857398"
        order_id = "someId"
        price = "46100.0000000000"
        amount = "1.0000000000"

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ORDER_DETAIL_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        resp = {
            "message": "OK",
            "code": 1000,
            "trace": "a27c2cb5-ead4-471d-8455-1cfeda054ea6",
            "data": {
                "order_id": int(exchange_order_id),
                "symbol": self.exchange_trading_pair,
                "create_time": 1591096004000,
                "side": "buy",
                "type": "limit",
                "price": price,
                "price_avg": "0",
                "size": amount,
                "notional": "0.00000000",
                "filled_notional": "0",
                "filled_size": "0",
                "status": "3",  # failure
            }
        }
        mocked_api.get(regex_url, body=json.dumps(resp))

        clock = Clock(
            ClockMode.BACKTEST,
            start_time=self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL,
            end_time=self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL * 2,
        )
        TimeIterator.start(self.exchange, clock)
        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
            order_type=OrderType.LIMIT,
        )
        order = self.exchange.in_flight_orders[order_id]

        self.async_run_with_timeout(self.exchange._update_order_status())

        order_completed_events = self.buy_order_completed_logger.event_log
        order_failure_events = self.order_failure_logger.event_log

        self.assertTrue(order.is_failure and order.is_done)
        self.assertFalse(order.is_cancelled)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(0, len(order_completed_events))
        self.assertEqual(1, len(order_failure_events))
        self.assertEqual(order_id, order_failure_events[0].order_id)

    def test_user_stream_event_queue_error_is_logged(self):
        self.exchange_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())

        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = lambda: self.create_exception_and_unlock_with_event(
            Exception("Dummy test error")
        )
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream

        self.async_run_with_timeout(self.resume_test_event.wait())
        self.resume_test_event.clear()

        self.assertTrue(self.is_logged("NETWORK", "Unknown error. Retrying after 1 seconds."))

    def test_user_stream_event_queue_notifies_async_cancel_errors(self):
        self.tracker_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())

        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = lambda: self.create_exception_and_unlock_with_event(
            asyncio.CancelledError()
        )
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.tracker_task)

    def test_user_stream_order_event_registers_partial_fill_event(self):
        exchange_order_id = "2147857398"
        order_id = "someId"
        price = "46100.0000000000"
        amount = "1.0000000000"

        message = {
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "side": "buy",
                    "type": "limit",
                    "notional": "",
                    "size": amount,
                    "ms_t": "1609926028000",
                    "price": price,
                    "filled_notional": str(Decimal(price) / 2),
                    "filled_size": str(Decimal(amount) / 2),
                    "margin_trading": "0",
                    "state": "5",  # partially filled
                    "order_id": exchange_order_id,
                    "order_type": "0",
                    "last_fill_time": "1609926039226",
                    "last_fill_price": price,
                    "last_fill_count": str(Decimal(amount) / 2)
                }
            ],
            "table": "spot/user/order"
        }
        self.return_values_queue.put_nowait(message)
        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = self.return_queued_values_and_unlock_with_event
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream
        self.tracker_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())

        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
            order_type=OrderType.LIMIT,
        )

        self.async_run_with_timeout(self.resume_test_event.wait())
        self.resume_test_event.clear()

        order = self.exchange.in_flight_orders[order_id]
        order_completed_events = self.buy_order_completed_logger.event_log
        orders_filled_events = self.order_filled_logger.event_log

        self.assertFalse(order.is_done or order.is_failure or order.is_cancelled)
        self.assertEqual(0, len(order_completed_events))
        self.assertEqual(1, len(orders_filled_events))
        self.assertEqual(order_id, orders_filled_events[0].order_id)

    def test_user_stream_order_event_registers_filled_event(self):
        exchange_order_id = "2147857398"
        order_id = "someId"
        price = "46100.0000000000"
        amount = "1.0000000000"

        message = {
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "side": "buy",
                    "type": "limit",
                    "notional": "",
                    "size": amount,
                    "ms_t": "1609926028000",
                    "price": price,
                    "filled_notional": price,
                    "filled_size": amount,
                    "margin_trading": "0",
                    "state": "6",  # filled
                    "order_id": exchange_order_id,
                    "order_type": "0",
                    "last_fill_time": "1609926039226",
                    "last_fill_price": price,
                    "last_fill_count": amount
                }
            ],
            "table": "spot/user/order"
        }
        self.return_values_queue.put_nowait(message)
        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = self.return_queued_values_and_unlock_with_event
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream
        self.tracker_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())

        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
            order_type=OrderType.LIMIT,
        )
        order = self.exchange.in_flight_orders[order_id]

        self.async_run_with_timeout(self.resume_test_event.wait())
        self.resume_test_event.clear()

        order_completed_events = self.buy_order_completed_logger.event_log
        orders_filled_events = self.order_filled_logger.event_log

        self.assertTrue(order.is_done)
        self.assertFalse(order.is_failure or order.is_cancelled)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(1, len(order_completed_events))
        self.assertEqual(order_id, order_completed_events[0].order_id)
        self.assertEqual(1, len(orders_filled_events))
        self.assertEqual(order_id, orders_filled_events[0].order_id)

    def test_user_stream_order_event_registers_cancelled_event(self):
        exchange_order_id = "2147857398"
        order_id = "someId"
        price = "46100.0000000000"
        amount = "1.0000000000"

        message = {
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "side": "buy",
                    "type": "limit",
                    "notional": "",
                    "size": amount,
                    "ms_t": "1609926028000",
                    "price": price,
                    "filled_notional": "0",
                    "filled_size": "0",
                    "margin_trading": "0",
                    "state": "8",  # cancelled
                    "order_id": exchange_order_id,
                    "order_type": "0",
                    "last_fill_time": "1609926039226",
                    "last_fill_price": "0",
                    "last_fill_count": "0"
                }
            ],
            "table": "spot/user/order"
        }
        self.return_values_queue.put_nowait(message)
        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = self.return_queued_values_and_unlock_with_event
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream
        self.tracker_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())

        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
            order_type=OrderType.LIMIT,
        )
        order = self.exchange.in_flight_orders[order_id]

        self.async_run_with_timeout(self.resume_test_event.wait())
        self.resume_test_event.clear()

        order_completed_events = self.buy_order_completed_logger.event_log
        order_cancelled_events = self.order_cancelled_logger.event_log

        self.assertTrue(order.is_cancelled and order.is_done)
        self.assertFalse(order.is_failure)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(0, len(order_completed_events))
        self.assertEqual(1, len(order_cancelled_events))
        self.assertEqual(order_id, order_cancelled_events[0].order_id)

    def test_user_stream_order_event_registers_failed_event(self):
        exchange_order_id = "2147857398"
        order_id = "someId"
        price = "46100.0000000000"
        amount = "1.0000000000"

        message = {
            "data": [
                {
                    "symbol": self.exchange_trading_pair,
                    "side": "buy",
                    "type": "limit",
                    "notional": "",
                    "size": amount,
                    "ms_t": "1609926028000",
                    "price": price,
                    "filled_notional": "0",
                    "filled_size": "0",
                    "margin_trading": "0",
                    "state": "3",  # failure
                    "order_id": exchange_order_id,
                    "order_type": "0",
                    "last_fill_time": "1609926039226",
                    "last_fill_price": "0",
                    "last_fill_count": "0"
                }
            ],
            "table": "spot/user/order"
        }
        self.return_values_queue.put_nowait(message)
        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = self.return_queued_values_and_unlock_with_event
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream
        self.tracker_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())

        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
            order_type=OrderType.LIMIT,
        )
        order = self.exchange.in_flight_orders[order_id]

        self.async_run_with_timeout(self.resume_test_event.wait())
        self.resume_test_event.clear()

        order_completed_events = self.buy_order_completed_logger.event_log
        order_failure_events = self.order_failure_logger.event_log

        self.assertTrue(order.is_failure and order.is_done)
        self.assertFalse(order.is_cancelled)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(0, len(order_completed_events))
        self.assertEqual(1, len(order_failure_events))
        self.assertEqual(order_id, order_failure_events[0].order_id)

    @aioresponses()
    def test_get_open_orders(self, mocked_api):
        exchange_order_id = "2147857398"
        order_id = "someId"
        price = "9000.00"

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_OPEN_ORDERS_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        resp = {
            "message": "OK",
            "code": 1000,
            "trace": "70e7d427-7436-4fb8-8cdd-97e1f5eadbe9",
            "data": {
                "current_page": 1,
                "orders": [
                    {
                        "order_id": int(exchange_order_id),
                        "symbol": self.exchange_trading_pair,
                        "create_time": 1591099963000,
                        "side": "buy",
                        "type": "limit",
                        "price": price,
                        "price_avg": "0.00",
                        "size": "1.00000",
                        "notional": "9000.00000000",
                        "filled_notional": "0.00000000",
                        "filled_size": "0.00000",
                        "status": "4"
                    },
                    {
                        "order_id": 2147601252,
                        "symbol": "BTC_USDT",
                        "create_time": 1591099964000,
                        "side": "sell",
                        "type": "limit",
                        "price": "10000.00",
                        "price_avg": "0.00",
                        "size": "2.00000",
                        "notional": "10000.00000000",
                        "filled_notional": "0.00000000",
                        "filled_size": "0.00000",
                        "status": "4"
                    }
                ]
            }
        }
        mocked_api.get(regex_url, body=json.dumps(resp))

        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
        )

        orders = self.async_run_with_timeout(self.exchange.get_open_orders())

        self.assertEqual(1, len(orders))

        order = orders[0]

        self.assertEqual(order_id, order.client_order_id)
        self.assertEqual(Decimal(price), order.price)

    @aioresponses()
    def test_get_open_orders_fetches_next_page(self, mocked_api):
        exchange_order_id = "2147857398"
        order_id = "someId"
        price = "9000.00"

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_OPEN_ORDERS_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        orders_list = [
            {
                "order_id": 2147601252,
                "symbol": "BTC_USDT",
                "create_time": 1591099964000,
                "side": "sell",
                "type": "limit",
                "price": "10000.00",
                "price_avg": "0.00",
                "size": "2.00000",
                "notional": "10000.00000000",
                "filled_notional": "0.00000000",
                "filled_size": "0.00000",
                "status": "4"
            }
        ]
        resp = {
            "message": "OK",
            "code": 1000,
            "trace": "70e7d427-7436-4fb8-8cdd-97e1f5eadbe9",
            "data": {
                "current_page": 1,
                "orders": orders_list * 100
            }
        }
        mocked_api.get(regex_url, body=json.dumps(resp))  # first page
        resp = {
            "message": "OK",
            "code": 1000,
            "trace": "70e7d427-7436-4fb8-8cdd-97e1f5eadbe9",
            "data": {
                "current_page": 2,
                "orders": [
                    {
                        "order_id": int(exchange_order_id),
                        "symbol": self.exchange_trading_pair,
                        "create_time": 1591099963000,
                        "side": "buy",
                        "type": "limit",
                        "price": price,
                        "price_avg": "0.00",
                        "size": "1.00000",
                        "notional": "9000.00000000",
                        "filled_notional": "0.00000000",
                        "filled_size": "0.00000",
                        "status": "4"
                    },
                ]
            }
        }
        mocked_api.get(regex_url, body=json.dumps(resp))  # second page

        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
        )

        orders = self.async_run_with_timeout(self.exchange.get_open_orders())

        self.assertEqual(1, len(orders))

    def test_cancel_all_raises_on_no_trading_pairs(self):
        self.exchange._trading_pairs = None

        with self.assertRaises(Exception):
            self.async_run_with_timeout(self.exchange.cancel_all(timeout_seconds=1))

    @aioresponses()
    def test_cancel_all(self, mocked_api):
        order_id = "someId"

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.CANCEL_ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        resp = self.get_order_cancelled_response_mock(success=True)
        mocked_api.post(regex_url, body=json.dumps(resp))

        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_OPEN_ORDERS_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        resp = {
            "message": "OK",
            "code": 1000,
            "trace": "70e7d427-7436-4fb8-8cdd-97e1f5eadbe9",
            "data": {
                "current_page": 1,
                "orders": []
            }
        }
        mocked_api.get(regex_url, body=json.dumps(resp))

        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id="1234",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
        )

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(timeout_seconds=1))

        order_cancelled_events = self.order_cancelled_logger.event_log

        self.assertEqual(1, len(order_cancelled_events))
        self.assertEqual(order_id, order_cancelled_events[0].order_id)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(1, len(cancellation_results))
        self.assertEqual(order_id, cancellation_results[0].order_id)

    @aioresponses()
    def test_cancel_all_logs_exceptions(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.CANCEL_ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}")
        mocked_api.post(regex_url, exception=Exception("Dummy test error"))

        self.exchange.start_tracking_order(
            order_id="someId",
            exchange_order_id="1234",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
        )

        self.async_run_with_timeout(self.exchange.cancel_all(timeout_seconds=1))

        self.assertTrue(self.is_logged("NETWORK", "Failed to cancel all orders."))

    def test_tick_no_poll(self):
        timestamp = self.exchange.POLL_INTERVAL
        self.exchange._last_timestamp = self.exchange.POLL_INTERVAL

        self.exchange.tick(timestamp)

        self.assertTrue(not self.exchange._poll_notifier.is_set())

    def test_tick_sets_poll(self):
        timestamp = self.exchange.POLL_INTERVAL * 2
        self.exchange._last_timestamp = self.exchange.POLL_INTERVAL

        self.exchange.tick(timestamp)

        self.assertTrue(self.exchange._poll_notifier.is_set())

    def test_get_fee(self):
        fee = self.exchange.get_fee(
            self.base_asset,
            self.quote_asset,
            OrderType.LIMIT,
            TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("10"),
        )

        self.assertEqual(Decimal("0.0025"), fee.percent)

        fee = self.exchange.get_fee(
            self.base_asset,
            self.quote_asset,
            OrderType.LIMIT_MAKER,
            TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("10"),
        )

        self.assertEqual(Decimal("0.0025"), fee.percent)
