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
from test.integration.api_request_mock import mock_aiohttp, mock_requests, PASSTHROUGH
from test.integration.assets.mock_data.fixture_liquid import FixtureLiquid
from hummingbot.market.liquid.liquid_api_order_book_data_source import LiquidAPIOrderBookDataSource
import aresponses

MAINNET_RPC_URL = "http://mainnet-rpc.mainnet:8545"
logging.basicConfig(level=METRICS_LOG_LEVEL)
import json

class LiquidMarketMockUnitTest(unittest.TestCase):
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
    @mock_aiohttp([('api.liquid.com', '/products', 'get', PASSTHROUGH),
                   ('api.liquid.com', '/fiat_accounts', 'get', FixtureLiquid.FIAT_ACCOUNTS),
                   ('api.liquid.com', '/crypto_accounts', 'get', FixtureLiquid.CRYPTO_ACCOUNTS),
                   ('api.ddex.io', '/v3/markets', 'get', PASSTHROUGH),
                   ('api.pro.coinbase.com', '/products/', 'get', PASSTHROUGH),
                   ('exchange-api.dolomite.io', '/v1/markets', 'get', PASSTHROUGH),
                   ('api.huobi.pro', '/v1/common/symbols', 'get', PASSTHROUGH),
                   ('api.idex.market', '/returnTicker', 'get', PASSTHROUGH),
                   ('api.bittrex.com', '/v3/markets', 'get', PASSTHROUGH),
                   ('api.exchange.bitcoin.com', '/api/2/public/symbol', 'get', PASSTHROUGH),
                   ('rest.bamboorelay.com', '/main/0x/markets', 'get', PASSTHROUGH),
                   ('api.liquid.com', '/orders', 'get', "{}"),
                   ('api.liquid.com', '/currencies', 'get', PASSTHROUGH)
                   ])
    def setUpClass(cls):
        global MAINNET_RPC_URL

        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: LiquidMarket = LiquidMarket(
            "XXXXXXX", "YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY",
            order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
            user_stream_tracker_data_source_type=UserStreamTrackerDataSourceType.EXCHANGE_API,
            trading_pairs=['ETH-USD']
        )
        print("Initializing Liquid market... this will take about a minute.")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.market)
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





class SimpleTest(unittest.TestCase):

    @mock_aiohttp([('api.liquid.com', '/products', 'get', json.dumps({"test": 1}))])
    def test_get_ex_data(self):
        loop = asyncio.get_event_loop()
        markets = loop.run_until_complete(LiquidAPIOrderBookDataSource.get_exchange_markets_data())
        print(markets)
        self.assertEqual(markets["test"], 1)

    @mock_aiohttp([('api.liquid.com', '/products', 'get', PASSTHROUGH)])
    def test_pass_through(self):
        loop = asyncio.get_event_loop()
        markets = loop.run_until_complete(LiquidAPIOrderBookDataSource.get_exchange_markets_data())
        print(markets)
        self.assertEqual(markets["test"], 1)

import aiohttp
async def get_aio_response():
    async with aiohttp.ClientSession() as session:
        async with session.get('http://google.com') as response:
            return await response.text()


class TestMockAioResponse(unittest.TestCase):
    @mock_aiohttp([('google.com', '/', 'get', 'hi there!!')])
    def test_mock_aiohttp(self):
        loop = asyncio.get_event_loop()
        text = loop.run_until_complete(get_aio_response())
        self.assertEqual(text, 'hi there!!')

if __name__ == "__main__":
    logging.getLogger("hummingbot.core.event.event_reporter").setLevel(logging.WARNING)
    unittest.main()
