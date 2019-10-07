#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

from aiohttp import web, request
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from unittest.mock import patch

import asyncio
import contextlib
from decimal import Decimal
import logging
import os
import time
from typing import List
import types
import unittest

import conf
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    TradeFee,
    TradeType,
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.market.huobi.huobi_market import HuobiMarket
from hummingbot.market.market_base import OrderType
from hummingbot.market.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill


logging.basicConfig(level=METRICS_LOG_LEVEL)
MOCK_HUOBI_USER_ID = 10000000
MOCK_HUOBI_BUY_ORDER_ID = 59378


class HuobiMarketUnitTest(AioHTTPTestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.OrderCancelled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled
    ]

    market: HuobiMarket
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()

    async def get_application(self):
        app = web.Application()
        app.router.add_get("/market/tickers", self.get_market_tickers)
        app.router.add_get("/account/accounts", self.get_account_accounts)
        app.router.add_get("/common/timestamp", self.get_common_timestamp)
        app.router.add_get("/common/symbols", self.get_common_symbols)
        app.router.add_get(f"/account/accounts/{MOCK_HUOBI_USER_ID}/balance", self.get_user_balance)
        app.router.add_post("/order/orders/place", self.post_order_place)
        app.router.add_get(f"/order/orders/{MOCK_HUOBI_BUY_ORDER_ID}", self.get_order)
        return app

    async def get_market_tickers(self, _):
        return web.json_response({
            'status': 'ok',
            'ts': 1570060262253,
            'data': [{
                "symbol": "ethusdt",
                "open": 175.57,
                "high": 181,
                "low": 175,
                "close": 180.11,
                "amount": 330265.5220692477,
                "vol": 58300213.797686026,
                "count": 93755
            }]
        }, status=200)

    async def get_account_accounts(self, _):
        return web.json_response({
            'status': 'ok',
            'data': [{'id': MOCK_HUOBI_USER_ID, 'type': 'spot', 'subtype': '', 'state': 'working'}]
        }, status=200)

    async def get_common_timestamp(self, _):
        return web.json_response({'status': 'ok', 'data': 1569445000000}, status=200)

    async def get_common_symbols(self, _):
        return web.json_response({
            'status': 'ok',
            'data': [
                {
                    'base-currency': 'eth',
                    'quote-currency': 'usdt',
                    'price-precision': 2,
                    'amount-precision': 4,
                    'symbol-partition': 'main',
                    'symbol': 'ethusdt',
                    'state': 'online',
                    'value-precision': 8,
                    'min-order-amt': 0.001,
                    'max-order-amt': 10000,
                    'min-order-value': 1
                }
            ]
        }, status=200)

    async def get_user_balance(self, _):
        return web.json_response({
            'status': 'ok',
            'data': {
                'id': MOCK_HUOBI_USER_ID,
                'type': 'spot',
                'state': 'working',
                'list': [{
                    'currency': 'eth',
                    'type': 'trade',
                    'balance': '0.259942948171422263'
                }]
            }
        }, status=200)

    async def post_order_place(self, _):
        return web.json_response({
            'status': 'ok',
            'data': MOCK_HUOBI_BUY_ORDER_ID
        })

    async def get_order(self, _):
        response = {
            "status": 'ok',
            "data": {
                "id": MOCK_HUOBI_BUY_ORDER_ID,
                "symbol": "ethusdt",
                "account-id": 100009,
                "amount": "10.1000000000",
                "price": "100.1000000000",
                "created-at": 1494901162595,
                "type": "buy-limit",
                "field-amount": "10.1000000000",
                "field-cash-amount": "1011.0100000000",
                "field-fees": "0.0202000000",
                "finished-at": 1494901400468,
                "user-id": MOCK_HUOBI_USER_ID,
                "source": "api",
                "state": "filled",
                "canceled-at": 0,
                "exchange": "huobi",
                "batch": ""
            }
        }
        return web.json_response(response)

    @staticmethod
    async def wait_til_ready(market, clock):
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if market.ready:
                break
            else:
                await clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def mock_get_price(symbol, is_buy) -> float:
        return float(100.0)

    def customSetUp(self):
        self.market: HuobiMarket = HuobiMarket(
            conf.huobi_api_key,
            conf.huobi_secret_key,
            symbols=["ethusdt"]
        )
        self.market.shared_client = self.client
        # self.market.get_price = self.mock_get_price
        # self.market.order_book_tracker.data_source
        self.clock.add_iterator(self.market)
        self.run_parallel(self.wait_til_ready(self.market, self._clock))
        self.db_path: str = realpath(join(__file__, "../huobi_test.sqlite"))
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
        future: asyncio.Future = asyncio.ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(0.5)
        return future.result()

    def run_parallel(self, *tasks):
        self.ev_loop = asyncio.get_event_loop()
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    # def test_get_fee(self):
    #     limit_fee: TradeFee = self.market.get_fee("eth", "usdt", OrderType.LIMIT, TradeType.BUY, 1, 10)
    #     self.assertGreater(limit_fee.percent, 0)
    #     self.assertEqual(len(limit_fee.flat_fees), 0)
    #     market_fee: TradeFee = self.market.get_fee("eth", "usdt", OrderType.MARKET, TradeType.BUY, 1)
    #     self.assertGreater(market_fee.percent, 0)
    #     self.assertEqual(len(market_fee.flat_fees), 0)
    #     sell_trade_fee: TradeFee = self.market.get_fee("eth", "usdt", OrderType.LIMIT, TradeType.SELL, 1, 10)
    #     self.assertGreater(sell_trade_fee.percent, 0)
    #     self.assertEqual(len(sell_trade_fee.flat_fees), 0)

    def test_limit_buy(self):
        self.customSetUp()
        symbol = "ethusdt"
        amount: Decimal = Decimal(0.02)
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)
        current_bid_price: float = self.market.get_price(symbol, True)
        print('@@@@@@@@@@@@@ CURRENT BUY PRICE', current_bid_price)
        bid_price: Decimal = Decimal(current_bid_price + 0.05 * current_bid_price)
        quantize_bid_price: Decimal = self.market.quantize_order_price(symbol, bid_price)

        order_id = self.market.buy(symbol, quantized_amount, OrderType.LIMIT, quantize_bid_price)

        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: float = sum(t.amount for t in trade_events)
        quote_amount_traded: float = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(float(quantized_amount), order_completed_event.base_asset_amount)
        self.assertEqual("eth", order_completed_event.base_asset)
        self.assertEqual("usdt", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, float(order_completed_event.base_asset_amount))
        self.assertAlmostEqual(quote_amount_traded, float(order_completed_event.quote_asset_amount))
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    # def test_limit_sell(self):
    #     symbol = "ethusdt"
    #     amount: Decimal = Decimal(0.02)
    #     quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

    #     current_ask_price: float = self.market.get_price(symbol, False)
    #     ask_price: Decimal = Decimal(current_ask_price - 0.05 * current_ask_price)
    #     quantize_ask_price: Decimal = self.market.quantize_order_price(symbol, ask_price)

    #     order_id = self.market.sell(symbol, amount, OrderType.LIMIT, quantize_ask_price)
    #     [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
    #     order_completed_event: SellOrderCompletedEvent = order_completed_event
    #     trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
    #                                             if isinstance(t, OrderFilledEvent)]
    #     base_amount_traded = sum(t.amount for t in trade_events)
    #     quote_amount_traded = sum(t.amount * t.price for t in trade_events)

    #     self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
    #     self.assertEqual(order_id, order_completed_event.order_id)
    #     self.assertAlmostEqual(float(quantized_amount), order_completed_event.base_asset_amount)
    #     self.assertEqual("eth", order_completed_event.base_asset)
    #     self.assertEqual("usdt", order_completed_event.quote_asset)
    #     self.assertAlmostEqual(base_amount_traded, float(order_completed_event.base_asset_amount))
    #     self.assertAlmostEqual(quote_amount_traded, float(order_completed_event.quote_asset_amount))
    #     self.assertGreater(order_completed_event.fee_amount, Decimal(0))
    #     self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
    #                          for event in self.market_logger.event_log]))
    #     # Reset the logs
    #     self.market_logger.clear()

    # def test_market_buy(self):
    #     symbol = "ethusdt"
    #     amount: Decimal = Decimal(0.02)
    #     quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

    #     order_id = self.market.buy(symbol, quantized_amount, OrderType.MARKET, 0)
    #     [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
    #     buy_order_completed_event: BuyOrderCompletedEvent = buy_order_completed_event
    #     trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
    #                                             if isinstance(t, OrderFilledEvent)]
    #     base_amount_traded: float = sum(t.amount for t in trade_events)
    #     quote_amount_traded: float = sum(t.amount * t.price for t in trade_events)

    #     self.assertTrue([evt.order_type == OrderType.MARKET for evt in trade_events])
    #     self.assertEqual(order_id, buy_order_completed_event.order_id)
    #     self.assertAlmostEqual(float(quantized_amount), buy_order_completed_event.base_asset_amount, places=4)
    #     self.assertEqual("eth", buy_order_completed_event.base_asset)
    #     self.assertEqual("usdt", buy_order_completed_event.quote_asset)
    #     self.assertAlmostEqual(base_amount_traded, float(buy_order_completed_event.base_asset_amount), places=4)
    #     self.assertAlmostEqual(quote_amount_traded, float(buy_order_completed_event.quote_asset_amount), places=4)
    #     self.assertGreater(buy_order_completed_event.fee_amount, Decimal(0))
    #     self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
    #                          for event in self.market_logger.event_log]))
    #     # Reset the logs
    #     self.market_logger.clear()

    # def test_market_sell(self):
    #     symbol = "ethusdt"
    #     amount: Decimal = Decimal(0.02)
    #     quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

    #     order_id = self.market.sell(symbol, amount, OrderType.MARKET, 0)
    #     [sell_order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
    #     sell_order_completed_event: SellOrderCompletedEvent = sell_order_completed_event
    #     trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
    #                                             if isinstance(t, OrderFilledEvent)]
    #     base_amount_traded = sum(t.amount for t in trade_events)
    #     quote_amount_traded = sum(t.amount * t.price for t in trade_events)

    #     self.assertTrue([evt.order_type == OrderType.MARKET for evt in trade_events])
    #     self.assertEqual(order_id, sell_order_completed_event.order_id)
    #     self.assertAlmostEqual(float(quantized_amount), sell_order_completed_event.base_asset_amount)
    #     self.assertEqual("eth", sell_order_completed_event.base_asset)
    #     self.assertEqual("usdt", sell_order_completed_event.quote_asset)
    #     self.assertAlmostEqual(base_amount_traded, float(sell_order_completed_event.base_asset_amount))
    #     self.assertAlmostEqual(quote_amount_traded, float(sell_order_completed_event.quote_asset_amount))
    #     self.assertGreater(sell_order_completed_event.fee_amount, Decimal(0))
    #     self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
    #                          for event in self.market_logger.event_log]))
    #     # Reset the logs
    #     self.market_logger.clear()

    # def test_cancel_order(self):
    #     symbol = "ethusdt"

    #     current_bid_price: float = self.market.get_price(symbol, True)
    #     amount: Decimal = Decimal(0.02)

    #     bid_price: Decimal = Decimal(current_bid_price - 0.1 * current_bid_price)
    #     quantize_bid_price: Decimal = self.market.quantize_order_price(symbol, bid_price)
    #     quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

    #     client_order_id = self.market.buy(symbol, quantized_amount, OrderType.LIMIT, quantize_bid_price)
    #     [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
    #     self.market.cancel(symbol, client_order_id)
    #     [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
    #     order_cancelled_event: OrderCancelledEvent = order_cancelled_event
    #     self.assertEqual(order_cancelled_event.order_id, client_order_id)

    # def test_cancel_all(self):
    #     symbol = "ethusdt"

    #     bid_price: Decimal = Decimal(self.market_2.get_price(symbol, True) * 0.5)
    #     ask_price: Decimal = Decimal(self.market_2.get_price(symbol, False) * 2)
    #     amount: Decimal = Decimal(0.05)
    #     quantized_amount: Decimal = self.market_2.quantize_order_amount(symbol, amount)

    #     # Intentionally setting high price to prevent getting filled
    #     quantize_bid_price: Decimal = self.market_2.quantize_order_price(symbol, bid_price * Decimal(0.7))
    #     quantize_ask_price: Decimal = self.market_2.quantize_order_price(symbol, ask_price * Decimal(1.5))

    #     self.market_2.buy(symbol, quantized_amount, OrderType.LIMIT, quantize_bid_price)
    #     self.market_2.sell(symbol, quantized_amount, OrderType.LIMIT, quantize_ask_price)
    #     self.run_parallel(asyncio.sleep(1))
    #     [cancellation_results] = self.run_parallel(self.market_2.cancel_all(5))
    #     for cr in cancellation_results:
    #         self.assertEqual(cr.success, True)

    # def test_orders_saving_and_restoration(self):
    #     config_path: str = "test_config"
    #     strategy_name: str = "test_strategy"
    #     symbol: str = "ethusdt"
    #     sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
    #     order_id: Optional[str] = None
    #     recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
    #     recorder.start()

    #     try:
    #         self.assertEqual(0, len(self.market.tracking_states))

    #         # Try to put limit buy order for 0.04 ETH, and watch for order creation event.
    #         current_bid_price: float = self.market.get_price(symbol, True)
    #         bid_price: Decimal = Decimal(current_bid_price * 0.8)
    #         quantize_bid_price: Decimal = self.market.quantize_order_price(symbol, bid_price)

    #         amount: Decimal = Decimal(0.04)
    #         quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)

    #         order_id = self.market.buy(symbol, quantized_amount, OrderType.LIMIT, quantize_bid_price)
    #         [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
    #         order_created_event: BuyOrderCreatedEvent = order_created_event
    #         self.assertEqual(order_id, order_created_event.order_id)

    #         # Verify tracking states
    #         self.assertEqual(1, len(self.market.tracking_states))
    #         self.assertEqual(order_id, list(self.market.tracking_states.keys())[0])

    #         # Verify orders from recorder
    #         recorded_orders: List[Order] = recorder.get_orders_for_config_and_market(config_path, self.market)
    #         self.assertEqual(1, len(recorded_orders))
    #         self.assertEqual(order_id, recorded_orders[0].id)

    #         # Verify saved market states
    #         saved_market_states: MarketState = recorder.get_market_states(config_path, self.market)
    #         self.assertIsNotNone(saved_market_states)
    #         self.assertIsInstance(saved_market_states.saved_state, dict)
    #         self.assertGreater(len(saved_market_states.saved_state), 0)

    #         # Close out the current market and start another market.
    #         self.clock.remove_iterator(self.market)
    #         for event_tag in self.events:
    #             self.market.remove_listener(event_tag, self.market_logger)
    #         self.market: HuobiMarket = HuobiMarket(
    #             huobi_api_key=conf.huobi_api_key,
    #             huobi_secret_key=conf.huobi_secret_key,
    #             symbols=["ethusdt", "btcusdt"]
    #         )
    #         for event_tag in self.events:
    #             self.market.add_listener(event_tag, self.market_logger)
    #         recorder.stop()
    #         recorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
    #         recorder.start()
    #         saved_market_states = recorder.get_market_states(config_path, self.market)
    #         self.clock.add_iterator(self.market)
    #         self.assertEqual(0, len(self.market.limit_orders))
    #         self.assertEqual(0, len(self.market.tracking_states))
    #         self.market.restore_tracking_states(saved_market_states.saved_state)
    #         self.assertEqual(1, len(self.market.limit_orders))
    #         self.assertEqual(1, len(self.market.tracking_states))

    #         # Cancel the order and verify that the change is saved.
    #         self.market.cancel(symbol, order_id)
    #         self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
    #         order_id = None
    #         self.assertEqual(0, len(self.market.limit_orders))
    #         self.assertEqual(0, len(self.market.tracking_states))
    #         saved_market_states = recorder.get_market_states(config_path, self.market)
    #         self.assertEqual(0, len(saved_market_states.saved_state))
    #     finally:
    #         if order_id is not None:
    #             self.market.cancel(symbol, order_id)
    #             self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

    #         recorder.stop()
    #         os.unlink(self.db_path)

    # def test_order_fill_record(self):
    #     config_path: str = "test_config"
    #     strategy_name: str = "test_strategy"
    #     symbol: str = "ethusdt"
    #     sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
    #     order_id: Optional[str] = None
    #     recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
    #     recorder.start()

    #     try:
    #         # Try to buy 0.04 ETH from the exchange, and watch for completion event.
    #         amount: Decimal = Decimal(0.04)
    #         order_id = self.market.buy(symbol, amount)
    #         [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

    #         # Reset the logs
    #         self.market_logger.clear()

    #         # Try to sell back the same amount of ETH to the exchange, and watch for completion event.
    #         amount: Decimal = Decimal(buy_order_completed_event.base_asset_amount)
    #         order_id = self.market.sell(symbol, amount)
    #         [sell_order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))

    #         # Query the persisted trade logs
    #         trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
    #         self.assertEqual(2, len(trade_fills))
    #         buy_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
    #         sell_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "SELL"]
    #         self.assertEqual(1, len(buy_fills))
    #         self.assertEqual(1, len(sell_fills))

    #         order_id = None

    #     finally:
    #         if order_id is not None:
    #             self.market.cancel(symbol, order_id)
    #             self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

    #         recorder.stop()
    #         os.unlink(self.db_path)


if __name__ == "__main__":
    unittest.main()
