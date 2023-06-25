import asyncio
import time
import unittest
from contextlib import ExitStack
from decimal import Decimal
from os.path import join, realpath
from test.mock.http_recorder import HttpPlayer
from typing import Dict, List
from unittest.mock import patch

from aiohttp import ClientSession
from aiounittest import async_test
from async_timeout import timeout

from bin import path_util  # noqa: F401
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.gateway.amm_lp.gateway_evm_amm_lp import GatewayEVMAMMLP, GatewayInFlightLPOrder
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    LPType,
    MarketEvent,
    RangePositionFeeCollectedEvent,
    RangePositionLiquidityAddedEvent,
    RangePositionLiquidityRemovedEvent,
    RangePositionUpdateEvent,
    TokenApprovalEvent,
    TokenApprovalSuccessEvent,
)
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future

ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
s_decimal_0: Decimal = Decimal(0)


class GatewayEVMAMMLPConnectorUnitTest(unittest.TestCase):
    _db_path: str
    _http_player: HttpPlayer
    _patch_stack: ExitStack
    _clock: Clock
    _connector: GatewayEVMAMMLP

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._db_path = realpath(join(__file__, "../fixtures/gateway_evm_amm_lp_fixture.db"))
        cls._http_player = HttpPlayer(cls._db_path)
        cls._clock: Clock = Clock(ClockMode.REALTIME)
        cls._client_config_map = ClientConfigAdapter(ClientConfigMap())
        cls._connector: GatewayEVMAMMLP = GatewayEVMAMMLP(
            client_config_map=cls._client_config_map,
            connector_name="uniswapLP",
            chain="ethereum",
            network="kovan",
            address="0xefb7be8631d154d4c0ad8676fec0897b2894fe8f",
            trading_pairs=["COIN1-COIN3"],
            trading_required=True
        )
        cls._clock.add_iterator(cls._connector)
        cls._patch_stack = ExitStack()
        cls._patch_stack.enter_context(cls._http_player.patch_aiohttp_client())
        cls._patch_stack.enter_context(
            patch(
                "hummingbot.core.gateway.gateway_http_client.GatewayHttpClient._http_client",
                return_value=ClientSession()
            )
        )
        cls._patch_stack.enter_context(cls._clock)
        GatewayHttpClient.get_instance(client_config_map=cls._client_config_map).base_url = "https://localhost:5000"
        ev_loop.run_until_complete(cls.wait_til_ready())

    @classmethod
    def tearDownClass(cls) -> None:
        cls._patch_stack.close()

    def setUp(self) -> None:
        self._http_player.replay_timestamp_ms = None

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now: float = time.time()
            next_iteration = now // 1.0 + 1
            if cls._connector.ready:
                break
            else:
                await cls._clock.run_til(next_iteration + 0.1)

    async def run_clock(self):
        while True:
            now: float = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration + 0.1)

    @async_test(loop=ev_loop)
    async def test_update_balances(self):
        self._connector._account_balances.clear()
        self.assertEqual(0, len(self._connector.get_all_balances()))
        await self._connector.update_balances(on_interval=False)
        self.assertEqual(3, len(self._connector.get_all_balances()))
        self.assertAlmostEqual(Decimal("299914.137497713523375729"), self._connector.get_balance("COIN1"))
        self.assertAlmostEqual(Decimal("599007.076157878187323412"), self._connector.get_balance("COIN3"))

    @async_test(loop=ev_loop)
    async def test_get_allowances(self):
        big_num: Decimal = Decimal("1000000000000000000000000000")
        allowances: Dict[str, Decimal] = await self._connector.get_allowances()
        self.assertEqual(2, len(allowances))
        self.assertGreater(allowances.get("uniswapLP_COIN1"), big_num)
        self.assertGreater(allowances.get("uniswapLP_COIN3"), big_num)

    @async_test(loop=ev_loop)
    async def test_get_chain_info(self):
        self._connector._chain_info.clear()
        await self._connector.get_chain_info()
        self.assertGreater(len(self._connector._chain_info), 2)
        self.assertEqual("ETH", self._connector._chain_info.get("nativeCurrency"))

    @async_test(loop=ev_loop)
    async def test_update_approval_status(self):
        def create_approval_record(token_symbol: str, tx_hash: str) -> GatewayInFlightLPOrder:
            return GatewayInFlightLPOrder(
                client_order_id=self._connector.create_approval_order_id("uniswapLP", token_symbol),
                exchange_order_id=tx_hash,
                trading_pair=token_symbol,
                lp_type = LPType.ADD,
                lower_price = s_decimal_0,
                upper_price = s_decimal_0,
                amount_0 = s_decimal_0,
                amount_1 = s_decimal_0,
                token_id = 0,
                gas_price=s_decimal_0,
                creation_timestamp=self._connector.current_timestamp
            )
        successful_records: List[GatewayInFlightLPOrder] = [
            create_approval_record(
                "COIN1",
                "0x273a720fdc92554c47f409f4f74d3c262937451ccdbaddfd8d0185a9e3c64dd2"        # noqa: mock
            ),
            create_approval_record(
                "COIN3",
                "0x27d7a7156bd0afc73092602da67774aa3319adbc72213122d65480e482ce0a8b"        # noqa: mock
            ),
        ]
        """fake_records: List[GatewayInFlightLPOrder] = [
            create_approval_record(
                "COIN1",
                "0x273a720fdc92554c47f409f4f74d3c262937451ccdbaddfd8d0185a9e3c64dd1"        # noqa: mock
            ),
            create_approval_record(
                "COIN3",
                "0x27d7a7156bd0afc73092602da67774aa3319adbc72213122d65480e482ce0a8a"        # noqa: mock
            ),
        ]"""

        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(TokenApprovalEvent.ApprovalSuccessful, event_logger)
        self._connector.add_listener(TokenApprovalEvent.ApprovalFailed, event_logger)

        try:
            await self._connector.update_token_approval_status(successful_records)
            self.assertEqual(2, len(event_logger.event_log))
            self.assertEqual(
                {"uniswapLP_COIN1", "uniswapLP_COIN3"},
                set(e.token_symbol for e in event_logger.event_log)
            )
        finally:
            self._connector.remove_listener(TokenApprovalEvent.ApprovalSuccessful, event_logger)
            self._connector.remove_listener(TokenApprovalEvent.ApprovalFailed, event_logger)

    @async_test(loop=ev_loop)
    async def test_get_price(self):
        pool_price: Decimal = await self._connector.get_price("COIN1-COIN3", "LOW")
        self.assertEqual([Decimal("0.66141134")], pool_price)

    @async_test(loop=ev_loop)
    async def test_approve_token(self):
        self._http_player.replay_timestamp_ms = 1652728282963
        coin1_in_flight_order: GatewayInFlightLPOrder = await self._connector.approve_token("uniswapLP", "COIN1")
        self._http_player.replay_timestamp_ms = 1652728286030
        coin3_in_flight_order: GatewayInFlightLPOrder = await self._connector.approve_token("uniswapLP", "COIN3")

        self.assertEqual(
            "0x65ef330422dc9892460e3ea67338013b9ca619270f960c4531f47a1812cb7677",       # noqa: mock
            coin1_in_flight_order.exchange_order_id
        )
        self.assertEqual(
            "0x551970f039ed4190b00a7277bf7e952aec371ac562853e89b54bbeea82c9ed86",       # noqa: mock
            coin3_in_flight_order.exchange_order_id
        )

        clock_task: asyncio.Task = safe_ensure_future(self.run_clock())
        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(TokenApprovalEvent.ApprovalSuccessful, event_logger)

        self._http_player.replay_timestamp_ms = 1652728338292
        try:
            async with timeout(5):
                while len(event_logger.event_log) < 2:
                    await event_logger.wait_for(TokenApprovalSuccessEvent)
            self.assertEqual(2, len(event_logger.event_log))
            self.assertEqual(
                {"uniswapLP_COIN1", "uniswapLP_COIN3"},
                set(e.token_symbol for e in event_logger.event_log)
            )
        finally:
            clock_task.cancel()
            try:
                await clock_task
            except asyncio.CancelledError:
                pass

    @async_test(loop=ev_loop)
    async def test_add_liquidity(self):
        self._http_player.replay_timestamp_ms = 1652728316475
        clock_task: asyncio.Task = safe_ensure_future(self.run_clock())
        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(MarketEvent.RangePositionUpdate, event_logger)
        self._connector.add_listener(MarketEvent.RangePositionLiquidityAdded, event_logger)

        try:
            self._connector.add_liquidity("COIN1-COIN3", Decimal("1"), Decimal("1"), Decimal("1"), Decimal("5"), "LOW")
            pos_update_event: RangePositionUpdateEvent = await event_logger.wait_for(
                RangePositionUpdateEvent,
                timeout_seconds=5
            )
            self.assertEqual(
                "0x0b6145277c7a6eefff5db3f595a3563da77df7f6face91122fd117fb6345ba0f",       # noqa: mock
                pos_update_event.exchange_order_id
            )
            self._http_player.replay_timestamp_ms = 1652728320503
            liquidity_added_event: RangePositionLiquidityAddedEvent = await event_logger.wait_for(RangePositionLiquidityAddedEvent, timeout_seconds=5)
            self.assertEqual(
                "0x0b6145277c7a6eefff5db3f595a3563da77df7f6face91122fd117fb6345ba0f",       # noqa: mock
                liquidity_added_event.exchange_order_id
            )
        finally:
            clock_task.cancel()
            try:
                await clock_task
            except asyncio.CancelledError:
                pass

    @async_test(loop=ev_loop)
    async def test_remove_liquidity(self):
        self._http_player.replay_timestamp_ms = 1652728331046
        clock_task: asyncio.Task = safe_ensure_future(self.run_clock())
        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(MarketEvent.RangePositionUpdate, event_logger)
        self._connector.add_listener(MarketEvent.RangePositionLiquidityRemoved, event_logger)

        try:
            self._connector.remove_liquidity("COIN1-COIN3", 1000)
            pos_update_event: RangePositionUpdateEvent = await event_logger.wait_for(
                RangePositionUpdateEvent,
                timeout_seconds=5
            )
            self.assertEqual(
                "0x84c2e5633ea6f5aaa8fe19464a65b2a30d1fce66513db4b11439c09288962e7a",       # noqa: mock
                pos_update_event.exchange_order_id
            )
            self._http_player.replay_timestamp_ms = 1652728338292
            liquidity_removed_event: RangePositionLiquidityRemovedEvent = await event_logger.wait_for(RangePositionLiquidityRemovedEvent, timeout_seconds=5)
            self.assertEqual(
                "0x84c2e5633ea6f5aaa8fe19464a65b2a30d1fce66513db4b11439c09288962e7a",       # noqa: mock
                liquidity_removed_event.exchange_order_id
            )
        finally:
            clock_task.cancel()
            try:
                await clock_task
            except asyncio.CancelledError:
                pass

    @async_test(loop=ev_loop)
    async def test_collect_fees(self):
        self._http_player.replay_timestamp_ms = 1652728322607
        clock_task: asyncio.Task = safe_ensure_future(self.run_clock())
        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(MarketEvent.RangePositionUpdate, event_logger)
        self._connector.add_listener(MarketEvent.RangePositionFeeCollected, event_logger)

        try:
            self._connector.collect_fees("COIN1-COIN3", 1001)
            pos_update_event: RangePositionUpdateEvent = await event_logger.wait_for(
                RangePositionUpdateEvent,
                timeout_seconds=5
            )
            self.assertEqual(
                "0x74ae9ae03e8bee4d6954dfb4944c87dae5de5f63f4932be3b16dfc93601f0fdc",       # noqa: mock
                pos_update_event.exchange_order_id
            )
            self._http_player.replay_timestamp_ms = 1652728328486
            fees_collected_event: RangePositionFeeCollectedEvent = await event_logger.wait_for(RangePositionFeeCollectedEvent, timeout_seconds=5)
            self.assertEqual(
                "0x74ae9ae03e8bee4d6954dfb4944c87dae5de5f63f4932be3b16dfc93601f0fdc",       # noqa: mock
                fees_collected_event.exchange_order_id
            )
        finally:
            clock_task.cancel()
            try:
                await clock_task
            except asyncio.CancelledError:
                pass
