#!/usr/bin/env python

import asyncio
import time
from contextlib import asynccontextmanager
from decimal import Decimal
from os.path import join, realpath
from test.mock.http_recorder import HttpRecorder
from typing import Generator, Optional

from bin import path_util  # noqa: F401
from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.connector.gateway.amm.gateway_ethereum_amm import GatewayEthereumAMM
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
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
gateway_http_client: GatewayHttpClient = GatewayHttpClient.get_instance()


class GatewayCancelDataCollector:
    fixture_path: str = realpath(join(__file__, "../fixtures/gateway_cancel_fixture.db"))

    def __init__(self):
        self._clock: Clock = Clock(ClockMode.REALTIME)
        self._connector: GatewayEthereumAMM = GatewayEthereumAMM(
            "uniswap",
            "ethereum",
            NETWORK,
            WALLET_ADDRESS,
            trading_pairs=[TRADING_PAIR],
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

    async def collect_testing_data(self):
        await self.collect_cancel_order()
        await self.collect_cancel_approval()

    async def collect_cancel_order(self):
        print("Creating and then canceling Uniswap order...\t\t", end="", flush=True)
        connector: GatewayEthereumAMM = self._connector
        event_logger: EventLogger = EventLogger()
        connector.add_listener(MarketEvent.OrderCancelled, event_logger)
        try:
            async with self.run_clock():
                amount: Decimal = Decimal("0.001")
                buy_price: Decimal = await connector.get_order_price(TRADING_PAIR, True, amount) * Decimal("1.02")
                sell_price: Decimal = await connector.get_order_price(TRADING_PAIR, False, amount) * Decimal("0.98")
                await connector._create_order(
                    TradeType.BUY,
                    GatewayEthereumAMM.create_market_order_id(TradeType.BUY, TRADING_PAIR),
                    TRADING_PAIR,
                    amount,
                    buy_price,
                    max_fee_per_gas=MAX_FEE_PER_GAS,
                    max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS
                )
                await connector._create_order(
                    TradeType.SELL,
                    GatewayEthereumAMM.create_market_order_id(TradeType.SELL, TRADING_PAIR),
                    TRADING_PAIR,
                    amount,
                    sell_price,
                    max_fee_per_gas=MAX_FEE_PER_GAS,
                    max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS
                )
                for in_flight_order in connector._in_flight_orders.values():
                    in_flight_order._creation_timestamp = connector.current_timestamp - 86400
                safe_ensure_future(connector.cancel_outdated_orders(600))
                while len(event_logger.event_log) < 2:
                    await event_logger.wait_for(OrderCancelledEvent)
        finally:
            connector.remove_listener(MarketEvent.OrderCancelled, event_logger)
        print("done")

    async def collect_cancel_approval(self):
        print("Creating and then canceling token approval...\t\t", end="", flush=True)
        connector: GatewayEthereumAMM = self._connector
        event_logger: EventLogger = EventLogger()
        connector.add_listener(TokenApprovalEvent.ApprovalCancelled, event_logger)
        try:
            async with self.run_clock():
                tracked_order_1: GatewayInFlightOrder = await connector.approve_token(
                    "DAI",
                    max_fee_per_gas=MAX_FEE_PER_GAS,
                    max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS
                )
                tracked_order_2: GatewayInFlightOrder = await connector.approve_token(
                    "WETH",
                    max_fee_per_gas=MAX_FEE_PER_GAS,
                    max_priority_fee_per_gas=MAX_PRIORITY_FEE_PER_GAS
                )
                tracked_order_1._creation_timestamp = connector.current_timestamp - 86400
                tracked_order_2._creation_timestamp = connector.current_timestamp - 86400
                safe_ensure_future(connector.cancel_outdated_orders(600))
                while len(event_logger.event_log) < 2:
                    await event_logger.wait_for(TokenApprovalCancelledEvent)
        finally:
            connector.remove_listener(TokenApprovalEvent.ApprovalCancelled, event_logger)
        print("done")


if __name__ == "__main__":
    data_collector: GatewayCancelDataCollector = GatewayCancelDataCollector()
    try:
        asyncio.run(data_collector.main())
    except KeyboardInterrupt:
        pass
