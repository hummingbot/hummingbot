import asyncio
import json
import re
import time
from decimal import Decimal
from functools import partial
from typing import Awaitable, Dict, List
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.altmarkets.altmarkets_constants import Constants
from hummingbot.connector.exchange.altmarkets.altmarkets_exchange import AltmarketsExchange
from hummingbot.connector.exchange.altmarkets.altmarkets_in_flight_order import AltmarketsInFlightOrder
from hummingbot.connector.exchange.altmarkets.altmarkets_utils import (
    convert_to_exchange_trading_pair,
    get_new_client_order_id,
)
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.time_iterator import TimeIterator


class AltmarketsExchangeTests(TestCase):
    # logging.Level required to receive logs from the exchange
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "HBOT"
        cls.quote_asset = "BTC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.exchange_trading_pair = convert_to_exchange_trading_pair(cls.trading_pair)
        cls.api_key = "testKey"
        cls.api_secret_key = "testSecretKey"
        cls.username = "testUsername"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.async_tasks: List[asyncio.Task] = []
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.exchange = AltmarketsExchange(
            client_config_map=self.client_config_map,
            altmarkets_api_key=self.api_key,
            altmarkets_secret_key=self.api_secret_key,
            trading_pairs=[self.trading_pair]
        )
        self.return_values_queue = asyncio.Queue()
        self.resume_test_event = asyncio.Event()

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

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)

    def tearDown(self) -> None:
        for task in self.async_tasks:
            task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    async def return_queued_values_and_unlock_with_event(self):
        val = await self.return_values_queue.get()
        self.resume_test_event.set()
        return val

    def create_exception_and_unlock_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    def _register_sent_request(requests_list, url, **kwargs):
        requests_list.append((url, kwargs))

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    def get_order_create_response_mock(self,
                                       cancelled: bool = False,
                                       failed: bool = False,
                                       exchange_order_id: str = "someExchId",
                                       amount: str = "1",
                                       price: str = "5.00032",
                                       executed: str = "0.5") -> Dict:
        order_state = "wait"
        if cancelled:
            order_state = "cancel"
        elif failed:
            order_state = "reject"
        order_create_resp_mock = {
            "id": exchange_order_id,
            "client_id": "t-123456",
            "market": convert_to_exchange_trading_pair(self.trading_pair),
            "kind": "ask",
            "side": "buy",
            "ord_type": "limit",
            "price": price,
            "state": order_state,
            "origin_volume": amount,
            "executed_volume": str(Decimal(executed)),
            "remaining_volume": str(Decimal(amount) - Decimal(executed)),
            "at": "1548000000",
            "created_at": "1548000000",
            "updated_at": "1548000100",
        }
        return order_create_resp_mock

    def get_in_flight_order(self,
                            client_order_id: str,
                            exchange_order_id: str = "someExchId",
                            amount: str = "1",
                            price: str = "5.1") -> AltmarketsInFlightOrder:
        order = AltmarketsInFlightOrder(
            client_order_id,
            exchange_order_id,
            self.trading_pair,
            OrderType.LIMIT,
            TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
            creation_timestamp=1640001112.223
        )
        return order

    def get_user_balances_mock(self) -> List:
        user_balances = [
            {
                "currency": self.base_asset,
                "balance": "968.8",
                "locked": "0",
            },
            {
                "currency": self.quote_asset,
                "balance": "543.9",
                "locked": "0",
            },
        ]
        return user_balances

    def get_open_order_mock(self, exchange_order_id: str = "someExchId") -> List:
        open_orders = [
            {
                "id": exchange_order_id,
                "client_id": f"{Constants.HBOT_BROKER_ID}-{exchange_order_id}",
                "market": convert_to_exchange_trading_pair(self.trading_pair),
                "kind": "ask",
                "side": "buy",
                "ord_type": "limit",
                "price": "5.00032",
                "state": "wait",
                "origin_volume": "3.00016",
                "remaining_volume": "0.5",
                "executed_volume": "2.50016",
                "at": "1548000000",
                "created_at": "2020-01-16T21:02:23Z",
                "updated_at": "2020-01-16T21:02:23Z",
            }
        ]
        return open_orders

    def _get_order_status_url(self, with_id: bool = False):
        order_status_url = f"{Constants.REST_URL}/{Constants.ENDPOINT['ORDER_STATUS']}"
        if with_id:
            return re.compile(f"^{order_status_url[:-4]}[\\w]+".replace(".", r"\.").replace("?", r"\?"))
        return re.compile(f"^{order_status_url[:-4]}".replace(".", r"\.").replace("?", r"\?"))

    def _start_exchange_iterator(self):
        clock = Clock(
            ClockMode.BACKTEST,
            start_time=Constants.UPDATE_ORDER_STATUS_INTERVAL,
            end_time=Constants.UPDATE_ORDER_STATUS_INTERVAL * 2,
        )
        TimeIterator.start(self.exchange, clock)

    # BEGIN Tests

    @aioresponses()
    def test_check_network_success(self, mock_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['NETWORK_CHECK']}"
        resp = {}
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.CONNECTED)

    @aioresponses()
    def test_check_network_raises_cancelled_error(self, mock_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['NETWORK_CHECK']}"
        mock_api.get(url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(coroutine=self.exchange.check_network())

    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_http_utils.retry_sleep_time")
    @aioresponses()
    def test_check_network_not_connected_for_error_status(self, retry_sleep_time_mock, mock_api):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['NETWORK_CHECK']}"
        resp = {}
        for i in range(Constants.API_MAX_RETRIES):
            mock_api.get(url, status=405, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED)

    @aioresponses()
    def test_not_ready(self, mock_api):
        self.assertEqual(False, self.exchange.ready)
        self.assertEqual(False, self.exchange.status_dict['order_books_initialized'])

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['SYMBOL']}"
        resp = [{
            "id": "btcusdt",
            "base_unit": "btc",
            "quote_unit": "usdt",
            "min_price": "0.01",
            "max_price": "200000.0",
            "min_amount": "0.00000001",
            "amount_precision": 8,
            "price_precision": 2,
            "state": "enabled"
        }, {
            "id": "rogerbtc",
            "base_unit": "roger",
            "quote_unit": "btc",
            "min_price": "0.000000001",
            "max_price": "200000.0",
            "min_amount": "0.00000001",
            "amount_precision": 8,
            "price_precision": 8,
            "state": "enabled"
        }]
        mock_api.get(url, status=200, body=json.dumps(resp))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertIn("BTC-USDT", self.exchange.trading_rules)
        self.assertIn("ROGER-BTC", self.exchange.trading_rules)

        rule = self.exchange.trading_rules["BTC-USDT"]
        self.assertEqual(Decimal("0.00000001"), rule.min_order_size)
        self.assertEqual(Decimal("0.0000000001"), rule.min_notional_size)
        self.assertEqual(Decimal("1e-2"), rule.min_price_increment)
        self.assertEqual(Decimal("0.00000001"), rule.min_base_amount_increment)

    @aioresponses()
    def test_create_order(self, mock_api):
        sent_messages = []
        order_id = get_new_client_order_id(True, self.trading_pair)
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['ORDER_CREATE']}"
        resp = {"id": "Exchange-OID-1"}
        mock_api.post(url, body=json.dumps(resp), callback=partial(self._register_sent_request, sent_messages))

        self._simulate_trading_rules_initialized()

        self.async_run_with_timeout(self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id=order_id,
            trading_pair=self.trading_pair,
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
            price=Decimal(1000)
        ))

        self.assertTrue(resp, self.exchange.in_flight_orders[order_id].exchange_order_id)

        sent_message = json.loads(sent_messages[0][1]["data"])
        self.assertEqual(convert_to_exchange_trading_pair(self.trading_pair), sent_message["market"])
        self.assertEqual(OrderType.LIMIT.name.lower(), sent_message["ord_type"])
        self.assertEqual(TradeType.BUY.name.lower(), sent_message["side"])
        self.assertEqual(Decimal(1), Decimal(sent_message["volume"]))
        self.assertEqual(Decimal(1000), Decimal(sent_message["price"]))
        self.assertEqual(order_id, sent_message["client_id"])

    @aioresponses()
    def test_create_order_raises_on_asyncio_cancelled_error(self, mocked_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['ORDER_CREATE']}"
        regex_url = re.compile(f"^{url}")
        mocked_api.post(regex_url, exception=asyncio.CancelledError)

        self._simulate_trading_rules_initialized()

        order_id = "someId"
        amount = Decimal("1")
        price = Decimal("1000")

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.exchange._create_order(
                    TradeType.SELL, order_id, self.trading_pair, amount, OrderType.LIMIT, price
                )
            )

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
    def test_execute_cancel(self, mock_api):
        sent_messages = []
        order_id = get_new_client_order_id(True, self.trading_pair)
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['ORDER_DELETE'].format(id='E-OID-1')}"
        resp = {"state": "cancel"}
        mock_api.post(url, body=json.dumps(resp), callback=partial(self._register_sent_request, sent_messages))

        self._simulate_trading_rules_initialized()

        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(50000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
        )
        self.exchange.in_flight_orders[order_id].update_exchange_order_id("E-OID-1")

        result: CancellationResult = self.async_run_with_timeout(self.exchange._execute_cancel(self.trading_pair, order_id))

        self.assertEqual(order_id, result.order_id)
        self.assertTrue(result.success)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)

        self.assertEqual(url, f"{sent_messages[0][0]}")

    @aioresponses()
    def test_execute_cancel_ignores_local_orders(self, mock_api):
        sent_messages = []
        order_id = get_new_client_order_id(True, self.trading_pair)
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['ORDER_DELETE']}"
        # To ensure the request is not sent we associate an exception to it
        mock_api.post(url, exception=Exception(), callback=partial(self._register_sent_request, sent_messages))

        self._simulate_trading_rules_initialized()

        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(50000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
        )

        result: CancellationResult = self.async_run_with_timeout(
            self.exchange._execute_cancel(self.trading_pair, order_id))

        self.assertEqual(order_id, result.order_id)
        self.assertFalse(result.success)
        self.assertIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(0, len(sent_messages))

    def test_cancel_order_not_present_in_inflight_orders(self):
        client_order_id = "test-id"
        event_logger = EventLogger()
        self.exchange.add_listener(MarketEvent.OrderCancelled, event_logger)

        result = self.async_run_with_timeout(
            coroutine=self.exchange._execute_cancel(self.trading_pair, client_order_id)
        )

        self.assertEqual(0, len(event_logger.event_log))
        self.assertTrue(
            self._is_logged("WARNING", f"Failed to cancel order {client_order_id}. Order not found in inflight orders.")
        )
        self.assertFalse(result.success)

    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_http_utils.retry_sleep_time")
    @aioresponses()
    def test_execute_cancel_failed_is_logged(self, retry_sleep_time_mock, mocked_api):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['ORDER_DELETE'].format(id='1234')}"
        resp = {"errors": ['market.order.invaild_id_or_uuid']}
        for x in range(self.exchange.ORDER_NOT_EXIST_CANCEL_COUNT):
            mocked_api.post(url, body=json.dumps(resp))

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

        self.exchange.in_flight_orders[order_id].update_exchange_order_id("1234")

        self.async_run_with_timeout(self.exchange._execute_cancel(self.trading_pair, order_id))

        logged_msg = (
            f"Failed to cancel order - {order_id}: "
            f"['market.order.invaild_id_or_uuid']"
        )
        self.assertTrue(self._is_logged("NETWORK", logged_msg))

    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_http_utils.retry_sleep_time")
    @aioresponses()
    def test_execute_cancel_raises_on_asyncio_cancelled_error(self, retry_sleep_time_mock, mocked_api):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['ORDER_DELETE'].format(id='1234')}"
        mocked_api.post(url, exception=asyncio.CancelledError)

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

        self.exchange.in_flight_orders[order_id].update_exchange_order_id("1234")

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.exchange._execute_cancel(self.trading_pair, order_id))

    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_http_utils.retry_sleep_time")
    @aioresponses()
    def test_execute_cancel_other_exceptions_are_logged(self, retry_sleep_time_mock, mocked_api):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['ORDER_DELETE'].format(id='1234')}"
        resp = {"errors": {"message": 'Dummy test error'}}
        for x in range(self.exchange.ORDER_NOT_EXIST_CANCEL_COUNT):
            mocked_api.post(url, body=json.dumps(resp))

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

        self.exchange.in_flight_orders[order_id].update_exchange_order_id("1234")

        self.async_run_with_timeout(self.exchange._execute_cancel(self.trading_pair, order_id))

        logged_msg = f"Failed to cancel order - {order_id}: Dummy test error"
        self.assertTrue(self._is_logged("NETWORK", logged_msg))

    def test_stop_tracking_order_exceed_not_found_limit(self):
        client_order_id = "someId"
        exchange_order_id = "someExchId"
        self.exchange._in_flight_orders[client_order_id] = self.get_in_flight_order(client_order_id, exchange_order_id)
        self.assertEqual(1, len(self.exchange.in_flight_orders))

        self.exchange._order_not_found_records[client_order_id] = self.exchange.ORDER_NOT_EXIST_CONFIRMATION_COUNT

        self.exchange.stop_tracking_order_exceed_not_found_limit(self.exchange._in_flight_orders[client_order_id])
        self.assertEqual(0, len(self.exchange.in_flight_orders))

    @aioresponses()
    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_exchange.AltmarketsExchange.current_timestamp")
    def test_update_order_status_unable_to_fetch_order_status(self, mock_api, current_ts_mock):
        client_order_id = "someId"
        exchange_order_id = "someExchId"
        self.exchange._in_flight_orders[client_order_id] = self.get_in_flight_order(client_order_id, exchange_order_id)
        self.exchange._order_not_found_records[client_order_id] = self.exchange.ORDER_NOT_EXIST_CONFIRMATION_COUNT

        error_resp = {
            "errors": ["record.not_found"]
        }
        order_status_called_event = asyncio.Event()
        mock_api.get(
            self._get_order_status_url(),
            body=json.dumps(error_resp),
            callback=lambda *args, **kwargs: order_status_called_event.set(),
        )

        self.async_tasks.append(self.ev_loop.create_task(self.exchange._update_order_status()))
        self.async_run_with_timeout(order_status_called_event.wait())

        self._is_logged("WARNING", f"Failed to fetch order updates for order {client_order_id}. Response: {error_resp}")
        self.assertEqual(0, len(self.exchange.in_flight_orders))

    @aioresponses()
    def test_update_order_status_cancelled_event(self, mocked_api):
        exchange_order_id = "2147857398"
        order_id = "someId"
        price = "46100.0000000000"
        amount = "1.0000000000"

        self.exchange._order_not_found_records[order_id] = self.exchange.ORDER_NOT_EXIST_CONFIRMATION_COUNT

        resp = self.get_order_create_response_mock(cancelled=True,
                                                   exchange_order_id=exchange_order_id,
                                                   amount=amount,
                                                   price=price,
                                                   executed="0")
        mocked_api.get(self._get_order_status_url(), body=json.dumps(resp))

        self._start_exchange_iterator()
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
    def test_update_order_status_logs_missing_data_in_response(self, mocked_api):
        resp = {
            "invalid": "data missing id",
        }
        mocked_api.get(self._get_order_status_url(), body=json.dumps(resp))

        self._start_exchange_iterator()
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
            self._is_logged("INFO", f"_update_order_status order id not in resp: {resp}")
        )

    @aioresponses()
    def test_update_order_status_order_fill(self, mocked_api):
        exchange_order_id = "2147857398"
        order_id = "someId"
        price = "46100.0000000000"
        amount = "1.0000000000"

        resp = self.get_order_create_response_mock(cancelled=False,
                                                   exchange_order_id=exchange_order_id,
                                                   amount=amount,
                                                   price=price,
                                                   executed=str(Decimal(amount) / 2))
        mocked_api.get(self._get_order_status_url(), body=json.dumps(resp))

        self._start_exchange_iterator()
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

        resp = self.get_order_create_response_mock(cancelled=False,
                                                   exchange_order_id=exchange_order_id,
                                                   amount=amount,
                                                   price=price,
                                                   executed=amount)
        mocked_api.get(self._get_order_status_url(), body=json.dumps(resp))

        self._start_exchange_iterator()
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
    def test_update_order_status_order_failed_event(self, mocked_api):
        exchange_order_id = "2147857398"
        order_id = "someId"
        price = "46100.0000000000"
        amount = "1.0000000000"

        resp = self.get_order_create_response_mock(failed=True,
                                                   exchange_order_id=exchange_order_id,
                                                   amount=amount,
                                                   price=price,
                                                   executed="0")
        mocked_api.get(self._get_order_status_url(), body=json.dumps(resp))

        self._start_exchange_iterator()
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

    @aioresponses()
    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_exchange.AltmarketsExchange._sleep_time")
    def test_update_order_status_no_exchange_id(self, mocked_api, sleep_time_mock):
        sleep_time_mock.return_value = 0
        exchange_order_id = "someId"
        order_id = "HBOT-someId"
        price = "46100.0000000000"
        amount = "1.0000000000"

        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['USER_ORDERS']}"
        regex_url = re.compile(f"^{url}$".replace(".", r"\.").replace("?", r"\?"))
        open_resp = self.get_open_order_mock(exchange_order_id=exchange_order_id)
        mocked_api.get(regex_url, body=json.dumps(open_resp))

        resp = self.get_order_create_response_mock(exchange_order_id=None,
                                                   amount=amount,
                                                   price=price,
                                                   executed="0")
        mocked_api.get(self._get_order_status_url(with_id=True), body=json.dumps(resp))

        self._start_exchange_iterator()
        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
            order_type=OrderType.LIMIT,
        )
        order = self.exchange.in_flight_orders[order_id]

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.exchange.stop_tracking_order(order_id)

        self.assertEqual(exchange_order_id, order.exchange_order_id)

    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_exchange.AltmarketsExchange._sleep_time")
    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_http_utils.retry_sleep_time")
    @aioresponses()
    def test_update_order_status_no_exchange_id_failure(self, retry_sleep_time_mock, sleep_time_mock, mocked_api):
        sleep_time_mock.return_value = 0
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        order_id = "HBOT-someId"
        price = "46100.0000000000"
        amount = "1.0000000000"

        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['USER_ORDERS']}"
        regex_url = re.compile(f"^{url}$".replace(".", r"\.").replace("?", r"\?"))

        resp = self.get_order_create_response_mock(exchange_order_id=None,
                                                   amount=amount,
                                                   price=price,
                                                   executed="0")
        for x in range(4):
            mocked_api.get(self._get_order_status_url(with_id=True), body=json.dumps(resp))
            mocked_api.get(regex_url, body=json.dumps([]))

        self._start_exchange_iterator()
        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(price),
            amount=Decimal(amount),
            order_type=OrderType.LIMIT,
        )
        order = self.exchange.in_flight_orders[order_id]

        for x in range(4):
            self.async_run_with_timeout(self.exchange._update_order_status())

        order_completed_events = self.buy_order_completed_logger.event_log
        order_failure_events = self.order_failure_logger.event_log

        self.assertEqual(None, order.exchange_order_id)
        self.assertTrue(order.is_failure and order.is_done)
        self.assertFalse(order.is_cancelled)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(0, len(order_completed_events))
        self.assertEqual(1, len(order_failure_events))
        self.assertEqual(order_id, order_failure_events[0].order_id)

    @aioresponses()
    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_exchange.AltmarketsExchange.current_timestamp")
    def test_status_polling_loop(self, mock_api, current_ts_mock):
        # Order Balance Updates
        balances_url = f"{Constants.REST_URL}/{Constants.ENDPOINT['USER_BALANCES']}"
        balances_resp = self.get_user_balances_mock()
        balances_called_event = asyncio.Event()
        mock_api.get(
            balances_url, body=json.dumps(balances_resp), callback=lambda *args, **kwargs: balances_called_event.set()
        )

        client_order_id = "someId"
        exchange_order_id = "someExchId"
        self.exchange._in_flight_orders[client_order_id] = self.get_in_flight_order(client_order_id, exchange_order_id)

        # Order Status Updates
        order_status_resp = self.get_order_create_response_mock(cancelled=False, exchange_order_id=exchange_order_id)
        order_status_called_event = asyncio.Event()
        mock_api.get(
            self._get_order_status_url(),
            body=json.dumps(order_status_resp),
            callback=lambda *args, **kwargs: order_status_called_event.set(),
        )

        current_ts_mock.return_value = time.time()

        self.ev_loop.create_task(self.exchange._status_polling_loop())
        self.exchange._poll_notifier.set()
        self.async_run_with_timeout(balances_called_event.wait())
        self.async_run_with_timeout(order_status_called_event.wait())

        self.assertEqual(self.exchange.available_balances[self.base_asset], Decimal("968.8"))
        self.assertTrue(client_order_id in self.exchange.in_flight_orders)

        partially_filled_order = self.exchange.in_flight_orders[client_order_id]
        self.assertEqual(Decimal("0.5"), partially_filled_order.executed_amount_base)

    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_exchange.AltmarketsExchange._update_balances")
    def test_status_polling_loop_raises_on_asyncio_cancelled_error(self, update_balances_mock: AsyncMock):
        update_balances_mock.side_effect = lambda: self.create_exception_and_unlock_with_event(
            exception=asyncio.CancelledError
        )

        self.exchange._poll_notifier.set()

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.exchange._status_polling_loop())

    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_exchange.AltmarketsExchange._update_balances")
    def test_status_polling_loop_logs_other_exceptions(self, update_balances_mock: AsyncMock):
        update_balances_mock.side_effect = lambda: self.create_exception_and_unlock_with_event(
            exception=Exception("Dummy test error")
        )

        self.exchange._poll_notifier.set()

        self.async_tasks.append(self.ev_loop.create_task(self.exchange._status_polling_loop()))
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(self._is_logged("ERROR", "Dummy test error"))
        self.assertTrue(
            self._is_logged("NETWORK", "Unexpected error while fetching account updates.")
        )

    @aioresponses()
    def test_update_balances_adds_new_balances(self, mocked_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['USER_BALANCES']}"
        regex_url = re.compile(f"^{url}")
        resp = [
            {
                "currency": self.base_asset,
                "balance": "10.000000",
                "locked": "5.000000",
            },
        ]
        mocked_api.get(regex_url, body=json.dumps(resp))

        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertIn(self.base_asset, self.exchange.available_balances)
        self.assertEqual(Decimal("10"), self.exchange.available_balances[self.base_asset])
        self.assertEqual(Decimal("15"), self.exchange.get_balance(self.base_asset))

    @aioresponses()
    def test_update_balances_updates_balances(self, mocked_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['USER_BALANCES']}"
        regex_url = re.compile(f"^{url}")
        resp = [
            {
                "currency": self.base_asset,
                "balance": "10.000000",
                "locked": "5.000000",
            },
        ]
        mocked_api.get(regex_url, body=json.dumps(resp))

        self.exchange.available_balances[self.base_asset] = Decimal("1")
        self.exchange._account_balances[self.base_asset] = Decimal("2")

        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertIn(self.base_asset, self.exchange.available_balances)
        self.assertEqual(Decimal("10"), self.exchange.available_balances[self.base_asset])
        self.assertEqual(Decimal("15"), self.exchange.get_balance(self.base_asset))

    @aioresponses()
    def test_update_balances_removes_balances(self, mocked_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['USER_BALANCES']}"
        regex_url = re.compile(f"^{url}")
        resp = [
            {
                "currency": self.base_asset,
                "balance": "10.000000",
                "locked": "5.000000",
            },
        ]
        mocked_api.get(regex_url, body=json.dumps(resp))

        self.exchange.available_balances[self.quote_asset] = Decimal("1")
        self.exchange._account_balances[self.quote_asset] = Decimal("2")

        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertNotIn(self.quote_asset, self.exchange.available_balances)

    @aioresponses()
    def test_get_open_orders(self, mock_api):
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['USER_ORDERS']}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_open_order_mock()
        mock_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.get_open_orders())

        self.assertTrue(len(ret) == 1)

    def test_process_trade_message_matching_order_by_internal_order_id(self):
        self.exchange.start_tracking_order(
            order_id="OID-1",
            exchange_order_id="5736713",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1),
            order_type=OrderType.LIMIT,
        )

        trade_message = {
            "amount": "0.5",
            "created_at": 1615978645,
            "id": "5736713134",
            "market": self.exchange_trading_pair,
            "order_id": "5736713",
            "price": "10000",
            "side": "sell",
            "taker_type": "sell",
            "total": "5000"
        }

        self.async_run_with_timeout(coroutine=self.exchange._process_trade_message(trade_message))

        order = self.exchange.in_flight_orders["OID-1"]

        self.assertIn(f"{trade_message['order_id']}-{trade_message['created_at']}", order.trade_id_set)
        self.assertEqual(Decimal(0.5), order.executed_amount_base)
        self.assertEqual(Decimal(5000), order.executed_amount_quote)
        self.assertEqual(Decimal("0.00125"), order.fee_paid)
        self.assertEqual(self.quote_asset, order.fee_asset)

    def test_cancel_all_raises_on_no_trading_pairs(self):
        self.exchange._trading_pairs = None

        with self.assertRaises(Exception):
            self.async_run_with_timeout(self.exchange.cancel_all(timeout_seconds=1))

    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_http_utils.retry_sleep_time")
    @aioresponses()
    def test_cancel_all(self, retry_sleep_time_mock, mocked_api):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        order_id = "someId"
        endpoint = Constants.ENDPOINT['ORDER_DELETE'].format(id=r'[\w]+')
        url = f"{Constants.REST_URL}/{endpoint}"
        regex_url = re.compile(f"^{url}")
        resp = {"state": "cancel"}
        mocked_api.post(regex_url, body=json.dumps(resp))

        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['USER_ORDERS']}"
        resp = []
        mocked_api.get(url, body=json.dumps(resp))

        self.exchange.start_tracking_order(
            order_id,
            exchange_order_id="1234",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
        )

        self.exchange.in_flight_orders[order_id].update_exchange_order_id("1234")

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(timeout_seconds=1))

        order_cancelled_events = self.order_cancelled_logger.event_log

        self.assertEqual(1, len(order_cancelled_events))
        self.assertEqual(order_id, order_cancelled_events[0].order_id)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(1, len(cancellation_results))
        self.assertEqual(order_id, cancellation_results[0].order_id)

    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_http_utils.retry_sleep_time")
    @aioresponses()
    def test_cancel_all_logs_exceptions(self, retry_sleep_time_mock, mocked_api):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        url = f"{Constants.REST_URL}/{Constants.ENDPOINT['ORDER_DELETE'].format(id='1234')}"
        resp = {"errors": {"message": 'Dummy test error'}}
        mocked_api.post(url, body=json.dumps(resp))

        self.exchange.start_tracking_order(
            order_id="someId",
            exchange_order_id="1234",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
        )

        self.exchange.in_flight_orders["someId"].update_exchange_order_id("1234")

        self.async_run_with_timeout(self.exchange.cancel_all(timeout_seconds=1))

        self.assertTrue(self._is_logged("NETWORK", "Failed to cancel all orders, unexpected error."))

    def test_tick_no_poll(self):
        timestamp = Constants.SHORT_POLL_INTERVAL
        self.exchange._last_timestamp = Constants.SHORT_POLL_INTERVAL

        self.exchange.tick(timestamp)

        self.assertTrue(not self.exchange._poll_notifier.is_set())

    def test_tick_sets_poll(self):
        timestamp = Constants.SHORT_POLL_INTERVAL * 2
        self.exchange._last_timestamp = Constants.SHORT_POLL_INTERVAL

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

    def test_user_stream_event_queue_error_is_logged(self):
        self.async_tasks.append(self.ev_loop.create_task(self.exchange._user_stream_event_listener()))

        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = lambda: self.create_exception_and_unlock_with_event(
            Exception("Dummy test error")
        )
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream

        self.async_run_with_timeout(self.resume_test_event.wait())
        self.resume_test_event.clear()

        self.assertTrue(self._is_logged("NETWORK", "Unknown error. Retrying after 1 seconds."))

    def test_user_stream_event_queue_notifies_async_cancel_errors(self):
        tracker_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())
        self.async_tasks.append(tracker_task)

        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = lambda: self.create_exception_and_unlock_with_event(
            asyncio.CancelledError()
        )
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(tracker_task)

    def test_user_stream_order_event_registers_partial_fill_event(self):
        exchange_order_id = "2147857398"
        order_id = "someId"
        price = "46100.0000000000"
        amount = "1.0000000000"

        order = self.get_order_create_response_mock(exchange_order_id=exchange_order_id,
                                                    amount=amount,
                                                    price=price,
                                                    executed=str(Decimal(amount) / 2))
        message = {
            "order": order
        }
        self.return_values_queue.put_nowait(message)
        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = self.return_queued_values_and_unlock_with_event
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream
        self.async_tasks.append(self.ev_loop.create_task(self.exchange._user_stream_event_listener()))

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

        order = self.get_order_create_response_mock(exchange_order_id=exchange_order_id,
                                                    amount=amount,
                                                    price=price,
                                                    executed=amount)
        message = {
            "order": order
        }
        self.return_values_queue.put_nowait(message)
        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = self.return_queued_values_and_unlock_with_event
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream
        self.async_tasks.append(self.ev_loop.create_task(self.exchange._user_stream_event_listener()))

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

        order = self.get_order_create_response_mock(cancelled=True,
                                                    exchange_order_id=exchange_order_id,
                                                    amount=amount,
                                                    price=price,
                                                    executed="0")
        message = {
            "order": order
        }
        self.return_values_queue.put_nowait(message)
        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = self.return_queued_values_and_unlock_with_event
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream
        self.async_tasks.append(self.ev_loop.create_task(self.exchange._user_stream_event_listener()))

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

        order = self.get_order_create_response_mock(failed=True,
                                                    exchange_order_id=exchange_order_id,
                                                    amount=amount,
                                                    price=price,
                                                    executed="0")
        message = {
            "order": order
        }
        self.return_values_queue.put_nowait(message)
        dummy_user_stream = AsyncMock()
        dummy_user_stream.get.side_effect = self.return_queued_values_and_unlock_with_event
        self.exchange._user_stream_tracker._user_stream = dummy_user_stream
        self.async_tasks.append(self.ev_loop.create_task(self.exchange._user_stream_event_listener()))

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
