from os.path import join, realpath
import sys
import asyncio
import conf
import contextlib
from decimal import Decimal
import logging
import os
import time
import math
from typing import (
    List,
    Dict,
    Optional
)
import unittest
from unittest.mock import patch

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
    MarketOrderFailureEvent,
    TradeFee,
    TradeType,
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.connector.exchange.binance.binance_exchange import (
    BinanceExchange,
    BinanceTime,
    binance_client_module
)
from hummingbot.connector.exchange.binance.binance_utils import convert_to_exchange_trading_pair
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
from test.connector.exchange.binance.fixture_binance import FixtureBinance
from hummingbot.core.mock_api.mock_web_server import MockWebServer
from unittest import mock
import requests
from hummingbot.core.mock_api.mock_web_socket_server import MockWebSocketServerFactory
sys.path.insert(0, realpath(join(__file__, "../../../../bin")))

MAINNET_RPC_URL = "http://mainnet-rpc.mainnet:8545"
logging.basicConfig(level=METRICS_LOG_LEVEL)
API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
API_KEY = "XXX" if API_MOCK_ENABLED else conf.binance_api_key
API_SECRET = "YYY" if API_MOCK_ENABLED else conf.binance_api_secret


class BinanceExchangeUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderFailure
    ]

    market: BinanceExchange
    market_logger: EventLogger
    stack: contextlib.ExitStack
    base_api_url = "api.binance.com"

    @classmethod
    def setUpClass(cls):
        global MAINNET_RPC_URL

        cls.ev_loop = asyncio.get_event_loop()

        if API_MOCK_ENABLED:
            cls.web_app = MockWebServer.get_instance()
            cls.web_app.add_host_to_mock(cls.base_api_url, ["/api/v1/ping", "/api/v1/time", "/api/v1/ticker/24hr"])
            cls.web_app.start()
            cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
            cls._patcher = mock.patch("aiohttp.client.URL")
            cls._url_mock = cls._patcher.start()
            cls._url_mock.side_effect = cls.web_app.reroute_local

            cls._req_patcher = unittest.mock.patch.object(requests.Session, "request", autospec=True)
            cls._req_url_mock = cls._req_patcher.start()
            cls._req_url_mock.side_effect = MockWebServer.reroute_request
            cls.web_app.update_response("get", cls.base_api_url, "/api/v3/account", FixtureBinance.BALANCES)
            cls.web_app.update_response("get", cls.base_api_url, "/api/v1/exchangeInfo",
                                        FixtureBinance.MARKETS)
            cls.web_app.update_response("get", cls.base_api_url, "/wapi/v3/tradeFee.html",
                                        FixtureBinance.TRADE_FEES)
            cls.web_app.update_response("post", cls.base_api_url, "/api/v1/userDataStream",
                                        FixtureBinance.LISTEN_KEY)
            cls.web_app.update_response("put", cls.base_api_url, "/api/v1/userDataStream",
                                        FixtureBinance.LISTEN_KEY)
            cls.web_app.update_response("get", cls.base_api_url, "/api/v1/depth",
                                        FixtureBinance.LINKETH_SNAP, params={'symbol': 'LINKETH'})
            cls.web_app.update_response("get", cls.base_api_url, "/api/v1/depth",
                                        FixtureBinance.ZRXETH_SNAP, params={'symbol': 'ZRXETH'})
            cls.web_app.update_response("get", cls.base_api_url, "/api/v3/myTrades",
                                        {}, params={'symbol': 'ZRXETH'})
            cls.web_app.update_response("get", cls.base_api_url, "/api/v3/myTrades",
                                        {}, params={'symbol': 'LINKETH'})
            ws_base_url = "wss://stream.binance.com:9443/ws"
            cls._ws_user_url = f"{ws_base_url}/{FixtureBinance.LISTEN_KEY['listenKey']}"
            MockWebSocketServerFactory.start_new_server(cls._ws_user_url)
            MockWebSocketServerFactory.start_new_server(f"{ws_base_url}/linketh@depth/zrxeth@depth")
            cls._ws_patcher = unittest.mock.patch("websockets.connect", autospec=True)
            cls._ws_mock = cls._ws_patcher.start()
            cls._ws_mock.side_effect = MockWebSocketServerFactory.reroute_ws_connect

            cls._t_nonce_patcher = unittest.mock.patch(
                "hummingbot.connector.exchange.binance.binance_exchange.get_tracking_nonce")
            cls._t_nonce_mock = cls._t_nonce_patcher.start()
        cls.current_nonce = 1000000000000000
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: BinanceExchange = BinanceExchange(API_KEY, API_SECRET, ["LINK-ETH", "ZRX-ETH"], True)
        print("Initializing Binance market... this will take about a minute.")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.market)
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
            cls._req_patcher.stop()
            cls._ws_patcher.stop()
            cls._t_nonce_patcher.stop()

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
        self.db_path: str = realpath(join(__file__, "../binance_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        self.market._current_trade_fills = set()
        self.market._exchange_order_ids = dict()
        self.ev_loop.run_until_complete(self.wait_til_ready())
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

    @classmethod
    def get_current_nonce(cls):
        cls.current_nonce += 1
        return cls.current_nonce

    def test_get_fee(self):
        maker_buy_trade_fee: TradeFee = self.market.get_fee("BTC", "USDT", OrderType.LIMIT_MAKER, TradeType.BUY, Decimal(1), Decimal(4000))
        self.assertGreater(maker_buy_trade_fee.percent, 0)
        self.assertEqual(len(maker_buy_trade_fee.flat_fees), 0)
        taker_buy_trade_fee: TradeFee = self.market.get_fee("BTC", "USDT", OrderType.LIMIT, TradeType.BUY, Decimal(1))
        self.assertGreater(taker_buy_trade_fee.percent, 0)
        self.assertEqual(len(taker_buy_trade_fee.flat_fees), 0)
        sell_trade_fee: TradeFee = self.market.get_fee("BTC", "USDT", OrderType.LIMIT, TradeType.SELL, Decimal(1), Decimal(4000))
        self.assertGreater(sell_trade_fee.percent, 0)
        self.assertEqual(len(sell_trade_fee.flat_fees), 0)
        sell_trade_fee: TradeFee = self.market.get_fee("BTC", "USDT", OrderType.LIMIT_MAKER, TradeType.SELL, Decimal(1),
                                                       Decimal(4000))
        self.assertGreater(sell_trade_fee.percent, 0)
        self.assertEqual(len(sell_trade_fee.flat_fees), 0)

    def test_fee_overrides_config(self):
        fee_overrides_config_map["binance_taker_fee"].value = None
        taker_fee: TradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.001"), taker_fee.percent)
        fee_overrides_config_map["binance_taker_fee"].value = Decimal('0.2')
        taker_fee: TradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.002"), taker_fee.percent)
        fee_overrides_config_map["binance_maker_fee"].value = None
        maker_fee: TradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT_MAKER, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.001"), maker_fee.percent)
        fee_overrides_config_map["binance_maker_fee"].value = Decimal('0.5')
        maker_fee: TradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT_MAKER, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.005"), maker_fee.percent)

    def test_buy_and_sell(self):
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.05"))
        bid_price: Decimal = self.market.get_price("LINK-ETH", True)
        amount: Decimal = 1
        quantized_amount: Decimal = self.market.quantize_order_amount("LINK-ETH", amount)

        order_id = self.place_order(True, "LINK-ETH", amount, OrderType.LIMIT, bid_price, self.get_current_nonce(), FixtureBinance.BUY_MARKET_ORDER,
                                    FixtureBinance.WS_AFTER_BUY_1, FixtureBinance.WS_AFTER_BUY_2)
        self.market.add_exchange_order_ids_from_market_recorder({str(FixtureBinance.BUY_MARKET_ORDER['orderId']): "buy-LINKETH-1580093594011279"})
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("LINK", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

        # Reset the logs
        self.market_logger.clear()

        # Try to sell back the same amount of ZRX to the exchange, and watch for completion event.
        ask_price: Decimal = self.market.get_price("LINK-ETH", False)
        amount = order_completed_event.base_asset_amount
        quantized_amount = order_completed_event.base_asset_amount
        order_id = self.place_order(False, "LINK-ETH", amount, OrderType.LIMIT, ask_price, 10002, FixtureBinance.SELL_MARKET_ORDER,
                                    FixtureBinance.WS_AFTER_SELL_1, FixtureBinance.WS_AFTER_SELL_2)
        self.market.add_exchange_order_ids_from_market_recorder({str(FixtureBinance.SELL_MARKET_ORDER['orderId']): "sell-LINKETH-1580194659898896"})
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.market_logger.event_log
                        if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("LINK", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

    def test_limit_maker_rejections(self):
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.05"))

        # Try to put a buy limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.market.get_price("LINK-ETH", True) * Decimal('1.02')
        price: Decimal = self.market.quantize_order_price("LINK-ETH", price)
        amount = self.market.quantize_order_amount("LINK-ETH", 1)

        order_id = self.place_order(True, "LINK-ETH", amount, OrderType.LIMIT_MAKER,
                                    price, self.get_current_nonce(),
                                    FixtureBinance.LIMIT_MAKER_ERROR)
        [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

        self.market_logger.clear()

        # Try to put a sell limit maker order that is going to match, this should triggers order failure event.
        price: Decimal = self.market.get_price("LINK-ETH", True) * Decimal('0.98')
        price: Decimal = self.market.quantize_order_price("LINK-ETH", price)
        amount = self.market.quantize_order_amount("LINK-ETH", 1)

        order_id = self.place_order(False, "LINK-ETH", amount, OrderType.LIMIT_MAKER,
                                    price, self.get_current_nonce(),
                                    FixtureBinance.LIMIT_MAKER_ERROR)
        [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
        self.assertEqual(order_id, order_failure_event.order_id)

    def test_limit_makers_unfilled(self):
        price = self.market.get_price("LINK-ETH", True) * Decimal("0.8")
        price = self.market.quantize_order_price("LINK-ETH", price)
        amount = self.market.quantize_order_amount("LINK-ETH", 1)

        buy_id = self.place_order(True, "LINK-ETH", amount, OrderType.LIMIT_MAKER,
                                  price, self.get_current_nonce(),
                                  FixtureBinance.OPEN_BUY_ORDER)
        [buy_order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        buy_order_created_event: BuyOrderCreatedEvent = buy_order_created_event
        self.assertEqual(buy_id, buy_order_created_event.order_id)

        price = self.market.get_price("LINK-ETH", True) * Decimal("1.2")
        price = self.market.quantize_order_price("LINK-ETH", price)
        amount = self.market.quantize_order_amount("LINK-ETH", 1)

        sell_id = self.place_order(False, "LINK-ETH", amount, OrderType.LIMIT_MAKER,
                                   price, self.get_current_nonce(),
                                   FixtureBinance.OPEN_SELL_ORDER)
        [sell_order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        sell_order_created_event: BuyOrderCreatedEvent = sell_order_created_event
        self.assertEqual(sell_id, sell_order_created_event.order_id)

        if API_MOCK_ENABLED:
            resp = self.fixture(FixtureBinance.CANCEL_ORDER, origClientOrderId=buy_id, side="BUY")
            self.web_app.update_response("delete", self.base_api_url, "/api/v3/order", resp,
                                         params={'origClientOrderId': buy_id})
            resp = self.fixture(FixtureBinance.CANCEL_ORDER, origClientOrderId=sell_id, side="SELL")
            self.web_app.update_response("delete", self.base_api_url, "/api/v3/order", resp,
                                         params={'origClientOrderId': sell_id})

        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def fixture(self, fixture_data, **overwrites):
        data = fixture_data.copy()
        for key, value in overwrites.items():
            if key not in data:
                raise Exception(f"{key} not found in fixture_data")
            data[key] = value
        return data

    def order_response(self, fixture_data, nonce, side, trading_pair):
        self._t_nonce_mock.return_value = nonce
        order_id = f"{side.lower()}-{trading_pair}-{str(nonce)}"
        order_resp = fixture_data.copy()
        order_resp["clientOrderId"] = order_id
        return order_resp

    def place_order(self, is_buy, trading_pair, amount, order_type, price, nonce, fixture_resp,
                    fixture_ws_1 = None, fixture_ws_2 = None):
        order_id = None
        if API_MOCK_ENABLED:
            resp = self.order_response(fixture_resp, nonce, 'buy' if is_buy else 'sell', trading_pair)
            self.web_app.update_response("post", self.base_api_url, "/api/v3/order", resp)
        if is_buy:
            order_id = self.market.buy(trading_pair, amount, order_type, price)
        else:
            order_id = self.market.sell(trading_pair, amount, order_type, price)
        if API_MOCK_ENABLED and fixture_ws_1 is not None and fixture_ws_2 is not None:
            exchange_order_id = str(resp['orderId'])
            data = self.fixture(fixture_ws_1, c=order_id, i=exchange_order_id)
            MockWebSocketServerFactory.send_json_threadsafe(self._ws_user_url, data, delay=0.1)
            data = self.fixture(fixture_ws_2, c=order_id, i=exchange_order_id)
            MockWebSocketServerFactory.send_json_threadsafe(self._ws_user_url, data, delay=0.11)
        return order_id

    def test_cancel_all(self):
        trading_pair = "LINK-ETH"
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        ask_price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = 1
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price * Decimal("0.7"))
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price * Decimal("1.5"))

        buy_id = self.place_order(True, "LINK-ETH", quantized_amount, OrderType.LIMIT, quantize_bid_price, self.get_current_nonce(),
                                  FixtureBinance.OPEN_BUY_ORDER, FixtureBinance.WS_AFTER_BUY_1,
                                  FixtureBinance.WS_AFTER_BUY_2)

        sell_id = self.place_order(False, "LINK-ETH", quantized_amount, OrderType.LIMIT, quantize_ask_price, self.get_current_nonce(),
                                   FixtureBinance.OPEN_SELL_ORDER, FixtureBinance.WS_AFTER_SELL_1,
                                   FixtureBinance.WS_AFTER_SELL_2)

        self.run_parallel(asyncio.sleep(1))
        if API_MOCK_ENABLED:
            resp = self.fixture(FixtureBinance.CANCEL_ORDER, origClientOrderId=buy_id, side="BUY")
            self.web_app.update_response("delete", self.base_api_url, "/api/v3/order", resp,
                                         params={'origClientOrderId': buy_id})
            resp = self.fixture(FixtureBinance.CANCEL_ORDER, origClientOrderId=sell_id, side="SELL")
            self.web_app.update_response("delete", self.base_api_url, "/api/v3/order", resp,
                                         params={'origClientOrderId': sell_id})
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_order_price_precision(self):
        # As of the day this test was written, the min order size (base) is 1 LINK, the min order size (quote) is
        # 0.01 ETH, and order step size is 1 LINK.
        trading_pair = "LINK-ETH"
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        ask_price: Decimal = self.market.get_price(trading_pair, False)
        mid_price: Decimal = (bid_price + ask_price) / 2
        amount: Decimal = Decimal("1.23123216")
        binance_client = self.market.binance_client

        # Make sure there's enough balance to make the limit orders.
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.05"))
        self.assertGreater(self.market.get_balance("LINK"), amount * 2)

        # Intentionally set some prices with too many decimal places s.t. they
        # need to be quantized. Also, place them far away from the mid-price s.t. they won't
        # get filled during the test.
        bid_price: Decimal = mid_price * Decimal("0.9333192292111341")
        ask_price: Decimal = mid_price * Decimal("1.0492431474884933")

        # This is needed to get around the min quote amount limit.
        bid_amount: Decimal = Decimal("1.23123216")

        if API_MOCK_ENABLED:
            resp = self.order_response(FixtureBinance.ORDER_BUY_PRECISION, self.get_current_nonce(), "buy", "LINK-ETH")
            self.web_app.update_response("post", self.base_api_url, "/api/v3/order", resp)
        # Test bid order
        bid_order_id: str = self.market.buy(
            trading_pair,
            Decimal(bid_amount),
            OrderType.LIMIT,
            Decimal(bid_price)
        )
        if API_MOCK_ENABLED:
            resp = FixtureBinance.ORDER_BUY_PRECISION_GET
            resp["clientOrderId"] = bid_order_id
            self.web_app.update_response("get", self.base_api_url, "/api/v3/order", resp)

        # Wait for the order created event and examine the order made
        [order_created_event] = self.run_parallel(
            self.market_logger.wait_for(BuyOrderCreatedEvent, timeout_seconds=10)
        )
        order_data: Dict[str, any] = binance_client.get_order(
            symbol=trading_pair,
            origClientOrderId=bid_order_id
        )
        quantized_bid_price: Decimal = self.market.quantize_order_price(trading_pair, Decimal(bid_price))
        bid_size_quantum: Decimal = self.market.get_order_size_quantum(trading_pair, Decimal(bid_amount))
        self.assertEqual(quantized_bid_price, Decimal(order_data["price"]))
        self.assertTrue(Decimal(order_data["origQty"]) % bid_size_quantum == 0)

        # Test ask order
        if API_MOCK_ENABLED:
            resp = self.order_response(FixtureBinance.ORDER_SELL_PRECISION, self.get_current_nonce(), "sell", "LINK-ETH")
            self.web_app.update_response("post", self.base_api_url, "/api/v3/order", resp)
        ask_order_id: str = self.market.sell(
            trading_pair,
            Decimal(amount),
            OrderType.LIMIT,
            Decimal(ask_price)
        )
        if API_MOCK_ENABLED:
            resp = FixtureBinance.ORDER_SELL_PRECISION_GET
            resp["clientOrderId"] = ask_order_id
            self.web_app.update_response("get", self.base_api_url, "/api/v3/order", resp)

        # Wait for the order created event and examine and order made
        [order_created_event] = self.run_parallel(
            self.market_logger.wait_for(SellOrderCreatedEvent, timeout_seconds=10)
        )
        order_data = binance_client.get_order(
            symbol=trading_pair,
            origClientOrderId=ask_order_id
        )
        quantized_ask_price: Decimal = self.market.quantize_order_price(trading_pair, Decimal(ask_price))
        quantized_ask_size: Decimal = self.market.quantize_order_amount(trading_pair, Decimal(amount))
        self.assertEqual(quantized_ask_price, Decimal(order_data["price"]))
        self.assertEqual(quantized_ask_size, Decimal(order_data["origQty"]))

        # Cancel all the orders
        if API_MOCK_ENABLED:
            resp = self.fixture(FixtureBinance.CANCEL_ORDER, origClientOrderId=bid_order_id, side="BUY")
            self.web_app.update_response("delete", self.base_api_url, "/api/v3/order", resp,
                                         params={'origClientOrderId': bid_order_id})
            resp = self.fixture(FixtureBinance.CANCEL_ORDER, origClientOrderId=ask_order_id, side="SELL")
            self.web_app.update_response("delete", self.base_api_url, "/api/v3/order", resp,
                                         params={'origClientOrderId': ask_order_id})
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_server_time_offset(self):
        time_obj: BinanceTime = binance_client_module.time
        old_check_interval: float = time_obj._server_time_offset_check_interval
        time_obj._server_time_offset_check_interval = 1.0
        time_obj.stop()
        time_obj.start()

        try:
            local_time_offset = (time.time() - time.perf_counter()) * 1e3
            with patch("hummingbot.connector.exchange.binance.binance_time.time") as market_time:
                def delayed_time():
                    return time.perf_counter() - 30.0
                market_time.perf_counter = delayed_time
                self.run_parallel(asyncio.sleep(3.0))
                raw_time_offset = BinanceTime.get_instance().time_offset_ms
                time_offset_diff = raw_time_offset - local_time_offset
                # check if it is less than 5% off
                self.assertTrue(time_offset_diff > 10000)
                self.assertTrue(abs(time_offset_diff - 30.0 * 1e3) < 1.5 * 1e3)
        finally:
            time_obj._server_time_offset_check_interval = old_check_interval
            time_obj.stop()
            time_obj.start()

    def test_orders_saving_and_restoration(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            self.assertEqual(0, len(self.market.tracking_states))

            # Try to put limit buy order for 0.02 ETH worth of ZRX, and watch for order creation event.
            current_bid_price: Decimal = self.market.get_price("LINK-ETH", True)
            bid_price: Decimal = current_bid_price * Decimal("0.8")
            quantize_bid_price: Decimal = self.market.quantize_order_price("LINK-ETH", bid_price)

            amount: Decimal = 1
            quantized_amount: Decimal = self.market.quantize_order_amount("LINK-ETH", amount)

            if API_MOCK_ENABLED:
                resp = self.order_response(FixtureBinance.OPEN_BUY_ORDER, self.get_current_nonce(), "buy", "LINK-ETH")
                self.web_app.update_response("post", self.base_api_url, "/api/v3/order", resp)
            order_id = self.market.buy("LINK-ETH", quantized_amount, OrderType.LIMIT, quantize_bid_price)
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
            self.__class__.market: BinanceExchange = BinanceExchange(API_KEY, API_SECRET, ["LINK-ETH", "ZRX-ETH"], True)
            for event_tag in self.events:
                self.market.add_listener(event_tag, self.market_logger)
            recorder.stop()
            recorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
            recorder.start()
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.clock.add_iterator(self.market)
            self.ev_loop.run_until_complete(self.wait_til_ready())

            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            self.market.restore_tracking_states(saved_market_states.saved_state)
            self.assertEqual(1, len(self.market.limit_orders))
            self.assertEqual(1, len(self.market.tracking_states))

            # Cancel the order and verify that the change is saved.
            if API_MOCK_ENABLED:
                resp = self.fixture(FixtureBinance.CANCEL_ORDER, origClientOrderId=order_id, side="BUY")
                self.web_app.update_response("delete", self.base_api_url, "/api/v3/order", resp,
                                             params={'origClientOrderId': order_id})
            self.market.cancel("LINK-ETH", order_id)
            self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
            order_id = None
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.assertEqual(0, len(saved_market_states.saved_state))
        finally:
            if order_id is not None:
                self.market.cancel("LINK-ETH", order_id)
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

    def test_order_fill_record(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        buy_id: Optional[str] = None
        sell_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy 1 LINK from the exchange, and watch for completion event.
            bid_price: Decimal = self.market.get_price("LINK-ETH", True)
            amount: Decimal = 1
            buy_id = self.place_order(True, "LINK-ETH", amount, OrderType.LIMIT, bid_price, self.get_current_nonce(),
                                      FixtureBinance.BUY_LIMIT_ORDER, FixtureBinance.WS_AFTER_BUY_1,
                                      FixtureBinance.WS_AFTER_BUY_2)
            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logs
            self.market_logger.clear()

            # Try to sell back the same amount of LINK to the exchange, and watch for completion event.
            ask_price: Decimal = self.market.get_price("LINK-ETH", False)
            amount = buy_order_completed_event.base_asset_amount
            sell_id = self.place_order(False, "LINK-ETH", amount, OrderType.LIMIT, ask_price, self.get_current_nonce(),
                                       FixtureBinance.SELL_LIMIT_ORDER, FixtureBinance.WS_AFTER_SELL_1,
                                       FixtureBinance.WS_AFTER_SELL_2)
            [sell_order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))

            # Query the persisted trade logs
            trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
            self.assertGreaterEqual(len(trade_fills), 2)
            buy_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
            sell_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "SELL"]
            self.assertGreaterEqual(len(buy_fills), 1)
            self.assertGreaterEqual(len(sell_fills), 1)

            buy_id = sell_id = None

        finally:
            if buy_id is not None:
                self.market.cancel("LINK-ETH", buy_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
            if sell_id is not None:
                self.market.cancel("LINK-ETH", sell_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)

    def test_prevent_duplicated_orders(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        buy_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            # Perform the same order twice which should produce the same exchange_order_id
            # Try to buy 1 LINK from the exchange, and watch for completion event.
            bid_price: Decimal = self.market.get_price("LINK-ETH", True)
            amount: Decimal = 1
            buy_id = self.place_order(True, "LINK-ETH", amount, OrderType.LIMIT, bid_price, self.get_current_nonce(),
                                      FixtureBinance.BUY_LIMIT_ORDER, FixtureBinance.WS_AFTER_BUY_1,
                                      FixtureBinance.WS_AFTER_BUY_2)
            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            self.market_logger.clear()

            # Simulate that order is still in in_flight_orders
            order_json = {"client_order_id": buy_id,
                          "exchange_order_id": str(FixtureBinance.WS_AFTER_BUY_2['t']),
                          "trading_pair": "LINK-ETH",
                          "order_type": "MARKET",
                          "trade_type": "BUY",
                          "price": bid_price,
                          "amount": amount,
                          "last_state": "NEW",
                          "executed_amount_base": "0",
                          "executed_amount_quote": "0",
                          "fee_asset": "LINK",
                          "fee_paid": "0.0"}
            self.market.restore_tracking_states({buy_id: order_json})
            self.market.in_flight_orders.get(buy_id).trade_id_set.add(str(FixtureBinance.WS_AFTER_BUY_2['t']))
            # Simulate incoming responses as if buy_id is executed again
            data = self.fixture(FixtureBinance.WS_AFTER_BUY_2, c=buy_id)
            MockWebSocketServerFactory.send_json_threadsafe(self._ws_user_url, data, delay=0.11)
            # Will wait, but no order filled event should be triggered because order is ignored
            self.run_parallel(asyncio.sleep(1))
            # Query the persisted trade logs
            trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
            buy_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
            exchange_trade_id = FixtureBinance.WS_AFTER_BUY_2['t']
            self.assertEqual(len([bf for bf in buy_fills if int(bf.exchange_trade_id) == exchange_trade_id]), 1)

            buy_id = None

        finally:
            if buy_id is not None:
                self.market.cancel("LINK-ETH", buy_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)

    def test_history_reconciliation(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()
        try:
            bid_price: Decimal = self.market.get_price("LINK-ETH", True)
            # Will temporarily change binance history request to return trades
            buy_id = "1580204166011219"
            order_id = "123456"
            self._t_nonce_mock.return_value = 1234567890123456
            binance_trades = [{
                'symbol': "LINKETH",
                'id': buy_id,
                'orderId': order_id,
                'orderListId': -1,
                'price': float(bid_price),
                'qty': 1,
                'quoteQty': float(bid_price),
                'commission': 0,
                'commissionAsset': "ETH",
                'time': 1580093596074,
                'isBuyer': True,
                'isMaker': True,
                'isBestMatch': True,
            }]
            self.market.add_exchange_order_ids_from_market_recorder({order_id: "buy-LINKETH-1580093594011279"})
            self.web_app.update_response("get", self.base_api_url, "/api/v3/myTrades",
                                         binance_trades, params={'symbol': 'LINKETH'})
            [market_order_completed] = self.run_parallel(self.market_logger.wait_for(OrderFilledEvent))

            trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
            buy_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
            self.assertEqual(len([bf for bf in buy_fills if bf.exchange_trade_id == buy_id]), 1)

            buy_id = None

        finally:
            if buy_id is not None:
                self.market.cancel("LINK-ETH", buy_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            # Undo change to binance history request
            self.web_app.update_response("get", self.base_api_url, "/api/v3/myTrades",
                                         {}, params={'symbol': 'LINKETH'})

            recorder.stop()
            os.unlink(self.db_path)

    def test_pair_conversion(self):
        if API_MOCK_ENABLED:
            return
        for pair in self.market.trading_rules:
            exchange_pair = convert_to_exchange_trading_pair(pair)
            self.assertTrue(exchange_pair in self.market.order_books)


if __name__ == "__main__":
    logging.getLogger("hummingbot.core.event.event_reporter").setLevel(logging.WARNING)
    unittest.main()
