from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
import unittest
import unittest.mock
import asyncio
import os
from decimal import Decimal
from typing import List
import contextlib
import time
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.connector.derivative.perpetual_finance.perpetual_finance_derivative import PerpetualFinanceDerivative
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketEvent,
    OrderType,
    SellOrderCompletedEvent,
    MarketOrderFailureEvent,
    PositionAction, PositionMode
)
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.client.config.global_config_map import global_config_map

global_config_map['gateway_api_host'].value = "localhost"
global_config_map['gateway_api_port'].value = 5000
global_config_map.get("ethereum_chain_name").value = "mainnet"

trading_pair = "SNX-USDC"
leverage = 3
base, quote = trading_pair.split("-")


class PerpetualFinanceDerivativeUnitTest(unittest.TestCase):
    event_logger: EventLogger
    events: List[MarketEvent] = [
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderFailure,
        MarketEvent.FundingPaymentCompleted
    ]
    connector: PerpetualFinanceDerivative
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.connector: PerpetualFinanceDerivative = PerpetualFinanceDerivative(
            [trading_pair],
            "PRIVATE_KEY_HERE",
            "")
        print("Initializing PerpetualFinanceDerivative market... this will take about a minute.")
        cls.connector.set_leverage(trading_pair, leverage)
        cls.connector.set_position_mode(PositionMode.ONEWAY)
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
        self.assertIn(quote, all_bals)
        self.assertTrue(all_bals["XDAI"] > 0)

    def test_allowances(self):
        asyncio.get_event_loop().run_until_complete(self._test_allowances())

    async def _test_allowances(self):
        perfi = self.connector
        allowances = await perfi.get_allowances()
        print(allowances)

    def test_approve(self):
        asyncio.get_event_loop().run_until_complete(self._test_approve())

    async def _test_approve(self):
        perfi = self.connector
        ret_val = await perfi.approve_perpetual_finance_spender()
        print(ret_val)

    def test_get_quote_price(self):
        asyncio.get_event_loop().run_until_complete(self._test_get_quote_price())

    async def _test_get_quote_price(self):
        perfi = self.connector
        buy_price = await perfi.get_quote_price(trading_pair, True, Decimal("1"))
        self.assertTrue(buy_price > 0)
        print(f"buy_price: {buy_price}")
        sell_price = await perfi.get_quote_price(trading_pair, False, Decimal("1"))
        self.assertTrue(sell_price > 0)
        print(f"sell_price: {sell_price}")
        self.assertTrue(buy_price != sell_price)

    def test_open_and_close_long_position(self):
        perfi = self.connector
        amount = Decimal("0.1")
        price = Decimal("10")
        order_id = perfi.buy(trading_pair, amount, OrderType.LIMIT, price, position_action=PositionAction.OPEN)
        event = self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCompletedEvent))
        self.assertTrue(event.order_id is not None)
        self.assertEqual(order_id, event.order_id)
        self.assertEqual(event.base_asset_amount, amount)
        print(event.order_id)

        order_id = perfi.sell(trading_pair, amount, OrderType.LIMIT, price, position_action=PositionAction.CLOSE)
        event = self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCompletedEvent))
        self.assertTrue(event.order_id is not None)
        self.assertEqual(order_id, event.order_id)
        self.assertEqual(event.base_asset_amount, amount)
        print(event.order_id)

    def test_open_position_failure(self):
        perfi = self.connector
        # Since we don't have 1000000 xUSDC, this should trigger order failure
        amount = Decimal("1000000")
        price = Decimal("10")
        order_id = perfi.sell(trading_pair, amount, OrderType.LIMIT, price, position_action=PositionAction.OPEN)
        event = self.ev_loop.run_until_complete(self.event_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, event.order_id)

    def test_filled_orders_recorded(self):
        config_path = "test_config"
        strategy_name = "test_strategy"
        sql = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        recorder = MarketsRecorder(sql, [self.connector], config_path, strategy_name)
        recorder.start()
        try:
            self.connector._in_flight_orders.clear()
            self.assertEqual(0, len(self.connector.tracking_states))

            price: Decimal = Decimal("10")  # quote_price * Decimal("0.8")
            price = self.connector.quantize_order_price(trading_pair, price)

            amount: Decimal = Decimal("0.1")
            amount = self.connector.quantize_order_amount(trading_pair, amount)

            sell_order_id = self.connector.sell(trading_pair, amount, OrderType.LIMIT, price, position_action=PositionAction.OPEN)
            self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCompletedEvent))
            self.ev_loop.run_until_complete(asyncio.sleep(1))

            price: Decimal = Decimal("10")  # quote_price * Decimal("0.8")
            price = self.connector.quantize_order_price(trading_pair, price)

            buy_order_id = self.connector.buy(trading_pair, amount, OrderType.LIMIT, price, position_action=PositionAction.CLOSE)
            self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCompletedEvent))
            self.ev_loop.run_until_complete(asyncio.sleep(1))

            # Query the persisted trade logs
            trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
            # self.assertGreaterEqual(len(trade_fills), 2)
            fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "SELL"]
            self.assertGreaterEqual(len(fills), 1)
            self.assertEqual(amount, Decimal(str(fills[0].amount)))
            # self.assertEqual(price, Decimal(str(fills[0].price)))
            self.assertEqual(base, fills[0].base_asset)
            self.assertEqual(quote, fills[0].quote_asset)
            self.assertEqual(sell_order_id, fills[0].order_id)
            self.assertEqual(trading_pair, fills[0].symbol)
            fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
            self.assertGreaterEqual(len(fills), 1)
            self.assertEqual(amount, Decimal(str(fills[0].amount)))
            # self.assertEqual(price, Decimal(str(fills[0].price)))
            self.assertEqual(base, fills[0].base_asset)
            self.assertEqual(quote, fills[0].quote_asset)
            self.assertEqual(buy_order_id, fills[0].order_id)
            self.assertEqual(trading_pair, fills[0].symbol)

        finally:
            recorder.stop()
            os.unlink(self.db_path)
