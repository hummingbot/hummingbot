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
from async_timeout import timeout

from bin import path_util  # noqa: F401
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.gateway.clob.gateway_sol_clob import GatewaySOLCLOB
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent, OrderCancelledEvent, TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future

WALLET_ADDRESS = "FMosjpvtAxwL6GFDSL31o9pU5somKjifbkt32bEgLddf"  # noqa: mock
NETWORK = "testnet"
TRADING_PAIR = "SOL-USDC"
MAX_FEE_PER_GAS = 2000
MAX_PRIORITY_FEE_PER_GAS = 200

ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()


class GatewayCancelUnitTest(unittest.TestCase):
    _db_path: str
    _http_player: HttpPlayer
    _patch_stack: ExitStack
    _clock: Clock
    _clock_task: Optional[asyncio.Task]
    _connector: GatewaySOLCLOB

    @classmethod
    def setUpClass(cls) -> None:
        cls._db_path = realpath(join(__file__, "../fixtures/gateway_cancel_fixture.db"))
        cls._http_player = HttpPlayer(cls._db_path)
        cls._clock: Clock = Clock(ClockMode.REALTIME)
        cls._client_config_map = ClientConfigAdapter(ClientConfigMap())
        cls._connector: GatewaySOLCLOB = GatewaySOLCLOB(
            client_config_map=cls._client_config_map,
            connector_name="serum",
            chain="solana",
            network=NETWORK,
            wallet_address=WALLET_ADDRESS,
            trading_pairs=[TRADING_PAIR],
            trading_required=True
        )
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

    # @async_test(loop=ev_loop)
    async def test_cancel_order(self):
        amount: Decimal = Decimal("0.2")
        connector: GatewaySOLCLOB = self._connector
        event_logger: EventLogger = EventLogger()
        connector.add_listener(MarketEvent.OrderCancelled, event_logger)

        expected_order_tx_hash_set: Set[str] = {
            "12sFho8chAFK8Mxj8sZTWQJfQTPLgHFrCuGxyapnEMPSbGtSuBWkFaJaNG3E9fmzvbtvmFf1qnPEGWGj4dRR98N",  # noqa: mock
            "22sFho8chAFK8Mxj8sZTWQJfQTPLgHFrCuGxyapnEMPSbGtSuBWkFaJaNG3E9fmzvbtvmFf1qnPEGWGj4dRR98N" # noqa: mock
        }
        expected_cancel_tx_hash_set: Set[str] = {
            "1HEGEidnzzGvdKAB6dui5dZBB4qcBbqEMPgjbch8b9qdzf72Wworr11FqxdHDCjJVoG4Q3P9Fw4ergmwW3u47rC7",  # noqa: mock
            "2HEGEidnzzGvdKAB6dui5dZBB4qcBbqEMPgjbch8b9qdzf72Wworr11FqxdHDCjJVoG4Q3P9Fw4ergmwW3u47rC7" # noqa: mock
        }

        try:
            async with self.run_clock():
                self._http_player.replay_timestamp_ms = 1648503302272
                buy_price: Decimal = await connector.get_order_price(TRADING_PAIR, True, amount) * Decimal("1.02")
                sell_price: Decimal = await connector.get_order_price(TRADING_PAIR, False, amount) * Decimal("0.98")

                self._http_player.replay_timestamp_ms = 1648503304951
                await connector._create_order(
                    trade_type=TradeType.BUY,
                    order_id='buy-SOL-USDC-1658434205028888',
                    trading_pair=TRADING_PAIR,
                    amount=amount,
                    price=buy_price,
                    max_fee_per_gas=MAX_FEE_PER_GAS,
                    max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS,
                )
                self._http_player.replay_timestamp_ms = 1648503309059
                await connector._create_order(
                    TradeType.SELL,
                    'sell-SOL-USDC-1658434205059909',
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

                self.assertEqual(2, len(connector.amm_orders))
                self.assertEqual(expected_cancel_tx_hash_set, set(o.cancel_tx_hash for o in connector.amm_orders))

                self._http_player.replay_timestamp_ms = 1648503331511
                await connector.update_canceling_transactions(connector.amm_orders)

                async with timeout(10):
                    while len(event_logger.event_log) < 2:
                        await event_logger.wait_for(OrderCancelledEvent)
                self.assertEqual(0, len(connector.amm_orders))
        finally:
            connector.remove_listener(MarketEvent.OrderCancelled, event_logger)

    # # TODO Check about the possibility to cancel POST solana/token transactions.
    # @async_test(loop=ev_loop)
    # async def test_cancel_approval(self):
    #     connector: GatewaySOLCLOB = self._connector
    #     event_logger: EventLogger = EventLogger()
    #     connector.add_listener(TokenApprovalEvent.ApprovalCancelled, event_logger)
    #
    #     expected_evm_approve_tx_hash_set: Set[str] = {
    #         "8PZnzjEUJ1B1sMAU3xhzpfK8T4QzydDrnTZrWdzzcno",  # noqa: mock
    #         "9PZnzjEUJ1B1sMAU3xhzpfK8T4QzydDrnTZrWdzzcno",  # noqa: mock
    #     }
    #     expected_cancel_tx_hash_set: Set[str] = {
    #         "0x21b4d0e956241a497cf50d9c5dcefea4ec9fb225a1d11f80477ca434caab30ff",  # noqa: mock
    #         "0x7ac85d5a77f28e9317127218c06eb3d70f4c68924a4b5b743fe8faef6d011d11",  # noqa: mock
    #     }
    #
    #     try:
    #         async with self.run_clock():
    #             self._http_player.replay_timestamp_ms = 1648503333290
    #             tracked_order_1: CLOBInFlightOrder = await connector.approve_token(
    #                 "SOL", max_fee_per_gas=MAX_FEE_PER_GAS, max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS
    #             )
    #             self._http_player.replay_timestamp_ms = 1648503337964
    #             tracked_order_2: CLOBInFlightOrder = await connector.approve_token(
    #                 "USDC", max_fee_per_gas=MAX_FEE_PER_GAS, max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS
    #             )
    #             self.assertEqual(2, len(connector.approval_orders))
    #             self.assertEqual(
    #                 expected_evm_approve_tx_hash_set, set(o.exchange_order_id for o in connector.approval_orders)
    #             )
    #
    #             self._http_player.replay_timestamp_ms = 1648503342513
    #             tracked_order_1.creation_timestamp = connector.current_timestamp - 86400
    #             tracked_order_2.creation_timestamp = connector.current_timestamp - 86400
    #             await connector.cancel_outdated_orders(600)
    #             self.assertEqual(2, len(connector.approval_orders))
    #             self.assertEqual(expected_cancel_tx_hash_set, set(o.cancel_tx_hash for o in connector.approval_orders))
    #
    #             self._http_player.replay_timestamp_ms = 1648503385484
    #             async with timeout(10):
    #                 while len(event_logger.event_log) < 2:
    #                     await event_logger.wait_for(TokenApprovalCancelledEvent)
    #                 cancelled_approval_symbols = [e.token_symbol for e in event_logger.event_log]
    #                 self.assertIn("USDC", cancelled_approval_symbols)
    #                 self.assertIn("SOL", cancelled_approval_symbols)
    #     finally:
    #         connector.remove_listener(TokenApprovalEvent.ApprovalCancelled, event_logger)
