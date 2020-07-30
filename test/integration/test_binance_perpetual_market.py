# import asyncio
import logging
import unittest
import uuid
from decimal import Decimal

from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.user_stream_tracker import UserStreamTrackerDataSourceType
from hummingbot.core.event.events import TradeType, OrderType
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.market.binance_perpetual.binance_perpetual_market import BinancePerpetualMarket
from hummingbot.core.utils.async_utils import safe_ensure_future
from .assets.test_keys import Keys

logging.basicConfig(level=METRICS_LOG_LEVEL)


class BinancePerpetualMarketUnitTest(unittest.TestCase):
    market: BinancePerpetualMarket

    def test_signed_order_request(self):
        self.market: BinancePerpetualMarket = BinancePerpetualMarket(
            binance_api_key=Keys.get_binance_futures_api_key(),
            binance_api_secret=Keys.get_binance_futures_api_secret(),
            order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
            user_stream_tracker_data_source_type=UserStreamTrackerDataSourceType.EXCHANGE_API,
            trading_pairs=["ETHUSDT"]
        )
        safe_ensure_future(
            self.market.create_order(
                trade_type=TradeType.SELL,
                order_id=uuid.uuid1().__str__(),
                trading_pair="ETHUSDT",
                amount=Decimal(0.01),
                order_type=OrderType.LIMIT,
                price=Decimal(320)
            )
        )


if __name__ == "__main__":
    unittest.main()
