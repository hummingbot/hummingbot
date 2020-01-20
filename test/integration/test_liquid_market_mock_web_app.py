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
    liquid_api_host = "api.liquid.com"

    @classmethod
    def setUpClass(cls):
        global MAINNET_RPC_URL
        cls.ev_loop = asyncio.get_event_loop()

        api_key, api_secret = "XXX", "YYY"
        if API_MOCK_ENABLED:
            cls.web_app = HummingWebApp()
            cls.web_app.add_host_to_handle(cls.liquid_api_host, ["/products", "/currencies"])
            cls.web_app.start()
            cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
            cls._patcher = mock.patch("aiohttp.client.URL")
            cls._url_mock = cls._patcher.start()
            cls._url_mock.side_effect = cls.web_app.reroute_local
            cls.web_app.update_response_data("get", cls.liquid_api_host, "/fiat_accounts", FixtureLiquid.FIAT_ACCOUNTS,
                                             is_permanent=True)
            cls.web_app.update_response_data("get", cls.liquid_api_host, "/crypto_accounts",
                                             FixtureLiquid.CRYPTO_ACCOUNTS,
                                             is_permanent=True)
            cls.web_app.update_response_data("get", cls.liquid_api_host, "/orders", FixtureLiquid.ORDERS_GET,
                                             query_string="with_details=1",
                                             is_permanent=True)
        else:
            api_key, api_secret = conf.liquid_api_key, conf.liquid_secret_key

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
        if API_MOCK_ENABLED:
            cls.web_app.stop()
            cls._patcher.stop()
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
        maker_buy_trade_fee: TradeFee = self.market.get_fee("BTC", "USD", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                            Decimal(4000))
        self.assertGreater(maker_buy_trade_fee.percent, 0)
        self.assertEqual(len(maker_buy_trade_fee.flat_fees), 0)
        taker_buy_trade_fee: TradeFee = self.market.get_fee("BTC", "USD", OrderType.MARKET, TradeType.BUY, Decimal(1))
        self.assertGreater(taker_buy_trade_fee.percent, 0)
        self.assertEqual(len(taker_buy_trade_fee.flat_fees), 0)
        sell_trade_fee: TradeFee = self.market.get_fee("BTC", "USD", OrderType.LIMIT, TradeType.SELL, Decimal(1),
                                                       Decimal(4000))
        self.assertGreater(sell_trade_fee.percent, 0)
        self.assertEqual(len(sell_trade_fee.flat_fees), 0)

    def test_buy_and_sell(self):
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.05"))

        current_price: Decimal = self.market.get_price("CEL-ETH", True)
        amount: Decimal = 1
        quantized_amount: Decimal = self.market.quantize_order_amount("CEL-ETH", amount)
        order_id = self.market.buy("CEL-ETH", amount, price=current_price)
        if API_MOCK_ENABLED:
            order_buy_resp = FixtureLiquid.ORDER_BUY
            order_buy_resp["client_order_id"] = order_id
            self.web_app.update_response_data("post", self.liquid_api_host, "/orders", order_buy_resp)
            orders_get = FixtureLiquid.ORDERS_GET_AFTER_BUY
            orders_get["models"][0]["client_order_id"] = order_id
            self.web_app.update_response_data("get", self.liquid_api_host, "/orders", orders_get,
                                              query_string="with_details=1")
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.MARKET for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("CEL", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

        # Reset the logs
        self.market_logger.clear()

        # Try to sell back the same amount of CEL to the exchange, and watch for completion event.
        amount = order_completed_event.base_asset_amount
        quantized_amount = order_completed_event.base_asset_amount
        order_id = self.market.sell("CEL-ETH", amount, price=current_price)
        if API_MOCK_ENABLED:
            order_sell_resp = FixtureLiquid.ORDER_SELL
            order_sell_resp["client_order_id"] = order_id
            self.web_app.update_response_data("post", self.liquid_api_host, "/orders", order_sell_resp)
            orders_get = FixtureLiquid.ORDERS_GET_AFTER_SELL
            orders_get["models"][0]["client_order_id"] = order_id
            self.web_app.update_response_data("get", self.liquid_api_host, "/orders", orders_get,
                                              query_string="with_details=1")
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.market_logger.event_log
                        if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.MARKET for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("CEL", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))


if __name__ == "__main__":
    logging.getLogger("hummingbot.core.event.event_reporter").setLevel(logging.WARNING)
    unittest.main()
