
# TODO: Question: anyone planing to use this file? if not I will delete them in next PR

# from os.path import join, realpath
# import sys;
#
# from hummingbot.connector.exchange.idex.conf import settings
# from hummingbot.connector.exchange.idex.idex_exchange import IdexExchange
#
# sys.path.insert(0, realpath(join(__file__, "../../bin")))
# # import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))
# import asyncio
# import conf
# import contextlib
# from decimal import Decimal
# import logging
# import os
# import time
# import math
# from typing import (
#     List,
#     Dict,
#     Optional
# )
# import unittest
# from unittest.mock import patch
#
# from hummingbot.core.clock import (
#     Clock,
#     ClockMode
# )
# from hummingbot.core.event.events import (
#     BuyOrderCompletedEvent,
#     BuyOrderCreatedEvent,
#     MarketEvent,
#     OrderCancelledEvent,
#     OrderFilledEvent,
#     OrderType,
#     SellOrderCompletedEvent,
#     SellOrderCreatedEvent,
#     MarketOrderFailureEvent,
#     TradeFee,
#     TradeType,
# )
# from hummingbot.core.event.event_logger import EventLogger
# from hummingbot.core.utils.async_utils import (
#     safe_ensure_future,
#     safe_gather,
# )
# from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
#
# from hummingbot.connector.markets_recorder import MarketsRecorder
# from hummingbot.model.market_state import MarketState
# from hummingbot.model.order import Order
# from hummingbot.model.sql_connection_manager import (
#     SQLConnectionManager,
#     SQLConnectionType
# )
# from hummingbot.model.trade_fill import TradeFill
# from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
# from test.integration.assets.mock_data.fixture_idex import FixtureIdex
# from test.integration.humming_web_app import HummingWebApp
# from unittest import mock
# import requests
# from test.integration.humming_ws_server import HummingWsServerFactory
#
#
# # MAINNET_RPC_URL = "http://mainnet-rpc.mainnet:8545"
# logging.basicConfig(level=METRICS_LOG_LEVEL)
# API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
# API_KEY = os.getenv("IDEX_API_KEY") if API_MOCK_ENABLED else conf.idex_api_key
# API_SECRET = os.getenv("IDEX_API_SECRET") if API_MOCK_ENABLED else conf.idex_api_secret_key
#
#
# class IdexExchangeUnitTest(unittest.TestCase):
#     events: List[MarketEvent] = [
#         MarketEvent.ReceivedAsset,
#         MarketEvent.BuyOrderCompleted,
#         MarketEvent.SellOrderCompleted,
#         MarketEvent.OrderFilled,
#         MarketEvent.TransactionFailure,
#         MarketEvent.BuyOrderCreated,
#         MarketEvent.SellOrderCreated,
#         MarketEvent.OrderCancelled,
#         MarketEvent.OrderFailure
#     ]
#
#     market: IdexExchange
#     market_logger: EventLogger
#     stack: contextlib.ExitStack
#     base_api_url = settings.rest_api_url
#
#     @classmethod
#     def setUpClass(cls):
#         # global MAINNET_RPC_URL
#         #
#         # cls.ev_loop = asyncio.get_event_loop()
#         #
#         # if API_MOCK_ENABLED:
#         #     cls.web_app = HummingWebApp.get_instance()
#         #     cls.web_app.add_host_to_mock(cls.base_api_url, ["ping", "time"])
#         #     cls.web_app.start()
#         #     cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
#         #     cls._patcher = mock.patch("aiohttp.client.URL")
#         #     cls._url_mock = cls._patcher.start()
#         #     cls._url_mock.side_effect = cls.web_app.reroute_local
#         #
#         #     cls._req_patcher = unittest.mock.patch.object(requests.Session, "request", autospec=True)
#         #     cls._req_url_mock = cls._req_patcher.start()
#         #     cls._req_url_mock.side_effect = HummingWebApp.reroute_request
#         #     cls.web_app.update_response("get", cls.base_api_url, "/api/v3/account", FixtureIdex.BALANCES)
#         #     cls.web_app.update_response("get", cls.base_api_url, "/api/v1/exchangeInfo",
#         #                                 FixtureIdex.MARKETS)
#         #     cls.web_app.update_response("get", cls.base_api_url, "/wapi/v3/tradeFee.html",
#         #                                 FixtureIdex.TRADE_FEES)
#         #     cls.web_app.update_response("post", cls.base_api_url, "/api/v1/userDataStream",
#         #                                 FixtureIdex.LISTEN_KEY)
#         #     cls.web_app.update_response("put", cls.base_api_url, "/api/v1/userDataStream",
#         #                                 FixtureIdex.LISTEN_KEY)
#         #     cls.web_app.update_response("get", cls.base_api_url, "/api/v1/depth",
#         #                                 FixtureIdex.LINKETH_SNAP, params={'symbol': 'LINKETH'})
#         #     cls.web_app.update_response("get", cls.base_api_url, "/api/v1/depth",
#         #                                 FixtureIdex.ZRXETH_SNAP, params={'symbol': 'ZRXETH'})
#         #     ws_base_url = "wss://stream.binance.com:9443/ws"
#         #     cls._ws_user_url = f"{ws_base_url}/{FixtureIdex.LISTEN_KEY['listenKey']}"
#         #     HummingWsServerFactory.start_new_server(cls._ws_user_url)
#         #     HummingWsServerFactory.start_new_server(f"{ws_base_url}/linketh@depth/zrxeth@depth")
#         #     cls._ws_patcher = unittest.mock.patch("websockets.connect", autospec=True)
#         #     cls._ws_mock = cls._ws_patcher.start()
#         #     cls._ws_mock.side_effect = HummingWsServerFactory.reroute_ws_connect
#         #
#         #     cls._t_nonce_patcher = unittest.mock.patch(
#         #         "hummingbot.connector.exchange.idex.idex_exchange.get_tracking_nonce"
#         #     )
#         #     cls._t_nonce_mock = cls._t_nonce_patcher.start()
#         cls.clock: Clock = Clock(ClockMode.REALTIME)
#         cls.market: IdexExchange = IdexExchange(API_KEY, API_SECRET, ["DIL-ETH", "PIP-ETH", "CUR-ETH"], True)
#         print("Initializing Idex market... this will take about a minute.")
#         cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
#         cls.clock.add_iterator(cls.market)
#         cls.stack: contextlib.ExitStack = contextlib.ExitStack()
#         cls._clock = cls.stack.enter_context(cls.clock)
#         cls.ev_loop.run_until_complete(cls.wait_til_ready())
#         print("Ready.")
#
#     @classmethod
#     def tearDownClass(cls) -> None:
#         cls.stack.close()
#         # if API_MOCK_ENABLED:
#         #     cls.web_app.stop()
#         #     cls._patcher.stop()
#         #     cls._req_patcher.stop()
#         #     cls._ws_patcher.stop()
#         #     cls._t_nonce_patcher.stop()
#
#     @classmethod
#     async def wait_til_ready(cls):
#         while True:
#             now = time.time()
#             next_iteration = now // 1.0 + 1
#             if cls.market.ready:
#                 break
#             else:
#                 await cls._clock.run_til(next_iteration)
#             await asyncio.sleep(1.0)
#
#     def setUp(self):
#         self.db_path: str = realpath(join(__file__, "../idex_test.sqlite"))
#         try:
#             os.unlink(self.db_path)
#         except FileNotFoundError:
#             pass
#
#         self.market_logger = EventLogger()
#         for event_tag in self.events:
#             self.market.add_listener(event_tag, self.market_logger)
#
#     def tearDown(self):
#         for event_tag in self.events:
#             self.market.remove_listener(event_tag, self.market_logger)
#         self.market_logger = None
#
#     async def run_parallel_async(self, *tasks):
#         future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
#         while not future.done():
#             now = time.time()
#             next_iteration = now // 1.0 + 1
#             await self._clock.run_til(next_iteration)
#             await asyncio.sleep(1.0)
#         return future.result()
#
#     def run_parallel(self, *tasks):
#         return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))
#
#     def test_get_fee(self):
#         maker_buy_trade_fee: TradeFee = self.market.get_fee("ETH", "DIL", OrderType.LIMIT_MAKER, TradeType.BUY, Decimal(1), Decimal(4000))
#         self.assertGreater(maker_buy_trade_fee.percent, 0)
#         self.assertEqual(len(maker_buy_trade_fee.flat_fees), 0)
#         taker_buy_trade_fee: TradeFee = self.market.get_fee("ETH", "DIL", OrderType.LIMIT, TradeType.BUY, Decimal(1))
#         self.assertGreater(taker_buy_trade_fee.percent, 0)
#         self.assertEqual(len(taker_buy_trade_fee.flat_fees), 0)
#         sell_trade_fee: TradeFee = self.market.get_fee("ETH", "DIL", OrderType.LIMIT, TradeType.SELL, Decimal(1), Decimal(4000))
#         self.assertGreater(sell_trade_fee.percent, 0)
#         self.assertEqual(len(sell_trade_fee.flat_fees), 0)
#         sell_trade_fee: TradeFee = self.market.get_fee("ETH", "DIL", OrderType.LIMIT_MAKER, TradeType.SELL, Decimal(1),
#                                                        Decimal(4000))
#         self.assertGreater(sell_trade_fee.percent, 0)
#         self.assertEqual(len(sell_trade_fee.flat_fees), 0)
#
#     def test_fee_overrides_config(self):
#         fee_overrides_config_map["idex_taker_fee"].value = None
#         taker_fee: TradeFee = self.market.get_fee("DIL", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
#                                                   Decimal('0.1'))
#         self.assertAlmostEqual(Decimal("0.002"), taker_fee.percent)
#         fee_overrides_config_map["idex_taker_fee"].value = Decimal('0.2')
#         taker_fee: TradeFee = self.market.get_fee("DIL", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
#                                                   Decimal('0.1'))
#         self.assertAlmostEqual(Decimal("0.002"), taker_fee.percent)
#         fee_overrides_config_map["idex_taker_fee"].value = None
#         maker_fee: TradeFee = self.market.get_fee("DIL", "ETH", OrderType.LIMIT_MAKER, TradeType.BUY, Decimal(1),
#                                                   Decimal('0.1'))
#         self.assertAlmostEqual(Decimal("0.002"), maker_fee.percent)
#         fee_overrides_config_map["idex_taker_fee"].value = Decimal('0.5')
#         maker_fee: TradeFee = self.market.get_fee("DIL", "ETH", OrderType.LIMIT_MAKER, TradeType.BUY, Decimal(1),
#                                                   Decimal('0.1'))
#         self.assertAlmostEqual(Decimal("0.005"), maker_fee.percent)
#
#     def test_buy_and_sell(self):
#         amount = Decimal(0.00001)
#         self.assertGreater(self.market.get_balance("ETH"), amount)
#         bid_price: Decimal = self.market.get_price("CUR-ETH", True)
#         quantized_amount: Decimal = self.market.quantize_order_amount("CUR-ETH", amount)
#
#         order_id = self.place_order(True, "CUR-ETH", amount, OrderType.LIMIT, bid_price)
#         [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
#         order_completed_event: BuyOrderCompletedEvent = order_completed_event
#         trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
#                                                 if isinstance(t, OrderFilledEvent)]
#         print(f"TRADE: {order_completed_event}")
#         print(f"TRADE: {trade_events}")
#         base_amount_traded: Decimal = sum(t.amount for t in trade_events)
#         quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)
#
#         self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
#         self.assertEqual(order_id, order_completed_event.order_id)
#         self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
#         self.assertEqual("CUR", order_completed_event.base_asset)
#         self.assertEqual("ETH", order_completed_event.quote_asset)
#         self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
#         self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
#         self.assertGreater(order_completed_event.fee_amount, Decimal(0))
#         self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
#                              for event in self.market_logger.event_log]))
#
#         # Reset the logs
#         self.market_logger.clear()
#
#         # Try to sell back the same amount of ZRX to the exchange, and watch for completion event.
#         ask_price: Decimal = self.market.get_price("LINK-ETH", False)
#         amount = order_completed_event.base_asset_amount
#         quantized_amount = order_completed_event.base_asset_amount
#         order_id = self.place_order(False, "LINK-ETH", amount, OrderType.LIMIT, ask_price, 10002, FixtureIdex.SELL_MARKET_ORDER,
#                                     FixtureIdex.WS_AFTER_SELL_1, FixtureIdex.WS_AFTER_SELL_2)
#         [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
#         order_completed_event: SellOrderCompletedEvent = order_completed_event
#         trade_events = [t for t in self.market_logger.event_log
#                         if isinstance(t, OrderFilledEvent)]
#         base_amount_traded = sum(t.amount for t in trade_events)
#         quote_amount_traded = sum(t.amount * t.price for t in trade_events)
#
#         self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
#         self.assertEqual(order_id, order_completed_event.order_id)
#         self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
#         self.assertEqual("LINK", order_completed_event.base_asset)
#         self.assertEqual("ETH", order_completed_event.quote_asset)
#         self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
#         self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
#         self.assertGreater(order_completed_event.fee_amount, Decimal(0))
#         self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
#                              for event in self.market_logger.event_log]))
#
#     # TBD
#     # def test_limit_maker_rejections(self):
#     #     self.assertGreater(self.market.get_balance("ETH"), Decimal("0.05"))
#     #
#     #     # Try to put a buy limit maker order that is going to match, this should triggers order failure event.
#     #     price: Decimal = self.market.get_price("LINK-ETH", True) * Decimal('1.02')
#     #     price: Decimal = self.market.quantize_order_price("LINK-ETH", price)
#     #     amount = self.market.quantize_order_amount("LINK-ETH", 1)
#     #
#     #     order_id = self.place_order(True, "LINK-ETH", amount, OrderType.LIMIT_MAKER,
#     #                                 price, 10001,
#     #                                 FixtureIdex.LIMIT_MAKER_ERROR)
#     #     [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
#     #     self.assertEqual(order_id, order_failure_event.order_id)
#     #
#     #     self.market_logger.clear()
#     #
#     #     # Try to put a sell limit maker order that is going to match, this should triggers order failure event.
#     #     price: Decimal = self.market.get_price("LINK-ETH", True) * Decimal('0.98')
#     #     price: Decimal = self.market.quantize_order_price("LINK-ETH", price)
#     #     amount = self.market.quantize_order_amount("LINK-ETH", 1)
#     #
#     #     order_id = self.place_order(False, "LINK-ETH", amount, OrderType.LIMIT_MAKER,
#     #                                 price, 10002,
#     #                                 FixtureIdex.LIMIT_MAKER_ERROR)
#     #     [order_failure_event] = self.run_parallel(self.market_logger.wait_for(MarketOrderFailureEvent))
#     #     self.assertEqual(order_id, order_failure_event.order_id)
#
#     # TBD
#     def test_limit_makers_unfilled(self):
#         price = self.market.get_price("LINK-ETH", True) * Decimal("0.8")
#         price = self.market.quantize_order_price("LINK-ETH", price)
#         amount = self.market.quantize_order_amount("LINK-ETH", 1)
#
#         order_id = self.place_order(True, "LINK-ETH", amount, OrderType.LIMIT_MAKER,
#                                     price, 10001,
#                                     FixtureIdex.OPEN_BUY_ORDER)
#         [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
#         order_created_event: BuyOrderCreatedEvent = order_created_event
#         self.assertEqual(order_id, order_created_event.order_id)
#
#         price = self.market.get_price("LINK-ETH", True) * Decimal("1.2")
#         price = self.market.quantize_order_price("LINK-ETH", price)
#         amount = self.market.quantize_order_amount("LINK-ETH", 1)
#
#         order_id = self.place_order(False, "LINK-ETH", amount, OrderType.LIMIT_MAKER,
#                                     price, 10002,
#                                     FixtureIdex.OPEN_SELL_ORDER)
#         [order_created_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
#         order_created_event: BuyOrderCreatedEvent = order_created_event
#         self.assertEqual(order_id, order_created_event.order_id)
#
#         [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
#         for cr in cancellation_results:
#             self.assertEqual(cr.success, True)
#
#     def fixture(self, fixture_data, **overwrites):
#         data = fixture_data.copy()
#         for key, value in overwrites.items():
#             if key not in data:
#                 raise Exception(f"{key} not found in fixture_data")
#             data[key] = value
#         return data
#
#     def order_response(self, fixture_data, nonce, side, trading_pair):
#         self._t_nonce_mock.return_value = nonce
#         order_id = f"{side.lower()}-{trading_pair}-{str(nonce)}"
#         order_resp = fixture_data.copy()
#         order_resp["clientOrderId"] = order_id
#         return order_resp
#
#     def place_order(self, is_buy, trading_pair, amount, order_type, price):
#         if is_buy:
#             order_id = self.market.buy(trading_pair, amount, order_type, price)
#         else:
#             order_id = self.market.sell(trading_pair, amount, order_type, price)
#         return order_id
#
#
# if __name__ == "__main__":
#     logging.getLogger("hummingbot.core.event.event_reporter").setLevel(logging.WARNING)
#     unittest.main()
