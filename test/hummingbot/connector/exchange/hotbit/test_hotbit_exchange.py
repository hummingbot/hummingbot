import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Any, Awaitable, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.hotbit import hotbit_constants as CONSTANTS
from hummingbot.connector.exchange.hotbit.hotbit_exchange import HotbitExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
)
from hummingbot.core.network_iterator import NetworkStatus


class TestHotbitExchange(unittest.TestCase):
    # logging.Level required to receive logs from the exchange
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        cls.api_key = "someKey"
        cls.api_secret = "someSecret"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.mocking_assistant = NetworkMockingAssistant()
        self.async_tasks: List[asyncio.Task] = []
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.exchange = HotbitExchange(
            client_config_map=self.client_config_map,
            hotbit_api_key=self.api_key,
            hotbit_api_secret=self.api_secret,
            trading_pairs=[self.trading_pair])

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
        self.exchange._time_synchronizer.logger().setLevel(1)
        self.exchange._time_synchronizer.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)

        self._initialize_event_loggers()

        self.exchange._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        for task in self.async_tasks:
            task.cancel()
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

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_trading_rules_mock(self) -> List:
        trading_rules = {
            "error": None,
            "result": [
                {
                    "name": self.ex_trading_pair,
                    "stock": self.base_asset,
                    "money": self.quote_asset,
                    "fee_prec": 4,
                    "stock_prec": 2,
                    "money_prec": 8,
                    "min_amount": "0.1"
                }
            ],
            "id": 1521169333
        }
        return trading_rules

    def get_order_create_response_mock(self, cancelled: bool = False, exchange_order_id: str = "someExchId") -> Dict:
        order_create_resp_mock = {
            "error": None,
            "result": {
                "id": exchange_order_id,
                "market": self.ex_trading_pair,
                "source": "web",
                "type": 1,
                "side": 2,
                "user": 15731,
                "ctime": 1526971722.164765,
                "mtime": 1526971722.164765,
                "price": "0.08",
                "amount": "0.4",
                "taker_fee": "0.0025",
                "maker_fee": "0",
                "left": "0.4",
                "deal_stock": "0",
                "deal_money": "0",
                "deal_fee": "0",
                "status": 8 if cancelled else 0,
                "fee_stock": "HTB",
                "alt_fee": "0.5",
                "deal_fee_alt": "0.123"
            },
            "id": 1521169460
        }
        return order_create_resp_mock

    def get_order_trade_response(
            self, order: InFlightOrder, is_completely_filled: bool = False
    ) -> Dict[str, Any]:
        order_amount = order.amount
        if not is_completely_filled:
            order_amount = float(Decimal("0.5") * order_amount)
        base_asset, quote_asset = order.trading_pair.split("-")[0], order.trading_pair.split("-")[1]
        return [
            {
                "id": 5736713,
                "user_id": 1000001,
                "order_id": order.exchange_order_id,
                "currency_pair": order.trading_pair,
                "create_time": 1605176741,
                "create_time_ms": "1605176741123.456",
                "side": "buy" if order.trade_type == TradeType.BUY else "sell",
                "amount": str(order_amount),
                "role": "maker",
                "price": str(order.price),
                "fee": "0.00200000000000",
                "fee_currency": base_asset if order.trade_type == TradeType.BUY else quote_asset,
                "point_fee": "0",
                "gt_fee": "0",
                "text": order.client_order_id,
            }
        ]

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    @aioresponses()
    def test_all_trading_pairs(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)
        url = f"{CONSTANTS.REST_URL_P1}{CONSTANTS.EXCHANGE_INFO_PATH_URL}"
        resp = {
            "error": None,
            "result": [
                {
                    "name": self.ex_trading_pair,
                    "stock": self.base_asset,
                    "money": self.quote_asset,
                    "fee_prec": 4,
                    "stock_prec": 2,
                    "money_prec": 8,
                    "min_amount": "0.1"
                }
            ],
            "id": 1521169333
        }
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

        self.assertEqual(1, len(ret))
        self.assertIn(self.trading_pair, ret)
        self.assertNotIn("SOMEPAIR", ret)

    @aioresponses()
    def test_all_trading_pairs_does_not_raise_exception(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)

        url = f"{CONSTANTS.REST_URL_P1}{CONSTANTS.EXCHANGE_INFO_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception)

        result: Dict[str] = self.async_run_with_timeout(self.exchange.all_trading_pairs())

        self.assertEqual(0, len(result))

    @aioresponses()
    def test_get_last_traded_prices(self, mock_api):
        url = f"{CONSTANTS.REST_URL_P1}{CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = {
            "error": None,
            "result": {
                "period": 10,
                "last": "0.0743",
                "open": "0.074162",
                "close": "0.0743",
                "high": "0.0743",
                "low": "0.074162",
                "volume": "0.314",
                "deal": "0.023315531"
            },
            "id": 1521169247
        }
        mock_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(
            coroutine=self.exchange.get_last_traded_prices(trading_pairs=[self.trading_pair])
        )

        ticker_requests = [(key, value) for key, value in mock_api.requests.items()
                           if key[1].human_repr().startswith(url)]

        request_params = ticker_requests[0][1][0].kwargs["params"]
        self.assertEqual(self.ex_trading_pair, request_params["market"])

        self.assertEqual(ret[self.trading_pair], float(resp["result"]["last"]))

    @aioresponses()
    def test_check_network_not_connected(self, mock_api):
        url = f"{CONSTANTS.REST_URL_P1}{CONSTANTS.CHECK_NETWORK_PATH_URL}"
        resp = ""
        for i in range(5):
            mock_api.get(url, status=500, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED, msg=f"{ret}")

    @aioresponses()
    def test_check_network(self, mock_api):
        url = f"{CONSTANTS.REST_URL_P1}{CONSTANTS.CHECK_NETWORK_PATH_URL}"
        resp = {"error": None, "result": "0.06805299", "id": 809329876}
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.CONNECTED)

    @aioresponses()
    def test_update_trading_rules_polling_loop(self, mock_api):
        url = f"{CONSTANTS.REST_URL_P1}{CONSTANTS.EXCHANGE_INFO_PATH_URL}"
        resp = self.get_trading_rules_mock()
        called_event = asyncio.Event()
        mock_api.get(url, body=json.dumps(resp), callback=lambda *args, **kwargs: called_event.set())

        self.ev_loop.create_task(self.exchange._trading_rules_polling_loop())
        self.async_run_with_timeout(called_event.wait())

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        url = f"{CONSTANTS.REST_URL_P1}{CONSTANTS.EXCHANGE_INFO_PATH_URL}"
        resp = {
            "error": None,
            "result": [
                {
                    "name": self.ex_trading_pair,
                    "stock": self.base_asset,
                    "money": self.quote_asset
                }
            ],
            "id": 1521169333
        }
        called_event = asyncio.Event()
        mock_api.get(url, body=json.dumps(resp), callback=lambda *args, **kwargs: called_event.set())

        self.ev_loop.create_task(self.exchange._trading_rules_polling_loop())
        self.async_run_with_timeout(called_event.wait())

        self.assertEqual(0, len(self.exchange.trading_rules))
        self.assertTrue(
            self._is_logged("ERROR", f"Error parsing the trading pair rule {resp['result'][0]}. Skipping.")
        )

    @aioresponses()
    def test_create_order(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        url = f"{CONSTANTS.REST_URL_P2}{CONSTANTS.ORDER_LIMIT_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_create_response_mock()
        mock_api.post(regex_url, body=json.dumps(resp))
        order_id = "someId"

        self.async_run_with_timeout(
            coroutine=self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("0.4"),
                order_type=OrderType.LIMIT,
                price=Decimal("0.08"),
            )
        )

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        request_data = parse_qs(order_request[1][0].kwargs["data"])
        self.assertEqual(self.ex_trading_pair, request_data["market"][0])
        self.assertEqual(CONSTANTS.SIDE_BUY, int(request_data["side"][0]))
        self.assertEqual(Decimal("0.4"), Decimal(request_data["amount"][0]))
        self.assertEqual(Decimal("0.08"), Decimal(request_data["price"][0]))

        self.assertIn(order_id, self.exchange.in_flight_orders)

        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("0.4"), create_event.amount)
        self.assertEqual(Decimal("0.08"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(resp["result"]["id"], create_event.exchange_order_id)

    @aioresponses()
    def test_order_with_less_amount_than_allowed_is_not_created(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)

        url = f"{CONSTANTS.REST_URL_P2}{CONSTANTS.ORDER_LIMIT_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, exception=Exception("The request should never happen"))

        order_id = "someId"
        self.async_run_with_timeout(
            coroutine=self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("0.000001"),
                order_type=OrderType.LIMIT,
                price=Decimal("1"),
            )
        )

        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(1, len(self.order_failure_logger.event_log))
        self.assertTrue(
            self._is_logged(
                "WARNING",
                "Buy order amount 0 is lower than the minimum order size 0.01. The order will not be created."
            )
        )

    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    @aioresponses()
    def test_create_order_fails(self, _, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)

        url = f"{CONSTANTS.REST_URL_P2}{CONSTANTS.ORDER_LIMIT_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = {"error": {"code": 4, "message": "pair not found"}, "result": None, "id": 0}
        mock_api.post(regex_url, body=json.dumps(resp))

        order_id = "someId"
        self.async_run_with_timeout(
            coroutine=self.exchange._create_order(
                trade_type=TradeType.BUY,
                order_id=order_id,
                trading_pair=self.trading_pair,
                amount=Decimal("0.4"),
                order_type=OrderType.LIMIT,
                price=Decimal("0.08"),
            )
        )

        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        self.assertEqual(1, len(self.order_failure_logger.event_log))

    @aioresponses()
    def test_create_order_request_fails_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        url = f"{CONSTANTS.REST_URL_P2}{CONSTANTS.ORDER_LIMIT_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, status=400)

        order_id = "OID1"
        self.async_run_with_timeout(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id=order_id,
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))

        self.assertNotIn("OID1", self.exchange.in_flight_orders)
        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual("OID1", failure_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Order OID1 has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                "client_order_id='OID1', exchange_order_id=None, misc_updates=None)"
            )
        )

    @aioresponses()
    def test_execute_cancel(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)
        client_order_id = "someId"
        exchange_order_id = "someExchId"
        self.exchange.start_tracking_order(
            order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        url = f"{CONSTANTS.REST_URL_P2}{CONSTANTS.ORDER_CANCEL_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_order_create_response_mock(cancelled=True)
        mock_api.post(regex_url, body=json.dumps(resp))

        self.async_run_with_timeout(self.exchange._execute_cancel(self.trading_pair, client_order_id))

        cancel_request = next(((key, value) for key, value in mock_api.requests.items() if key[1].human_repr().startswith(url)))
        request_data = parse_qs(cancel_request[1][0].kwargs["data"])
        self.assertEqual(self.ex_trading_pair, request_data["market"][0])

        self.assertEqual(1, len(self.order_cancelled_logger.event_log))

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(exchange_order_id, cancel_event.exchange_order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Successfully canceled order {client_order_id}."
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

        url = f"{CONSTANTS.REST_URL_P2}{CONSTANTS.ORDER_CANCEL_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set()
                      )

        self.exchange.cancel(trading_pair=self.trading_pair, client_order_id="OID1")
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(0, len(self.order_cancelled_logger.event_log))

        self.assertTrue(
            self._is_logged(
                "ERROR",
                f"Failed to cancel order {order.client_order_id}"
            )
        )

    def test_cancel_order_without_exchange_order_id_marks_order_as_fail_after_retries(self):
        update_event = MagicMock()
        update_event.wait.side_effect = asyncio.TimeoutError

        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("OID1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders["OID1"]
        order.exchange_order_id_update_event = update_event

        self.async_run_with_timeout(self.exchange._execute_cancel(
            trading_pair=order.trading_pair,
            order_id=order.client_order_id,
        ), 5)

        self.assertEqual(0, len(self.order_cancelled_logger.event_log))

        self.assertTrue(
            self._is_logged(
                "WARNING",
                f"Failed to cancel the order {order.client_order_id} because it does not have an exchange order id yet"
            )
        )

        # After the fourth time not finding the exchange order id the order should be marked as failed
        for i in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(self.exchange._execute_cancel(
                trading_pair=order.trading_pair,
                order_id=order.client_order_id,
            ), 5)

        self.assertTrue(order.is_failure)

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)

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

        url = f"{CONSTANTS.REST_URL_P2}{CONSTANTS.ORDER_CANCEL_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = self.get_order_create_response_mock(cancelled=True, exchange_order_id=order1.exchange_order_id)

        mock_api.post(regex_url, body=json.dumps(response))

        url = f"{CONSTANTS.REST_URL_P2}{CONSTANTS.ORDER_CANCEL_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, status=400)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(10))

        self.assertEqual(2, len(cancellation_results))
        self.assertEqual(CancellationResult(order1.client_order_id, True), cancellation_results[0])
        self.assertEqual(CancellationResult(order2.client_order_id, False), cancellation_results[1])

        self.assertEqual(1, len(self.order_cancelled_logger.event_log))
        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order1.client_order_id, cancel_event.order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Successfully canceled order {order1.client_order_id}."
            )
        )

    @aioresponses()
    def test_update_balances(self, mock_api):
        url = f"{CONSTANTS.REST_URL_P2}{CONSTANTS.ACCOUNTS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {
            "error": None,
            "id": 1585283976,
            "result": {
                self.base_asset:
                {
                    "available": "968.8",
                    "freeze": "0"
                },
                self.quote_asset:
                {
                    "available": "500",
                    "freeze": "300"
                }
            }
        }

        mock_api.post(regex_url, body=json.dumps(response))
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("968.8"), available_balances[self.base_asset])
        self.assertEqual(Decimal("500"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("968.8"), total_balances[self.base_asset])
        self.assertEqual(Decimal("800"), total_balances[self.quote_asset])

    @aioresponses()
    def test_update_order_status_when_filled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

        # Order Trade Updates
        order_trade_updates_url = f"{CONSTANTS.REST_URL_P2}{CONSTANTS.PENDING_ORDER_PATH_URL}"
        regex_order_trade_updates_url = re.compile(
            f"^{order_trade_updates_url}".replace(".", r"\.").replace("?", r"\?"))
        order_trade_updates_resp = {"error": None, "result": {}, "id": 2723023357}
        mock_api.post(
            regex_order_trade_updates_url,
            body=json.dumps(order_trade_updates_resp)
        )

        # Order Status Updates
        order_status_url = (f"{CONSTANTS.REST_URL_P2}"
                            f"{CONSTANTS.MY_TRADES_PATH_URL}")
        regex_order_status_url = re.compile(f"^{order_status_url}".replace(".", r"\.").replace("?", r"\?"))
        order_status_resp = {
            "error": None,
            "result": {
                "offset": 0,
                "limit": 0,
                "records": [
                    {
                        "alt_fee": -0.003,
                        "amount": 300,
                        "create_time": 1677141969.558242,
                        "deal_fee": -0.08988039,
                        "deal_fee_alt": 0,
                        "deal_money": 29.96013,
                        "deal_stock": 46.05,
                        "fee_stock": '',
                        "finish_time": 1677142027.846882,
                        "id": "id",
                        "maker_fee": -0.003,
                        "market": self.ex_trading_pair,
                        "platform": '',
                        "price": 0.6506,
                        "side": 1,
                        "source": '2001:19f0:7001:3e91:3eec:efff:feb9:8604',
                        "status": CONSTANTS.FINISHED_STATE_FILLED,
                        "t": 1,
                        "taker_fee": 0.003,
                        "type": 1,
                        "user_id": 2478863
                    }
                ]
            },
            "id": 2723023357
        }
        mock_api.post(
            regex_order_status_url,
            body=json.dumps(order_status_resp),
        )

        # Simulate the order has been filled with a TradeUpdate
        order.completely_filled_event.set()
        self.async_run_with_timeout(self.exchange._update_order_status())
        self.async_run_with_timeout(order.wait_until_completely_filled())

        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(Decimal(0), buy_event.base_asset_amount)
        self.assertEqual(Decimal(0), buy_event.quote_asset_amount)
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
    def test_update_order_status_registers_order_not_found(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

        # Order Trade Updates
        order_trade_updates_url = f"{CONSTANTS.REST_URL_P2}{CONSTANTS.PENDING_ORDER_PATH_URL}"
        regex_order_trade_updates_url = re.compile(
            f"^{order_trade_updates_url}".replace(".", r"\.").replace("?", r"\?"))
        order_trade_updates_resp = {"error": None, "result": {}, "id": 2723023357}
        mock_api.post(
            regex_order_trade_updates_url,
            body=json.dumps(order_trade_updates_resp)
        )

        # Order Status Updates
        order_status_url = (f"{CONSTANTS.REST_URL_P2}"
                            f"{CONSTANTS.MY_TRADES_PATH_URL}")
        regex_order_status_url = re.compile(f"^{order_status_url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_order_status_url, status=404)

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertTrue(order.is_open)
        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

        self.assertTrue(
            self._is_logged(
                "WARNING",
                f"Error fetching status update for the order {order.client_order_id}: "
                f"Error executing request POST "
                f"{CONSTANTS.REST_URL_P2}{CONSTANTS.MY_TRADES_PATH_URL}. "
                f"HTTP status is 404. Error: ."
            )
        )

    def test_update_order_status_marks_order_with_no_exchange_id_as_not_found(self):
        update_event = MagicMock()
        update_event.wait.side_effect = asyncio.TimeoutError

        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]
        order.exchange_order_id_update_event = update_event

        self.async_run_with_timeout(self.exchange._update_order_status(), 5)

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)

        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

    @patch("hummingbot.connector.utils.get_tracking_nonce")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 7

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

    def test_user_stream_update_for_new_order(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        event_message = {
            "method": "order.update",
            "params": [
                1,
                {
                    "id": order.exchange_order_id,
                    "market": self.ex_trading_pair,
                    "source": "",
                    "type": 1,
                    "side": CONSTANTS.SIDE_BUY,
                    "user": 5,
                    "ctime": 1513819599.987308,
                    "mtime": 1513819599.987308,
                    "price": str(order.price),
                    "amount": str(order.amount),
                    "taker_fee": "0.002",
                    "maker_fee": "0.001",
                    "left": str(order.amount),
                    "deal_stock": "0",
                    "deal_money": "0",
                    "deal_fee": "0"}
            ],
            "id": 102
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        self.assertTrue(order.is_open)

    def test_user_stream_update_for_cancelled_order(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        event_message = {
            "method": "order.update",
            "params": [
                3,
                {
                    "id": order.exchange_order_id,
                    "market": self.ex_trading_pair,
                    "source": "",
                    "type": 1,
                    "side": CONSTANTS.SIDE_BUY,
                    "user": 5,
                    "ctime": 1513819599.987308,
                    "mtime": 1513819599.987308,
                    "price": str(order.price),
                    "amount": str(order.amount),
                    "taker_fee": "0.002",
                    "maker_fee": "0.001",
                    "left": str(order.amount),
                    "deal_stock": "0",
                    "deal_money": "0",
                    "deal_fee": "0"}
            ],
            "id": 102
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_cancelled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self._is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    def test_user_stream_update_for_order_partial_fill(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]
        order.current_state = OrderState.OPEN

        event_message = {
            "method": "order.update",
            "params": [
                2,
                {
                    "id": order.exchange_order_id,
                    "market": self.ex_trading_pair,
                    "source": "",
                    "type": 1,
                    "side": CONSTANTS.SIDE_BUY,
                    "user": 5,
                    "ctime": 1513819599.987308,
                    "mtime": 1513819599.987308,
                    "price": str(order.price),
                    "amount": str(order.amount),
                    "taker_fee": "0.002",
                    "maker_fee": "0.001",
                    "left": str(order.amount),
                    "deal_stock": "0.1",
                    "deal_money": "1000",
                    "deal_fee": "0"}
            ],
            "id": 102
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertTrue(order.is_open)
        self.assertEqual(OrderState.PARTIALLY_FILLED, order.current_state)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(event_message["params"][1]["price"]), fill_event.price)
        self.assertEqual(Decimal(event_message["params"][1]["deal_stock"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(
                self.quote_asset,
                Decimal(event_message["params"][1]["deal_fee"]))],
            fill_event.trade_fee.flat_fees)
        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

        self.assertTrue(
            self._is_logged("INFO", f"The {order.trade_type.name} order {order.client_order_id} amounting to "
                                    f"0.1/{order.amount} {order.base_asset} has been filled.")
        )

    def test_user_stream_update_for_order_fill(self):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        filled_event_message = {
            "method": "order.update",
            "params": [
                3,
                {
                    "id": order.exchange_order_id,
                    "market": self.ex_trading_pair,
                    "source": "",
                    "type": 1,
                    "side": CONSTANTS.SIDE_BUY,
                    "user": 5,
                    "ctime": 1513819599.987308,
                    "mtime": 1513819599.987308,
                    "price": str(order.price),
                    "amount": str(order.amount),
                    "taker_fee": "0.002",
                    "maker_fee": "0.001",
                    "left": str(order.amount),
                    "deal_stock": str(order.amount),
                    "deal_money": "10000",
                    "deal_fee": "0"}
            ],
            "id": 102
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [filled_event_message, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(filled_event_message["params"][1]["price"]), fill_event.price)
        self.assertEqual(Decimal(filled_event_message["params"][1]["amount"]), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([
            TokenAmount(
                self.quote_asset,
                Decimal(filled_event_message["params"][1]["deal_fee"]))],
            fill_event.trade_fee.flat_fees)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        self.assertEqual(order.amount * Decimal(filled_event_message["params"][1]["price"]),
                         buy_event.quote_asset_amount)
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

    def test_user_stream_raises_cancel_exception(self):
        self.exchange._set_current_timestamp(1640780000)

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError
        self.exchange._user_stream_tracker._user_stream = mock_queue

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout,
            self.exchange._user_stream_event_listener())

    @patch("hummingbot.connector.exchange.hotbit.hotbit_exchange.HotbitExchange._sleep")
    def test_user_stream_logs_errors(self, sleep_mock):
        self.exchange._set_current_timestamp(1640780000)

        incomplete_event = {
            "method": "order.update",
            "id": 102
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_event, asyncio.CancelledError]
        self.exchange._user_stream_tracker._user_stream = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._user_stream_event_listener())
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error in user stream listener loop."
            )
        )

    def test_initial_status_dict(self):
        self.exchange._set_trading_pair_symbol_map(None)

        status_dict = self.exchange.status_dict

        expected_initial_dict = {
            "symbols_mapping_initialized": False,
            "order_books_initialized": False,
            "account_balance": False,
            "trading_rule_initialized": False,
            "user_stream_initialized": False,
        }

        self.assertEqual(expected_initial_dict, status_dict)
        self.assertFalse(self.exchange.ready)
