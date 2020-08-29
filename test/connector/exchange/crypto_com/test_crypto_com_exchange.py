from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
import asyncio
import conf
import logging
from decimal import Decimal
import unittest
import contextlib
import time
import os
from typing import List
from unittest import mock

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.core.utils.async_utils import safe_gather, safe_ensure_future
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.connector.exchange.crypto_com.crypto_com_exchange import CryptoComExchange
from hummingbot.connector.exchange.crypto_com.crypto_com_constants import WSS_PUBLIC_URL, WSS_PRIVATE_URL
from test.integration.humming_web_app import HummingWebApp
from test.integration.humming_ws_server import HummingWsServerFactory
from . import fixture

logging.basicConfig(level=METRICS_LOG_LEVEL)
API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
API_KEY = "XXX" if API_MOCK_ENABLED else conf.crypto_com_api_key
API_SECRET = "YYY" if API_MOCK_ENABLED else conf.crypto_com_secret_key
BASE_API_URL = "api.crypto.com"


class CryptoComExchangeUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderFailure
    ]
    connector: CryptoComExchange
    event_logger: EventLogger
    trading_pair = "BTC-USDT"
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        global MAINNET_RPC_URL

        cls.ev_loop = asyncio.get_event_loop()

        if API_MOCK_ENABLED:
            cls.web_app = HummingWebApp.get_instance()
            cls.web_app.add_host_to_mock(BASE_API_URL, [])
            cls.web_app.start()
            cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
            cls._patcher = mock.patch("aiohttp.client.URL")
            cls._url_mock = cls._patcher.start()
            cls._url_mock.side_effect = cls.web_app.reroute_local
            cls.web_app.update_response("get", BASE_API_URL, "/v2/public/get-ticker", fixture.TICKERS)
            cls.web_app.update_response("get", BASE_API_URL, "/v2/public/get-instruments", fixture.INSTRUMENTS)
            cls.web_app.update_response("get", BASE_API_URL, "/v2/public/get-book", fixture.GET_BOOK)
            cls.web_app.update_response("post", BASE_API_URL, "/v2/private/get-account-summary", fixture.BALANCES)
            cls.web_app.update_response("post", BASE_API_URL, "/v2/private/cancel-order", fixture.CANCEL)

            HummingWsServerFactory.start_new_server(WSS_PRIVATE_URL)
            HummingWsServerFactory.start_new_server(WSS_PUBLIC_URL)
            cls._ws_patcher = unittest.mock.patch("websockets.connect", autospec=True)
            cls._ws_mock = cls._ws_patcher.start()
            cls._ws_mock.side_effect = HummingWsServerFactory.reroute_ws_connect

        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.connector: CryptoComExchange = CryptoComExchange(
            balance_limits={},
            fee_estimates={True: Decimal("0.001"), False: Decimal("0.002")},
            crypto_com_api_key=API_KEY,
            crypto_com_api_secret=API_SECRET,
            trading_pairs=[cls.trading_pair],
            trading_required=True
        )
        print("Initializing CryptoCom market... this will take about a minute.")
        cls.clock.add_iterator(cls.connector)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()
        if API_MOCK_ENABLED:
            cls.web_app.stop()
            cls._patcher.stop()
            cls._ws_patcher.stop()

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if cls.connector.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../connector_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.event_logger = EventLogger()
        for event_tag in self.events:
            self.connector.add_listener(event_tag, self.event_logger)

    def tearDown(self):
        for event_tag in self.events:
            self.connector.remove_listener(event_tag, self.event_logger)
        self.event_logger = None

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

    def test_estimate_fee(self):
        maker_fee = self.connector.estimate_fee(True)
        self.assertEqual(maker_fee, Decimal("0.001"))
        taker_fee = self.connector.estimate_fee(False)
        self.assertEqual(taker_fee, Decimal("0.002"))

    def _place_order(self, is_buy, amount, order_type, price, nonce, get_order_fixture=None,
                     ws_trade_fixture=None, ws_order_fixture=None) -> str:
        if API_MOCK_ENABLED:
            self.web_app.update_response("post", BASE_API_URL, "/v2/private/create-order", fixture.PLACE_ORDER)
        if is_buy:
            cl_order_id = self.connector.buy(self.trading_pair, amount, order_type, price)
        else:
            cl_order_id = self.connector.sell(self.trading_pair, amount, order_type, price)
        if API_MOCK_ENABLED:
            if get_order_fixture is not None:
                get_order_fixture["result"]["order_info"]["client_oid"] = cl_order_id
                self.web_app.update_response("post", BASE_API_URL, "/v2/private/get-order-detail", get_order_fixture)
            if ws_trade_fixture is not None:
                HummingWsServerFactory.send_json_threadsafe(WSS_PRIVATE_URL, ws_trade_fixture, delay=0.1)
            if ws_order_fixture is not None:
                HummingWsServerFactory.send_json_threadsafe(WSS_PRIVATE_URL, ws_order_fixture, delay=0.1)
        return cl_order_id

    def test_buy_and_sell(self):
        price = self.connector.get_price(self.trading_pair, True) * Decimal("1.05")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0001"))

        order_id = self._place_order(True, amount, OrderType.LIMIT, price, 10001, None,
                                     fixture.WS_TRADE)
        [order_completed_event] = self.run_parallel(self.event_logger.wait_for(BuyOrderCompletedEvent))
        self.ev_loop.run_until_complete(asyncio.sleep(2))
        trade_events = [t for t in self.event_logger.event_log if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(amount, order_completed_event.base_asset_amount)
        self.assertEqual("BTC", order_completed_event.base_asset)
        self.assertEqual("USDT", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.event_logger.event_log]))

        # Reset the logs
        self.event_logger.clear()

        # Try to sell back the same amount to the exchange, and watch for completion event.
        price = self.connector.get_price(self.trading_pair, True) * Decimal("0.95")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0001"))
        order_id = self._place_order(False, amount, OrderType.LIMIT, price, 10002, None,
                                     fixture.WS_TRADE)
        [order_completed_event] = self.run_parallel(self.event_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.event_logger.event_log
                        if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(amount, order_completed_event.base_asset_amount)
        self.assertEqual("BTC", order_completed_event.base_asset)
        self.assertEqual("USDT", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.event_logger.event_log]))

    def test_limit_makers_unfilled(self):
        price = self.connector.get_price(self.trading_pair, True) * Decimal("0.8")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0001"))

        # order_id = self.connector.buy(self.trading_pair, amount, OrderType.LIMIT_MAKER, price)
        cl_order_id = self._place_order(True, amount, OrderType.LIMIT_MAKER, price, 10001, fixture.UNFILLED_ORDER)
        [order_created_event] = self.run_parallel(self.event_logger.wait_for(BuyOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(cl_order_id, order_created_event.order_id)

        price = self.connector.get_price(self.trading_pair, True) * Decimal("1.2")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0001"))

        cl_order_id = self._place_order(False, amount, OrderType.LIMIT_MAKER, price, 10002, fixture.UNFILLED_ORDER)
        [order_created_event] = self.run_parallel(self.event_logger.wait_for(SellOrderCreatedEvent))
        order_created_event: SellOrderCreatedEvent = order_created_event
        self.assertEqual(cl_order_id, order_created_event.order_id)

        self.run_parallel(self.connector.cancel_all(5))
