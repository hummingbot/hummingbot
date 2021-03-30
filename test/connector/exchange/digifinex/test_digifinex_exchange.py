# print('__file__={0:<35} | __name__={1:<20} | __package__={2:<20}'.format(__file__,__name__,str(__package__)))
import os
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
import asyncio
import logging
from decimal import Decimal
import unittest
import contextlib
import time
from typing import List
# from unittest import mock
import conf
import math

from test.connector.exchange.digifinex import fixture
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
    OrderCancelledEvent
)
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.trade_fill import TradeFill
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.connector.exchange.digifinex.digifinex_exchange import DigifinexExchange
# from hummingbot.connector.exchange.digifinex.digifinex_constants import WSS_PUBLIC_URL, WSS_PRIVATE_URL
# from test.integration.humming_web_app import HummingWebApp
# from test.integration.humming_ws_server import HummingWsServerFactory

# API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
API_MOCK_ENABLED = False

logging.basicConfig(level=METRICS_LOG_LEVEL)
# logging.basicConfig(level=logging.NETWORK)
# logging.basicConfig(level=logging.DEBUG)
API_KEY = conf.digifinex_api_key
API_SECRET = conf.digifinex_secret_key
# BASE_API_URL = "openapi.digifinex.com"


class DigifinexExchangeUnitTest(unittest.TestCase):
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
    connector: DigifinexExchange
    event_logger: EventLogger
    trading_pair = "BTC-USDT"
    base_token, quote_token = trading_pair.split("-")
    stack: contextlib.ExitStack
    sql: SQLConnectionManager

    @classmethod
    def setUpClass(cls):
        global MAINNET_RPC_URL

        cls.ev_loop = asyncio.get_event_loop()

        if API_MOCK_ENABLED:
            raise NotImplementedError()
            # cls.web_app = HummingWebApp.get_instance()
            # cls.web_app.add_host_to_mock(BASE_API_URL, [])
            # cls.web_app.start()
            # cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
            # cls._patcher = mock.patch("aiohttp.client.URL")
            # cls._url_mock = cls._patcher.start()
            # cls._url_mock.side_effect = cls.web_app.reroute_local
            # cls.web_app.update_response("get", BASE_API_URL, "/v2/public/get-ticker", fixture.TICKERS)
            # cls.web_app.update_response("get", BASE_API_URL, "/v2/public/get-instruments", fixture.INSTRUMENTS)
            # cls.web_app.update_response("get", BASE_API_URL, "/v2/public/get-book", fixture.GET_BOOK)
            # cls.web_app.update_response("post", BASE_API_URL, "/v2/private/get-account-summary", fixture.BALANCES)
            # cls.web_app.update_response("post", BASE_API_URL, "/v2/private/cancel-order", fixture.CANCEL)

            # HummingWsServerFactory.start_new_server(WSS_PRIVATE_URL)
            # HummingWsServerFactory.start_new_server(WSS_PUBLIC_URL)
            # cls._ws_patcher = unittest.mock.patch("websockets.connect", autospec=True)
            # cls._ws_mock = cls._ws_patcher.start()
            # cls._ws_mock.side_effect = HummingWsServerFactory.reroute_ws_connect

        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.connector: DigifinexExchange = DigifinexExchange(
            digifinex_api_key=API_KEY,
            digifinex_secret_key=API_SECRET,
            trading_pairs=[cls.trading_pair],
            trading_required=True
        )
        print("Initializing Digifinex market... this will take about a minute.")
        cls.clock.add_iterator(cls.connector)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        # if API_MOCK_ENABLED:
        #     HummingWsServerFactory.send_json_threadsafe(WSS_PRIVATE_URL, fixture.WS_INITIATED, delay=0.5)
        #     HummingWsServerFactory.send_json_threadsafe(WSS_PRIVATE_URL, fixture.WS_SUBSCRIBE, delay=0.51)
        #     HummingWsServerFactory.send_json_threadsafe(WSS_PRIVATE_URL, fixture.WS_HEARTBEAT, delay=0.52)

        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()
        # if API_MOCK_ENABLED:
        #     cls.web_app.stop()
        #     cls._patcher.stop()
        #     cls._ws_patcher.stop()

    @classmethod
    async def wait_til_ready(cls, connector = None):
        if connector is None:
            connector = cls.connector
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if connector.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../connector_test.sqlite"))
        try:
            # on windows cannot unlink the sqlite db file before closing the db
            if os.name != 'nt':
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
        # self.sql._engine.dispose()

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
        maker_fee = self.connector.estimate_fee_pct(True)
        self.assertAlmostEqual(maker_fee, Decimal("0.001"))
        taker_fee = self.connector.estimate_fee_pct(False)
        self.assertAlmostEqual(taker_fee, Decimal("0.001"))

    def _place_order(self, is_buy, amount, order_type, price, ex_order_id, get_order_fixture=None,
                     ws_trade_fixture=None, ws_order_fixture=None) -> str:
        # if API_MOCK_ENABLED:
        #     data = fixture.PLACE_ORDER.copy()
        #     data["result"]["order_id"] = str(ex_order_id)
        #     self.web_app.update_response("post", BASE_API_URL, "/v2/private/create-order", data)
        if is_buy:
            cl_order_id = self.connector.buy(self.trading_pair, amount, order_type, price)
        else:
            cl_order_id = self.connector.sell(self.trading_pair, amount, order_type, price)
        # if API_MOCK_ENABLED:
        #     if get_order_fixture is not None:
        #         data = get_order_fixture.copy()
        #         data["result"]["order_info"]["client_oid"] = cl_order_id
        #         data["result"]["order_info"]["order_id"] = ex_order_id
        #         self.web_app.update_response("post", BASE_API_URL, "/v2/private/get-order-detail", data)
        #     if ws_trade_fixture is not None:
        #         data = ws_trade_fixture.copy()
        #         data["result"]["data"][0]["order_id"] = str(ex_order_id)
        #         HummingWsServerFactory.send_json_threadsafe(WSS_PRIVATE_URL, data, delay=0.1)
        #     if ws_order_fixture is not None:
        #         data = ws_order_fixture.copy()
        #         data["result"]["data"][0]["order_id"] = str(ex_order_id)
        #         data["result"]["data"][0]["client_oid"] = cl_order_id
        #         HummingWsServerFactory.send_json_threadsafe(WSS_PRIVATE_URL, data, delay=0.12)
        return cl_order_id

    def _cancel_order(self, cl_order_id):
        self.connector.cancel(self.trading_pair, cl_order_id)
        # if API_MOCK_ENABLED:
        #     data = fixture.WS_ORDER_CANCELLED.copy()
        #     data["result"]["data"][0]["client_oid"] = cl_order_id
        #     HummingWsServerFactory.send_json_threadsafe(WSS_PRIVATE_URL, data, delay=0.1)

    def test_buy_and_sell(self):
        self.ev_loop.run_until_complete(self.connector.cancel_all(0))

        price = self.connector.get_price(self.trading_pair, True) * Decimal("1.05")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0001"))
        quote_bal = self.connector.get_available_balance(self.quote_token)
        base_bal = self.connector.get_available_balance(self.base_token)

        order_id = self._place_order(True, amount, OrderType.LIMIT, price, 1, None,
                                     fixture.WS_TRADE)
        order_completed_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCompletedEvent))
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
        # todo: get fee
        # self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.event_logger.event_log]))

        # check available quote balance gets updated, we need to wait a bit for the balance message to arrive
        expected_quote_bal = quote_bal - quote_amount_traded
        # self._mock_ws_bal_update(self.quote_token, expected_quote_bal)
        self.ev_loop.run_until_complete(asyncio.sleep(1))
        self.assertAlmostEqual(expected_quote_bal, self.connector.get_available_balance(self.quote_token), delta=0.1)

        # Reset the logs
        self.event_logger.clear()

        # Try to sell back the same amount to the exchange, and watch for completion event.
        price = self.connector.get_price(self.trading_pair, True) * Decimal("0.95")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0001"))
        order_id = self._place_order(False, amount, OrderType.LIMIT, price, 2, None,
                                     fixture.WS_TRADE)
        order_completed_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCompletedEvent))
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
        # todo: get fee
        # self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.event_logger.event_log]))

        # check available base balance gets updated, we need to wait a bit for the balance message to arrive
        expected_base_bal = base_bal
        # self._mock_ws_bal_update(self.base_token, expected_base_bal)
        self.ev_loop.run_until_complete(asyncio.sleep(1))
        self.assertAlmostEqual(expected_base_bal, self.connector.get_available_balance(self.base_token), 5)

    def test_limit_makers_unfilled(self):
        price = self.connector.get_price(self.trading_pair, True) * Decimal("0.8")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.00005"))
        quote_bal = self.connector.get_available_balance(self.quote_token)

        # order_id = self.connector.buy(self.trading_pair, amount, OrderType.LIMIT_MAKER, price)
        cl_order_id = self._place_order(True, amount, OrderType.LIMIT_MAKER, price, 1, fixture.UNFILLED_ORDER)
        order_created_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCreatedEvent))
        self.assertEqual(cl_order_id, order_created_event.order_id)
        # check available quote balance gets updated, we need to wait a bit for the balance message to arrive
        expected_quote_bal = quote_bal - (price * amount)
        # self._mock_ws_bal_update(self.quote_token, expected_quote_bal)
        self.ev_loop.run_until_complete(asyncio.sleep(2))
        self.assertAlmostEqual(expected_quote_bal, self.connector.get_available_balance(self.quote_token), 1)
        self._cancel_order(cl_order_id)
        event = self.ev_loop.run_until_complete(self.event_logger.wait_for(OrderCancelledEvent))
        self.assertEqual(cl_order_id, event.order_id)

        price = self.connector.get_price(self.trading_pair, True) * Decimal("1.2")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0001"))

        cl_order_id = self._place_order(False, amount, OrderType.LIMIT_MAKER, price, 2, fixture.UNFILLED_ORDER)
        order_created_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCreatedEvent))
        self.assertEqual(cl_order_id, order_created_event.order_id)
        self._cancel_order(cl_order_id)
        event = self.ev_loop.run_until_complete(self.event_logger.wait_for(OrderCancelledEvent))
        self.assertEqual(cl_order_id, event.order_id)

    # def _mock_ws_bal_update(self, token, available):
    #     if API_MOCK_ENABLED:
    #         available = float(available)
    #         data = fixture.WS_BALANCE.copy()
    #         data["result"]["data"][0]["currency"] = token
    #         data["result"]["data"][0]["available"] = available
    #         HummingWsServerFactory.send_json_threadsafe(WSS_PRIVATE_URL, fixture.WS_BALANCE, delay=0.1)

    def test_limit_maker_rejections(self):
        price = self.connector.get_price(self.trading_pair, True) * Decimal("1.2")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0001"))
        cl_order_id = self._place_order(True, amount, OrderType.LIMIT_MAKER, price, 1, None, None,
                                        fixture.WS_ORDER_CANCELLED)
        event = self.ev_loop.run_until_complete(self.event_logger.wait_for(OrderCancelledEvent))
        self.assertEqual(cl_order_id, event.order_id)

        price = self.connector.get_price(self.trading_pair, False) * Decimal("0.8")
        price = self.connector.quantize_order_price(self.trading_pair, price)
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0001"))
        cl_order_id = self._place_order(False, amount, OrderType.LIMIT_MAKER, price, 2, None, None,
                                        fixture.WS_ORDER_CANCELLED)
        event = self.ev_loop.run_until_complete(self.event_logger.wait_for(OrderCancelledEvent))
        self.assertEqual(cl_order_id, event.order_id)

    def test_cancel_all(self):
        bid_price = self.connector.get_price(self.trading_pair, True)
        ask_price = self.connector.get_price(self.trading_pair, False)
        bid_price = self.connector.quantize_order_price(self.trading_pair, bid_price * Decimal("0.7"))
        ask_price = self.connector.quantize_order_price(self.trading_pair, ask_price * Decimal("1.5"))
        amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0001"))

        buy_id = self._place_order(True, amount, OrderType.LIMIT, bid_price, 1)
        sell_id = self._place_order(False, amount, OrderType.LIMIT, ask_price, 2)

        self.ev_loop.run_until_complete(asyncio.sleep(1))
        asyncio.ensure_future(self.connector.cancel_all(3))
        # if API_MOCK_ENABLED:
        #     data = fixture.WS_ORDER_CANCELLED.copy()
        #     data["result"]["data"][0]["client_oid"] = buy_id
        #     data["result"]["data"][0]["order_id"] = 1
        #     HummingWsServerFactory.send_json_threadsafe(WSS_PRIVATE_URL, data, delay=0.1)
        #     self.ev_loop.run_until_complete(asyncio.sleep(1))
        #     data = fixture.WS_ORDER_CANCELLED.copy()
        #     data["result"]["data"][0]["client_oid"] = sell_id
        #     data["result"]["data"][0]["order_id"] = 2
        #     HummingWsServerFactory.send_json_threadsafe(WSS_PRIVATE_URL, data, delay=0.11)
        self.ev_loop.run_until_complete(asyncio.sleep(3))
        cancel_events = [t for t in self.event_logger.event_log if isinstance(t, OrderCancelledEvent)]
        self.assertEqual({buy_id, sell_id}, {o.order_id for o in cancel_events})

    def test_order_price_precision(self):
        bid_price: Decimal = self.connector.get_price(self.trading_pair, True)
        ask_price: Decimal = self.connector.get_price(self.trading_pair, False)
        mid_price: Decimal = (bid_price + ask_price) / 2
        amount: Decimal = Decimal("0.000123456")

        # Make sure there's enough balance to make the limit orders.
        self.assertGreater(self.connector.get_balance("BTC"), Decimal("0.001"))
        self.assertGreater(self.connector.get_balance("USDT"), Decimal("10"))

        # Intentionally set some prices with too many decimal places s.t. they
        # need to be quantized. Also, place them far away from the mid-price s.t. they won't
        # get filled during the test.
        bid_price = mid_price * Decimal("0.9333192292111341")
        ask_price = mid_price * Decimal("1.0492431474884933")

        cl_order_id_1 = self._place_order(True, amount, OrderType.LIMIT, bid_price, 1, fixture.UNFILLED_ORDER)

        # Wait for the order created event and examine the order made
        self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCreatedEvent))
        order = self.connector.in_flight_orders[cl_order_id_1]
        quantized_bid_price = self.connector.quantize_order_price(self.trading_pair, bid_price)
        quantized_bid_size = self.connector.quantize_order_amount(self.trading_pair, amount)
        self.assertEqual(quantized_bid_price, order.price)
        self.assertEqual(quantized_bid_size, order.amount)

        # Test ask order
        cl_order_id_2 = self._place_order(False, amount, OrderType.LIMIT, ask_price, 1, fixture.UNFILLED_ORDER)

        # Wait for the order created event and examine and order made
        self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCreatedEvent))
        order = self.connector.in_flight_orders[cl_order_id_2]
        quantized_ask_price = self.connector.quantize_order_price(self.trading_pair, Decimal(ask_price))
        quantized_ask_size = self.connector.quantize_order_amount(self.trading_pair, Decimal(amount))
        self.assertEqual(quantized_ask_price, order.price)
        self.assertEqual(quantized_ask_size, order.amount)

        self._cancel_order(cl_order_id_1)
        self._cancel_order(cl_order_id_2)

    def test_orders_saving_and_restoration(self):
        config_path = "test_config"
        strategy_name = "test_strategy"
        sql = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id = None
        recorder = MarketsRecorder(sql, [self.connector], config_path, strategy_name)
        recorder.start()

        try:
            self.connector._in_flight_orders.clear()
            self.assertEqual(0, len(self.connector.tracking_states))

            # Try to put limit buy order for 0.02 ETH worth of ZRX, and watch for order creation event.
            current_bid_price: Decimal = self.connector.get_price(self.trading_pair, True)
            price: Decimal = current_bid_price * Decimal("0.8")
            price = self.connector.quantize_order_price(self.trading_pair, price)

            amount: Decimal = Decimal("0.0001")
            amount = self.connector.quantize_order_amount(self.trading_pair, amount)

            cl_order_id = self._place_order(True, amount, OrderType.LIMIT_MAKER, price, 1, fixture.UNFILLED_ORDER)
            order_created_event = self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCreatedEvent))
            self.assertEqual(cl_order_id, order_created_event.order_id)

            # Verify tracking states
            self.assertEqual(1, len(self.connector.tracking_states))
            self.assertEqual(cl_order_id, list(self.connector.tracking_states.keys())[0])

            # Verify orders from recorder
            recorded_orders: List[Order] = recorder.get_orders_for_config_and_market(config_path, self.connector)
            self.assertEqual(1, len(recorded_orders))
            self.assertEqual(cl_order_id, recorded_orders[0].id)

            # Verify saved market states
            saved_market_states: MarketState = recorder.get_market_states(config_path, self.connector)
            self.assertIsNotNone(saved_market_states)
            self.assertIsInstance(saved_market_states.saved_state, dict)
            self.assertGreater(len(saved_market_states.saved_state), 0)

            # Close out the current market and start another market.
            self.connector.stop(self._clock)
            self.ev_loop.run_until_complete(asyncio.sleep(5))
            self.clock.remove_iterator(self.connector)
            for event_tag in self.events:
                self.connector.remove_listener(event_tag, self.event_logger)
            new_connector = DigifinexExchange(API_KEY, API_SECRET, [self.trading_pair], True)
            for event_tag in self.events:
                new_connector.add_listener(event_tag, self.event_logger)
            recorder.stop()
            recorder = MarketsRecorder(sql, [new_connector], config_path, strategy_name)
            recorder.start()
            saved_market_states = recorder.get_market_states(config_path, new_connector)
            self.clock.add_iterator(new_connector)
            if not API_MOCK_ENABLED:
                self.ev_loop.run_until_complete(self.wait_til_ready(new_connector))
            self.assertEqual(0, len(new_connector.limit_orders))
            self.assertEqual(0, len(new_connector.tracking_states))
            new_connector.restore_tracking_states(saved_market_states.saved_state)
            self.assertEqual(1, len(new_connector.limit_orders))
            self.assertEqual(1, len(new_connector.tracking_states))

            # Cancel the order and verify that the change is saved.
            self._cancel_order(cl_order_id)
            self.ev_loop.run_until_complete(self.event_logger.wait_for(OrderCancelledEvent))
            order_id = None
            self.assertEqual(0, len(new_connector.limit_orders))
            self.assertEqual(0, len(new_connector.tracking_states))
            saved_market_states = recorder.get_market_states(config_path, new_connector)
            self.assertEqual(0, len(saved_market_states.saved_state))
        finally:
            if order_id is not None:
                self.connector.cancel(self.trading_pair, cl_order_id)
                self.run_parallel(self.event_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            # sql._engine.dispose()
            # on windows cannot unlink the sqlite db file before closing the db
            if os.name != 'nt':
                os.unlink(self.db_path)

    def test_update_last_prices(self):
        # This is basic test to see if order_book last_trade_price is initiated and updated.
        for order_book in self.connector.order_books.values():
            for _ in range(5):
                self.ev_loop.run_until_complete(asyncio.sleep(1))
                print(order_book.last_trade_price)
                self.assertFalse(math.isnan(order_book.last_trade_price))

    def test_filled_orders_recorded(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id = None
        recorder = MarketsRecorder(sql, [self.connector], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy some token from the exchange, and watch for completion event.
            price = self.connector.get_price(self.trading_pair, True) * Decimal("1.05")
            price = self.connector.quantize_order_price(self.trading_pair, price)
            amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0001"))

            order_id = self._place_order(True, amount, OrderType.LIMIT, price, 1, None,
                                         fixture.WS_TRADE)
            self.ev_loop.run_until_complete(self.event_logger.wait_for(BuyOrderCompletedEvent))
            self.ev_loop.run_until_complete(asyncio.sleep(1))

            # Reset the logs
            self.event_logger.clear()

            # Try to sell back the same amount to the exchange, and watch for completion event.
            price = self.connector.get_price(self.trading_pair, True) * Decimal("0.95")
            price = self.connector.quantize_order_price(self.trading_pair, price)
            amount = self.connector.quantize_order_amount(self.trading_pair, Decimal("0.0001"))
            order_id = self._place_order(False, amount, OrderType.LIMIT, price, 2, None,
                                         fixture.WS_TRADE)
            self.ev_loop.run_until_complete(self.event_logger.wait_for(SellOrderCompletedEvent))

            # Query the persisted trade logs
            trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
            self.assertGreaterEqual(len(trade_fills), 2)
            buy_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
            sell_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "SELL"]
            self.assertGreaterEqual(len(buy_fills), 1)
            self.assertGreaterEqual(len(sell_fills), 1)

            order_id = None

        finally:
            if order_id is not None:
                self.connector.cancel(self.trading_pair, order_id)
                self.run_parallel(self.event_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            # sql._engine.dispose()
            # on windows cannot unlink the sqlite db file before closing the db
            if os.name != 'nt':
                os.unlink(self.db_path)


# unittest.main()
