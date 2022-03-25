#!/usr/bin/env python

from bin import path_util        # noqa: F401

import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
from os.path import realpath, join
import time
from typing import Optional, Generator

from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.connector.gateway_EVM_AMM import GatewayEVMAMM
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.events import TradeType, MarketEvent, OrderCancelledEvent
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from test.mock.http_recorder import HttpRecorder

WALLET_ADDRESS = "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92"
NETWORK = "ropsten"
TRADING_PAIR = "WETH-DAI"
gateway_http_client: GatewayHttpClient = GatewayHttpClient.get_instance()


class GatewayCancelDataCollector:
    fixture_path: str = realpath(join(__file__, "../fixtures/gateway_cancel_fixture.db"))

    def __init__(self):
        self._clock: Clock = Clock(ClockMode.REALTIME)
        self._connector: GatewayEVMAMM = GatewayEVMAMM(
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
        with self._http_recorder.patch_aiohttp_client():
            await self.collect_cancel_order()

    async def collect_cancel_order(self):
        print("Creating and then canceling Uniswap order...\t\t", end="", flush=True)
        connector: GatewayEVMAMM = self._connector
        event_logger: EventLogger = EventLogger()
        try:
            connector.add_listener(MarketEvent.OrderCancelled, event_logger)
            async with self.run_clock():
                amount: Decimal = Decimal("0.001")
                order_price: Decimal = await connector.get_order_price(TRADING_PAIR, False, amount) * Decimal("0.98")
                await connector._create_order(
                    TradeType.SELL,
                    GatewayEVMAMM.create_market_order_id(TradeType.SELL, TRADING_PAIR),
                    TRADING_PAIR,
                    amount,
                    order_price,
                    max_fee_per_gas=1000,
                    max_priority_fee_per_gas=100
                )
                for in_flight_order in connector._in_flight_orders.values():
                    in_flight_order._creation_timestamp = connector.current_timestamp - 86400
                safe_ensure_future(connector.cancel_outdated_orders(600))
                await event_logger.wait_for(OrderCancelledEvent)
        finally:
            connector.remove_listener(MarketEvent.OrderCancelled, event_logger)
        print("done")


if __name__ == "__main__":
    data_collector: GatewayCancelDataCollector = GatewayCancelDataCollector()
    try:
        asyncio.run(data_collector.main())
    except KeyboardInterrupt:
        pass
