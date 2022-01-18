import asyncio
import json
import re
import unittest

from decimal import Decimal
from typing import Awaitable, Optional, List
from unittest.mock import MagicMock

from aioresponses import aioresponses

from hummingbot.connector.exchange.ascend_ex import ascend_ex_constants as CONSTANTS, ascend_ex_utils
from hummingbot.connector.exchange.ascend_ex.ascend_ex_exchange import (
    AscendExExchange,
    AscendExTradingRule,
    AscendExCommissionType,
)
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import OrderType, TradeType, MarketEvent, MarketOrderFailureEvent
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


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

        self.exchange = AscendExExchange(self.api_key, self.api_secret_key, trading_pairs=[self.trading_pair])
        self.mocking_assistant = NetworkMockingAssistant()
        self._initialize_event_loggers()

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._in_flight_order_tracker.logger().setLevel(1)
        self.exchange._in_flight_order_tracker.logger().addHandler(self)

    def tearDown(self) -> None:
        self.exchange._shared_client and self.exchange._shared_client.close()
        self.async_task and self.async_task.cancel()
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

    def simulate_trading_rules_initialized(self):
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

    def test_get_fee(self):
        self.simulate_trading_rules_initialized()
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
