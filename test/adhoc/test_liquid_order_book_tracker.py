import asyncio
import concurrent
import inspect
from typing import List
from unittest import TestCase

# from test.adhoc.assets.mock_data.fixture_liquid import FixtureLiquid
# from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.market.liquid.liquid_api_order_book_data_source import LiquidAPIOrderBookDataSource
# from hummingbot.market.liquid.liquid_order_book import LiquidOrderBook
from hummingbot.market.liquid.liquid_order_book_tracker import LiquidOrderBookTracker


PATCH_BASE_PATH = \
    'hummingbot.market.liquid.liquid_order_book_tracker.LiquidOrderBookTracker.{method}'


class TestLiquidOrderBookTracker(TestCase):

    trading_pairs: List[str] = [
        "ETHUSD",
        "LCXBTC"
    ]

    def test_property_exchange_name(self):
        exchange_name = LiquidOrderBookTracker(
            OrderBookTrackerDataSourceType.EXCHANGE_API,
            trading_pairs=self.trading_pairs
        ).exchange_name

        # Validate the type of property exchange name is equal to 'liquid'
        self.assertEqual(
            exchange_name,
            'liquid'
        )

    def test_property_data_source(self):
        data_source = LiquidOrderBookTracker(
            OrderBookTrackerDataSourceType.EXCHANGE_API,
            trading_pairs=self.trading_pairs
        ).data_source

        # Validate the type of property data source is LiquidAPIOrderBookDataSource
        self.assertIsInstance(
            data_source,
            LiquidAPIOrderBookDataSource
        )

    def test_method_start(self):
        timeout = 10
        loop = asyncio.get_event_loop()

        order_book_tracker = LiquidOrderBookTracker(
            OrderBookTrackerDataSourceType.EXCHANGE_API,
            trading_pairs=self.trading_pairs
        )

        print('{class_name} test {test_name} is going to run for {timeout} seconds, starting now'.format(
            class_name=self.__class__.__name__,
            test_name=inspect.stack()[0][3],
            timeout=timeout))

        try:
            loop.run_until_complete(
                # Force exit from event loop after set timeout seconds
                asyncio.wait_for(
                    order_book_tracker.start(),
                    timeout=timeout
                )
            )
        except concurrent.futures.TimeoutError as e:
            print(e)
