import asyncio
import functools
from decimal import Decimal
from typing import Awaitable, Callable, Optional
from unittest import TestCase
from unittest.mock import AsyncMock

from hummingbot.connector.exchange.ftx.ftx_exchange import FtxExchange
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketEvent,
    OrderFilledEvent,
    OrderType,
    TradeType,
)


class FtxExchangeTests(TestCase):
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

        self.exchange = FtxExchange(
            ftx_api_key="testAPIKey",
            ftx_secret_key="testSecret",
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

    def test_order_fill_event_takes_fee_from_update_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )

        order = self.exchange.in_flight_orders.get("OID1")

        partial_fill = {
            "fee": 10.0,
            "feeRate": 0.0014,
            "feeCurrency": "HBOT",
            "future": None,
            "id": 7828307,
            "liquidity": "taker",
            "market": "BTC-USDT",
            "orderId": 38065410,
            "tradeId": 1,
            "price": 10050.0,
            "side": "buy",
            "size": 0.1,
            "time": "2019-05-07T16:40:58.358438+00:00",
            "type": "order"
        }

        message = {
            "channel": "fills",
            "type": "update",
            "data": partial_fill,
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
        self.assertEqual([TokenAmount(partial_fill["feeCurrency"], Decimal(partial_fill["fee"]))],
                         fill_event.trade_fee.flat_fees)
        self.assertTrue(self._is_logged(
            "INFO",
            f"Filled {Decimal(partial_fill['size'])} out of {order.amount} of the "
            f"{order.order_type_description} order {order.client_order_id}"
        ))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

        complete_fill = {
            "fee": 30.0,
            "feeRate": 0.0014,
            "feeCurrency": "HBOT",
            "future": None,
            "id": 7828307,
            "liquidity": "taker",
            "market": "BTC-USDT",
            "orderId": 38065410,
            "tradeId": 2,
            "price": 10060.0,
            "side": "buy",
            "size": 0.9,
            "time": "2019-05-07T16:40:58.358438+00:00",
            "type": "order"
        }

        message["data"] = complete_fill

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
        self.assertEqual([TokenAmount(complete_fill["feeCurrency"], Decimal(complete_fill["fee"]))],
                         fill_event.trade_fee.flat_fees)

        # Complete events are not produced by fill notifivations, only by order updates
        self.assertFalse(self._is_logged(
            "INFO",
            f"The market buy order {order.client_order_id} has completed according to user stream."
        ))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

    def test_order_fill_event_processed_before_order_complete_event(self):
        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="38065410",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )

        order = self.exchange.in_flight_orders.get("OID1")

        complete_fill = {
            "fee": 10.0,
            "feeRate": 0.0014,
            "feeCurrency": "HBOT",
            "future": None,
            "id": 7828307,
            "liquidity": "taker",
            "market": "BTC/USDT",
            "orderId": 38065410,
            "tradeId": 1,
            "price": 10050.0,
            "side": "buy",
            "size": 1,
            "time": "2019-05-07T16:40:58.358438+00:00",
            "type": "order"
        }

        fill_message = {
            "channel": "fills",
            "type": "update",
            "data": complete_fill,
        }

        update_data = {
            'id': 103744440814,
            'clientId': 'OID1',
            'market': 'BTC/USDT',
            'type': 'limit',
            'side': 'buy',
            'price': Decimal('10050.0'),
            'size': Decimal('1'),
            'status': 'closed',
            'filledSize': Decimal('1'),
            'remainingSize': Decimal('0.0'),
            'reduceOnly': False,
            'liquidation': False,
            'avgFillPrice': Decimal('10050.0'),
            'postOnly': True,
            'ioc': False,
            'createdAt': '2021-12-10T15:33:57.882329+00:00'
        }

        update_message = {
            "channel": "orders",
            "type": "update",
            "data": update_data,
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
        self.assertEqual([TokenAmount(complete_fill["feeCurrency"], Decimal(complete_fill["fee"]))],
                         fill_event.trade_fee.flat_fees)
        self.assertTrue(self._is_logged(
            "INFO",
            f"Filled {Decimal(complete_fill['size'])} out of {order.amount} of the "
            f"{order.order_type_description} order {order.client_order_id}"
        ))

        self.assertTrue(self._is_logged(
            "INFO",
            f"The market buy order {order.client_order_id} has completed according to user stream."
        ))

        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))
        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(complete_fill["feeCurrency"], buy_event.fee_asset)
        self.assertEqual(Decimal(complete_fill["fee"]), buy_event.fee_amount)
