from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
import unittest
import asyncio
import os
from decimal import Decimal
from typing import List
import contextlib
import time
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.connector.connector.balancer.balancer_connector import BalancerConnector
from hummingbot.core.event.events import (
    # BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    # OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
    # OrderCancelledEvent
)
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.connector.markets_recorder import MarketsRecorder

trading_pair = "WETH-DAI"
base, quote = trading_pair.split("-")


class BalancerConnectorUnitTest(unittest.TestCase):
    event_logger: EventLogger
    events: List[MarketEvent] = [
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderFailure
    ]
    connector: BalancerConnector
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.connector: BalancerConnector = BalancerConnector()
        print("Initializing CryptoCom market... this will take about a minute.")
        cls.clock.add_iterator(cls.connector)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if cls.connector.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../connector_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass
        self.event_logger = EventLogger()
        for event_tag in self.events:
            self.connector.add_listener(event_tag, self.event_logger)

    def test_update_balances(self):
        all_bals = self.connector.get_all_balances()
        for token, bal in all_bals.items():
            print(f"{token}: {bal}")
        self.assertIn(base, all_bals)
        self.assertTrue(all_bals[base] > 0)
        # asyncio.get_event_loop().run_until_complete(self._test_update_balances())

    def test_get_quote_price(self):
        balancer = self.connector
        buy_price = balancer.get_quote_price(trading_pair, True, Decimal("1"))
        self.assertTrue(buy_price is None)
        sell_price = balancer.get_quote_price(trading_pair, False, Decimal("1"))
        self.assertTrue(sell_price > 0)
        self.assertTrue(buy_price != sell_price)

    def test_buy(self):
        balancer = self.connector
        balancer.buy("WETH-DAI", Decimal("0.1"), OrderType.LIMIT, Decimal("1"))
        order_completed_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCreatedEvent))
        self.assertTrue(order_completed_event.order_id is not None)
        print(order_completed_event.order_id)

    def test_sell(self):
        balancer = self.connector
        balancer.sell("WETH-DAI", Decimal("0.01"), OrderType.LIMIT, Decimal("1"))
        order_completed_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCreatedEvent))
        self.assertTrue(order_completed_event.order_id is not None)
        print(order_completed_event.order_id)

    def test_filled_orders_recorded(self):
        config_path = "test_config"
        strategy_name = "test_strategy"
        sql = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        recorder = MarketsRecorder(sql, [self.connector], config_path, strategy_name)
        recorder.start()
        try:
            self.connector._in_flight_orders.clear()
            self.assertEqual(0, len(self.connector.tracking_states))

            # Try to put limit buy order for 0.02 ETH worth of ZRX, and watch for order creation event.
            # quote_price: Decimal = self.connector.get_quote_price(trading_pair, False, Decimal("1"))
            price: Decimal = Decimal("1")  # quote_price * Decimal("0.8")
            price = self.connector.quantize_order_price(trading_pair, price)

            amount: Decimal = Decimal("0.01")
            amount = self.connector.quantize_order_amount(trading_pair, amount)

            cl_order_id = self.connector.sell(trading_pair, amount, OrderType.LIMIT, price)
            order_created_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCreatedEvent))
            self.assertEqual(cl_order_id, order_created_event.order_id)
            self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCompletedEvent))
            self.ev_loop.run_until_complete(asyncio.sleep(1))

            # Query the persisted trade logs
            trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
            # self.assertGreaterEqual(len(trade_fills), 2)
            # buy_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
            sell_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "SELL"]
            # self.assertGreaterEqual(len(buy_fills), 1)
            self.assertGreaterEqual(len(sell_fills), 1)
        finally:
            recorder.stop()
            os.unlink(self.db_path)
