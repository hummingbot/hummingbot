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
from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS, ascend_ex_utils
from hummingbot.connector.exchange.ascend_ex.ascend_ex_api_order_book_data_source import AscendExAPIOrderBookDataSource
from hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange import (
    AscendExCommissionType,
    AscendExExchange,
    AscendExOrder,
    AscendExTradingRule,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import BuyOrderCompletedEvent, MarketEvent, MarketOrderFailureEvent, OrderFilledEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class TestAscendExExchange(unittest.TestCase):
    # logging.Level required to receive logs from the exchange
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}/{cls.quote_asset}"
        cls.api_key = "someKey"
        cls.api_secret_key = "someSecretKey"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.async_task: Optional[asyncio.Task] = None
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

        self.exchange = AscendExExchange(
            client_config_map=self.client_config_map,
            ascend_ex_api_key=self.api_key,
            ascend_ex_secret_key=self.api_secret_key,
            trading_pairs=[self.trading_pair])
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()
        self._initialize_event_loggers()

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._in_flight_order_tracker.logger().setLevel(1)
        self.exchange._in_flight_order_tracker.logger().addHandler(self)

        AscendExAPIOrderBookDataSource._trading_pair_symbol_map = bidict(
            {self.ex_trading_pair: f"{self.base_asset}-{self.quote_asset}"}
        )

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
        AscendExAPIOrderBookDataSource._trading_pair_symbol_map = None
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
            self.trading_pair: AscendExTradingRule(
                trading_pair=self.trading_pair,
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
                min_notional_size=Decimal("0.001"),
                max_notional_size=Decimal("99999999"),
                commission_type=AscendExCommissionType.QUOTE,
                commission_reserve_rate=Decimal("0.002"),
            ),
        }
        self.exchange._trading_rules[self.trading_pair].min_order_size = Decimal(str(0.01))

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    async def _iter_user_event_queue_task(self):
        async for event_message in self.exchange._iter_user_event_queue():
            pass

    def test_get_fee(self):
        self._simulate_trading_rules_initialized()
        trading_rule: AscendExTradingRule = self.exchange._trading_rules[self.trading_pair]
        amount = Decimal("1")
        price = Decimal("2")
        trading_rule.commission_reserve_rate = Decimal("0.002")

        trading_rule.commission_type = AscendExCommissionType.QUOTE
        buy_fee = self.exchange.get_fee(
            self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY, amount, price
        )
        sell_fee = self.exchange.get_fee(
            self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.SELL, amount, price
        )

        self.assertEqual(Decimal("0.002"), buy_fee.percent)
        self.assertEqual(Decimal("0"), sell_fee.percent)

        trading_rule.commission_type = AscendExCommissionType.BASE
        buy_fee = self.exchange.get_fee(
            self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY, amount, price
        )
        sell_fee = self.exchange.get_fee(
            self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.SELL, amount, price
        )

        self.assertEqual(Decimal("0"), buy_fee.percent)
        self.assertEqual(Decimal("0.002"), sell_fee.percent)

        trading_rule.commission_type = AscendExCommissionType.RECEIVED
        buy_fee = self.exchange.get_fee(
            self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY, amount, price
        )
        sell_fee = self.exchange.get_fee(
            self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.SELL, amount, price
        )

        self.assertEqual(Decimal("0"), buy_fee.percent)
        self.assertEqual(Decimal("0"), sell_fee.percent)

    @aioresponses()
    def test_cancel_all_does_not_cancel_orders_without_exchange_id(self, mock_api):
        self.exchange._account_group = 0

        url = f"{ascend_ex_utils.get_rest_url_private(0)}/{CONSTANTS.ORDER_BATCH_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "code": 0,
            "data": {
                "ac": "CASH",
                "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
                "action": "batch-cancel-order",
                "status": "Ack",
                "info": [
                    {
                        "id": "0a8bXHbAwwoqDo3b485d7ea0b09c2cd8",
                        "orderId": "16e61d5ff43s8bXHbAwwoqDo9d817339",
                        "orderType": "NULL_VAL",
                        "symbol": f"{self.base_asset}/{self.quote_asset}",
                        "timestamp": 1573619097746
                    },
                ]
            }
        }

        mock_api.delete(regex_url, body=json.dumps(mock_response))

        self.exchange.start_tracking_order(
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            exchange_order_id="16e61d5ff43s8bXHbAwwoqDo9d817339"
        )
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
            amount=Decimal("2"),
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
            exchange_order_id="16e61d5ff43s8bXHbAwwoqDo9d817339"
        )

        # Check before
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual(self.exchange.in_flight_orders["testOrderId1"].current_state, OrderState.PENDING_CREATE)

        self.exchange._account_group = 0

        url = f"{ascend_ex_utils.get_rest_url_private(0)}/{CONSTANTS.ORDER_STATUS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        status_update = {
            "code": 0,
            "accountCategory": "CASH",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "data": [{
                "symbol": self.ex_trading_pair,
                "price": "20000",
                "orderQty": "2",
                "orderType": "Limit",
                "avgPx": "",
                "cumFee": "0",
                "cumFilledQty": "0",
                "errorCode": "",
                "feeAsset": self.quote_asset,
                "lastExecTime": 1640780000,
                "orderId": "16e61d5ff43s8bXHbAwwoqDo9d817339",
                "seqNum": 2622058,
                "side": "Buy",
                "status": "New",
                "stopPrice": "",
                "execInst": "NULL_VAL"
            }]
        }

        mock_response = status_update
        mock_api.get(regex_url, body=json.dumps(mock_response))

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

        url = f"{ascend_ex_utils.get_rest_url_private(0)}/{CONSTANTS.ORDER_STATUS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        status_update = {
            "code": 0,
            "accountCategory": "CASH",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "data": [{
                "symbol": self.ex_trading_pair,
                "price": "20000",
                "orderQty": "2",
                "orderType": "Limit",
                "avgPx": "",
                "cumFee": "0",
                "cumFilledQty": "0",
                "errorCode": "",
                "feeAsset": self.quote_asset,
                "lastExecTime": 1640780000,
                "orderId": "16e61d5ff43s8bXHbAwwoqDo9d817339",
                "seqNum": 2622058,
                "side": "Buy",
                "status": "New",
                "stopPrice": "",
                "execInst": "NULL_VAL"
            }]
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
            order_type=OrderType.LIMIT,
            exchange_order_id="16e61d5ff43s8bXHbAwwoqDo9d817339"
        )

        # Check before
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual(self.exchange.in_flight_orders["testOrderId1"].current_state, OrderState.PENDING_CREATE)

        self.exchange._account_group = 0

        url = f"{ascend_ex_utils.get_rest_url_private(0)}/{CONSTANTS.ORDER_STATUS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps({}), status=401)

        with self.assertRaises(IOError):
            self.async_run_with_timeout(self.exchange._update_order_status())

        # Check after
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual(self.exchange.in_flight_orders["testOrderId1"].current_state, OrderState.PENDING_CREATE)

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "There was an error requesting updates for the active orders ({'16e61d5ff43s8bXHbAwwoqDo9d817339': 'testOrderId1'})"
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
            exchange_order_id="16e61d5ff43s8bXHbAwwoqDo9d817339"
        )

        # Check before
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual(self.exchange.in_flight_orders["testOrderId1"].current_state, OrderState.PENDING_CREATE)

        self.exchange._account_group = 0

        url = f"{ascend_ex_utils.get_rest_url_private(0)}/{CONSTANTS.ORDER_STATUS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        status_update = {
            "code": 0,
            "accountCategory": "CASH",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "data": [{
                "symbol": self.ex_trading_pair,
                "price": "20000",
                "orderQty": "2",
                "orderType": "Limit",
                "avgPx": "",
                "cumFee": "0",
                "cumFilledQty": "0",
                "errorCode": "",
                "feeAsset": self.quote_asset,
                "lastExecTime": 1640780000,
                "orderId": "16e61d5ff43s8bXHbAwwoqDo9d817339",
                "seqNum": 2622058,
                "side": "Buy",
                "status": "New",
                "stopPrice": "",
                "execInst": "NULL_VAL"
            }]
        }

        mock_response = status_update
        mock_api.get(regex_url, body=json.dumps(mock_response))

        mock_process_order.side_effect = Exception()

        # No exception is passed. If yes -> test failure
        self.async_run_with_timeout(self.exchange._update_order_status())

        # Check after
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual(self.exchange.in_flight_orders["testOrderId1"].current_state, OrderState.PENDING_CREATE)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Unexpected error during processing order status. The Ascend Ex Response: {json.dumps(status_update)}".replace("\"", "'")
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

    def test_partial_fill_and_full_fill_generate_fill_events(self):
        AscendExAPIOrderBookDataSource._trading_pair_symbol_map = bidict(
            {self.ex_trading_pair: f"{self.base_asset}-{self.quote_asset}"}
        )

        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="OID1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("20000"),
            amount=Decimal("2"),
            order_type=OrderType.LIMIT,
            exchange_order_id="EOID1"
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            "m": "order",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "ac": "CASH",
            "data": {
                "s": f"{self.base_asset}/{self.quote_asset}",
                "sn": 8159711,
                "sd": "Buy",
                "ap": "20050",
                "bab": "2006.5974027",
                "btb": "2006.5974027",
                "cf": "5",
                "cfq": "1",
                "err": "",
                "fa": self.quote_asset,
                "orderId": "EOID1",
                "ot": "Market",
                "p": "20000",
                "q": "2",
                "qab": "793.23",
                "qtb": "860.23",
                "sp": "",
                "st": "PartiallyFilled",
                "t": 1576019215402,
                "ei": "NULL_VAL"
            }
        }

        total_fill = {
            "m": "order",
            "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
            "ac": "CASH",
            "data": {
                "s": f"{self.base_asset}/{self.quote_asset}",
                "sn": 8159712,
                "sd": "Buy",
                "ap": "20050",
                "bab": "2006.5974027",
                "btb": "2006.5974027",
                "cf": "15",
                "cfq": "2",
                "err": "",
                "fa": self.quote_asset,
                "orderId": "EOID1",
                "ot": "Market",
                "p": "20000",
                "q": "2",
                "qab": "793.23",
                "qtb": "860.23",
                "sp": "",
                "st": "Filled",
                "t": 1576019215412,
                "ei": "NULL_VAL"
            }
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = [partial_fill, total_fill, asyncio.CancelledError()]

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        self.test_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())

        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            # Ignore cancellation errors, it is the expected signal to cut the background loop
            pass

        self.assertEqual(2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(partial_fill["data"]["ap"]), fill_event.price)
        self.assertEqual(Decimal(1), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(partial_fill["data"]["fa"], Decimal("5"))],
                         fill_event.trade_fee.flat_fees)

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(Decimal(total_fill["data"]["ap"]), fill_event.price)
        self.assertEqual(Decimal(1), fill_event.amount)
        self.assertEqual(0.0, fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(total_fill["data"]["fa"], Decimal("10"))],
                         fill_event.trade_fee.flat_fees)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        self.assertEqual(order.amount * Decimal(total_fill["data"]["ap"]), buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    def test_balance_update_events(self):
        self.exchange._account_available_balances[self.base_asset] = Decimal(0)
        self.exchange._account_balances[self.base_asset] = Decimal(99)

        AscendExAPIOrderBookDataSource._trading_pair_symbol_map = bidict(
            {self.ex_trading_pair: f"{self.base_asset}-{self.quote_asset}"}
        )

        balance_update = {
            "m": "balance",
            "data": {
                "a": self.base_asset,
                "sn": 8159798,
                "tb": Decimal(100),
                "ab": Decimal(10)
            }
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = [balance_update, asyncio.CancelledError()]

        self.exchange._user_stream_tracker._user_stream = mock_user_stream

        # Check before
        self.assertEqual(Decimal(0), self.exchange._account_available_balances[self.base_asset])
        self.assertEqual(Decimal(99), self.exchange._account_balances[self.base_asset])

        self.test_task = self.ev_loop.create_task(self.exchange._user_stream_event_listener())

        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            # Ignore cancellation errors, it is the expected signal to cut the background loop
            pass

        # Check after
        self.assertEqual(Decimal(10), self.exchange._account_available_balances[self.base_asset])
        self.assertEqual(Decimal(100), self.exchange._account_balances[self.base_asset])

    @aioresponses()
    def test_update_balances(self, mock_api):
        self.exchange._account_available_balances[self.base_asset] = Decimal(0)
        self.exchange._account_balances[self.base_asset] = Decimal(99)

        self.exchange._account_group = 0

        AscendExAPIOrderBookDataSource._trading_pair_symbol_map = bidict(
            {self.ex_trading_pair: f"{self.base_asset}-{self.quote_asset}"}
        )

        url = f"{ascend_ex_utils.get_rest_url_private(0)}/{CONSTANTS.BALANCE_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        balance_update = {
            "code": 0,
            "data": [{
                "asset": self.base_asset,
                "totalBalance": "100",
                "availableBalance": "10"
            }]
        }

        mock_response = balance_update
        mock_api.get(regex_url, body=json.dumps(mock_response))

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
        self.assertEqual(Decimal(10), self.exchange._account_available_balances[self.base_asset])
        self.assertEqual(Decimal(100), self.exchange._account_balances[self.base_asset])

    @patch("hummingbot.connector.utils.get_tracking_nonce")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 6

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True, trading_pair=self.trading_pair, hbot_order_id_prefix=ascend_ex_utils.HBOT_BROKER_ID
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=False, trading_pair=self.trading_pair, hbot_order_id_prefix=ascend_ex_utils.HBOT_BROKER_ID
        )

        self.assertEqual(result, expected_client_order_id)

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.PRODUCTS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        products = {
            "code": 0,
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "displayName": self.ex_trading_pair,
                    "domain": "USDS",
                    "tradingStartTime": 1546300800000,
                    "collapseDecimals": "1,0.1,0.01",
                    "minQty": "0",
                    "maxQty": "1000000000",
                    "minNotional": "0.001",
                    "maxNotional": "400000",
                    "statusCode": "Normal",
                    "statusMessage": "",
                    "tickSize": "0.0001",
                    "useTick": False,
                    "lotSize": "0.000001",
                    "useLot": False,
                    "commissionType": "Quote",
                    "commissionReserveRate": "0.001",
                    "qtyScale": 5,
                    "priceScale": 2,
                    "notionalScale": 4
                },
            ]
        }

        mock_response = products
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_trading_rules())

        trading_rule = self.exchange._trading_rules[self.trading_pair]
        self.assertEqual(self.trading_pair, trading_rule.trading_pair)
        self.assertEqual(Decimal(products["data"][0]["minQty"]),
                         trading_rule.min_order_size)
        self.assertEqual(Decimal(products["data"][0]["tickSize"]),
                         trading_rule.min_price_increment)
        self.assertEqual(Decimal(products["data"][0]["lotSize"]),
                         trading_rule.min_base_amount_increment)
        self.assertEqual(Decimal(products["data"][0]["minNotional"]),
                         trading_rule.min_notional_size)

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.PRODUCTS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        products = {
            "code": 0,
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "displayName": self.ex_trading_pair,
                    "domain": "USDS",
                    "tradingStartTime": 1546300800000,
                    "collapseDecimals": "1,0.1,0.01",
                    "minQty": "0",
                    "maxQty": "1000000000",
                    "minNotional": "0.001",
                    "maxNotional": "400000",
                    "statusCode": "Normal",
                    "statusMessage": "",
                    # "tickSize": "0.0001",
                    "useTick": False,
                    "lotSize": "0.000001",
                    "useLot": False,
                    "commissionType": "Quote",
                    "commissionReserveRate": "0.001",
                    "qtyScale": 5,
                    "priceScale": 2,
                    "notionalScale": 4
                },
            ]
        }

        mock_response = products
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_trading_rules())

        self.assertEqual(0, len(self.exchange._trading_rules))
        self.assertTrue(
            self._is_logged("ERROR", f"Error parsing the trading pair rule {products['data'][0]}. Skipping.")
        )

    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange.AscendExExchange._sleep")
    @aioresponses()
    def test_trading_rules_polling_loop(self, sleep_mock, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.PRODUCTS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        products = {
            "code": 0,
            "data": [
                {
                    "symbol": self.ex_trading_pair,
                    "displayName": self.ex_trading_pair,
                    "domain": "USDS",
                    "tradingStartTime": 1546300800000,
                    "collapseDecimals": "1,0.1,0.01",
                    "minQty": "0",
                    "maxQty": "1000000000",
                    "minNotional": "0.001",
                    "maxNotional": "400000",
                    "statusCode": "Normal",
                    "statusMessage": "",
                    "tickSize": "0.0001",
                    "useTick": False,
                    "lotSize": "0.000001",
                    "useLot": False,
                    "commissionType": "Quote",
                    "commissionReserveRate": "0.001",
                    "qtyScale": 5,
                    "priceScale": 2,
                    "notionalScale": 4
                },
            ]
        }

        mock_response = products
        mock_api.get(regex_url, body=json.dumps(mock_response))

        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        try:
            self.async_run_with_timeout(self.exchange._trading_rules_polling_loop())
        except asyncio.exceptions.CancelledError:
            pass

        trading_rule = self.exchange._trading_rules[self.trading_pair]
        self.assertEqual(self.trading_pair, trading_rule.trading_pair)
        self.assertEqual(Decimal(products["data"][0]["minQty"]),
                         trading_rule.min_order_size)
        self.assertEqual(Decimal(products["data"][0]["tickSize"]),
                         trading_rule.min_price_increment)
        self.assertEqual(Decimal(products["data"][0]["lotSize"]),
                         trading_rule.min_base_amount_increment)
        self.assertEqual(Decimal(products["data"][0]["minNotional"]),
                         trading_rule.min_notional_size)

    @aioresponses()
    def test_api_request_public(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.PRODUCTS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {"code": 0, "data": "test"}
        mock_api.get(regex_url, body=json.dumps(mock_response))

        response = self.async_run_with_timeout(self.exchange._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.PRODUCTS_PATH_URL,
            data=None,
            params=None,
            is_auth_required=False))

        self.assertEqual(response, mock_response)

    @aioresponses()
    def test_api_request_private(self, mock_api):
        url = f"{ascend_ex_utils.get_rest_url_private(0)}/{CONSTANTS.ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {"code": 0, "data": "test"}
        mock_api.post(regex_url, body=json.dumps(mock_response))

        self.exchange._account_group = 0

        response = self.async_run_with_timeout(self.exchange._api_request(
            method=RESTMethod.POST,
            path_url=CONSTANTS.ORDER_PATH_URL,
            data=None,
            is_auth_required=True,
            force_auth_path_url="order"))

        self.assertEqual(response, mock_response)

    @aioresponses()
    def test_api_request_failed(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.PRODUCTS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {"code": 1, "data": "test"}
        mock_api.get(regex_url, body=json.dumps(mock_response))

        error = None

        try:
            self.async_run_with_timeout(self.exchange._api_request(
                method=RESTMethod.GET,
                path_url=CONSTANTS.PRODUCTS_PATH_URL,
                data=None,
                params=None,
                is_auth_required=False))
        except IOError as e:
            error = str(e)

        self.assertIsNotNone(error)
        self.assertEqual(error, f"{url} API call failed, response: {mock_response}")

    @aioresponses()
    def test_api_request_error_status(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.PRODUCTS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {"code": 0, "data": "test"}
        mock_api.get(regex_url, body=json.dumps(mock_response), status=401)

        error = None

        try:
            self.async_run_with_timeout(self.exchange._api_request(
                method=RESTMethod.GET,
                path_url=CONSTANTS.PRODUCTS_PATH_URL,
                data=None,
                params=None,
                is_auth_required=False))
        except IOError as e:
            error = str(e)

        self.assertIsNotNone(error)
        self.assertEqual(error, f"Error calling {url}. HTTP status is {401}. " f"Message: {json.dumps(mock_response)}")

    @aioresponses()
    def test_api_request_exception_json(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.PRODUCTS_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = "wkjqhqw:{"
        mock_api.get(regex_url, body=mock_response)

        error = None

        try:
            self.async_run_with_timeout(self.exchange._api_request(
                method=RESTMethod.GET,
                path_url=CONSTANTS.PRODUCTS_PATH_URL,
                data=None,
                params=None,
                is_auth_required=False))
        except IOError as e:
            error = str(e)

        self.assertIsNotNone(error)
        self.assertEqual(error, f"Error calling {url}. Error: Expecting value: line 1 column 1 (char 0)")

    @aioresponses()
    def test_update_account_data(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.INFO_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {"code": 0, "data": {"accountGroup": 0, "userUID": 1}}
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.async_run_with_timeout(self.exchange._update_account_data())

        self.assertEqual(self.exchange._account_group, 0)
        self.assertEqual(self.exchange._account_uid, 1)

    @aioresponses()
    def test_update_account_data_failed(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.INFO_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {"code": 1, "data": {"accountGroup": 0, "userUID": 1}}
        mock_api.get(regex_url, body=json.dumps(mock_response))

        error = None

        try:
            self.async_run_with_timeout(self.exchange._update_account_data())
        except IOError as e:
            error = str(e)

        self.assertIsNotNone(error)
        self.assertEqual(error, f"{url} API call failed, response: {mock_response}")

    @aioresponses()
    def test_update_account_data_error_status(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.INFO_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {"code": 0, "data": "test"}
        mock_api.get(regex_url, body=json.dumps(mock_response), status=401)

        error = None

        try:
            self.async_run_with_timeout(self.exchange._update_account_data())
        except IOError as e:
            error = str(e)

        self.assertIsNotNone(error)
        self.assertEqual(error, f"Error fetching data from {url}. HTTP status is {401}. " f"Message: {mock_response}")

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
            order_type=OrderType.LIMIT,
            exchange_order_id="16e61d5ff43s8bXHbAwwoqDo9d817339"
        )

        # Verify that the order is being tracked
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        # Update the order
        self.ev_loop.run_until_complete(
            self.exchange._process_order_message(AscendExOrder(
                self.ex_trading_pair,
                Decimal("10000"),
                Decimal("1"),
                OrderType.LIMIT,
                Decimal("1"),
                Decimal("0"),
                Decimal("6000"),
                0,
                self.base_asset,
                1640780001,
                "16e61d5ff43s8bXHbAwwoqDo9d817339",
                0,
                TradeType.BUY,
                "PartiallyFilled",
                0,
                0
            ))
        )

        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertTrue(self.exchange.in_flight_orders["testOrderId1"].executed_amount_base, Decimal("6000"))

    @aioresponses()
    def test_check_network_successful(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.TICKER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps({"code": 0}))

        status = self.async_run_with_timeout(self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, status)

    @aioresponses()
    def test_check_network_unsuccessful(self, mock_api):
        url = f"{CONSTANTS.REST_URL}/{CONSTANTS.TICKER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=404)

        status = self.async_run_with_timeout(self.exchange.check_network())

        self.assertEqual(NetworkStatus.NOT_CONNECTED, status)

    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange.AscendExExchange.get_price")
    def test_quantize_order_amount(self, mock_price):
        self._simulate_trading_rules_initialized()

        mock_price.return_value = Decimal(1)

        amount = self.exchange.quantize_order_amount(self.trading_pair, Decimal(10))
        self.assertEqual(amount, Decimal(10))

    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange.AscendExExchange.get_price")
    def test_quantize_order_amount_insufficient(self, mock_price):
        self._simulate_trading_rules_initialized()

        mock_price.return_value = Decimal(1)

        amount = self.exchange.quantize_order_amount(self.trading_pair, Decimal(0.00001))
        self.assertEqual(amount, Decimal(0))

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

    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange.AscendExExchange.get_price")
    @aioresponses()
    def test_create_order_ack(self, mock_price, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._account_group = 0

        url = f"{ascend_ex_utils.get_rest_url_private(0)}/{CONSTANTS.ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "code": 0,
            "data": {
                "ac": "CASH",
                "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
                "action": "place-order",
                "info": {
                    "id": "16e607e2b83a8bXHbAwwoqDo55c166fa",
                    "orderId": "16e85b4d9b9a8bXHbAwwoqDoc3d66830",
                    "orderType": "Limit",
                    "symbol": self.ex_trading_pair,
                    "timestamp": 1573576916201
                },
                "status": "Ack"
            }
        }

        mock_api.post(regex_url, body=json.dumps(mock_response))

        mock_price.return_value = Decimal(1)

        self.async_run_with_timeout(self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            amount=Decimal(1000),
            order_type=OrderType.LIMIT,
            price=Decimal(99),
        ))

        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertIsNone(self.exchange.in_flight_orders["testOrderId1"].exchange_order_id)

    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange.AscendExExchange.get_price")
    @aioresponses()
    def test_create_order_accept(self, mock_price, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._account_group = 0

        url = f"{ascend_ex_utils.get_rest_url_private(0)}/{CONSTANTS.ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "code": 0,
            "data": {
                "ac": "CASH",
                "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
                "action": "place-order",
                "info": {
                    "avgPx": "0",
                    "cumFee": "0",
                    "cumFilledQty": "0",
                    "errorCode": "",
                    "feeAsset": self.quote_asset,
                    "lastExecTime": 1575573998500,
                    "orderId": "a16ed787462fU9490877774N4KBHIVN0",
                    "orderQty": "1000",
                    "orderType": "Limit",
                    "price": "99",
                    "seqNum": 2323407894,
                    "side": "Buy",
                    "status": "New",
                    "stopPrice": "",
                    "symbol": self.ex_trading_pair,
                    "execInst": "NULL_VAL"
                },
                "status": "ACCEPT"
            }
        }

        mock_api.post(regex_url, body=json.dumps(mock_response))

        mock_price.return_value = Decimal(1)

        self.async_run_with_timeout(self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            amount=Decimal(1000),
            order_type=OrderType.LIMIT,
            price=Decimal(99),
        ))

        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual("a16ed787462fU9490877774N4KBHIVN0", self.exchange.in_flight_orders["testOrderId1"].exchange_order_id)
        self.assertEqual(OrderState.OPEN, self.exchange.in_flight_orders["testOrderId1"].current_state)

    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange.AscendExExchange.get_price")
    @aioresponses()
    def test_create_order_done(self, mock_price, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._account_group = 0

        url = f"{ascend_ex_utils.get_rest_url_private(0)}/{CONSTANTS.ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "code": 0,
            "data": {
                "ac": "CASH",
                "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
                "action": "place-order",
                "info": {
                    "avgPx": "98.7",
                    "cumFee": "0.12",
                    "cumFilledQty": "600",
                    "errorCode": "",
                    "feeAsset": self.quote_asset,
                    "id": "a16ed787462fU9490877774N4KBHIVN0",
                    "lastExecTime": 1575573998500,
                    "orderId": "a16ed787462fU9490877774N4KBHIVN0",
                    "orderQty": "1000",
                    "orderType": "Limit",
                    "price": "99",
                    "seqNum": 2323407894,
                    "side": "Buy",
                    "status": "PartiallyFilled",
                    "stopPrice": "",
                    "symbol": self.ex_trading_pair,
                    "execInst": "NULL_VAL"
                },
                "status": "DONE"
            }
        }

        mock_api.post(regex_url, body=json.dumps(mock_response))

        mock_price.return_value = Decimal(98.7)

        self.async_run_with_timeout(self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            amount=Decimal(1000),
            order_type=OrderType.LIMIT,
            price=Decimal(99),
        ))

        self.assertIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertEqual("a16ed787462fU9490877774N4KBHIVN0", self.exchange.in_flight_orders["testOrderId1"].exchange_order_id)
        self.assertEqual(OrderState.PARTIALLY_FILLED, self.exchange.in_flight_orders["testOrderId1"].current_state)

    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange.AscendExExchange.get_price")
    @aioresponses()
    def test_create_order_err(self, mock_price, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._account_group = 0

        url = f"{ascend_ex_utils.get_rest_url_private(0)}/{CONSTANTS.ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "code": 0,
            "data": {
                "code": 300011,
                "ac": "CASH",
                "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
                "action": "place-order",
                "info": {
                    "id": "JkpnjJRuBtFpW7F7PWDB7uwBEJtUOISZ",
                    "symbol": self.ex_trading_pair
                },
                "message": "Not Enough Account Balance",
                "reason": "INVALID_BALANCE",
                "status": "Err"
            }
        }

        mock_api.post(regex_url, body=json.dumps(mock_response))

        mock_price.return_value = Decimal(98.7)

        self.async_run_with_timeout(self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            amount=Decimal(1000),
            order_type=OrderType.LIMIT,
            price=Decimal(99),
        ))

        # Added and subsequently removed from tracking
        self.assertNotIn("testOrderId1", self.exchange.in_flight_orders)

    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange.AscendExExchange.get_price")
    @aioresponses()
    def test_create_order_api_error(self, mock_price, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._account_group = 0

        url = f"{ascend_ex_utils.get_rest_url_private(0)}/{CONSTANTS.ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body="{}", status=401)

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

    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange.AscendExExchange.get_price")
    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_api_order_book_data_source.AscendExAPIOrderBookDataSource.exchange_symbol_associated_to_pair")
    @aioresponses()
    def test_create_order_exception(self, mock_ex_pair, mock_price, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._account_group = 0

        url = f"{ascend_ex_utils.get_rest_url_private(0)}/{CONSTANTS.ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body="{}", status=401)

        mock_price.return_value = Decimal(98.7)

        mock_ex_pair.side_effect = Exception()

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
                f"Error submitting BUY LIMIT order to AscendEx for "
                f"1000.000000 {self.trading_pair} 99.0000."
            )
        )

    @patch("hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange.AscendExExchange.get_price")
    def test_create_order_amount_zero(self, mock_price):
        self._simulate_trading_rules_initialized()

        mock_price.return_value = Decimal(98.7)

        self.async_run_with_timeout(self.exchange._create_order(
            trade_type=TradeType.BUY,
            order_id="testOrderId1",
            trading_pair=self.trading_pair,
            amount=Decimal(0),
            order_type=OrderType.LIMIT,
            price=Decimal(99),
        ))

        self.assertNotIn("testOrderId1", self.exchange.in_flight_orders)
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Buy order amount 0 is lower than the minimum order size 0.01."
            )
        )

    def test_create_order_unsupported_order(self):
        self._simulate_trading_rules_initialized()

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
            order_type=OrderType.LIMIT,
            exchange_order_id="16e61d5ff43s8bXHbAwwoqDo9d817339"
        )

        # Verify that the order is being tracked
        self.assertIn("testOrderId1", self.exchange.in_flight_orders)

        url = f"{ascend_ex_utils.get_rest_url_private(0)}/{CONSTANTS.ORDER_PATH_URL}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "code": 0,
            "data": {
                "accountId": "cshQtyfq8XLAA9kcf19h8bXHbAwwoqDo",
                "ac": "CASH",
                "action": "cancel-order",
                "status": "Ack",
                "info": {
                    "id": "wv8QGquoeamhssvQBeHOHGQCGlcBjj23",
                    "orderId": "16e61d5ff43s8bXHbAwwoqDo9d817339",
                    "orderType": "",
                    "symbol": self.ex_trading_pair,
                    "timestamp": 1640780001
                }
            }
        }

        mock_api.delete(regex_url, body=json.dumps(mock_response))

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
                "Failed to cancel order testOrderId1: Failed to cancel order - testOrderId1. Order not found."
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
