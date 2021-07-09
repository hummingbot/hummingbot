#!/usr/bin/env python
from os.path import (
    join,
    realpath
)
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

from aiohttp import web
from aiohttp.test_utils import (
    AioHTTPTestCase,
    TestClient
)
import asyncio
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
from hummingbot.connector.exchange.huobi.huobi_exchange import HuobiExchange
from hummingbot.connector.exchange.huobi.huobi_order_book import HuobiOrderBook
from hummingbot.core.event.events import OrderType
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.connector.mock_api_order_book_data_source import MockAPIOrderBookDataSource
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill
from test.debug.huobi_mock_api import HuobiMockAPI

logging.basicConfig(level=METRICS_LOG_LEVEL)
MOCK_HUOBI_API_KEY = "zzzzzzzzzz-xxxxxxxx-55555555-xxxxx"
MOCK_HUOBI_SECRET_KEY = "11111111-aaaaaaaa-22222222-bbbbb"


class HuobiMarketUnitTest(AioHTTPTestCase):
    events: List[MarketEvent] = [
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderFilled,
        MarketEvent.OrderCancelled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled
    ]

    market: HuobiExchange
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

    # get_application overrides the aiohttp.web and allows mocking api endpoints
    async def get_application(self):
        app = web.Application()
        self.mock_api = HuobiMockAPI()
        app.router.add_get("/mockSnapshot", self.mock_api.get_mock_snapshot)
        app.router.add_get("/market/tickers", self.mock_api.get_market_tickers)
        app.router.add_get("/account/accounts", self.mock_api.get_account_accounts)
        app.router.add_get("/common/timestamp", self.mock_api.get_common_timestamp)
        app.router.add_get("/common/symbols", self.mock_api.get_common_symbols)
        app.router.add_get("/account/accounts/{user_id}/balance", self.mock_api.get_user_balance)
        app.router.add_post("/order/orders/place", self.mock_api.post_order_place)
        app.router.add_get("/order/orders/{order_id}", self.mock_api.get_order_update)
        app.router.add_post("/order/orders/{order_id}/submitcancel", self.mock_api.post_submit_cancel)
        app.router.add_post("/order/orders/batchcancel", self.mock_api.post_batch_cancel)
        return app

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

    # setUp function from unittests is called before get_application so this needs
    # to be called manually before every test
    def customSetUp(self):
        self.market: HuobiExchange = HuobiExchange(
            MOCK_HUOBI_API_KEY,
            MOCK_HUOBI_SECRET_KEY,
            trading_pairs=["ethusdt"]
        )

        # replace regular aiohttp client with test client
        self.market.shared_client: TestClient = self.client
        # replace default data source with mock data source
        mock_data_source: MockAPIOrderBookDataSource = MockAPIOrderBookDataSource(self.client, HuobiOrderBook, ["ethusdt"])
        self.market.order_book_tracker.data_source = mock_data_source

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
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(0.5)
        return future.result()

    def run_parallel(self, *tasks):
        self.ev_loop = asyncio.get_event_loop()
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_get_fee(self):
        self.customSetUp()
        limit_fee: TradeFee = self.market.get_fee("eth", "usdt", OrderType.LIMIT_MAKER, TradeType.BUY, 1, 10)
        self.assertGreater(limit_fee.percent, 0)
        self.assertEqual(len(limit_fee.flat_fees), 0)
        market_fee: TradeFee = self.market.get_fee("eth", "usdt", OrderType.LIMIT, TradeType.BUY, 1)
        self.assertGreater(market_fee.percent, 0)
        self.assertEqual(len(market_fee.flat_fees), 0)
        sell_trade_fee: TradeFee = self.market.get_fee("eth", "usdt", OrderType.LIMIT_MAKER, TradeType.SELL, 1, 10)
        self.assertGreater(sell_trade_fee.percent, 0)
        self.assertEqual(len(sell_trade_fee.flat_fees), 0)

    def test_market_buy(self):
        self.customSetUp()
        self.mock_api.order_id = self.mock_api.MOCK_HUOBI_MARKET_BUY_ORDER_ID
        trading_pair = "ethusdt"
        price: Decimal = self.market.get_price(trading_pair, True)
        amount: Decimal = Decimal(0.02)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, price)
        [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        buy_order_completed_event: BuyOrderCompletedEvent = buy_order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = Decimal(sum(t.amount for t in trade_events))
        quote_amount_traded: Decimal = Decimal(sum(t.amount * t.price for t in trade_events))

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, buy_order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, buy_order_completed_event.base_asset_amount, places=4)
        self.assertEqual("eth", buy_order_completed_event.base_asset)
        self.assertEqual("usdt", buy_order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, buy_order_completed_event.base_asset_amount, places=4)
        self.assertAlmostEqual(quote_amount_traded, buy_order_completed_event.quote_asset_amount, places=4)
        self.assertGreater(buy_order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_market_sell(self):
        self.customSetUp()
        self.mock_api.order_id = self.mock_api.MOCK_HUOBI_MARKET_SELL_ORDER_ID
        trading_pair = "ethusdt"
        price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = Decimal(0.02)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id = self.market.sell(trading_pair, amount, OrderType.LIMIT, price)
        [sell_order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        sell_order_completed_event: SellOrderCompletedEvent = sell_order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded = Decimal(sum(t.amount for t in trade_events))
        quote_amount_traded = Decimal(sum(t.amount * t.price for t in trade_events))

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, sell_order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, sell_order_completed_event.base_asset_amount)
        self.assertEqual("eth", sell_order_completed_event.base_asset)
        self.assertEqual("usdt", sell_order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, sell_order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, sell_order_completed_event.quote_asset_amount)
        self.assertGreater(sell_order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_cancel_order(self):
        self.customSetUp()
        self.mock_api.order_id = self.mock_api.MOCK_HUOBI_LIMIT_CANCEL_ORDER_ID
        trading_pair = "ethusdt"

        current_bid_price: Decimal = self.market.get_price(trading_pair, True)
        amount: Decimal = Decimal(0.02)

        bid_price: Decimal = current_bid_price * Decimal(0.9)
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        client_order_id = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_bid_price)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        self.market.cancel(trading_pair, client_order_id)
        self.mock_api.order_response_dict[self.mock_api.MOCK_HUOBI_LIMIT_CANCEL_ORDER_ID]["data"]["state"] = "canceled"
        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event
        self.assertEqual(order_cancelled_event.order_id, client_order_id)

    def test_cancel_all(self):
        self.customSetUp()
        self.mock_api.cancel_all_order_ids = [
            self.mock_api.MOCK_HUOBI_LIMIT_BUY_ORDER_ID,
            self.mock_api.MOCK_HUOBI_LIMIT_SELL_ORDER_ID,
        ]
        trading_pair = "ethusdt"

        bid_price: Decimal = self.market.get_price(trading_pair, True) * Decimal(0.5)
        ask_price: Decimal = self.market.get_price(trading_pair, False) * Decimal(2)
        amount: Decimal = Decimal(0.05)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # Intentionally setting high price to prevent getting filled
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price * Decimal(0.7))
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price * Decimal(1.5))
        self.mock_api.order_id = self.mock_api.MOCK_HUOBI_LIMIT_BUY_ORDER_ID
        self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_bid_price)
        self.mock_api.order_id = self.mock_api.MOCK_HUOBI_LIMIT_SELL_ORDER_ID
        self.market.sell(trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_ask_price)
        self.run_parallel(asyncio.sleep(1))
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_orders_saving_and_restoration(self):
        self.customSetUp()
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "ethusdt"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            self.assertEqual(0, len(self.market.tracking_states))

            # Try to put limit buy order for 0.04 ETH, and watch for order creation event.
            current_bid_price: Decimal = self.market.get_price(trading_pair, True)
            bid_price: Decimal = current_bid_price * Decimal(0.8)
            quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)

            amount: Decimal = Decimal(0.04)
            quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

            self.mock_api.order_id = self.mock_api.MOCK_HUOBI_LIMIT_OPEN_ORDER_ID
            order_id = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_bid_price)
            [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
            order_created_event: BuyOrderCreatedEvent = order_created_event
            self.assertEqual(order_id, order_created_event.order_id)

            # Verify tracking states
            self.assertEqual(1, len(self.market.tracking_states))
            self.assertEqual(order_id, list(self.market.tracking_states.keys())[0])

            # Verify orders from recorder
            recorded_orders: List[Order] = recorder.get_orders_for_config_and_market(config_path, self.market)
            self.assertEqual(1, len(recorded_orders))
            self.assertEqual(order_id, recorded_orders[0].id)

            # Verify saved market states
            saved_market_states: MarketState = recorder.get_market_states(config_path, self.market)
            self.assertIsNotNone(saved_market_states)
            self.assertIsInstance(saved_market_states.saved_state, dict)
            self.assertGreater(len(saved_market_states.saved_state), 0)

            # Close out the current market and start another market.
            self.clock.remove_iterator(self.market)
            for event_tag in self.events:
                self.market.remove_listener(event_tag, self.market_logger)
            self.market: HuobiExchange = HuobiExchange(
                huobi_api_key=MOCK_HUOBI_API_KEY,
                huobi_secret_key=MOCK_HUOBI_SECRET_KEY,
                trading_pairs=["ethusdt", "btcusdt"]
            )
            self.market.shared_client: TestClient = self.client
            mock_data_source: MockAPIOrderBookDataSource = MockAPIOrderBookDataSource(self.client, HuobiOrderBook, ["ethusdt"])
            self.market.order_book_tracker.data_source = mock_data_source

            for event_tag in self.events:
                self.market.add_listener(event_tag, self.market_logger)
            recorder.stop()
            recorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
            recorder.start()
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.clock.add_iterator(self.market)
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            self.market.restore_tracking_states(saved_market_states.saved_state)
            self.assertEqual(1, len(self.market.limit_orders))
            self.assertEqual(1, len(self.market.tracking_states))

            # Cancel the order and verify that the change is saved.
            self.mock_api.order_id = self.mock_api.MOCK_HUOBI_LIMIT_OPEN_ORDER_ID
            self.mock_api.order_response_dict[self.mock_api.MOCK_HUOBI_LIMIT_OPEN_ORDER_ID]["data"]["state"] = "canceled"
            self.market.cancel(trading_pair, order_id)
            self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
            order_id = None
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.assertEqual(0, len(saved_market_states.saved_state))
        finally:
            if order_id is not None:
                self.market.cancel(trading_pair, order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)

    def test_order_fill_record(self):
        self.customSetUp()
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "ethusdt"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy 0.04 ETH from the exchange, and watch for completion event.
            amount: Decimal = Decimal(0.04)
            self.mock_api.order_id = self.mock_api.MOCK_HUOBI_MARKET_BUY_ORDER_ID
            order_id = self.market.buy(trading_pair, amount)
            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logs
            self.market_logger.clear()

            # Try to sell back the same amount of ETH to the exchange, and watch for completion event.
            self.mock_api.order_id = self.mock_api.MOCK_HUOBI_MARKET_SELL_ORDER_ID
            amount: Decimal = Decimal(buy_order_completed_event.base_asset_amount)
            order_id = self.market.sell(trading_pair, amount)
            [sell_order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))

            # Query the persisted trade logs
            trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
            self.assertEqual(2, len(trade_fills))
            buy_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
            sell_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "SELL"]
            self.assertEqual(1, len(buy_fills))
            self.assertEqual(1, len(sell_fills))

            order_id = None

        finally:
            if order_id is not None:
                self.market.cancel(trading_pair, order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)


if __name__ == "__main__":
    unittest.main()
