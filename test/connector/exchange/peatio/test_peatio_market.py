# !/usr/bin/env python
import logging
import datetime

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL

from hummingbot.connector.exchange.peatio.peatio_exchange import PeatioExchange
from test.connector.exchange.peatio.fixture_peatio import FixturePeatio

import asyncio
import contextlib
from decimal import Decimal
import os
import time
from typing import (
    List,
    Optional
)
import unittest
import math
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
from hummingbot.connector.exchange.peatio.peatio_utils import convert_to_exchange_trading_pair
from hummingbot.core.event.events import OrderType
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
from hummingbot.core.mock_api.mock_web_server import MockWebServer
from unittest import mock


API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
ACCESS_KEY = "XXX" if API_MOCK_ENABLED else conf.peatio_access_key
API_SECRET = "YYY" if API_MOCK_ENABLED else conf.peatio_secret_key
API_BASE_URL = "market.bitzlato.com"
API_HOST = "market.bitzlato.com"
EXCHANGE_ORDER_ID = 20001
logging.basicConfig(level=METRICS_LOG_LEVEL)


class PeatioExchangeUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderFilled,
        MarketEvent.OrderCancelled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderFailure
    ]

    market: PeatioExchange
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        if API_MOCK_ENABLED:
            cls.web_app = MockWebServer.get_instance()
            api_endpoints = ["/api/v2/ranger/public", "/api/v2/peatio/public/timestamp", "/api/v2/peatio/public/markets"]
            cls.web_app.add_host_to_mock(API_BASE_URL, api_endpoints)
            cls.web_app.start()
            cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
            cls._patcher = mock.patch("aiohttp.client.URL")
            cls._url_mock = cls._patcher.start()
            cls._url_mock.side_effect = cls.web_app.reroute_local
            cls.web_app.update_response(method="get", host=API_BASE_URL, path="/api/v2/peatio/account/balances", data=FixturePeatio.BALANCES)
            cls._t_nonce_patcher = unittest.mock.patch("hummingbot.connector.exchange.peatio.peatio_exchange.get_tracking_nonce")
            cls._t_nonce_mock = cls._t_nonce_patcher.start()
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: PeatioExchange = PeatioExchange(
            ACCESS_KEY,
            API_SECRET,
            trading_pairs=["ETH-USDTERC20"]
        )
        # Need 2nd instance of market to prevent events mixing up across tests
        cls.market_2: PeatioExchange = PeatioExchange(
            ACCESS_KEY,
            API_SECRET,
            trading_pairs=["ETH-USDTERC20"]
        )
        cls.clock.add_iterator(cls.market)
        cls.clock.add_iterator(cls.market_2)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()
        if API_MOCK_ENABLED:
            cls.web_app.stop()
            cls._patcher.stop()
            cls._t_nonce_patcher.stop()

    @classmethod
    async def wait_til_ready(cls):
        while True:

            now = time.time()
            next_iteration = now // 1.0 + 1
            if cls.market.ready and cls.market_2.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../peatio_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        self.market_2_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)
            self.market_2.add_listener(event_tag, self.market_2_logger)

    def tearDown(self):
        for event_tag in self.events:
            self.market.remove_listener(event_tag, self.market_logger)
            self.market_2.remove_listener(event_tag, self.market_2_logger)
        self.market_logger = None
        self.market_2_logger = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(0.5)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def get_mock_order(self, **kwargs):
        resp = FixturePeatio.ORDER_PLACE.copy()
        resp.update(kwargs)
        return resp

    def place_order(self, is_buy, trading_pair, amount, order_type, price, nonce, get_resp=None, state="wait", market_connector=None):
        global EXCHANGE_ORDER_ID
        order_id, exch_order_id, mock_resp = None, None, None

        if API_MOCK_ENABLED:
            exch_order_id = f"PEATIO_{EXCHANGE_ORDER_ID}"
            EXCHANGE_ORDER_ID += 1
            self._t_nonce_mock.return_value = nonce
            current_time = datetime.datetime.utcnow().isoformat()
            mock_resp = self.get_mock_order(
                id=exch_order_id,
                side='buy' if is_buy else 'sell',
                ord_type="limit" if order_type.is_limit_type() else "market",
                price=str(Decimal(price)),
                avg_price=str(Decimal("0.0")),
                market=convert_to_exchange_trading_pair(trading_pair),
                created_at=str(current_time),
                updated_at=str(current_time),
                origin_volume=str(Decimal(amount)),
                state=state,
                remaining_volume=str(Decimal(amount))
            )
            self.web_app.update_response("post", API_BASE_URL, "/api/v2/peatio/market/orders", mock_resp)

        market = self.market if market_connector is None else market_connector
        if is_buy:
            order_id = market.buy(trading_pair, amount, order_type, price)
        else:
            order_id = market.sell(trading_pair, amount, order_type, price)

        if API_MOCK_ENABLED:
            response = get_resp or mock_resp
            response.update({"id": exch_order_id})
            self.web_app.update_response("get", API_BASE_URL, f"/api/v2/peatio/market/orders/{exch_order_id}", response)

        return order_id, exch_order_id

    def cancel_order(self, trading_pair, order_id, exchange_order_id, get_resp, **kwargs):
        global EXCHANGE_ORDER_ID
        if API_MOCK_ENABLED:
            resp = get_resp.copy()
            resp["id"] = exchange_order_id
            self.web_app.update_response("post", API_BASE_URL, f"/api/v2/peatio/market/orders/{exchange_order_id}/cancel", resp)
        self.market.cancel(trading_pair, order_id)
        if API_MOCK_ENABLED:
            resp = get_resp.copy()
            resp["id"] = exchange_order_id
            self.web_app.update_response("get", API_BASE_URL, f"/api/v2/peatio/market/orders/{exchange_order_id}", resp)

    def test_get_fee(self):
        limit_fee: TradeFee = self.market.get_fee("eth", "usdterc20", OrderType.LIMIT_MAKER, TradeType.BUY, Decimal("1"), Decimal("10"))
        self.assertGreater(limit_fee.percent, 0)
        self.assertEqual(len(limit_fee.flat_fees), 0)
        market_fee: TradeFee = self.market.get_fee("eth", "usdterc20", OrderType.LIMIT, TradeType.BUY, Decimal("1"))
        self.assertGreater(market_fee.percent, 0)
        self.assertEqual(len(market_fee.flat_fees), 0)
        sell_trade_fee: TradeFee = self.market.get_fee("eth", "usdterc20", OrderType.LIMIT_MAKER, TradeType.SELL, Decimal("1"), Decimal("10"))
        self.assertGreater(sell_trade_fee.percent, 0)
        self.assertEqual(len(sell_trade_fee.flat_fees), 0)

    def test_fee_overrides_config(self):
        fee_overrides_config_map["peatio_taker_fee"].value = None
        taker_fee: TradeFee = self.market.get_fee("ETH", "USDTERC20", OrderType.MARKET, TradeType.BUY, Decimal(1), Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.002"), taker_fee.percent)
        fee_overrides_config_map["peatio_taker_fee"].value = Decimal('0.1')
        taker_fee: TradeFee = self.market.get_fee("USDTERC20", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1), Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.001"), taker_fee.percent)
        fee_overrides_config_map["peatio_maker_fee"].value = None
        maker_fee: TradeFee = self.market.get_fee("USDTERC20", "ETH", OrderType.LIMIT_MAKER, TradeType.BUY, Decimal(1), Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.002"), maker_fee.percent)
        fee_overrides_config_map["peatio_maker_fee"].value = Decimal('0.5')
        maker_fee: TradeFee = self.market.get_fee("USDTERC20", "ETH", OrderType.LIMIT_MAKER, TradeType.BUY, Decimal(1), Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.005"), maker_fee.percent)

    def test_limit_makers_unfilled(self):
        if API_MOCK_ENABLED:
            return
        # TODO
        trading_pair = "ETH-USDTERC20"

        bid_price: Decimal = self.market.get_price(trading_pair, True) * Decimal("0.5")
        ask_price: Decimal = self.market.get_price(trading_pair, False) * 2
        amount: Decimal = Decimal("0.06")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price * Decimal("0.9"))
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price * Decimal("1.1"))

        order_id1, exch_order_id1 = self.place_order(True, trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_bid_price,
                                                     10001, FixturePeatio.OPEN_BUY_LIMIT_ORDER)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id1, order_created_event.order_id)

        order_id2, exch_order_id2 = self.place_order(False, trading_pair, quantized_amount, OrderType.LIMIT_MAKER, quantize_ask_price,
                                                     10002, FixturePeatio.OPEN_SELL_LIMIT_ORDER)
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id2, order_created_event.order_id)

        self.run_parallel(asyncio.sleep(1))
        if API_MOCK_ENABLED:
            resp = FixturePeatio.ORDERS_BATCH_CANCELLED.copy()
            resp["data"]["success"] = [exch_order_id1, exch_order_id2]
            self.web_app.update_response("post", API_BASE_URL, "/v1/order/orders/batchcancel", resp)
        [cancellation_results] = self.run_parallel(self.market_2.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

        # Reset the logs
        self.market_logger.clear()

    def test_limit_taker_buy(self):
        trading_pair = "ETH-USDTERC20"
        nonce = 10001

        price: Decimal = Decimal("2600.0")
        amount: Decimal = Decimal("0.06")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount, price)

        current_time = datetime.datetime.utcnow()
        trades = [
            {
                'id': 183513,
                'price': 2500.0,
                'amount': 0.04,
                'total': 100.0,
                'market': 'eth_usdterc20',
                'created_at': current_time.timestamp(),
                'taker_type': 'sell'
            },
            {
                'id': 183514,
                'price': 2600.0,
                'amount': 0.02,
                'total': 52.0,
                'market': 'eth_usdterc20',
                'created_at': current_time.timestamp(),
                'taker_type': 'sell'
            }
        ]
        mock_resp = self.get_mock_order(
            side='buy',
            ord_type="limit",
            price=str(Decimal(price)),
            avg_price=str(Decimal("2533.3333")),
            market=convert_to_exchange_trading_pair(trading_pair),
            created_at=str(current_time.isoformat()),
            updated_at=str(current_time.isoformat()),
            origin_volume=str(Decimal(amount)),
            executed_volume=str(Decimal(amount)),
            remaining_volume=str(Decimal(0)),
            state="done",
            trades=trades,
        )

        order_id, _ = self.place_order(
            is_buy=True,
            trading_pair=trading_pair,
            amount=quantized_amount,
            order_type=OrderType.LIMIT,
            price=price,
            nonce=nonce,
            get_resp=mock_resp,
            state='done'
        )

        [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        buy_order_completed_event: BuyOrderCompletedEvent = buy_order_completed_event

        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, buy_order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, buy_order_completed_event.base_asset_amount, places=4)
        self.assertEqual("ETH", buy_order_completed_event.base_asset)
        self.assertEqual("USDTERC20", buy_order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, buy_order_completed_event.base_asset_amount, places=4)
        self.assertAlmostEqual(quote_amount_traded, buy_order_completed_event.quote_asset_amount, places=4)
        self.assertGreater(buy_order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_create_limit_taker_buy(self):
        trading_pair = "ETH-USDTERC20"
        nonce = 10001
        price: Decimal = Decimal("2800.0")

        amount: Decimal = Decimal("0.06")
        order_id, _ = self.place_order(
            is_buy=True,
            trading_pair=trading_pair,
            amount=amount,
            order_type=OrderType.LIMIT,
            price=price,
            nonce=nonce,
        )

        [buy_order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        buy_order_created_event: BuyOrderCreatedEvent = buy_order_created_event

        self.assertEqual(OrderType.LIMIT, buy_order_created_event.type)
        self.assertEqual(order_id, buy_order_created_event.order_id)
        self.assertEqual(amount, buy_order_created_event.amount)
        self.assertEqual(price, buy_order_created_event.price)
        self.assertEqual(trading_pair, buy_order_created_event.trading_pair)

        self.market_logger.clear()

    def test_create_market_taker_buy(self):
        trading_pair = "ETH-USDTERC20"
        nonce = 10001
        price: Decimal = self.market.get_price(trading_pair, True)

        amount: Decimal = Decimal("0.06")
        order_id, _ = self.place_order(
            is_buy=True,
            trading_pair=trading_pair,
            amount=amount,
            order_type=OrderType.MARKET,
            price=price,
            nonce=nonce,
        )

        [buy_order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        buy_order_created_event: BuyOrderCreatedEvent = buy_order_created_event

        self.assertEqual(OrderType.MARKET, buy_order_created_event.type)
        self.assertEqual(order_id, buy_order_created_event.order_id)
        self.assertEqual(amount, buy_order_created_event.amount)
        self.assertEqual(price, buy_order_created_event.price)
        self.assertEqual(trading_pair, buy_order_created_event.trading_pair)

        self.market_logger.clear()

    def test_create_market_taker_sell(self):
        trading_pair = "ETH-USDTERC20"
        nonce = 10001
        price: Decimal = Decimal("3800.0")

        amount: Decimal = Decimal("0.06")
        order_id, _ = self.place_order(
            is_buy=False,
            trading_pair=trading_pair,
            amount=amount,
            order_type=OrderType.MARKET,
            price=price,
            nonce=nonce,
        )
        [sell_order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        sell_order_created_event: BuyOrderCreatedEvent = sell_order_created_event

        self.assertEqual(OrderType.MARKET, sell_order_created_event.type)
        self.assertEqual(order_id, sell_order_created_event.order_id)
        self.assertEqual(amount, sell_order_created_event.amount)
        self.assertEqual(price, sell_order_created_event.price)
        self.assertEqual(trading_pair, sell_order_created_event.trading_pair)

        self.market_logger.clear()

    def test_create_limit_order_sell(self):
        trading_pair = "ETH-USDTERC20"
        nonce = 10001
        price: Decimal = Decimal("3800.0")

        amount: Decimal = Decimal("0.06")
        order_id, _ = self.place_order(
            is_buy=False,
            trading_pair=trading_pair,
            amount=amount,
            order_type=OrderType.LIMIT,
            price=price,
            nonce=nonce,
        )
        [sell_order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        sell_order_created_event: BuyOrderCreatedEvent = sell_order_created_event

        self.assertEqual(OrderType.LIMIT, sell_order_created_event.type)
        self.assertEqual(order_id, sell_order_created_event.order_id)
        self.assertEqual(amount, sell_order_created_event.amount)
        self.assertEqual(price, sell_order_created_event.price)
        self.assertEqual(trading_pair, sell_order_created_event.trading_pair)

        self.market_logger.clear()

    def test_limit_taker_sell(self):
        trading_pair = "ETH-USDTERC20"

        nonce = 10098
        price: Decimal = Decimal("4000")
        amount: Decimal = Decimal("0.06")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount, price=price)

        current_time = datetime.datetime.utcnow()
        trades = [
            {
                'id': 183513,
                'price': 4000,
                'amount': 0.04,
                'total': 160.0,
                'market': 'eth_usdterc20',
                'created_at': current_time.timestamp(),
                'taker_type': 'buy'
            },
            {
                'id': 183514,
                'price': 4200,
                'amount': 0.02,
                'total': 84.0,
                'market': 'eth_usdterc20',
                'created_at': current_time.timestamp(),
                'taker_type': 'buy'
            }
        ]
        mock_resp = self.get_mock_order(
            side='sell',
            ord_type="limit",
            price=str(Decimal(price)),
            avg_price=str(Decimal("4066.6666")),
            market=convert_to_exchange_trading_pair(trading_pair),
            created_at=str(current_time.isoformat()),
            updated_at=str(current_time.isoformat()),
            origin_volume=str(Decimal(amount)),
            executed_volume=str(Decimal(amount)),
            remaining_volume=str(Decimal(0)),
            state="done",
            trades=trades,
        )

        order_id, _ = self.place_order(
            is_buy=False,
            trading_pair=trading_pair,
            amount=amount,
            order_type=OrderType.LIMIT,
            price=price,
            nonce=nonce,
            get_resp=mock_resp
        )
        [sell_order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        sell_order_completed_event: SellOrderCompletedEvent = sell_order_completed_event

        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, sell_order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, sell_order_completed_event.base_asset_amount)
        self.assertEqual("ETH", sell_order_completed_event.base_asset)
        self.assertEqual("USDTERC20", sell_order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, sell_order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, sell_order_completed_event.quote_asset_amount)
        self.assertGreater(sell_order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_cancel_order(self):
        trading_pair = "ETH-USDTERC20"

        nonce = 10001
        amount: Decimal = Decimal("0.06")

        current_bid_price: Decimal = self.market.get_price(trading_pair, True)
        bid_price: Decimal = current_bid_price - Decimal("0.01") * current_bid_price
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount, price=quantize_bid_price)

        order_id, exch_order_id = self.place_order(
            is_buy=True,
            trading_pair=trading_pair,
            amount=quantized_amount,
            order_type=OrderType.LIMIT,
            price=quantize_bid_price,
            nonce=nonce
        )
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))

        current_time = datetime.datetime.utcnow()
        mock_resp = self.get_mock_order(
            side='buy',
            ord_type="limit",
            price=str(Decimal(quantize_bid_price)),
            avg_price=str(Decimal("0")),
            market=convert_to_exchange_trading_pair(trading_pair),
            created_at=str(current_time.isoformat()),
            updated_at=str(current_time.isoformat()),
            origin_volume=str(Decimal(amount)),
            executed_volume=str(Decimal(0)),
            remaining_volume=str(Decimal(amount)),
            state="cancel",
            trades=[],
        )

        self.cancel_order(trading_pair, order_id, exch_order_id, mock_resp)
        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event
        self.assertEqual(order_cancelled_event.order_id, order_id)

    def test_cancel_all(self):
        trading_pair = "ETH-USDTERC20"

        bid_price: Decimal = self.market_2.get_price(trading_pair, True) * Decimal("0.5")
        ask_price: Decimal = bid_price * 4
        amount: Decimal = Decimal("0.06")
        quantized_amount: Decimal = self.market_2.quantize_order_amount(trading_pair, amount, price=bid_price)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.market_2.quantize_order_price(trading_pair, bid_price * Decimal("0.9"))
        quantize_ask_price: Decimal = self.market_2.quantize_order_price(trading_pair, ask_price * Decimal("1.1"))

        _, exch_order_id1 = self.place_order(
            is_buy=True,
            trading_pair=trading_pair,
            amount=quantized_amount,
            order_type=OrderType.LIMIT,
            price=quantize_bid_price,
            nonce=1001,
            market_connector=self.market_2
        )
        _, exch_order_id2 = self.place_order(
            is_buy=False,
            trading_pair=trading_pair,
            amount=quantized_amount,
            order_type=OrderType.LIMIT,
            price=quantize_ask_price,
            nonce=1002,
            market_connector=self.market_2
        )

        self.run_parallel(asyncio.sleep(30))
        if API_MOCK_ENABLED:
            current_time = datetime.datetime.utcnow()
            mock_resp = [
                self.get_mock_order(
                    side='buy',
                    ord_type="limit",
                    price=str(Decimal(quantize_bid_price)),
                    avg_price=str(Decimal("0")),
                    market=convert_to_exchange_trading_pair(trading_pair),
                    created_at=str(current_time.isoformat()),
                    updated_at=str(current_time.isoformat()),
                    origin_volume=str(Decimal(quantized_amount)),
                    executed_volume=str(Decimal(0)),
                    remaining_volume=str(Decimal(quantized_amount)),
                    state="cancel",
                    trades=[],
                    id=exch_order_id1,
                ),
                self.get_mock_order(
                    side='sell',
                    ord_type="limit",
                    price=str(Decimal(quantize_ask_price)),
                    avg_price=str(Decimal("0")),
                    market=convert_to_exchange_trading_pair(trading_pair),
                    created_at=str(current_time.isoformat()),
                    updated_at=str(current_time.isoformat()),
                    origin_volume=str(Decimal(quantized_amount)),
                    executed_volume=str(Decimal(0)),
                    remaining_volume=str(Decimal(quantized_amount)),
                    state="cancel",
                    trades=[],
                    id=exch_order_id2,
                )
            ]

            self.web_app.update_response("post", API_BASE_URL, "/api/v2/peatio/market/orders/cancel", mock_resp)
        [cancellation_results] = self.run_parallel(self.market_2.cancel_all(5))
        self.assertGreater(len(cancellation_results), 0)
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_orders_saving_and_restoration(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "ETH-USDTERC20"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            self.assertEqual(0, len(self.market.tracking_states))

            # Try to put limit buy order for 0.04 ETH, and watch for order creation event.
            current_bid_price: Decimal = self.market.get_price(trading_pair, True)
            bid_price: Decimal = current_bid_price * Decimal("0.8")
            quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)

            amount: Decimal = Decimal("0.06")
            quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount, price=quantize_bid_price)

            order_id, exch_order_id = self.place_order(
                is_buy=True,
                trading_pair=trading_pair,
                amount=quantized_amount,
                order_type=OrderType.LIMIT,
                price=quantize_bid_price,
                nonce=10001,
            )
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
            self.market: PeatioExchange = PeatioExchange(
                peatio_access_key=ACCESS_KEY,
                peatio_secret_key=API_SECRET,
                trading_pairs=["ETH-USDTERC20", "BTC-USDTERC20"]
            )
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

            current_time = datetime.datetime.utcnow()
            mock_resp = self.get_mock_order(
                id="PEATIO_20001",
                side="buy",
                ord_type="limit",
                price=str(Decimal(quantize_bid_price)),
                avg_price=str(Decimal("0")),
                market=convert_to_exchange_trading_pair(trading_pair),
                created_at=str(current_time.isoformat()),
                updated_at=str(current_time.isoformat()),
                origin_volume=str(Decimal(quantized_amount)),
                executed_volume=str(Decimal(0)),
                remaining_volume=str(Decimal(quantized_amount)),
                state="cancel",
                trades=[],
            )

            self.cancel_order(
                trading_pair=trading_pair,
                order_id=order_id,
                exchange_order_id=exch_order_id,
                get_resp=mock_resp
            )
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
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "ETH-USDTERC20"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy 0.04 ETH from the exchange, and watch for completion event.
            current_time = datetime.datetime.utcnow()

            price: Decimal = self.market.get_price(trading_pair, True)
            amount: Decimal = Decimal("0.06")

            trades = [
                {
                    'id': 183515,
                    'price': str(price),
                    'amount': 0.06,
                    'total': str(Decimal("0.06") * price),
                    'market': 'eth_usdterc20',
                    'created_at': current_time.timestamp(),
                    'taker_type': 'sell'
                },
            ]

            mock_resp = self.get_mock_order(
                side='buy',
                ord_type="limit",
                price=str(Decimal(price)),
                avg_price=str(Decimal(price)),
                market=convert_to_exchange_trading_pair(trading_pair),
                created_at=str(current_time.isoformat()),
                updated_at=str(current_time.isoformat()),
                origin_volume=str(Decimal(amount)),
                executed_volume=str(Decimal(amount)),
                remaining_volume=str(Decimal(0)),
                state="done",
                trades=trades,
            )

            order_id, exch_order_id = self.place_order(
                is_buy=True,
                trading_pair=trading_pair,
                amount=amount,
                order_type=OrderType.LIMIT,
                price=price,
                nonce=10001,
                get_resp=mock_resp
            )

            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logs
            self.market_logger.clear()

            # Try to sell back the same amount of ETH to the exchange, and watch for completion event.
            amount = buy_order_completed_event.base_asset_amount

            trades = [
                {
                    'id': 183513,
                    'price': str(price),
                    'amount': 0.06,
                    'total': str(Decimal("0.06") * price),
                    'market': 'eth_usdterc20',
                    'created_at': current_time.timestamp(),
                    'taker_type': 'buy'
                },
            ]
            mock_resp = self.get_mock_order(
                side='sell',
                ord_type="limit",
                price=str(Decimal(price)),
                avg_price=str(Decimal(price)),
                market=convert_to_exchange_trading_pair(trading_pair),
                created_at=str(current_time.isoformat()),
                updated_at=str(current_time.isoformat()),
                origin_volume=str(Decimal(amount)),
                executed_volume=str(Decimal(amount)),
                remaining_volume=str(Decimal(0)),
                state="done",
                trades=trades,
            )

            order_id, exch_order_id = self.place_order(
                is_buy=False,
                trading_pair=trading_pair,
                amount=amount,
                order_type=OrderType.LIMIT,
                price=price,
                nonce=10002,
                get_resp=mock_resp
            )

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

    def test_update_last_prices(self):
        # This is basic test to see if order_book last_trade_price is initiated and updated.
        for order_book in self.market.order_books.values():
            for _ in range(5):
                self.ev_loop.run_until_complete(asyncio.sleep(1))
                print(order_book.last_trade_price)
                self.assertFalse(math.isnan(order_book.last_trade_price))

    def test_pair_convesion(self):
        if API_MOCK_ENABLED:
            return
        for pair in self.market.trading_rules:
            exchange_pair = convert_to_exchange_trading_pair(pair)
            self.assertTrue(exchange_pair in self.market.order_books)


if __name__ == "__main__":
    unittest.main()
