#!/usr/bin/env python
import logging
from os.path import join, realpath
import sys;sys.path.insert(0, realpath(join(__file__, "../../")))

from wings.logger.struct_logger import METRICS_LOG_LEVEL

import asyncio
from decimal import Decimal
import time
from typing import List
import unittest

import conf
from wings.market_base import OrderType
from wings.coinbase_pro_market import CoinbaseProMarket
from wings.clock import (
    Clock,
    ClockMode
)
from wings.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    MarketReceivedAssetEvent,
    MarketWithdrawAssetEvent,
    OrderFilledEvent,
    BuyOrderCreatedEvent, SellOrderCreatedEvent)
from wings.mock_wallet import MockWallet
from wings.event_logger import EventLogger


MAINNET_RPC_URL = "http://mainnet-rpc.mainnet:8545"
logging.basicConfig(level=METRICS_LOG_LEVEL)


class CoinbaseProMarketUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated
    ]

    market: CoinbaseProMarket
    market_logger: EventLogger

    @classmethod
    def setUpClass(cls):
        global MAINNET_RPC_URL
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: CoinbaseProMarket = CoinbaseProMarket(
            web3_url=MAINNET_RPC_URL,
            coinbase_pro_api_key=conf.coinbase_pro_api_key,
            coinbase_pro_secret_key=conf.coinbase_pro_secret_key,
            coinbase_pro_passphrase=conf.coinbase_pro_passphrase,
            symbols=["ETH-USDC"]
        )
        print("Initializing Coinbase Pro market... this will take about a minute.")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.market)
        cls.ev_loop.run_until_complete(cls.clock.run_til(time.time() + 1))
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    async def wait_til_ready(cls):
        while True:
            if cls.market.ready:
                break
            await asyncio.sleep(1.0)

    def setUp(self):
        self.market_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)

    def tearDown(self):
        for event_tag in self.events:
            self.market.remove_listener(event_tag, self.market_logger)
        self.market_logger = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = asyncio.ensure_future(asyncio.gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self.clock.run_til(next_iteration)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_get_balances(self):
        [results] = self.run_parallel(self.market._update_balances())
        print(results)

    @unittest.skip
    def test_buy_and_sell(self):
        # self.assertGreater(self.market.get_balance("ETH"), 0.1)
        symbol = "ETH-USDC"
        amount: float = 1.0

        current_bid_price: float = 100
        # current_bid_price: float = self.market.get_price(symbol, True)
        bid_price: float = current_bid_price + 0.05 * current_bid_price
        quantize_bid_price: Decimal = self.market.quantize_order_price(symbol, bid_price)
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

        order_id = self.market.buy(symbol, quantized_amount, OrderType.LIMIT, quantize_bid_price)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: float = sum(t.amount for t in trade_events)
        quote_amount_traded: float = sum(t.amount * t.price for t in trade_events)

        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("ETH", order_completed_event.base_asset)
        self.assertEqual("USDC", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, float(order_completed_event.base_asset_amount))
        self.assertAlmostEqual(quote_amount_traded, float(order_completed_event.quote_asset_amount))
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))


if __name__ == "__main__":
    unittest.main()
