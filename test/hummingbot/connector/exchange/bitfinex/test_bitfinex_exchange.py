import asyncio
from decimal import Decimal
from typing import Awaitable, Optional
from unittest import TestCase

from hummingbot.connector.exchange.bitfinex.bitfinex_exchange import BitfinexExchange
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, TradeType, OrderType, OrderFilledEvent, BuyOrderCompletedEvent


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

        self.exchange = BitfinexExchange(
            bitfinex_api_key="testAPIKey",
            bitfinex_secret_key="testSecret",
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
        order.update_exchange_order_id("34938060782")

        partial_fill = [
            0,  # CHAN_ID
            "tu",  # TYPE
            [
                1,  # ID
                f"t{self.trading_pair}",  # SYMBOL
                1574963975602,  # MTS_CREATE
                34938060782,  # ORDER_ID
                0.1,  # EXEC_AMOUNT
                10053.57,  # EXEC_PRICE
                "LIMIT",  # ORDER_TYPE
                0,  # ORDER_PRICE
                -1,  # MAKER
                10.0,  # FEE
                "USDT",  # FEE_CURRENCY
                0  # CID
            ]
        ]

        self.exchange._process_trade_event(event_message=partial_fill)

        self.assertEqual(partial_fill[2][10], order.fee_asset)
        self.assertEqual(Decimal(str(partial_fill[2][9])), order.fee_paid)
        self.assertEqual(1, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual(
            [TokenAmount(partial_fill[2][10], Decimal(str(partial_fill[2][9])))], fill_event.trade_fee.flat_fees
        )
        self.assertTrue(self._is_logged(
            "INFO",
            f"Order filled {Decimal(str(partial_fill[2][4]))} out of {order.amount} of the "
            f"{order.order_type_description} order {order.client_order_id}"
        ))

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))

        complete_fill = [
            0,  # CHAN_ID
            "tu",  # TYPE
            [
                2,  # ID
                f"t{self.trading_pair}",  # SYMBOL
                1574963975602,  # MTS_CREATE
                34938060782,  # ORDER_ID
                0.9,  # EXEC_AMOUNT
                10060.0,  # EXEC_PRICE
                "LIMIT",  # ORDER_TYPE
                0,  # ORDER_PRICE
                -1,  # MAKER
                20.0,  # FEE
                "USDT",  # FEE_CURRENCY
                0  # CID
            ]
        ]

        self.exchange._process_trade_event(event_message=complete_fill)

        self.assertEqual(complete_fill[2][10], order.fee_asset)
        self.assertEqual(Decimal(30), order.fee_paid)

        self.assertEqual(2, len(self.order_filled_logger.event_log))
        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[1]
        self.assertEqual(Decimal("0"), fill_event.trade_fee.percent)
        self.assertEqual([TokenAmount(complete_fill[2][10], Decimal(complete_fill[2][9]))],
                         fill_event.trade_fee.flat_fees)

        self.assertTrue(self._is_logged(
            "INFO",
            f"The market {order.trade_type.name.lower()} "
            f"order {order.client_order_id} has completed "
            "according to Bitfinex user stream."
        ))

        self.assertEqual(1, len(self.buy_order_completed_logger.event_log))
        buy_complete_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(Decimal(30), buy_complete_event.fee_amount)
        self.assertEqual(partial_fill[2][10], buy_complete_event.fee_asset)
