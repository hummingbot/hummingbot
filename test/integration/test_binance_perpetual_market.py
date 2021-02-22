import asyncio
import contextlib
import logging
import unittest
import time
from decimal import Decimal
from typing import List

from hummingbot.core.clock import Clock
from hummingbot.core.clock_mode import ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    OrderType,
    MarketEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    OrderCancelledEvent, BuyOrderCompletedEvent, SellOrderCompletedEvent
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_derivative import BinancePerpetualDerivative
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
import conf

logging.basicConfig(level=METRICS_LOG_LEVEL)


class BinancePerpetualMarketUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderFailure
    ]

    market: BinancePerpetualDerivative
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls) -> None:
        cls._ev_loop = asyncio.get_event_loop()
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: BinancePerpetualDerivative = BinancePerpetualDerivative(
            api_key=conf.binance_perpetual_api_key,
            api_secret=conf.binance_perpetual_api_secret,
            trading_pairs=["ETH-USDT"]
        )
        print("Initializing Binance Perpetual market... this will take about a minute.")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.market)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_till_ready())
        print("Market Ready.")

    @classmethod
    async def wait_till_ready(cls):
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if cls.market.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self) -> None:
        self.market_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)

    def tearDown(self):
        for event_tag in self.events:
            self.market.remove_listener(event_tag, self.market_logger)
        self.market_logger = None

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    @unittest.skip("Too Simple, Unnecessary")
    def test_network_status(self):
        network_status: NetworkStatus = self.ev_loop.run_until_complete(self.market.check_network())
        self.assertEqual(NetworkStatus.CONNECTED, network_status)

    @unittest.skip("")
    def test_buy_and_sell_order_then_cancel_individually(self):
        trading_pair = "ETH-USDT"
        # Create Buy Order
        buy_order_id = self.market.buy(
            trading_pair=trading_pair,
            amount=Decimal(0.01),
            order_type=OrderType.LIMIT,
            price=Decimal(300)
        )
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(buy_order_id, order_created_event.order_id)
        self.assertEqual(trading_pair, order_created_event.trading_pair)
        self.assertEqual(1, len(self.market.in_flight_orders))
        self.assertTrue(buy_order_id in self.market.in_flight_orders)

        # Create Sell Order
        sell_order_id = self.market.sell(
            trading_pair=trading_pair,
            amount=Decimal(0.01),
            order_type=OrderType.LIMIT,
            price=Decimal(500)
        )
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        order_created_event: SellOrderCreatedEvent = order_created_event
        self.assertEqual(sell_order_id, order_created_event.order_id)
        self.assertEqual(trading_pair, order_created_event.trading_pair)
        self.assertEqual(2, len(self.market.in_flight_orders))
        self.assertTrue(sell_order_id in self.market.in_flight_orders)
        self.assertTrue(buy_order_id in self.market.in_flight_orders)

        # Cancel Buy Order
        self.market.cancel(trading_pair, buy_order_id)
        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event
        self.assertEqual(buy_order_id, order_cancelled_event.order_id)
        self.assertEqual(1, len(self.market.in_flight_orders))
        self.assertTrue(sell_order_id in self.market.in_flight_orders)
        self.assertTrue(buy_order_id not in self.market.in_flight_orders)

        # Cancel Sell Order
        self.market.cancel(trading_pair, sell_order_id)
        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event
        self.assertEqual(sell_order_id, order_cancelled_event.order_id)
        self.assertEqual(0, len(self.market.in_flight_orders))
        self.assertTrue(sell_order_id not in self.market.in_flight_orders)
        self.assertTrue(buy_order_id not in self.market.in_flight_orders)

    @unittest.skip("")
    def test_buy_and_sell_order_then_cancel_all(self):
        trading_pair = "ETH-USDT"
        # Create Buy Order
        buy_order_id = self.market.buy(
            trading_pair=trading_pair,
            amount=Decimal(0.01),
            order_type=OrderType.LIMIT,
            price=Decimal(300)
        )
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(buy_order_id, order_created_event.order_id)
        self.assertEqual(trading_pair, order_created_event.trading_pair)
        self.assertEqual(1, len(self.market.in_flight_orders))
        self.assertTrue(buy_order_id in self.market.in_flight_orders)

        # Create Sell Order
        sell_order_id = self.market.sell(
            trading_pair=trading_pair,
            amount=Decimal(0.01),
            order_type=OrderType.LIMIT,
            price=Decimal(500)
        )
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        order_created_event: SellOrderCreatedEvent = order_created_event
        self.assertEqual(sell_order_id, order_created_event.order_id)
        self.assertEqual(trading_pair, order_created_event.trading_pair)
        self.assertEqual(2, len(self.market.in_flight_orders))
        self.assertTrue(sell_order_id in self.market.in_flight_orders)
        self.assertTrue(buy_order_id in self.market.in_flight_orders)

        # Cancel All Orders
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cancel_result in cancellation_results:
            self.assertEqual(cancel_result.success, True)

        self.assertEqual(0, len(self.market.in_flight_orders))
        self.assertTrue(sell_order_id not in self.market.in_flight_orders)
        self.assertTrue(buy_order_id not in self.market.in_flight_orders)

    @unittest.skip("")
    def test_buy_and_sell_order_then_cancel_account_orders(self):
        trading_pair = "ETH-USDT"
        # Create Buy Order
        buy_order_id = self.market.buy(
            trading_pair=trading_pair,
            amount=Decimal(0.01),
            order_type=OrderType.LIMIT,
            price=Decimal(300)
        )
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(buy_order_id, order_created_event.order_id)
        self.assertEqual(trading_pair, order_created_event.trading_pair)
        self.assertEqual(1, len(self.market.in_flight_orders))
        self.assertTrue(buy_order_id in self.market.in_flight_orders)

        # Create Sell Order
        sell_order_id = self.market.sell(
            trading_pair=trading_pair,
            amount=Decimal(0.01),
            order_type=OrderType.LIMIT,
            price=Decimal(500)
        )
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        order_created_event: SellOrderCreatedEvent = order_created_event
        self.assertEqual(sell_order_id, order_created_event.order_id)
        self.assertEqual(trading_pair, order_created_event.trading_pair)
        self.assertEqual(2, len(self.market.in_flight_orders))
        self.assertTrue(sell_order_id in self.market.in_flight_orders)
        self.assertTrue(buy_order_id in self.market.in_flight_orders)

        # Cancel All Open Orders on Account (specified by trading pair)
        self.ev_loop.run_until_complete(safe_ensure_future(self.market.cancel_all_account_orders(trading_pair)))
        self.assertEqual(0, len(self.market.in_flight_orders))
        self.assertTrue(sell_order_id not in self.market.in_flight_orders)
        self.assertTrue(buy_order_id not in self.market.in_flight_orders)

    @unittest.skip("")
    def test_order_fill_event(self):
        trading_pair = "ETH-USDT"

        amount: Decimal = Decimal(0.01)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # Initialize Pricing (Buy)
        price: Decimal = self.market.get_price(trading_pair, True) * Decimal("1.01")
        quantized_price: Decimal = self.market.quantize_order_price(trading_pair, price)

        # Create Buy Order
        buy_order_id = self.market.buy(
            trading_pair=trading_pair,
            amount=quantized_amount,
            order_type=OrderType.LIMIT,
            price=quantized_price
        )
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        self.assertEqual(buy_order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("ETH", order_completed_event.base_asset)
        self.assertEqual("USDT", order_completed_event.quote_asset)
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == buy_order_id
                             for event in self.market_logger.event_log]))

        # Initialize Pricing (Sell)
        price = self.market.get_price(trading_pair, False) * Decimal("0.99")
        quantized_price = self.market.quantize_order_price(trading_pair, price)

        # Create Sell Order
        sell_order_id = self.market.sell(
            trading_pair=trading_pair,
            amount=quantized_amount,
            order_type=OrderType.LIMIT,
            price=quantized_price
        )
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        self.assertEqual(sell_order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("ETH", order_completed_event.base_asset)
        self.assertEqual("USDT", order_completed_event.quote_asset)
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == sell_order_id
                             for event in self.market_logger.event_log]))


def main():
    logging.getLogger("hummingbot.core.event.event_reporter").setLevel(logging.WARNING)
    unittest.main()


if __name__ == "__main__":
    main()
