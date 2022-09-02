# import asyncio
# import time
# import unittest
# from contextlib import ExitStack
# from decimal import Decimal
# from os.path import join, realpath
# from test.mock.http_recorder import HttpPlayer
# from typing import Awaitable, Dict, List
# from unittest.mock import patch
#
# from aiohttp import ClientSession
# from aioresponses import aioresponses
# from async_timeout import timeout
#
# from bin import path_util  # noqa: F401
# from hummingbot.client.config.client_config_map import ClientConfigMap
# from hummingbot.client.config.config_helpers import ClientConfigAdapter
# from hummingbot.connector.gateway.clob.gateway_sol_clob import CLOBInFlightOrder, GatewaySOLCLOB
# from hummingbot.core.clock import Clock, ClockMode
# from hummingbot.core.event.event_logger import EventLogger
# from hummingbot.core.event.events import (
#     BuyOrderCreatedEvent,
#     MarketEvent,
#     OrderFilledEvent,
#     OrderType,
#     SellOrderCreatedEvent,
#     TokenApprovalEvent,
#     TokenApprovalSuccessEvent,
#     TradeType,
# )
# from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
# from hummingbot.core.utils.async_utils import safe_ensure_future
#
# s_decimal_0: Decimal = Decimal(0)
#
#
# class GatewaySOLCLOBConnectorUnitTest(unittest.TestCase):
#     _db_path: str
#     _http_player: HttpPlayer
#     _patch_stack: ExitStack
#     _clock: Clock
#     _connector: GatewaySOLCLOB
#
#     @classmethod
#     def setUpClass(cls) -> None:
#         super().setUpClass()
#         cls.ev_loop = asyncio.get_event_loop()
#         GatewayHttpClient.__instance = None
#         cls._db_path = realpath(join(__file__, "../fixtures/gateway_sol_clob_fixture.db"))
#         cls._http_player = HttpPlayer(cls._db_path)
#         cls._clock: Clock = Clock(ClockMode.REALTIME)
#         cls._client_config_map = ClientConfigAdapter(ClientConfigMap())
#         cls._connector: GatewaySOLCLOB = GatewaySOLCLOB(
#             client_config_map=cls._client_config_map,
#             connector_name="serum",
#             chain="solana",
#             network="testnet",
#             wallet_address="FMosjpvtAxwL6GFDSL31o9pU5somKjifbkt32bEgLddf", # noqa: mock
#             trading_pairs=["SOL-USDC"],
#             trading_required=True
#         )
#         cls._clock.add_iterator(cls._connector)
#         cls._patch_stack = ExitStack()
#         cls._patch_stack.enter_context(cls._http_player.patch_aiohttp_client())
#         cls._patch_stack.enter_context(
#             patch(
#                 "hummingbot.core.gateway.gateway_http_client.GatewayHttpClient._http_client",
#                 return_value=ClientSession()
#             )
#         )
#         cls._patch_stack.enter_context(cls._clock)
#         GatewayHttpClient.get_instance(client_config_map=cls._client_config_map).base_url = "https://localhost:5000"
#
#     @classmethod
#     def tearDownClass(cls) -> None:
#         cls._patch_stack.close()
#         GatewayHttpClient.__instance = None
#         super().tearDownClass()
#
#     def setUp(self) -> None:
#         super().setUp()
#         self.async_run_with_timeout(self.wait_til_ready(), 3)
#         self._http_player.replay_timestamp_ms = None
#
#     @classmethod
#     async def wait_til_ready(cls):
#         while True:
#             now: float = time.time()
#             next_iteration = now // 1.0 + 1
#             if cls._connector.ready:
#                 break
#             else:
#                 await cls._clock.run_til(next_iteration + 0.1)
#
#     async def run_clock(self):
#         while True:
#             now: float = time.time()
#             next_iteration = now // 1.0 + 1
#             await self._clock.run_til(next_iteration + 0.1)
#
#     def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
#         return self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
#
#     @aioresponses()
#     async def test_update_balances(self):
#         self._connector._account_balances.clear()
#         self.assertEqual(0, len(self._connector.get_all_balances()))
#         self.async_run_with_timeout(self._connector.update_balances(on_interval=False))
#         self.assertEqual(3, len(self._connector.get_all_balances()))
#         self.assertAlmostEqual(Decimal("38.230251744322271175"), self._connector.get_balance("SOL"))
#         self.assertAlmostEqual(Decimal("1015.242427495432379422"), self._connector.get_balance("USDC"))
#
#     @aioresponses()
#     async def test_get_allowances(self):
#         big_num: Decimal = Decimal("1000000000000000000000000000")
#         allowances: Dict[str, Decimal] = self.async_run_with_timeout(self._connector.get_allowances())
#         self.assertEqual(2, len(allowances))
#         self.assertGreater(allowances.get("SOL"), big_num)
#         self.assertGreater(allowances.get("USDC"), big_num)
#
#     @aioresponses()
#     async def test_get_chain_info(self):
#         self._connector._chain_info.clear()
#         self.async_run_with_timeout(self._connector.get_chain_info())
#         self.assertGreater(len(self._connector._chain_info), 2)
#         self.assertEqual("SOL", self._connector._chain_info.get("nativeCurrency"))
#
#     @aioresponses()
#     async def test_update_approval_status(self):
#         def create_approval_record(token_symbol: str, tx_hash: str) -> CLOBInFlightOrder:
#             return CLOBInFlightOrder(
#                 client_order_id=self._connector.create_approval_order_id(token_symbol),
#                 exchange_order_id=tx_hash,
#                 trading_pair=token_symbol,
#                 order_type=OrderType.LIMIT,
#                 trade_type=TradeType.BUY,
#                 price=s_decimal_0,
#                 amount=s_decimal_0,
#                 gas_price=s_decimal_0,
#                 creation_timestamp=self._connector.current_timestamp
#             )
#         successful_records: List[CLOBInFlightOrder] = [
#             create_approval_record(
#                 "SOL",
#                 "0x66b533792f45780fc38573bfd60d6043ab266471607848fb71284cd0d9eecff9"        # noqa: mock
#             ),
#             create_approval_record(
#                 "USDC",
#                 "0x4f81aa904fcb16a8938c0e0a76bf848df32ce6378e9e0060f7afc4b2955de405"        # noqa: mock
#             ),
#         ]
#         fake_records: List[CLOBInFlightOrder] = [
#             create_approval_record(
#                 "SOL",
#                 "0x66b533792f45780fc38573bfd60d6043ab266471607848fb71284cd0d9eecff8"        # noqa: mock
#             ),
#             create_approval_record(
#                 "USDC",
#                 "0x4f81aa904fcb16a8938c0e0a76bf848df32ce6378e9e0060f7afc4b2955de404"        # noqa: mock
#             ),
#         ]
#
#         event_logger: EventLogger = EventLogger()
#         self._connector.add_listener(TokenApprovalEvent.ApprovalSuccessful, event_logger)
#         self._connector.add_listener(TokenApprovalEvent.ApprovalFailed, event_logger)
#
#         try:
#             self.async_run_with_timeout(self._connector.update_token_approval_status(successful_records + fake_records))
#             self.assertEqual(2, len(event_logger.event_log))
#             self.assertEqual(
#                 {"SOL", "USDC"},
#                 set(e.token_symbol for e in event_logger.event_log)
#             )
#         finally:
#             self._connector.remove_listener(TokenApprovalEvent.ApprovalSuccessful, event_logger)
#             self._connector.remove_listener(TokenApprovalEvent.ApprovalFailed, event_logger)
#
#     @aioresponses()
#     async def test_update_order_status(self):
#         def create_order_record(
#                 trading_pair: str,
#                 trade_type: TradeType,
#                 tx_hash: str,
#                 price: Decimal,
#                 amount: Decimal,
#                 gas_price: Decimal) -> CLOBInFlightOrder:
#             order: CLOBInFlightOrder = CLOBInFlightOrder(
#                 client_order_id=self._connector.create_market_order_id(trade_type, trading_pair),
#                 exchange_order_id=tx_hash,
#                 trading_pair=trading_pair,
#                 order_type=OrderType.LIMIT,
#                 trade_type=trade_type,
#                 price=price,
#                 amount=amount,
#                 gas_price=gas_price,
#                 creation_timestamp=self._connector.current_timestamp
#             )
#             order.fee_asset = self._connector._native_currency
#             self._connector._order_tracker.start_tracking_order(order)
#             return order
#         successful_records: List[CLOBInFlightOrder] = [
#             create_order_record(
#                 "SOL-USDC",
#                 TradeType.BUY,
#                 "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18",  # noqa: mock
#                 Decimal("0.00267589"),
#                 Decimal("1000"),
#                 Decimal("29")
#             )
#         ]
#         fake_records: List[CLOBInFlightOrder] = [
#             create_order_record(
#                 "SOL-USDC",
#                 TradeType.BUY,
#                 "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e17",       # noqa: mock
#                 Decimal("0.00267589"),
#                 Decimal("1000"),
#                 Decimal("29")
#             )
#         ]
#
#         event_logger: EventLogger = EventLogger()
#         self._connector.add_listener(MarketEvent.OrderFilled, event_logger)
#
#         try:
#             self.async_run_with_timeout(self._connector.update_order_status(successful_records + fake_records))
#             async with timeout(10):
#                 while len(event_logger.event_log) < 1:
#                     self.async_run_with_timeout(event_logger.wait_for(OrderFilledEvent))
#             filled_event: OrderFilledEvent = event_logger.event_log[0]
#             self.assertEqual(
#                 "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18",       # noqa: mock
#                 filled_event.exchange_trade_id)
#         finally:
#             self._connector.remove_listener(MarketEvent.OrderFilled, event_logger)
#
#     @aioresponses()
#     async def test_get_quote_price(self):
#         buy_price: Decimal = self.async_run_with_timeout(self._connector.get_quote_price("SOL-USDC", True, Decimal(1000)))
#         sell_price: Decimal = self.async_run_with_timeout(self._connector.get_quote_price("SOL-USDC", False, Decimal(1000)))
#         self.assertEqual(Decimal("43.3752383799999989832940627820789813995361328125"), buy_price)
#         self.assertEqual(Decimal("43.3752383799999989832940627820789813995361328125"), sell_price)
#
#     @aioresponses()
#     async def test_approve_token(self):
#         self._http_player.replay_timestamp_ms = 1648499867736
#         sol_in_flight_order: CLOBInFlightOrder = self.async_run_with_timeout(self._connector.approve_token("SOL"))
#         self._http_player.replay_timestamp_ms = 1648499871595
#         usdc_in_flight_order: CLOBInFlightOrder = self.async_run_with_timeout(self._connector.approve_token("USDC"))
#
#         self.assertEqual(
#             "8PZnzjEUJ1B1sMAU3xhzpfK8T4QzydDrnTZrWdzzcno",       # noqa: mock
#             sol_in_flight_order.exchange_order_id
#         )
#         self.assertEqual(
#             "8PZnzjEUJ1B1sMAU3xhzpfK8T4QzydDrnTZrWdzzcno",       # noqa: mock
#             usdc_in_flight_order.exchange_order_id
#         )
#
#         clock_task: asyncio.Task = safe_ensure_future(self.run_clock())
#         event_logger: EventLogger = EventLogger()
#         self._connector.add_listener(TokenApprovalEvent.ApprovalSuccessful, event_logger)
#
#         self._http_player.replay_timestamp_ms = 1648500060232
#         try:
#             async with timeout(10):
#                 while len(event_logger.event_log) < 2:
#                     self.async_run_with_timeout(event_logger.wait_for(TokenApprovalSuccessEvent))
#             self.assertEqual(2, len(event_logger.event_log))
#             self.assertEqual(
#                 {"SOL", "USDC"},
#                 set(e.token_symbol for e in event_logger.event_log)
#             )
#         finally:
#             clock_task.cancel()
#             try:
#                 self.async_run_with_timeout(clock_task)
#             except asyncio.CancelledError:
#                 pass
#
#     @aioresponses()
#     async def test_buy_order(self):
#         self._http_player.replay_timestamp_ms = 1648500060561
#         clock_task: asyncio.Task = safe_ensure_future(self.run_clock())
#         event_logger: EventLogger = EventLogger()
#         self._connector.add_listener(MarketEvent.BuyOrderCreated, event_logger)
#         self._connector.add_listener(MarketEvent.OrderFilled, event_logger)
#
#         try:
#             self._connector.buy("SOL-USDC", Decimal(100), OrderType.LIMIT, Decimal("0.002861464039500"))
#             order_created_event: BuyOrderCreatedEvent = self.async_run_with_timeout(event_logger.wait_for(
#                 BuyOrderCreatedEvent,
#                 timeout_seconds=5
#             ))
#             self.assertEqual(
#                 "1HEGEidnzzGvdKAB6dui5dZBB4qcBbqEMPgjbch8b9qdzf72Wworr11FqxdHDCjJVoG4Q3P9Fw4ergmwW3u47rC7",       # noqa: mock
#                 order_created_event.exchange_order_id
#             )
#             self._http_player.replay_timestamp_ms = 1648500097569
#             order_filled_event: OrderFilledEvent = self.async_run_with_timeout(event_logger.wait_for(OrderFilledEvent, timeout_seconds=5))
#             self.assertEqual(
#                 "1HEGEidnzzGvdKAB6dui5dZBB4qcBbqEMPgjbch8b9qdzf72Wworr11FqxdHDCjJVoG4Q3P9Fw4ergmwW3u47rC7",       # noqa: mock
#                 order_filled_event.exchange_trade_id
#             )
#         finally:
#             clock_task.cancel()
#             try:
#                 self.async_run_with_timeout(clock_task)
#             except asyncio.CancelledError:
#                 pass
#
#     @aioresponses()
#     async def test_sell_order(self):
#         self._http_player.replay_timestamp_ms = 1648500097825
#         clock_task: asyncio.Task = safe_ensure_future(self.run_clock())
#         event_logger: EventLogger = EventLogger()
#         self._connector.add_listener(MarketEvent.SellOrderCreated, event_logger)
#         self._connector.add_listener(MarketEvent.OrderFilled, event_logger)
#
#         try:
#             self._connector.sell("SOL-USDC", Decimal(100), OrderType.LIMIT, Decimal("0.002816023229500"))
#             order_created_event: SellOrderCreatedEvent = self.async_run_with_timeout(event_logger.wait_for(
#                 SellOrderCreatedEvent,
#                 timeout_seconds=5
#             ))
#             self.assertEqual(
#                 "1HEGEidnzzGvdKAB6dui5dZBB4qcBbqEMPgjbch8b9qdzf72Wworr11FqxdHDCjJVoG4Q3P9Fw4ergmwW3u47rC7",       # noqa: mock
#                 order_created_event.exchange_order_id
#             )
#             self._http_player.replay_timestamp_ms = 1648500133889
#             order_filled_event: OrderFilledEvent = self.async_run_with_timeout(event_logger.wait_for(OrderFilledEvent, timeout_seconds=5))
#             self.assertEqual(
#                 "1HEGEidnzzGvdKAB6dui5dZBB4qcBbqEMPgjbch8b9qdzf72Wworr11FqxdHDCjJVoG4Q3P9Fw4ergmwW3u47rC7",       # noqa: mock
#                 order_filled_event.exchange_trade_id
#             )
#         finally:
#             clock_task.cancel()
#             try:
#                 self.async_run_with_timeout(clock_task)
#             except asyncio.CancelledError:
#                 pass
