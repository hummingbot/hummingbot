import os
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
import logging
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
import asyncio
import json
import contextlib
import time
import unittest
from unittest import mock
import conf
from decimal import Decimal
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
from hummingbot.core.mock_api.mock_web_server import MockWebServer
from hummingbot.core.mock_api.mock_web_socket_server import MockWebSocketServerFactory
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent, SellOrderCreatedEvent,
    TradeType,
    BuyOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCompletedEvent,
    MarketOrderFailureEvent,
    OrderType
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.connector.exchange.beaxy.beaxy_exchange import BeaxyExchange
from hummingbot.connector.exchange.beaxy.beaxy_constants import BeaxyConstants
from typing import (
    List,
)
from test.connector.exchange.beaxy.fixture_beaxy import FixtureBeaxy

logging.basicConfig(level=METRICS_LOG_LEVEL)
API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
API_KEY = "XXX" if API_MOCK_ENABLED else conf.beaxy_api_key
API_SECRET = "YYY" if API_MOCK_ENABLED else conf.beaxy_secret_key


def _transform_raw_message_patch(self, msg):
    return json.loads(msg)


PUBLIC_API_BASE_URL = "services.beaxy.com"
PRIVET_API_BASE_URL = "tradewith.beaxy.com"


class BeaxyExchangeUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderFailure,
    ]
    market: BeaxyExchange
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):

        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()

        if API_MOCK_ENABLED:

            cls.web_app = MockWebServer.get_instance()
            cls.web_app.add_host_to_mock(PRIVET_API_BASE_URL, [])
            cls.web_app.add_host_to_mock(PUBLIC_API_BASE_URL, [])
            cls.web_app.start()
            cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
            cls._patcher = mock.patch("aiohttp.client.URL")
            cls._url_mock = cls._patcher.start()
            cls._url_mock.side_effect = cls.web_app.reroute_local
            cls.web_app.update_response("get", PUBLIC_API_BASE_URL, "/api/v2/symbols", FixtureBeaxy.SYMBOLS)
            cls.web_app.update_response("get", PUBLIC_API_BASE_URL, "/api/v2/symbols/DASHBTC/book",
                                        FixtureBeaxy.TRADE_BOOK)
            cls.web_app.update_response("get", PUBLIC_API_BASE_URL, "/api/v2/symbols/DASHBTC/rate",
                                        FixtureBeaxy.EXCHANGE_RATE)
            cls.web_app.update_response("get", PRIVET_API_BASE_URL, "/api/v2/health",
                                        FixtureBeaxy.HEALTH)
            cls.web_app.update_response("get", PRIVET_API_BASE_URL, "/api/v2/wallets",
                                        FixtureBeaxy.BALANCES)
            cls.web_app.update_response("get", PRIVET_API_BASE_URL, "/api/v2/tradingsettings",
                                        FixtureBeaxy.TRADE_SETTINGS)
            cls.web_app.update_response("get", PRIVET_API_BASE_URL, "/api/v2/orders/open",
                                        FixtureBeaxy.ORDERS_OPEN_EMPTY)
            cls.web_app.update_response("get", PRIVET_API_BASE_URL, "/api/v2/orders/closed",
                                        FixtureBeaxy.ORDERS_CLOSED_EMPTY)

            cls._t_nonce_patcher = unittest.mock.patch(
                "hummingbot.connector.exchange.beaxy.beaxy_exchange.get_tracking_nonce")
            cls._t_nonce_mock = cls._t_nonce_patcher.start()

            MockWebSocketServerFactory.url_host_only = True
            MockWebSocketServerFactory.start_new_server(BeaxyConstants.TradingApi.WS_BASE_URL)
            MockWebSocketServerFactory.start_new_server(BeaxyConstants.PublicApi.WS_BASE_URL)

            cls._ws_patcher = unittest.mock.patch("websockets.connect", autospec=True)
            cls._ws_mock = cls._ws_patcher.start()
            cls._ws_mock.side_effect = MockWebSocketServerFactory.reroute_ws_connect

            cls._auth_confirm_patcher = unittest.mock.patch(
                "hummingbot.connector.exchange.beaxy.beaxy_auth.BeaxyAuth._BeaxyAuth__login_confirm")
            cls._auth_confirm_mock = cls._auth_confirm_patcher.start()
            cls._auth_session_patcher = unittest.mock.patch(
                "hummingbot.connector.exchange.beaxy.beaxy_auth.BeaxyAuth._BeaxyAuth__get_session_data")
            cls._auth_session_mock = cls._auth_session_patcher.start()
            cls._auth_session_mock.return_value = {"sign_key": 123, "session_id": '123'}
            cls._auth_headers_patcher = unittest.mock.patch(
                "hummingbot.connector.exchange.beaxy.beaxy_auth.BeaxyAuth.get_token")
            cls._auth_headers_mock = cls._auth_headers_patcher.start()
            cls._auth_headers_mock.return_value = '123'
            cls._auth_poll_patcher = unittest.mock.patch(
                "hummingbot.connector.exchange.beaxy.beaxy_auth.BeaxyAuth._auth_token_polling_loop")
            cls._auth_poll_mock = cls._auth_poll_patcher.start()

        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: BeaxyExchange = BeaxyExchange(
            API_KEY, API_SECRET,
            trading_pairs=["DASH-BTC"]
        )

        if API_MOCK_ENABLED:
            async def mock_status_polling_task():
                pass

            # disable status polling as it will make orders update inconsistent from mock view
            cls.market._status_polling_task = asyncio.ensure_future(mock_status_polling_task())
            cls.ev_loop.run_until_complete(cls.market._update_balances())

        print("Initializing Beaxy market... this will take about a minute.")
        cls.clock.add_iterator(cls.market)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

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

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self.clock.run_til(next_iteration)
        return future.result()

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../beaxy_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)

    def test_balances(self):
        balances = self.market.get_all_balances()
        self.assertGreater(len(balances), 0)

    def test_get_fee(self):
        limit_fee: AddedToCostTradeFee = self.market.get_fee("ETH", "USDC", OrderType.LIMIT, TradeType.BUY, 1, 1)
        self.assertGreater(limit_fee.percent, 0)
        self.assertEqual(len(limit_fee.flat_fees), 0)
        market_fee: AddedToCostTradeFee = self.market.get_fee("ETH", "USDC", OrderType.MARKET, TradeType.BUY, 1)
        self.assertGreater(market_fee.percent, 0)
        self.assertEqual(len(market_fee.flat_fees), 0)

    def test_fee_overrides_config(self):
        fee_overrides_config_map["beaxy_taker_fee"].value = None
        taker_fee: AddedToCostTradeFee = self.market.get_fee("BTC", "ETH", OrderType.MARKET, TradeType.BUY, Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.0025"), taker_fee.percent)
        fee_overrides_config_map["beaxy_taker_fee"].value = Decimal('0.2')
        taker_fee: AddedToCostTradeFee = self.market.get_fee("BTC", "ETH", OrderType.MARKET, TradeType.BUY, Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.002"), taker_fee.percent)
        fee_overrides_config_map["beaxy_maker_fee"].value = None
        maker_fee: AddedToCostTradeFee = self.market.get_fee("BTC", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.002"), maker_fee.percent)
        fee_overrides_config_map["beaxy_maker_fee"].value = Decimal('0.75')
        maker_fee: AddedToCostTradeFee = self.market.get_fee("BTC", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                             Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.002"), maker_fee.percent)

    def place_order(self, is_buy, trading_pair, amount, order_type, price, ws_resps=[]):
        global EXCHANGE_ORDER_ID
        order_id, exch_order_id = None, None

        if is_buy:
            order_id = self.market.buy(trading_pair, amount, order_type, price)
        else:
            order_id = self.market.sell(trading_pair, amount, order_type, price)
        if API_MOCK_ENABLED:
            for delay, ws_resp in ws_resps:
                MockWebSocketServerFactory.send_str_threadsafe(BeaxyConstants.TradingApi.WS_BASE_URL, ws_resp, delay=delay)
        return order_id, exch_order_id

    def cancel_order(self, trading_pair, order_id, exch_order_id):
        self.market.cancel(trading_pair, order_id)

    def test_limit_buy(self):

        if API_MOCK_ENABLED:
            self.web_app.update_response("post", PRIVET_API_BASE_URL, "/api/v2/orders",
                                         FixtureBeaxy.TEST_LIMIT_BUY_ORDER)

        amount: Decimal = Decimal("0.01")

        self.assertGreater(self.market.get_balance("BTC"), 0.00005)
        trading_pair = "DASH-BTC"

        price: Decimal = self.market.get_price(trading_pair, True) * Decimal(1.1)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id, _ = self.place_order(
            True, trading_pair, quantized_amount, OrderType.LIMIT, price,
            [(3, FixtureBeaxy.TEST_LIMIT_BUY_WS_ORDER_CREATED), (5, FixtureBeaxy.TEST_LIMIT_BUY_WS_ORDER_COMPLETED)]
        )
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("DASH", order_completed_event.base_asset)
        self.assertEqual("BTC", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_limit_sell(self):

        if API_MOCK_ENABLED:
            self.web_app.update_response("post", PRIVET_API_BASE_URL, "/api/v2/orders",
                                         FixtureBeaxy.TEST_LIMIT_SELL_ORDER)

        trading_pair = "DASH-BTC"
        self.assertGreater(self.market.get_balance("DASH"), 0.01)

        price: Decimal = self.market.get_price(trading_pair, False) * Decimal(0.9)
        amount: Decimal = Decimal("0.01")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id, _ = self.place_order(
            False, trading_pair, quantized_amount, OrderType.LIMIT, price,
            [(3, FixtureBeaxy.TEST_LIMIT_SELL_WS_ORDER_CREATED), (5, FixtureBeaxy.TEST_LIMIT_SELL_WS_ORDER_COMPLETED)]
        )
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.market_logger.event_log if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("DASH", order_completed_event.base_asset)
        self.assertEqual("BTC", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_limit_maker_rejections(self):
        if API_MOCK_ENABLED:
            return
        trading_pair = "DASH-BTC"

        # Try to put a buy limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.market.get_price(trading_pair, True) * Decimal('1.02')
        price: Decimal = self.market.quantize_order_price(trading_pair, price)
        amount = self.market.quantize_order_amount(trading_pair, 1)

        order_id = self.market.buy(trading_pair, amount, OrderType.LIMIT_MAKER, price)
        [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

        self.market_logger.clear()

        # Try to put a sell limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.market.get_price(trading_pair, True) * Decimal('0.98')
        price: Decimal = self.market.quantize_order_price(trading_pair, price)
        amount = self.market.quantize_order_amount(trading_pair, 1)

        order_id = self.market.sell(trading_pair, amount, OrderType.LIMIT_MAKER, price)
        [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

    def test_limit_makers_unfilled(self):

        if API_MOCK_ENABLED:
            self.web_app.update_response("post", PRIVET_API_BASE_URL, "/api/v2/orders",
                                         FixtureBeaxy.TEST_UNFILLED_ORDER1)

        self.assertGreater(self.market.get_balance("BTC"), 0.00005)
        trading_pair = "DASH-BTC"

        current_bid_price: Decimal = self.market.get_price(trading_pair, True) * Decimal('0.8')
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, current_bid_price)
        bid_amount: Decimal = Decimal('0.01')
        quantized_bid_amount: Decimal = self.market.quantize_order_amount(trading_pair, bid_amount)

        current_ask_price: Decimal = self.market.get_price(trading_pair, False)
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, current_ask_price)
        ask_amount: Decimal = Decimal('0.01')
        quantized_ask_amount: Decimal = self.market.quantize_order_amount(trading_pair, ask_amount)

        order_id1, exch_order_id_1 = self.place_order(
            True, trading_pair, quantized_bid_amount, OrderType.LIMIT, quantize_bid_price,
            [(3, FixtureBeaxy.TEST_UNFILLED_ORDER1_WS_ORDER_CREATED)]
        )
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id1, order_created_event.order_id)

        if API_MOCK_ENABLED:
            self.web_app.update_response("post", PRIVET_API_BASE_URL, "/api/v2/orders",
                                         FixtureBeaxy.TEST_UNFILLED_ORDER2)

        order_id2, exch_order_id_2 = self.place_order(
            False, trading_pair, quantized_ask_amount, OrderType.LIMIT, quantize_ask_price,
            [(3, FixtureBeaxy.TEST_UNFILLED_ORDER2_WS_ORDER_CREATED)]
        )
        [order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        order_created_event: BuyOrderCreatedEvent = order_created_event
        self.assertEqual(order_id2, order_created_event.order_id)

        if API_MOCK_ENABLED:
            MockWebSocketServerFactory.send_str_threadsafe(BeaxyConstants.TradingApi.WS_BASE_URL,
                                                           FixtureBeaxy.TEST_UNFILLED_ORDER1_WS_ORDER_CANCELED, delay=3)
            MockWebSocketServerFactory.send_str_threadsafe(BeaxyConstants.TradingApi.WS_BASE_URL,
                                                           FixtureBeaxy.TEST_UNFILLED_ORDER2_WS_ORDER_CANCELED, delay=3)

            self.web_app.update_response("delete", PRIVET_API_BASE_URL, "/api/v1/orders", "")

        self.run_parallel(asyncio.sleep(1))
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_market_buy(self):

        if API_MOCK_ENABLED:
            self.web_app.update_response("post", PRIVET_API_BASE_URL, "/api/v2/orders",
                                         FixtureBeaxy.TEST_MARKET_BUY_ORDER)

        amount: Decimal = Decimal("0.01")

        self.assertGreater(self.market.get_balance("BTC"), 0.00005)
        trading_pair = "DASH-BTC"

        price: Decimal = self.market.get_price(trading_pair, True)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id, _ = self.place_order(
            True, trading_pair, quantized_amount, OrderType.MARKET, price,
            [(3, FixtureBeaxy.TEST_MARKET_BUY_WS_ORDER_CREATED), (5, FixtureBeaxy.TEST_MARKET_BUY_WS_ORDER_COMPLETED)]
        )
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("DASH", order_completed_event.base_asset)
        self.assertEqual("BTC", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_market_sell(self):

        if API_MOCK_ENABLED:
            self.web_app.update_response("post", PRIVET_API_BASE_URL, "/api/v2/orders",
                                         FixtureBeaxy.TEST_MARKET_SELL_ORDER)

        trading_pair = "DASH-BTC"
        self.assertGreater(self.market.get_balance("DASH"), 0.01)

        price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = Decimal("0.01")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id, _ = self.place_order(
            False, trading_pair, quantized_amount, OrderType.MARKET, price,
            [(3, FixtureBeaxy.TEST_MARKET_SELL_WS_ORDER_CREATED), (5, FixtureBeaxy.TEST_MARKET_SELL_WS_ORDER_COMPLETED)]
        )
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.market_logger.event_log if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertAlmostEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("DASH", order_completed_event.base_asset)
        self.assertEqual("BTC", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))
        # Reset the logs
        self.market_logger.clear()

    def test_cancel_order(self):

        if API_MOCK_ENABLED:
            self.web_app.update_response("post", PRIVET_API_BASE_URL, "/api/v2/orders",
                                         FixtureBeaxy.TEST_CANCEL_BUY_ORDER)

            self.web_app.update_response("delete", PRIVET_API_BASE_URL, "/api/v2/orders/open/435118B0-A7F7-40D2-A409-820E8FC342A2", '')

        amount: Decimal = Decimal("0.01")

        self.assertGreater(self.market.get_balance("BTC"), 0.00005)
        trading_pair = "DASH-BTC"

        # make worst price so order wont be executed
        price: Decimal = self.market.get_price(trading_pair, True) * Decimal('0.5')
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        order_id, exch_order_id = self.place_order(
            True, trading_pair, quantized_amount, OrderType.LIMIT, price,
            [(3, FixtureBeaxy.TEST_CANCEL_BUY_WS_ORDER_COMPLETED)]
        )
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))

        if API_MOCK_ENABLED:
            MockWebSocketServerFactory.send_str_threadsafe(BeaxyConstants.TradingApi.WS_BASE_URL,
                                                           FixtureBeaxy.TEST_CANCEL_BUY_WS_ORDER_CANCELED, delay=3)

        self.cancel_order(trading_pair, order_id, exch_order_id)
        [order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event
        self.assertEqual(order_cancelled_event.order_id, order_id)

    def test_cancel_all(self):

        if API_MOCK_ENABLED:
            self.web_app.update_response("delete", PRIVET_API_BASE_URL, "/api/v2/orders/open/435118B0-A7F7-40D2-A409-820E8FC342A2", '')

        self.assertGreater(self.market.get_balance("BTC"), 0.00005)
        self.assertGreater(self.market.get_balance("DASH"), 0.01)
        trading_pair = "DASH-BTC"

        # make worst price so order wont be executed
        current_bid_price: Decimal = self.market.get_price(trading_pair, True) * Decimal('0.5')
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, current_bid_price)
        bid_amount: Decimal = Decimal('0.01')
        quantized_bid_amount: Decimal = self.market.quantize_order_amount(trading_pair, bid_amount)

        # make worst price so order wont be executed
        current_ask_price: Decimal = self.market.get_price(trading_pair, False) * Decimal('2')
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, current_ask_price)
        ask_amount: Decimal = Decimal('0.01')
        quantized_ask_amount: Decimal = self.market.quantize_order_amount(trading_pair, ask_amount)

        if API_MOCK_ENABLED:
            self.web_app.update_response("post", PRIVET_API_BASE_URL, "/api/v2/orders",
                                         FixtureBeaxy.TEST_CANCEL_ALL_ORDER1)

        _, exch_order_id_1 = self.place_order(True, trading_pair, quantized_bid_amount, OrderType.LIMIT_MAKER,
                                              quantize_bid_price)

        if API_MOCK_ENABLED:
            self.web_app.update_response("post", PRIVET_API_BASE_URL, "/api/v2/orders",
                                         FixtureBeaxy.TEST_CANCEL_ALL_ORDER2)

        _, exch_order_id_2 = self.place_order(False, trading_pair, quantized_ask_amount, OrderType.LIMIT_MAKER,
                                              quantize_ask_price)
        self.run_parallel(asyncio.sleep(1))

        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))

        if API_MOCK_ENABLED:
            MockWebSocketServerFactory.send_str_threadsafe(BeaxyConstants.TradingApi.WS_BASE_URL,
                                                           FixtureBeaxy.TEST_CANCEL_BUY_WS_ORDER1_CANCELED, delay=3)
            MockWebSocketServerFactory.send_str_threadsafe(BeaxyConstants.TradingApi.WS_BASE_URL,
                                                           FixtureBeaxy.TEST_CANCEL_BUY_WS_ORDER2_CANCELED, delay=3)

        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_cancel_empty(self):
        trading_pair = "DASH-BTC"
        self.cancel_order(trading_pair, '123', '123')
