import asyncio
import functools
import json
import re
import unittest

from decimal import Decimal
from typing import Awaitable, Callable, Dict, Optional
from unittest.mock import AsyncMock

from aioresponses import aioresponses

from hummingbot.connector.exchange.bittrex.bittrex_exchange import BittrexExchange
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketEvent,
    OrderFilledEvent,
    OrderType,
    TradeType,
)


class BittrexExchangeTest(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.secret_key = "someSecret"
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()
        self.log_records = []
        self.test_task: Optional[asyncio.Task] = None
        self.resume_test_event = asyncio.Event()

        self.exchange = BittrexExchange(self.api_key, self.secret_key, trading_pairs=[self.trading_pair])

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self._initialize_event_loggers()

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _return_calculation_and_set_done_event(self, calculation: Callable, *args, **kwargs):
        if self.resume_test_event.is_set():
            raise asyncio.CancelledError
        self.resume_test_event.set()
        return calculation(*args, **kwargs)

    def get_filled_response(self) -> Dict:
        filled_resp = {
            "id": "87076200-79bc-4f97-82b1-ad8fa3e630cf",
            "marketSymbol": self.trading_pair,
            "direction": "BUY",
            "type": "LIMIT",
            "quantity": "1",
            "limit": "10",
            "timeInForce": "POST_ONLY_GOOD_TIL_CANCELLED",
            "fillQuantity": "1",
            "commission": "0.11805420",
            "proceeds": "23.61084196",
            "status": "CLOSED",
            "createdAt": "2021-09-08T10:00:34.83Z",
            "updatedAt": "2021-09-08T10:00:35.05Z",
            "closedAt": "2021-09-08T10:00:35.05Z",
        }
        return filled_resp

    @aioresponses()
    def test_execute_cancel(self, mocked_api):
        url = f"{self.exchange.BITTREX_API_ENDPOINT}/orders/"
        regex_url = re.compile(f"^{url}")
        resp = {"status": "CLOSED"}
        mocked_api.delete(regex_url, body=json.dumps(resp))

        order_id = "someId"
        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id="someExchangeId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT_MAKER,
            trade_type=TradeType.BUY,
            price=Decimal("10.0"),
            amount=Decimal("1.0"),
        )

        self.async_run_with_timeout(coroutine=self.exchange.execute_cancel(self.trading_pair, order_id))

        self.assertEqual(1, len(self.order_cancelled_logger.event_log))

        event = self.order_cancelled_logger.event_log[0]

        self.assertEqual(order_id, event.order_id)
        self.assertTrue(order_id not in self.exchange.in_flight_orders)

    @aioresponses()
    def test_execute_cancel_already_filled(self, mocked_api):
        url = f"{self.exchange.BITTREX_API_ENDPOINT}/orders/"
        regex_url = re.compile(f"^{url}")
        del_resp = {"code": "ORDER_NOT_OPEN"}
        mocked_api.delete(regex_url, status=409, body=json.dumps(del_resp))
        get_resp = self.get_filled_response()
        mocked_api.get(regex_url, body=json.dumps(get_resp))

        order_id = "someId"
        self.exchange.start_tracking_order(
            order_id=order_id,
            exchange_order_id="someExchangeId",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT_MAKER,
            trade_type=TradeType.BUY,
            price=Decimal("10.0"),
            amount=Decimal("1.0"),
        )

        self.async_run_with_timeout(coroutine=self.exchange.execute_cancel(self.trading_pair, order_id))

        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))

        event = self.buy_order_completed_logger.event_log[0]

        self.assertEqual(order_id, event.order_id)
        self.assertTrue(order_id not in self.exchange.in_flight_orders)

    def test_order_fill_event_takes_fee_from_update_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            "accountId": "testAccount",
            "sequence": "1001",
            "deltas": [{
                "id": "1",
                "marketSymbol": f"{self.base_asset}{self.quote_asset}",
                "executedAt": "12-03-2021 6:17:16",
                "quantity": "0.1",
                "rate": "10050",
                "orderId": "EOID1",
                "commission": "10",
                "isTaker": False
            }]
        }

        message = {
            "event_type": "execution",
            "content": partial_fill,
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: message)

        self.exchange.user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(Decimal("10"), order.fee_paid)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(order.quote_asset, Decimal(partial_fill["deltas"][0]["commission"]))],
                         fill_event.trade_fee.flat_fees)
        self.assertTrue(self._is_logged(
            "INFO",
            f"Filled {Decimal(partial_fill['deltas'][0]['quantity'])} out of {order.amount} of the "
            f"{order.order_type_description} order {order.client_order_id}. - ws"
        ))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

        complete_fill = {
            "accountId": "testAccount",
            "sequence": "1001",
            "deltas": [{
                "id": "2",
                "marketSymbol": f"{self.base_asset}{self.quote_asset}",
                "executedAt": "12-03-2021 6:17:16",
                "quantity": "0.9",
                "rate": "10060",
                "orderId": "EOID1",
                "commission": "30",
                "isTaker": False
            }]
        }

        message["content"] = complete_fill

        self.resume_test_event = asyncio.Event()
        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: message)

        self.exchange.user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertEqual(Decimal("40"), order.fee_paid)

        self.assertEqual(2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(order.quote_asset, Decimal(complete_fill["deltas"][0]["commission"]))],
                         fill_event.trade_fee.flat_fees)

        # The order should be marked as complete only when the "done" event arrives, not with the fill event
        self.assertFalse(self._is_logged(
            "INFO",
            f"The market buy order {order.client_order_id} has completed according to Coinbase Pro user stream."
        ))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

    def test_order_fill_event_processed_before_order_complete_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )

        order = self.exchange.in_flight_orders.get("OID1")

        complete_fill = {
            "id": "1",
            "marketSymbol": f"{self.base_asset}{self.quote_asset}",
            "executedAt": "12-03-2021 6:17:16",
            "quantity": "1",
            "rate": "10050",
            "orderId": "EOID1",
            "commission": "10",
            "isTaker": False
        }

        fill_message = {
            "event_type": "execution",
            "content": {
                "accountId": "testAccount",
                "sequence": "1001",
                "deltas": [complete_fill]
            }
        }

        update_data = {
            "id": "EOID1",
            "marketSymbol": f"{self.base_asset}{self.quote_asset}",
            "direction": "BUY",
            "type": "LIMIT",
            "quantity": "1",
            "limit": "10000",
            "ceiling": "10000",
            "timeInForce": "GOOD_TIL_CANCELLED",
            "clientOrderId": "OID1",
            "fillQuantity": "1",
            "commission": "10",
            "proceeds": "10050",
            "status": "CLOSED",
            "createdAt": "12-03-2021 6:17:16",
            "updatedAt": "12-03-2021 6:17:16",
            "closedAt": "12-03-2021 6:17:16",
            "orderToCancel": {
                "type": "LIMIT",
                "id": "string (uuid)"
            }
        }

        update_message = {
            "event_type": "order",
            "content": {
                "accountId": "testAccount",
                "sequence": "1001",
                "delta": update_data
            }
        }

        mock_user_stream = AsyncMock()
        # We simulate the case when the order update arrives before the order fill
        mock_user_stream.get.side_effect = [update_message, fill_message, asyncio.CancelledError()]
        self.exchange.user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            pass

        self.async_run_with_timeout(order.wait_until_completely_filled())

        self.assertEqual(Decimal("10"), order.fee_paid)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(
            [TokenAmount(order.quote_asset, Decimal(complete_fill["commission"]))], fill_event.trade_fee.flat_fees
        )
        self.assertTrue(self._is_logged(
            "INFO",
            f"Filled {Decimal(complete_fill['quantity'])} out of {order.amount} of the "
            f"{order.order_type_description} order {order.client_order_id}. - ws"
        ))

        self.assertTrue(self._is_logged(
            "INFO",
            f"The BUY order {order.client_order_id} has completed according to order delta websocket API."
        ))

        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))
        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(order.quote_asset, buy_event.fee_asset)
        self.assertEqual(Decimal(complete_fill["commission"]), buy_event.fee_amount)
