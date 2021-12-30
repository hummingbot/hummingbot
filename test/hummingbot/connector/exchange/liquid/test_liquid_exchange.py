import asyncio
import json
from decimal import Decimal
from typing import Awaitable, Callable, Optional
from unittest import TestCase
from unittest.mock import AsyncMock

from hummingbot.connector.exchange.liquid.liquid_exchange import LiquidExchange
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketEvent,
    OrderFilledEvent,
    OrderType,
    TradeType,
)


class LiquidExchangeTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.symbol = f"{cls.base_asset}{cls.quote_asset}"
        cls.listen_key = "TEST_LISTEN_KEY"

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.test_task: Optional[asyncio.Task] = None
        self.resume_test_event = asyncio.Event()

        self.exchange = LiquidExchange(
            liquid_api_key="testAPIKey",
            liquid_secret_key="testSecret",
            trading_pairs=[self.trading_pair],
        )

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

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _return_calculation_and_set_done_event(self, calculation: Callable, *args, **kwargs):
        if self.resume_test_event.is_set():
            raise asyncio.CancelledError
        self.resume_test_event.set()
        return calculation(*args, **kwargs)

    def _trade_info(self, trade_id, amount, price, fee, status="live"):
        return {
            "average_price": 10000.0,
            "client_order_id": "OID1",
            "created_at": 1639429916,
            "crypto_account_id": None,
            "currency_pair_code": "BTCUSDT",
            "disc_quantity": 0.0,
            "filled_quantity": amount,
            "funding_currency": "USDT",
            "iceberg_total_quantity": 0.0,
            "id": 5821066005,
            "leverage_level": 1,
            "margin_interest": 0.0,
            "margin_type": None,
            "margin_used": 0.0,
            "order_fee": fee,
            "order_type": "limit",
            "price": price,
            "product_code": "CASH",
            "product_id": 761,
            "quantity": 1.0,
            "side": "buy",
            "source_action": "manual",
            "source_exchange": 0,
            "status": status,
            "stop_loss": None,
            "take_profit": None,
            "target": "spot",
            "trade_id": None,
            "trading_type": "spot",
            "unwound_trade_id": None,
            "unwound_trade_leverage_level": None,
            "updated_at": trade_id
        }

    def test_order_fill_event_takes_fee_from_update_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )

        order = self.exchange.in_flight_orders.get("OID1")
        order.update_exchange_order_id("5821066005")

        partial_fill = self._trade_info(1, 0.1, 10050.0, 10.0)

        message = {
            "channel": "user_account_usdt_orders",
            "data": json.dumps(partial_fill),
            "event": "updated",
        }

        mock_user_stream = AsyncMock()
        # We simulate the case when the order update arrives before the order fill
        mock_user_stream.get.side_effect = [message, asyncio.CancelledError()]

        self.exchange.user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10"), order.fee_paid)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(partial_fill["funding_currency"], Decimal(partial_fill["order_fee"]))],
                         fill_event.trade_fee.flat_fees)
        self.assertTrue(self._is_logged(
            "INFO",
            f"Filled {Decimal('0.1')} out of {order.amount} of the "
            f"{order.order_type_description} order {order.client_order_id} according to Liquid user stream."
        ))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

        complete_fill = self._trade_info(2, 1, 10060.0, 30.0)

        message["data"] = json.dumps(complete_fill)

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = [message, asyncio.CancelledError()]

        self.exchange.user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("30"), order.fee_paid)

        self.assertEqual(2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(
            [TokenAmount(complete_fill["funding_currency"],
             Decimal(complete_fill["order_fee"]) - Decimal(partial_fill["order_fee"]))],
            fill_event.trade_fee.flat_fees)

        # Complete events are not produced by fill notifications, only by order updates
        self.assertFalse(self._is_logged(
            "INFO",
            f"The market buy order {order.client_order_id} has completed according to Liquid user stream."
        ))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

    def test_single_complete_fill_is_processed_correctly(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )

        order = self.exchange.in_flight_orders.get("OID1")
        order.update_exchange_order_id("5821066005")

        complete_fill = self._trade_info(2, 1, 10060.0, 30.0)

        message = {
            "channel": "user_account_usdt_orders",
            "data": json.dumps(complete_fill),
            "event": "updated",
        }

        complete_fill = self._trade_info(1, 1, 10060.0, 30.0, "filled")

        message["data"] = json.dumps(complete_fill)

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = [message, asyncio.CancelledError()]

        self.exchange.user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        try:
            self.async_run_with_timeout(self.test_task)
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("30"), order.fee_paid)

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(complete_fill["funding_currency"], Decimal(complete_fill["order_fee"]))],
                         fill_event.trade_fee.flat_fees)

        self.assertTrue(self._is_logged(
            "INFO",
            f"The market buy order {order.client_order_id} has completed according to Liquid user stream."
        ))

        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))

        buy_complete_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(Decimal(30), buy_complete_event.fee_amount)
        self.assertEqual(complete_fill["funding_currency"], buy_complete_event.fee_asset)
