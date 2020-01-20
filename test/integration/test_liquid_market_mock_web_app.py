#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import asyncio
import conf
import contextlib
from decimal import Decimal
import logging
import os
import time
from typing import (
    List,
    Optional
)
import unittest

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.user_stream_tracker import UserStreamTrackerDataSourceType
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketWithdrawAssetEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
    TradeFee,
    TradeType,
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.market.liquid.liquid_market import LiquidMarket
from hummingbot.market.deposit_info import DepositInfo
from hummingbot.market.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.wallet.ethereum.mock_wallet import MockWallet
from test.integration.humming_web_app import HummingWebApp
from test.integration.assets.mock_data.fixture_liquid import FixtureLiquid
from unittest import mock
from yarl import URL

MAINNET_RPC_URL = "http://mainnet-rpc.mainnet:8545"
logging.basicConfig(level=METRICS_LOG_LEVEL)
API_MOCK_ENABLED = True



class LiquidMarketWebAppUnitTest(unittest.TestCase):
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

    market: LiquidMarket
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    @mock.patch("aiohttp.client.URL")
    def setUpClass(cls, mock):
        global MAINNET_RPC_URL
        cls.ev_loop = asyncio.get_event_loop()
        cls.web_app = HummingWebApp()
        api_host = "api.liquid.com"
        cls.web_app.add_json_response(f"{api_host}/fiat_accounts", FixtureLiquid.FIAT_ACCOUNTS)
        cls.web_app.add_json_response(f"{api_host}/crypto_accounts", FixtureLiquid.CRYPTO_ACCOUNTS)
        cls.web_app.add_json_response(f"{api_host}/orders", FixtureLiquid.ORDERS)
        cls.web_app.start()
        # cls._urls_to_reroute = {}
        # cls._urls_to_reroute = {"https://api.liquid.com/fiat_accounts",
        #                         "https://api.liquid.com/crypto_accounts",
        #                         "https://api.liquid.com/orders?with_details=1"}
        mock.side_effect = cls.web_app.reroute_local
        api_key, api_secret = "XXX", "YYY"
        if not API_MOCK_ENABLED:
            api_key, api_secret = conf.liquid_api_key, conf.liquid_secret_key
        cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())

        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: LiquidMarket = LiquidMarket(
            api_key, api_secret,
            order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
            user_stream_tracker_data_source_type=UserStreamTrackerDataSourceType.EXCHANGE_API,
            trading_pairs=['CEL-ETH']
        )
        # cls.ev_loop.run_until_complete(cls.market._update_balances())
        print("Initializing Liquid market... this will take about a minute.")
        cls.clock.add_iterator(cls.market)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.web_app.stop()
        cls.stack.close()

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
        self.db_path: str = realpath(join(__file__, "../liquid_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)

    def tearDown(self):
        for event_tag in self.events:
            self.market.remove_listener(event_tag, self.market_logger)
        self.market_logger = None

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

    def test_get_fee(self):
        maker_buy_trade_fee: TradeFee = self.market.get_fee("BTC", "USD", OrderType.LIMIT, TradeType.BUY, Decimal(1), Decimal(4000))
        self.assertGreater(maker_buy_trade_fee.percent, 0)
        self.assertEqual(len(maker_buy_trade_fee.flat_fees), 0)
        taker_buy_trade_fee: TradeFee = self.market.get_fee("BTC", "USD", OrderType.MARKET, TradeType.BUY, Decimal(1))
        self.assertGreater(taker_buy_trade_fee.percent, 0)
        self.assertEqual(len(taker_buy_trade_fee.flat_fees), 0)
        sell_trade_fee: TradeFee = self.market.get_fee("BTC", "USD", OrderType.LIMIT, TradeType.SELL, Decimal(1), Decimal(4000))
        self.assertGreater(sell_trade_fee.percent, 0)
        self.assertEqual(len(sell_trade_fee.flat_fees), 0)


if __name__ == "__main__":
    logging.getLogger("hummingbot.core.event.event_reporter").setLevel(logging.WARNING)
    unittest.main()
