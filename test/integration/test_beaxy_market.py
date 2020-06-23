import os
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))
import logging
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
import asyncio
import contextlib
import time
import unittest
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
import conf
from decimal import Decimal
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.market.market_base import OrderType
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent, SellOrderCreatedEvent,
    TradeFee,
    TradeType,
    OrderCancelledEvent,
)
from hummingbot.market.beaxy.beaxy_market import BeaxyMarket
from typing import (
    List,
)
from hummingbot.market.beaxy.beaxy_auth import BeaxyAuth

logging.basicConfig(level=METRICS_LOG_LEVEL)
API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
API_KEY = "XXX" if API_MOCK_ENABLED else conf.beaxy_api_key
API_SECRET = "YYY" if API_MOCK_ENABLED else conf.beaxy_api_secret


class BeaxyMarketUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled
    ]
    market: BeaxyMarket
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.beaxy_auth = BeaxyAuth(API_KEY, API_SECRET)
        cls.market: BeaxyMarket = BeaxyMarket(
            API_KEY, API_SECRET,
            trading_pairs=["BXYBTC", "BTCUSDC"]
        )
        print("Initializing Beaxy market... this will take about a minute.")
        cls.ev_loop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.market)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if cls.market.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../beaxy_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)

    def test_balances(self):
        balances = self.market.get_all_balances()
        self.assertGreater(0, len(balances))

    def test_get_fee(self):
        limit_fee: TradeFee = self.market.get_fee("ETH", "USDC", OrderType.LIMIT, TradeType.BUY, 1, 1)
        self.assertGreater(limit_fee.percent, 0)
        self.assertEqual(len(limit_fee.flat_fees), 0)
        market_fee: TradeFee = self.market.get_fee("ETH", "USDC", OrderType.MARKET, TradeType.BUY, 1)
        self.assertGreater(market_fee.percent, 0)
        self.assertEqual(len(market_fee.flat_fees), 0)

    def test_fee_overrides_config(self):
        fee_overrides_config_map["beaxy_taker_fee"].value = None
        taker_fee: TradeFee = self.market.get_fee("BTC", "ETH", OrderType.MARKET, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.25"), taker_fee.percent)
        fee_overrides_config_map["beaxy_taker_fee"].value = Decimal('0.2')
        taker_fee: TradeFee = self.market.get_fee("BTC", "ETH", OrderType.MARKET, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.002"), taker_fee.percent)
        fee_overrides_config_map["beaxy_maker_fee"].value = None
        maker_fee: TradeFee = self.market.get_fee("BTC", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.15"), maker_fee.percent)
        fee_overrides_config_map["beaxy_maker_fee"].value = Decimal('0.75')
        maker_fee: TradeFee = self.market.get_fee("BTC", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.0075"), maker_fee.percent)

    def test_cancel_order(self):
        trading_pair = "BXYBTC"

        current_bid_price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = Decimal("200")
        self.assertGreater(self.market.get_balance("BXY"), amount)

        bid_price: Decimal = current_bid_price
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id = self.market.sell(trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        order_created_event: SellOrderCreatedEvent = order_created_event
        self.market.cancel(trading_pair, order_id)
        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event
        self.assertEqual(order_cancelled_event.order_id, order_id)

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self.clock.run_til(next_iteration)
        return future.result()
