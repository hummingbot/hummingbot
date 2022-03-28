from bin import path_util       # noqa: F401

from aiounittest import async_test
from aiohttp import ClientSession
import asyncio
from async_timeout import timeout
from contextlib import ExitStack, asynccontextmanager
from decimal import Decimal
from os.path import join, realpath
import time
from typing import Generator, Optional, Set
import unittest
from unittest.mock import patch

from hummingbot.connector.gateway_EVM_AMM import GatewayEVMAMM
from hummingbot.connector.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    TradeType,
    MarketEvent,
    OrderCancelledEvent,
    TokenApprovalEvent,
    TokenApprovalCancelledEvent,
)
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from test.mock.http_recorder import HttpPlayer

WALLET_ADDRESS = "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92"
NETWORK = "ropsten"
TRADING_PAIR = "WETH-DAI"
MAX_FEE_PER_GAS = 2000
MAX_PRIORITY_FEE_PER_GAS = 200

ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()


class GatewayCancelUnitTest(unittest.TestCase):
    _db_path: str
    _http_player: HttpPlayer
    _patch_stack: ExitStack
    _clock: Clock
    _clock_task: Optional[asyncio.Task]
    _connector: GatewayEVMAMM

    @classmethod
    def setUpClass(cls) -> None:
        cls._db_path = realpath(join(__file__, "../fixtures/gateway_cancel_fixture.db"))
        cls._http_player = HttpPlayer(cls._db_path)
        cls._clock: Clock = Clock(ClockMode.REALTIME)
        cls._connector: GatewayEVMAMM = GatewayEVMAMM(
            "uniswap",
            "ethereum",
            NETWORK,
            WALLET_ADDRESS,
            trading_pairs=[TRADING_PAIR],
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
        GatewayHttpClient.get_instance().base_url = "https://localhost:5000"
        ev_loop.run_until_complete(cls.wait_til_ready())

    @classmethod
    def tearDownClass(cls) -> None:
        cls._patch_stack.close()

    def tearDown(self) -> None:
        self._connector._in_flight_orders.clear()

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now: float = time.time()
            next_iteration = now // 1.0 + 1
            if cls._connector.ready:
                break
            else:
                await cls._clock.run_til(next_iteration + 0.1)

    @asynccontextmanager
    async def run_clock(self) -> Generator[Clock, None, None]:
        self._clock_task = safe_ensure_future(self._clock.run())
        try:
            yield self._clock
        finally:
            self._clock_task.cancel()
            try:
                await self._clock_task
            except asyncio.CancelledError:
                pass
            self._clock_task = None

    @async_test(loop=ev_loop)
    async def test_cancel_order(self):
        amount: Decimal = Decimal("0.001")
        connector: GatewayEVMAMM = self._connector
        event_logger: EventLogger = EventLogger()
        connector.add_listener(MarketEvent.OrderCancelled, event_logger)

        expected_order_tx_hash_set: Set[str] = {
            "0x325efa81068961db0f769e9df64fb0174169a8b5bfd6ebff77a55e8e1bbdbbb8",       # noqa: mock
            "0x6b00d5215fdd9fbb603925c7d12b2c288a54d0fd262951a25383028d03ebe5eb",       # noqa: mock
        }
        expected_cancel_tx_hash_set: Set[str] = {
            "0xb0ee465ce1b72b90a179a73dfb9c91bc83bf279f828ec7d8bf17e94b3f0f524b",       # noqa: mock
            "0xc5bafd12c08fc324b77adbf6190dd09ee1c8cff5939c89d15fa4be6bed1f3657",       # noqa: mock
        }

        try:
            async with self.run_clock():
                self._http_player.replay_timestamp_ms = 1648244855358
                buy_price: Decimal = await connector.get_order_price(TRADING_PAIR, True, amount) * Decimal("1.02")
                sell_price: Decimal = await connector.get_order_price(TRADING_PAIR, False, amount) * Decimal("0.98")

                self._http_player.replay_timestamp_ms = 1648244857769
                await connector._create_order(
                    TradeType.BUY,
                    GatewayEVMAMM.create_market_order_id(TradeType.BUY, TRADING_PAIR),
                    TRADING_PAIR,
                    amount,
                    buy_price,
                    max_fee_per_gas=MAX_FEE_PER_GAS,
                    max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS
                )
                self._http_player.replay_timestamp_ms = 1648244861793
                await connector._create_order(
                    TradeType.SELL,
                    GatewayEVMAMM.create_market_order_id(TradeType.SELL, TRADING_PAIR),
                    TRADING_PAIR,
                    amount,
                    sell_price,
                    max_fee_per_gas=MAX_FEE_PER_GAS,
                    max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS
                )
                self.assertEqual(2, len(connector._in_flight_orders))
                self.assertEqual(expected_order_tx_hash_set,
                                 set(o.exchange_order_id for o in connector._in_flight_orders.values()))

                for in_flight_order in connector._in_flight_orders.values():
                    in_flight_order._creation_timestamp = connector.current_timestamp - 86400

                self._http_player.replay_timestamp_ms = 1648244866690
                await connector.cancel_outdated_orders(600)
                self.assertEqual(2, len(connector._in_flight_orders))
                self.assertTrue(all([o.is_cancelling for o in connector._in_flight_orders.values()]))
                self.assertEqual(expected_cancel_tx_hash_set,
                                 set(o.cancel_tx_hash for o in connector._in_flight_orders.values()))

                self._http_player.replay_timestamp_ms = 1648244886507
                async with timeout(10):
                    while len(event_logger.event_log) < 2:
                        await event_logger.wait_for(OrderCancelledEvent)
                self.assertEqual(0, len(connector._in_flight_orders))
        finally:
            connector.remove_listener(MarketEvent.OrderCancelled, event_logger)

    @async_test(loop=ev_loop)
    async def test_cancel_approval(self):
        connector: GatewayEVMAMM = self._connector
        event_logger: EventLogger = EventLogger()
        connector.add_listener(TokenApprovalEvent.ApprovalCancelled, event_logger)

        expected_evm_approve_tx_hash_set: Set[str] = {
            "0xf1e812069b2916a24e3ec47510f70dcdd08a50b309d4b51d8039340b95189988",       # noqa: mock
            "0x2ea695c06e04237ebb7b5d45d09fc120d7a2c88ed1b94ed0b0525ab6c74cde9e",       # noqa: mock
        }
        expected_cancel_tx_hash_set: Set[str] = {
            "0x9f3e992fc4a8da74825f41ff07ea3e763565e3fcb32a232a58c1206099a77343",       # noqa: mock
            "0x24c41c1063f9a255313056495d2cbd246239272b1e5ab0ce38960787d247080b",       # noqa: mock
        }

        try:
            async with self.run_clock():
                self._http_player.replay_timestamp_ms = 1648244889172
                tracked_order_1: GatewayInFlightOrder = await connector.approve_token(
                    "DAI",
                    max_fee_per_gas=MAX_FEE_PER_GAS,
                    max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS
                )
                self._http_player.replay_timestamp_ms = 1648244892744
                tracked_order_2: GatewayInFlightOrder = await connector.approve_token(
                    "WETH",
                    max_fee_per_gas=MAX_FEE_PER_GAS,
                    max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS
                )
                self.assertEqual(2, len(connector._in_flight_orders))
                self.assertEqual(expected_evm_approve_tx_hash_set,
                                 set(o.exchange_order_id for o in connector._in_flight_orders.values()))

                self._http_player.replay_timestamp_ms = 1648244897136
                tracked_order_1._creation_timestamp = connector.current_timestamp - 86400
                tracked_order_2._creation_timestamp = connector.current_timestamp - 86400
                await connector.cancel_outdated_orders(600)
                self.assertEqual(2, len(connector._in_flight_orders))
                self.assertEqual(expected_cancel_tx_hash_set,
                                 set(o.cancel_tx_hash for o in connector._in_flight_orders.values()))

                self._http_player.replay_timestamp_ms = 1648244902497
                async with timeout(10):
                    while len(event_logger.event_log) < 2:
                        await event_logger.wait_for(TokenApprovalCancelledEvent)
                self.assertEqual(0, len(connector._in_flight_orders))
        finally:
            connector.remove_listener(TokenApprovalEvent.ApprovalCancelled, event_logger)
