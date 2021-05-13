
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

import asyncio
import conf
import contextlib
import logging
import os
import time
from typing import List, Optional
import unittest
import requests
from decimal import Decimal

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    OrderCancelledEvent,
    OrderType,
    SellOrderCompletedEvent,
    TradeFee,
    TradeType,
)
from hummingbot.connector.exchange.dydx.dydx_exchange import DydxExchange
from hummingbot.model.trade_fill import TradeFill
from test.connector.exchange.dydx.fixture_dydx import FixtureDydx
# from hummingbot.connector.exchange.dydx.dydx_auth import DydxAuth
from hummingbot.core.mock_api.mock_web_server import MockWebServer
from unittest import mock
from hummingbot.core.mock_api.mock_web_socket_server import MockWebSocketServerFactory
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order

from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)

sys.path.insert(0, realpath(join(__file__, "../../../../../")))

# Note that the minimum order size is 40 ETH

API_MOCK_ENABLED = conf.mock_api_enabled is not None \
    and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
PRIVATE_KEY = "a3f18ad5927fa7cf218f1afa8eaeef8f794ad4\
  f324f4a030f7469aa297fb8ea9" if API_MOCK_ENABLED else conf.dydx_private_key
NODE_ADDRESS = "https://mainnet.infura.io/v3/ba0cd0f419124\
  5f18d04c934b220d227" if API_MOCK_ENABLED else conf.dydx_node_address
if API_MOCK_ENABLED:
    WALLET_ADDRESS = "0x7E1431664d05212774704Cff9d7949DfBe2d5d25"
    ACCOUNT_NUMBER = "7824991635838049259331423940903217391174126\
      8194868200833150293576330928686520"


class DydxExchangeUnitTest(unittest.TestCase):
    market_events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
    ]

    market: DydxExchange
    market_logger: EventLogger
    stack: contextlib.ExitStack
    base_api_url = "api.dydx.exchange"

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        if API_MOCK_ENABLED:

            cls.web_app = MockWebServer.get_instance()
            cls.web_app.add_host_to_mock(cls.base_api_url, [])

            cls.web_app.start()

            cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())

            cls._req_patcher = mock.patch.object(requests.Session,
                                                 "request",
                                                 autospec=True)
            cls._req_url_mock = cls._req_patcher.start()
            cls._req_url_mock.side_effect = MockWebServer.reroute_request

            cls.web_app.update_response("get",
                                        cls.base_api_url,
                                        f"/v1/accounts/{WALLET_ADDRESS}",
                                        FixtureDydx.BALANCES,
                                        params={'number': f'{ACCOUNT_NUMBER}'})

            cls.web_app.update_response("get", cls.base_api_url, "/v2/markets",
                                        FixtureDydx.MARKETS)
            cls.web_app.update_response("get",
                                        cls.base_api_url,
                                        "/v1/orderbook/WETH-USDC",
                                        FixtureDydx.WETHUSDC_SNAP)
            cls._buy_order_exchange_id = "0xb0751a113c759779ff5fd6a53b37b26211a9\
              f8845d443323b9f877f32d9aafd9"
            cls._sell_order_exchange_id = "0x03dfd18edc2f26fc9298edcd28ca6cad4971\
              bd1f44d40253d5154b0d1f217680"
            cls.web_app.update_response(
                "delete",
                cls.base_api_url,
                f"/v2/orders/{cls._buy_order_exchange_id}",
                FixtureDydx.CANCEL_ORDER_BUY)
            cls.web_app.update_response(
                "delete",
                cls.base_api_url,
                f"/v2/orders/{cls._sell_order_exchange_id}",
                FixtureDydx.CANCEL_ORDER_SELL)
            ws_base_url = "wss://api.dydx.exchange/v1/ws"
            cls._ws_user_url = f"{ws_base_url}"
            MockWebSocketServerFactory.start_new_server(cls._ws_user_url)
            MockWebSocketServerFactory.start_new_server(f"{ws_base_url}")
            cls._ws_patcher = unittest.mock.patch("websockets.connect",
                                                  autospec=True)
            cls._ws_mock = cls._ws_patcher.start()
            cls._ws_mock.side_effect = MockWebSocketServerFactory.reroute_ws_connect

            cls._t_nonce_patcher = unittest.mock.patch(
                "hummingbot.connector.exchange.dydx.\
                dydx_exchange.get_tracking_nonce")
            cls._t_nonce_mock = cls._t_nonce_patcher.start()

        cls.market: DydxExchange = DydxExchange(
            dydx_eth_private_key=PRIVATE_KEY,
            dydx_node_address=NODE_ADDRESS,
            poll_interval=10.0,
            trading_pairs=['WETH-USDC'],
            trading_required=True
        )

        print("Initializing Dydx market... ")
        cls.clock.add_iterator(cls.market)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()
        if API_MOCK_ENABLED:
            cls.web_app.stop()
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
        self.db_path: str = realpath(join(__file__, "../dydx_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        for event_tag in self.market_events:
            self.market.add_listener(event_tag, self.market_logger)

    def tearDown(self):
        for event_tag in self.market_events:
            self.market.remove_listener(event_tag, self.market_logger)
        self.market_logger = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = asyncio.ensure_future(asyncio.gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    # ====================================================

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
        order_resp["order"]["clientId"] = order_id
        return order_resp

    def place_order(self,
                    is_buy,
                    trading_pair,
                    amount,
                    order_type, price,
                    nonce,
                    fixture_resp,
                    fixture_ws_1=None,
                    fixture_ws_2=None,
                    fixture_ws_3=None):
        order_id = None
        if API_MOCK_ENABLED:
            resp = self.order_response(fixture_resp,
                                       nonce,
                                       'buy' if is_buy else 'sell',
                                       trading_pair)
            self.web_app.update_response("post",
                                         self.base_api_url,
                                         "/v2/orders",
                                         resp)
        if is_buy:
            order_id = self.market.buy(trading_pair,
                                       amount,
                                       order_type,
                                       price)
        else:
            order_id = self.market.sell(trading_pair,
                                        amount,
                                        order_type,
                                        price)
        if API_MOCK_ENABLED and fixture_ws_1 is not None:
            self.web_app.update_response("get",
                                         self.base_api_url,
                                         "/v2/fills",
                                         FixtureDydx.FILLS,
                                         params={"orderId": order_id,
                                                 "limit": 100
                                                 }
                                         )
            data = self.fixture(fixture_ws_1, id=order_id)
            MockWebSocketServerFactory.send_json_threadsafe(self._ws_user_url,
                                                            data,
                                                            delay=0.1)
            if fixture_ws_2 is not None:
                data = self.fixture(fixture_ws_2, id=order_id)
                MockWebSocketServerFactory.send_json_threadsafe(self._ws_user_url,
                                                                data,
                                                                delay=0.11)
            if fixture_ws_3 is not None:
                MockWebSocketServerFactory.send_json_threadsafe(self._ws_user_url,
                                                                fixture_ws_3,
                                                                delay=0.1)
        return order_id

    def test_get_fee(self):
        limit_trade_fee: TradeFee = self.market.get_fee("WETH",
                                                        "USDC",
                                                        OrderType.LIMIT_MAKER,
                                                        TradeType.SELL, 10000,
                                                        1)
        self.assertLess(limit_trade_fee.percent, 0.01)

    def test_limit_buy(self):
        self.assertGreater(self.market.get_balance("USDC"), 16000)
        # Try to buy 40 ETH from the exchange, and watch for creation event.
        trading_pair = "WETH-USDC"
        amount: Decimal = Decimal("40.0")
        ask_price: Decimal = self.market.get_price(trading_pair, False)
        buy_order_id: str = self.place_order(True,
                                             "WETH-USDC",
                                             amount,
                                             OrderType.LIMIT,
                                             ask_price * Decimal('1.5'),
                                             10001,
                                             FixtureDydx.BUY_LIMIT_ORDER,
                                             FixtureDydx.WS_AFTER_BUY_1,
                                             FixtureDydx.WS_AFTER_BUY_2,
                                             FixtureDydx.WS_AFTER_BUY_3)
        [buy_order_completed_event] = self.run_parallel(
            self.market_logger.wait_for(BuyOrderCompletedEvent))
        self.assertEqual(buy_order_id, buy_order_completed_event.order_id)

    def test_limit_sell(self):
        self.assertGreater(self.market.get_balance("WETH"), 40)
        # Try to sell 40 ETH to the exchange, and watch for creation event.
        trading_pair = "WETH-USDC"
        amount: Decimal = Decimal("40.0")
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        sell_order_id: str = self.place_order(False,
                                              "WETH-USDC",
                                              amount,
                                              OrderType.LIMIT,
                                              bid_price * Decimal('0.5'),
                                              10001,
                                              FixtureDydx.SELL_LIMIT_ORDER,
                                              FixtureDydx.WS_AFTER_SELL_1,
                                              FixtureDydx.WS_AFTER_SELL_2,
                                              FixtureDydx.WS_AFTER_SELL_3)
        [sell_order_completed_event] = self.run_parallel(
            self.market_logger.wait_for(SellOrderCompletedEvent))
        self.assertEqual(sell_order_id, sell_order_completed_event.order_id)

    def test_limit_maker_rejections(self):
        self.assertGreater(self.market.get_balance("WETH"), 40)
        trading_pair = "WETH-USDC"
        amount: Decimal = Decimal("40.0")
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        sell_order_id: str = self.place_order(
            False,
            "WETH-USDC",
            amount,
            OrderType.LIMIT_MAKER,
            bid_price * Decimal('0.5'),
            10001,
            FixtureDydx.SELL_LIMIT_MAKER_ORDER,
            FixtureDydx.WS_AFTER_SELL_1,
            FixtureDydx.LIMIT_MAKER_SELL_ERROR)
        [order_cancelled_event] = self.run_parallel(
            self.market_logger.wait_for(OrderCancelledEvent))
        self.assertEqual(sell_order_id, order_cancelled_event.order_id)

    def test_limit_makers_unfilled(self):
        self.assertGreater(self.market.get_balance("USDC"), 16000)
        trading_pair = "WETH-USDC"
        amount: Decimal = Decimal("40.0")
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        buy_order_id: str = self.place_order(True,
                                             "WETH-USDC",
                                             amount,
                                             OrderType.LIMIT_MAKER,
                                             bid_price * Decimal('0.5'),
                                             10001,
                                             FixtureDydx.BUY_LIMIT_MAKER_ORDER,
                                             FixtureDydx.WS_AFTER_BUY_1)
        self.run_parallel(asyncio.sleep(6.0))
        self.market.cancel(trading_pair, buy_order_id)

        if API_MOCK_ENABLED:
            MockWebSocketServerFactory.send_json_threadsafe(
                self._ws_user_url,
                FixtureDydx.WS_AFTER_CANCEL_BUY,
                delay=0.1)
        [order_cancelled_event] = self.run_parallel(
            self.market_logger.wait_for(OrderCancelledEvent))

    def test_market_buy(self):
        # Market orders not supported on Dydx
        pass

    def test_market_sell(self):
        # Market orders not supported on Dydx
        pass

    def test_cancel_order(self):
        self.assertGreater(self.market.get_balance("USDC"), 16000)
        trading_pair = "WETH-USDC"
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        amount: Decimal = Decimal("40.0")

        # Intentionally setting price far away from best ask
        client_order_id = self.place_order(True,
                                           "WETH-USDC",
                                           amount,
                                           OrderType.LIMIT_MAKER,
                                           bid_price * Decimal('0.5'),
                                           10001,
                                           FixtureDydx.BUY_LIMIT_ORDER,
                                           FixtureDydx.WS_AFTER_BUY_1)
        self.run_parallel(asyncio.sleep(1.0))
        self.market.cancel(trading_pair, client_order_id)
        if API_MOCK_ENABLED:
            MockWebSocketServerFactory.send_json_threadsafe(
                self._ws_user_url,
                FixtureDydx.WS_AFTER_CANCEL_BUY,
                delay=0.1)
        [order_cancelled_event] = self.run_parallel(
            self.market_logger.wait_for(OrderCancelledEvent))

        order_cancelled_event: OrderCancelledEvent = order_cancelled_event

        self.run_parallel(asyncio.sleep(6.0))
        self.assertEqual(0, len(self.market.limit_orders))
        self.assertEqual(client_order_id, order_cancelled_event.order_id)

    def test_cancel_all(self):
        self.assertGreater(self.market.get_balance("USDC"), 16000)
        trading_pair = "WETH-USDC"
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        amount: Decimal = Decimal("40.0")

        # Intentionally setting price far away from best ask
        client_order_id = self.place_order(True,
                                           "WETH-USDC",
                                           amount,
                                           OrderType.LIMIT,
                                           bid_price * Decimal('0.5'),
                                           10001,
                                           FixtureDydx.BUY_LIMIT_ORDER,
                                           FixtureDydx.WS_AFTER_BUY_1)
        self.run_parallel(asyncio.sleep(1.0))
        self.run_parallel(self.market.cancel_all(5.0))
        if API_MOCK_ENABLED:
            MockWebSocketServerFactory.send_json_threadsafe(
                self._ws_user_url,
                FixtureDydx.WS_AFTER_CANCEL_BUY,
                delay=0.1)
        [order_cancelled_event] = self.run_parallel(
            self.market_logger.wait_for(OrderCancelledEvent))
        order_cancelled_event: OrderCancelledEvent = order_cancelled_event

        self.run_parallel(asyncio.sleep(6.0))
        self.assertEqual(0, len(self.market.limit_orders))
        self.assertEqual(client_order_id, order_cancelled_event.order_id)

    def test_limit_orders(self):
        self.assertGreater(self.market.get_balance("USDC"), 16000)
        trading_pair = "WETH-USDC"
        amount: Decimal = Decimal("40.0")
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        buy_order_id: str = self.place_order(True,
                                             "WETH-USDC",
                                             amount,
                                             OrderType.LIMIT,
                                             bid_price * Decimal('0.5'),
                                             10001,
                                             FixtureDydx.BUY_LIMIT_ORDER,
                                             FixtureDydx.WS_AFTER_BUY_1)
        [buy_order_created_event] = self.run_parallel(
            self.market_logger.wait_for(BuyOrderCreatedEvent))
        self.assertEqual(1, len(self.market.limit_orders))
        self.assertEqual(amount, self.market.limit_orders[0].quantity)
        self.market.cancel(trading_pair, buy_order_id)
        if API_MOCK_ENABLED:
            MockWebSocketServerFactory.send_json_threadsafe(
                self._ws_user_url,
                FixtureDydx.WS_AFTER_CANCEL_BUY,
                delay=0.1)
        [order_cancelled_event] = self.run_parallel(
            self.market_logger.wait_for(OrderCancelledEvent))

    def test_order_saving_and_restoration(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql: SQLConnectionManager = SQLConnectionManager(
            SQLConnectionType.TRADE_FILLS,
            db_path=self.db_path)
        order_id: Optional[str] = None
        trading_pair: str = "WETH-USDC"

        recorder: MarketsRecorder = MarketsRecorder(
            sql,
            [self.market],
            config_path,
            strategy_name)
        recorder.start()
        try:
            self.assertEqual(0, len(self.market.tracking_states))
            self.assertGreater(self.market.get_balance("USDC"), 16000)
            amount: Decimal = Decimal("40.0")
            current_bid_price: Decimal = self.market.get_price(
                trading_pair,
                True)
            bid_price: Decimal = Decimal("0.5") * current_bid_price
            quantize_bid_price: Decimal = self.market.quantize_order_price(
                trading_pair,
                bid_price)
            order_id = self.place_order(True,
                                        trading_pair,
                                        amount,
                                        OrderType.LIMIT,
                                        quantize_bid_price,
                                        10001,
                                        FixtureDydx.BUY_LIMIT_ORDER,
                                        FixtureDydx.WS_AFTER_BUY_1)

            [order_created_event] = self.run_parallel(
                self.market_logger.wait_for(BuyOrderCreatedEvent))
            order_created_event: BuyOrderCreatedEvent = order_created_event

            self.assertEqual(order_id, order_created_event.order_id)

            # Verify tracking states
            self.assertEqual(1, len(self.market.tracking_states))
            self.assertEqual(order_id,
                             list(self.market.tracking_states.keys())[0])

            # Verify orders from recorder
            recorded_orders: List[Order] = recorder.get_orders_for_config_and_market(
                config_path,
                self.market)
            self.assertEqual(1, len(recorded_orders))
            self.assertEqual(order_id, recorded_orders[0].id)

            # Verify saved market states
            saved_market_states: MarketState = recorder.get_market_states(
                config_path,
                self.market)
            self.assertIsNotNone(saved_market_states)
            self.assertIsInstance(saved_market_states.saved_state, dict)
            self.assertGreater(len(saved_market_states.saved_state), 0)

            # Close out the current market and start another market.
            self.clock.remove_iterator(self.market)

            for event_tag in self.market_events:
                self.market.remove_listener(event_tag, self.market_logger)

            self.market: DydxExchange = DydxExchange(
                dydx_eth_private_key=PRIVATE_KEY,
                dydx_node_address=NODE_ADDRESS,
                poll_interval=10.0,
                trading_pairs=[trading_pair],
                trading_required=True
            )
            for event_tag in self.market_events:
                self.market.add_listener(event_tag, self.market_logger)
            recorder.stop()
            recorder = MarketsRecorder(sql,
                                       [self.market],
                                       config_path,
                                       strategy_name)
            recorder.start()
            saved_market_states = recorder.get_market_states(config_path,
                                                             self.market)
            self.clock.add_iterator(self.market)
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            self.market.restore_tracking_states(
                saved_market_states.saved_state)
            self.assertEqual(1, len(self.market.limit_orders))
            self.assertEqual(1, len(self.market.tracking_states))

            # Cancel the order and verify that the change is saved.
            self.run_parallel(asyncio.sleep(5.0))
            self.market.cancel(trading_pair, order_id)
            if API_MOCK_ENABLED:
                MockWebSocketServerFactory.send_json_threadsafe(
                    self._ws_user_url,
                    FixtureDydx.WS_AFTER_CANCEL_BUY,
                    delay=0.1)
            self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
            order_id = None
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            saved_market_states = recorder.get_market_states(
                config_path,
                self.market)
            self.assertEqual(0, len(saved_market_states.saved_state))
        finally:
            if order_id is not None:
                self.market.cancel(trading_pair, order_id)
                if API_MOCK_ENABLED:
                    MockWebSocketServerFactory.send_json_threadsafe(
                        self._ws_user_url,
                        FixtureDydx.WS_AFTER_CANCEL_BUY,
                        delay=0.1)
                self.run_parallel(
                    self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()

    def test_order_fill_record(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql: SQLConnectionManager = SQLConnectionManager(
            SQLConnectionType.TRADE_FILLS,
            db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql,
                                                    [self.market],
                                                    config_path,
                                                    strategy_name)
        recorder.start()
        try:
            ask_price: Decimal = self.market.get_price("WETH-USDC", True)
            self.assertGreater(self.market.get_balance("USDC"), 16000)
            amount: Decimal = Decimal('40')
            order_id = self.place_order(True,
                                        "WETH-USDC",
                                        amount,
                                        OrderType.LIMIT,
                                        ask_price * Decimal('1.5'),
                                        1000100010001000,
                                        FixtureDydx.BUY_LIMIT_ORDER,
                                        FixtureDydx.WS_AFTER_BUY_1,
                                        FixtureDydx.WS_AFTER_BUY_2,
                                        FixtureDydx.WS_AFTER_BUY_3)
            [buy_order_completed_event] = self.run_parallel(
                self.market_logger.wait_for(BuyOrderCompletedEvent))
            # Reset the logs
            self.market_logger.clear()
            # Try to sell back the same amount of LINK to the exchange,
            # and watch for completion event.
            ask_price: Decimal = self.market.get_price("WETH-USDC", False)
            amount = buy_order_completed_event.base_asset_amount
            order_id = self.place_order(False,
                                        "WETH-USDC",
                                        amount,
                                        OrderType.LIMIT,
                                        ask_price,
                                        1000200010001000,
                                        FixtureDydx.SELL_LIMIT_ORDER,
                                        FixtureDydx.WS_AFTER_SELL_1,
                                        FixtureDydx.WS_AFTER_SELL_2,
                                        FixtureDydx.WS_AFTER_SELL_3)
            [sell_order_completed_event] = self.run_parallel(
                self.market_logger.wait_for(SellOrderCompletedEvent))

            # Query the persisted trade logs
            trade_fills: List[TradeFill] = recorder.get_trades_for_config(
                config_path)
            self.assertGreaterEqual(len(trade_fills), 2)
            buy_fills: List[TradeFill] = [
                t for t in trade_fills if t.trade_type == "BUY"]
            sell_fills: List[TradeFill] = [
                t for t in trade_fills if t.trade_type == "SELL"]
            self.assertGreaterEqual(len(buy_fills), 1)
            self.assertGreaterEqual(len(sell_fills), 1)

            order_id = None

        finally:
            if order_id is not None:
                self.market.cancel("WETH-USDC", order_id)
            recorder.stop()
            os.unlink(self.db_path)


def main():
    logging.basicConfig(level=logging.ERROR)
    unittest.main()


if __name__ == "__main__":
    main()
