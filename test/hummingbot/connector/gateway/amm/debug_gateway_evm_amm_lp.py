#!/usr/bin/env python

"""
Fixture data collection script for GatewayEVMAMMLP unit test cases.

This is included for record only - if you need to run this to collect another batch of fixture data, you'll need to
change the wallet address and transaction hashes.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from decimal import Decimal
from os.path import join, realpath
from test.mock.http_recorder import HttpRecorder
from typing import Generator, List, Optional

from bin import path_util  # noqa: F401
from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.connector.gateway.amm_lp.gateway_evm_amm_lp import GatewayEVMAMMLP
from hummingbot.connector.gateway.amm_lp.gateway_in_flight_lp_order import GatewayInFlightLPOrder
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    LPType,
    MarketEvent,
    RangePositionFeeCollectedEvent,
    RangePositionLiquidityAddedEvent,
    RangePositionLiquidityRemovedEvent,
    RangePositionUpdateEvent,
)
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future

s_decimal_0 = Decimal(0)
gateway_http_client: GatewayHttpClient = GatewayHttpClient.get_instance()


class GatewayEVMAMMLPDataCollector:
    fixture_path: str = realpath(join(__file__, "../fixtures/gateway_evm_amm_lp_fixture.db"))

    def __init__(self):
        self._clock: Clock = Clock(ClockMode.REALTIME)
        self._connector: GatewayEVMAMMLP = GatewayEVMAMMLP(
            "uniswapLP",
            "ethereum",
            "kovan",
            "0xefB7Be8631d154d4C0ad8676FEC0897B2894FE8F",
            trading_pairs=["COIN1-COIN3"],
            trading_required=True
        )
        self._clock.add_iterator(self._connector)
        self._clock_task: Optional[asyncio.Task] = None
        self._http_recorder: HttpRecorder = HttpRecorder(self.fixture_path)

    async def main(self):
        await self.load_configs()
        with self._clock:
            with self._http_recorder.patch_aiohttp_client():
                await self.wait_til_ready()
                await self.collect_testing_data()

    @staticmethod
    async def load_configs():
        await read_system_configs_from_yml()
        gateway_http_client.base_url = "https://localhost:5000"

    async def wait_til_ready(self):
        print("Waiting til ready...\t\t", end="", flush=True)
        while True:
            now: float = time.time()
            next_iteration = now // 1.0 + 1
            if self._connector.ready:
                break
            else:
                await self._clock.run_til(next_iteration + 0.1)
            await asyncio.sleep(1.0)
        print("done")

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

    async def collect_testing_data(self):
        await self.collect_update_balances()
        await self.collect_get_allowances()
        await self.collect_get_chain_info()
        await self.collect_approval_status()
        await self.collect_get_price()
        await self.collect_approve_token()
        await self.collect_add_liquidity()
        await self.collect_fee_collect()
        await self.collect_remove_liquidity()

    async def collect_update_balances(self):
        print("Updating balances...\t\t", end="", flush=True)
        await self._connector.update_balances(on_interval=False)
        print("done")

    async def collect_get_allowances(self):
        print("Getting token allowances...\t\t", end="", flush=True)
        await self._connector.get_allowances()
        print("done")

    async def collect_get_chain_info(self):
        print("Getting chain info...\t\t", end="", flush=True)
        await self._connector.get_chain_info()
        print("done")

    async def collect_approval_status(self):
        def create_approval_record(token_symbol: str, tx_hash: str) -> GatewayInFlightLPOrder:
            return GatewayInFlightLPOrder(
                client_order_id=self._connector.create_approval_order_id(token_symbol),
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
        print("Getting token approval status...\t\t", end="", flush=True)
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
        await self._connector.update_token_approval_status(successful_records)
        fake_records: List[GatewayInFlightLPOrder] = [
            create_approval_record(
                "COIN1",
                "0x273a720fdc92554c47f409f4f74d3c262937451ccdbaddfd8d0185a9e3c64dd1"        # noqa: mock
            ),
            create_approval_record(
                "COIN3",
                "0x27d7a7156bd0afc73092602da67774aa3319adbc72213122d65480e482ce0a8a"        # noqa: mock
            ),
        ]
        await self._connector.update_token_approval_status(fake_records)
        print("done")

    async def collect_get_price(self):
        print("Getting current pool price...\t\t", end="", flush=True)
        await self._connector.get_price("COIN1-COIN3", "LOW")
        print("done")

    async def collect_approve_token(self):
        print("Approving tokens...")
        coin1_in_flight_order: GatewayInFlightLPOrder = await self._connector.approve_token("COIN1")
        coin3_in_flight_order: GatewayInFlightLPOrder = await self._connector.approve_token("COIN3")
        print(f"\tSent COIN1 approval with txHash: {coin1_in_flight_order.exchange_order_id}")
        print(f"\tSent COIN3 approval with txHash: {coin3_in_flight_order.exchange_order_id}")
        while len(self._connector.approval_orders) > 0:
            await asyncio.sleep(5)
            await self._connector.update_token_approval_status(self._connector.approval_orders)
        print("\tdone")

    async def collect_add_liquidity(self):
        print("Adding liquidity in LOW pool...")
        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(MarketEvent.RangePositionUpdate, event_logger)
        self._connector.add_listener(MarketEvent.RangePositionLiquidityAdded, event_logger)
        async with self.run_clock():
            try:
                self._connector.add_liquidity("COIN1-COIN3", Decimal("1"), Decimal("1"), Decimal("1"), Decimal("5"), "LOW")
                pos_update_event: RangePositionUpdateEvent = await event_logger.wait_for(RangePositionUpdateEvent)
                print(f"\tAdd liquidity sent with txHash: {pos_update_event.exchange_order_id}")
                await event_logger.wait_for(RangePositionLiquidityAddedEvent, timeout_seconds=600)
            finally:
                self._connector.remove_listener(MarketEvent.RangePositionUpdate, event_logger)
                self._connector.remove_listener(MarketEvent.RangePositionLiquidityAdded, event_logger)
        print("\tdone")

    async def collect_remove_liquidity(self):
        print("Removing liquidity in LOW pool...")
        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(MarketEvent.RangePositionUpdate, event_logger)
        self._connector.add_listener(MarketEvent.RangePositionLiquidityRemoved, event_logger)
        async with self.run_clock():
            try:
                self._connector.remove_liquidity("COIN1-COIN3", 11840)
                pos_update_event: RangePositionUpdateEvent = await event_logger.wait_for(RangePositionUpdateEvent)
                print(f"\tRemove liquidity sent with txHash: {pos_update_event.exchange_order_id}")
                await event_logger.wait_for(RangePositionLiquidityRemovedEvent, timeout_seconds=600)
            finally:
                self._connector.remove_listener(MarketEvent.RangePositionUpdate, event_logger)
                self._connector.remove_listener(MarketEvent.RangePositionLiquidityRemoved, event_logger)
        print("\tdone")

    async def collect_fee_collect(self):
        print("Collect earned fees...")
        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(MarketEvent.RangePositionUpdate, event_logger)
        self._connector.add_listener(MarketEvent.RangePositionFeeCollected, event_logger)
        async with self.run_clock():
            try:
                self._connector.collect_fees("COIN1-COIN3", 11840)
                pos_update_event: RangePositionUpdateEvent = await event_logger.wait_for(RangePositionUpdateEvent)
                print(f"\tCollect fees request sent with txHash: {pos_update_event.exchange_order_id}")
                await event_logger.wait_for(RangePositionFeeCollectedEvent, timeout_seconds=600)
            finally:
                self._connector.remove_listener(MarketEvent.RangePositionUpdate, event_logger)
                self._connector.remove_listener(MarketEvent.RangePositionFeeCollected, event_logger)
        print("\tdone")


if __name__ == "__main__":
    data_collector: GatewayEVMAMMLPDataCollector = GatewayEVMAMMLPDataCollector()
    ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    try:
        ev_loop.run_until_complete(data_collector.main())
    except KeyboardInterrupt:
        pass
