import asyncio
import functools
from decimal import Decimal
from typing import Awaitable, Callable, Optional
from unittest import TestCase
from unittest.mock import AsyncMock

from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_exchange import CoinbaseProExchange
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent, OrderType, TradeType


class BitfinexExchangeTests(TestCase):
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

        self.exchange = CoinbaseProExchange(
            coinbase_pro_api_key="testAPIKey",
            coinbase_pro_secret_key="testSecret",
            coinbase_pro_passphrase="testPassphrase",
            trading_pairs=[self.trading_pair]
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
        order.update_exchange_order_id("EOID1")

        partial_fill = {
            "type": "match",
            "trade_id": 1,
            "sequence": 50,
            "maker_order_id": "EOID1",
            "taker_order_id": "132fb6ae-456b-4654-b4e0-d681ac05cea1",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": "BTC-USDT",
            "size": "0.1",
            "price": "10050.0",
            "side": "buy",
            "taker_user_id": "5844eceecf7e803e259d0365",
            "user_id": "5844eceecf7e803e259d0365",
            "taker_profile_id": "765d1549-9660-4be2-97d4-fa2d65fa3352",
            "profile_id": "765d1549-9660-4be2-97d4-fa2d65fa3352",
            "taker_fee_rate": "0.005"
        }

        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: partial_fill)

        self.exchange.user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        expected_executed_quote_amount = Decimal(str(partial_fill["size"])) * Decimal(str(partial_fill["price"]))
        expected_partial_event_fee = (Decimal(partial_fill["taker_fee_rate"]) *
                                      expected_executed_quote_amount)

        self.assertEqual(expected_partial_event_fee, order.fee_paid)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0.005"), fill_event.trade_fee.percent)
        self.assertEqual([], fill_event.trade_fee.flat_fees)
        self.assertTrue(self._is_logged(
            "INFO",
            f"Filled {Decimal(partial_fill['size'])} out of {order.amount} of the "
            f"{order.order_type_description} order {order.client_order_id}"
        ))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

        complete_fill = {
            "type": "match",
            "trade_id": 2,
            "sequence": 50,
            "maker_order_id": "EOID1",
            "taker_order_id": "132fb6ae-456b-4654-b4e0-d681ac05cea1",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": "BTC-USDT",
            "size": "0.9",
            "price": "10050.0",
            "side": "buy",
            "taker_user_id": "5844eceecf7e803e259d0365",
            "user_id": "5844eceecf7e803e259d0365",
            "taker_profile_id": "765d1549-9660-4be2-97d4-fa2d65fa3352",
            "profile_id": "765d1549-9660-4be2-97d4-fa2d65fa3352",
            "taker_fee_rate": "0.001"
        }

        self.resume_test_event = asyncio.Event()
        mock_user_stream = AsyncMock()
        mock_user_stream.get.side_effect = functools.partial(self._return_calculation_and_set_done_event,
                                                             lambda: complete_fill)

        self.exchange.user_stream_tracker._user_stream = mock_user_stream

        self.test_task = asyncio.get_event_loop().create_task(self.exchange._user_stream_event_listener())
        self.async_run_with_timeout(self.resume_test_event.wait())

        expected_executed_quote_amount = Decimal(str(complete_fill["size"])) * Decimal(str(complete_fill["price"]))
        expected_partial_event_fee += Decimal(complete_fill["taker_fee_rate"]) * expected_executed_quote_amount

        self.assertEqual(expected_partial_event_fee, order.fee_paid)

        self.assertEqual(2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(Decimal("0.001"), fill_event.trade_fee.percent)
        self.assertEqual([], fill_event.trade_fee.flat_fees)

        # The order should be marked as complete only when the "done" event arrives, not with the fill event
        self.assertFalse(self._is_logged(
            "INFO",
            f"The market buy order {order.client_order_id} has completed according to Coinbase Pro user stream."
        ))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
