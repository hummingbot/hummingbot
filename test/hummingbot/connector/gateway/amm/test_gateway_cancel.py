import asyncio
import time
import unittest
from contextlib import ExitStack, asynccontextmanager
from decimal import Decimal
from os.path import join, realpath
from test.mock.http_recorder import HttpPlayer
from typing import Generator, Optional, Set
from unittest.mock import patch

from aiohttp import ClientSession
from aiounittest import async_test
from async_timeout import timeout

from bin import path_util  # noqa: F401
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.gateway.amm.evm_in_flight_order import EVMInFlightOrder
from hummingbot.connector.gateway.amm.gateway_evm_amm import GatewayEVMAMM
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    OrderCancelledEvent,
    TokenApprovalCancelledEvent,
    TokenApprovalEvent,
    TradeType,
)
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future

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
        cls._client_config_map = ClientConfigAdapter(ClientConfigMap())
        cls._connector: GatewayEVMAMM = GatewayEVMAMM(
            client_config_map=cls._client_config_map,
            connector_name="uniswap",
            chain="ethereum",
            network=NETWORK,
            wallet_address=WALLET_ADDRESS,
            trading_pairs=[TRADING_PAIR],
            trading_required=True
        )
        cls._connector._amount_quantum_dict = {"WETH": Decimal(str(1e-15)), "DAI": Decimal(str(1e-15))}
        cls._clock.add_iterator(cls._connector)
        cls._patch_stack = ExitStack()
        cls._patch_stack.enter_context(cls._http_player.patch_aiohttp_client())
        cls._patch_stack.enter_context(
            patch(
                "hummingbot.core.gateway.gateway_http_client.GatewayHttpClient._http_client",
                return_value=ClientSession(),
            )
        )
        cls._patch_stack.enter_context(cls._clock)
        GatewayHttpClient.get_instance().base_url = "https://localhost:5000"
        ev_loop.run_until_complete(cls.wait_til_ready())

    @classmethod
    def tearDownClass(cls) -> None:
        cls._patch_stack.close()

    def tearDown(self) -> None:
        self._connector._order_tracker.all_orders.clear()

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
            "0x08f410a0d5cd42446fef3faffc14251ccfa3e4388d83f75f3730c05bcba1c5ab",  # noqa: mock
            "0xe09a9d9593e7ca19205edd3a4ddd1ab1f348dad3ea922ad0ef8efc5c00e3abfb",  # noqa: mock
        }
        expected_cancel_tx_hash_set: Set[str] = {
            "0xcd03a16f309a01239b8f7c036865f1c413768f2809fd0355400e7595a3860988",  # noqa: mock
            "0x044eb2c220ec160e157949b0f18f7ba5e36c6e7b115a36e976f92b469f45cab5",  # noqa: mock
        }

        try:
            async with self.run_clock():
                self._http_player.replay_timestamp_ms = 1648503302272
                buy_price: Decimal = await connector.get_order_price(TRADING_PAIR, True, amount) * Decimal("1.02")
                sell_price: Decimal = await connector.get_order_price(TRADING_PAIR, False, amount) * Decimal("0.98")

                self._http_player.replay_timestamp_ms = 1648503304951
                await connector._create_order(
                    trade_type=TradeType.BUY,
                    order_id=GatewayEVMAMM.create_market_order_id(TradeType.BUY, TRADING_PAIR),
                    trading_pair=TRADING_PAIR,
                    amount=amount,
                    price=buy_price,
                    max_fee_per_gas=MAX_FEE_PER_GAS,
                    max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS,
                )
                self._http_player.replay_timestamp_ms = 1648503309059
                await connector._create_order(
                    TradeType.SELL,
                    GatewayEVMAMM.create_market_order_id(TradeType.SELL, TRADING_PAIR),
                    TRADING_PAIR,
                    amount,
                    sell_price,
                    max_fee_per_gas=MAX_FEE_PER_GAS,
                    max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS,
                )

                self._http_player.replay_timestamp_ms = 1648503311238
                await connector.update_order_status(connector.amm_orders)

                self.assertEqual(2, len(connector.amm_orders))
                self.assertEqual(expected_order_tx_hash_set, set(o.exchange_order_id for o in connector.amm_orders))

                for in_flight_order in connector.amm_orders:
                    in_flight_order.creation_timestamp = connector.current_timestamp - 86400

                self._http_player.replay_timestamp_ms = 1648503313675
                await connector.cancel_outdated_orders(600)

                self._http_player.replay_timestamp_ms = 1648503331511
                await connector.update_canceling_transactions(connector.amm_orders)
                # self._http_player.replay_timestamp_ms = 1648503331520
                # await connector.update_canceling_transactions(connector.amm_orders)
                self.assertEqual(2, len(connector.amm_orders))
                self.assertEqual(expected_cancel_tx_hash_set, set(o.cancel_tx_hash for o in connector.amm_orders))

                async with timeout(10):
                    while len(event_logger.event_log) < 2:
                        await event_logger.wait_for(OrderCancelledEvent)
                self.assertEqual(0, len(connector.amm_orders))
        finally:
            connector.remove_listener(MarketEvent.OrderCancelled, event_logger)

    @async_test(loop=ev_loop)
    async def test_cancel_approval(self):
        connector: GatewayEVMAMM = self._connector
        event_logger: EventLogger = EventLogger()
        connector.add_listener(TokenApprovalEvent.ApprovalCancelled, event_logger)

        expected_evm_approve_tx_hash_set: Set[str] = {
            "0x7666bb5ba3ecec828e323f20685dfd03a067e7b2830b217363293b166b48a679",  # noqa: mock
            "0x7291d26447e300bd37260add7ac7db9a745f64c7ee10854695b0a70b0897456f",  # noqa: mock
        }
        expected_cancel_tx_hash_set: Set[str] = {
            "0x21b4d0e956241a497cf50d9c5dcefea4ec9fb225a1d11f80477ca434caab30ff",  # noqa: mock
            "0x7ac85d5a77f28e9317127218c06eb3d70f4c68924a4b5b743fe8faef6d011d11",  # noqa: mock
        }

        try:
            async with self.run_clock():
                self._http_player.replay_timestamp_ms = 1648503333290
                tracked_order_1: EVMInFlightOrder = await connector.approve_token(
                    "DAI", max_fee_per_gas=MAX_FEE_PER_GAS, max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS
                )
                self._http_player.replay_timestamp_ms = 1648503337964
                tracked_order_2: EVMInFlightOrder = await connector.approve_token(
                    "WETH", max_fee_per_gas=MAX_FEE_PER_GAS, max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS
                )
                self.assertEqual(2, len(connector.approval_orders))
                self.assertEqual(
                    expected_evm_approve_tx_hash_set, set(o.exchange_order_id for o in connector.approval_orders)
                )

                self._http_player.replay_timestamp_ms = 1648503342513
                tracked_order_1.creation_timestamp = connector.current_timestamp - 86400
                tracked_order_2.creation_timestamp = connector.current_timestamp - 86400
                await connector.cancel_outdated_orders(600)
                self.assertEqual(2, len(connector.approval_orders))
                self.assertEqual(expected_cancel_tx_hash_set, set(o.cancel_tx_hash for o in connector.approval_orders))

                self._http_player.replay_timestamp_ms = 1648503385484
                async with timeout(10):
                    while len(event_logger.event_log) < 2:
                        await event_logger.wait_for(TokenApprovalCancelledEvent)
                    cancelled_approval_symbols = [e.token_symbol for e in event_logger.event_log]
                    self.assertIn("DAI", cancelled_approval_symbols)
                    self.assertIn("WETH", cancelled_approval_symbols)
        finally:
            connector.remove_listener(TokenApprovalEvent.ApprovalCancelled, event_logger)
