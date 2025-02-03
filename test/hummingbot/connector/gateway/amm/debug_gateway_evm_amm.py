#!/usr/bin/env python

"""
Fixture data collection script for GatewayEthereumAMM unit test cases.

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
from hummingbot.connector.gateway.amm.gateway_ethereum_amm import GatewayEthereumAMM
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCreatedEvent,
    MarketEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCreatedEvent,
    TradeType,
)
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future

s_decimal_0 = Decimal(0)
gateway_http_client: GatewayHttpClient = GatewayHttpClient.get_instance()


class GatewayEthereumAMMDataCollector:
    fixture_path: str = realpath(join(__file__, "../fixtures/gateway_ethereum_amm_fixture.db"))

    def __init__(self):
        self._clock: Clock = Clock(ClockMode.REALTIME)
        self._connector: GatewayEthereumAMM = GatewayEthereumAMM(
            "uniswap",
            "ethereum",
            "ropsten",
            "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92",
            trading_pairs=["DAI-WETH"],
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
        await self.collect_order_status()
        await self.collect_get_price()
        await self.collect_approve_token()
        await self.collect_buy_order()
        await self.collect_sell_order()

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
        def create_approval_record(token_symbol: str, tx_hash: str) -> GatewayInFlightOrder:
            return GatewayInFlightOrder(
                client_order_id=self._connector.create_approval_order_id(token_symbol),
                exchange_order_id=tx_hash,
                trading_pair=token_symbol,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=s_decimal_0,
                amount=s_decimal_0,
                gas_price=s_decimal_0,
                creation_timestamp=self._connector.current_timestamp
            )
        print("Getting token approval status...\t\t", end="", flush=True)
        successful_records: List[GatewayInFlightOrder] = [
            create_approval_record(
                "WETH",
                "0x66b533792f45780fc38573bfd60d6043ab266471607848fb71284cd0d9eecff9"        # noqa: mock
            ),
            create_approval_record(
                "DAI",
                "0x4f81aa904fcb16a8938c0e0a76bf848df32ce6378e9e0060f7afc4b2955de405"        # noqa: mock
            ),
        ]
        await self._connector.update_token_approval_status(successful_records)
        fake_records: List[GatewayInFlightOrder] = [
            create_approval_record(
                "WETH",
                "0x66b533792f45780fc38573bfd60d6043ab266471607848fb71284cd0d9eecff8"        # noqa: mock
            ),
            create_approval_record(
                "DAI",
                "0x4f81aa904fcb16a8938c0e0a76bf848df32ce6378e9e0060f7afc4b2955de404"        # noqa: mock
            ),
        ]
        await self._connector.update_token_approval_status(fake_records)
        print("done")

    async def collect_order_status(self):
        def create_order_record(
                trading_pair: str,
                trade_type: TradeType,
                tx_hash: str,
                price: Decimal,
                amount: Decimal,
                gas_price: Decimal) -> GatewayInFlightOrder:
            return GatewayInFlightOrder(
                client_order_id=self._connector.create_market_order_id(trade_type, trading_pair),
                exchange_order_id=tx_hash,
                trading_pair=trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=trade_type,
                price=price,
                amount=amount,
                gas_price=gas_price,
                creation_timestamp=self._connector.current_timestamp
            )
        print("Getting uniswap order status...\t\t", end="", flush=True)
        successful_records: List[GatewayInFlightOrder] = [
            create_order_record(
                "DAI-WETH",
                TradeType.BUY,
                "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18",       # noqa: mock
                Decimal("0.00267589"),
                Decimal("1000"),
                Decimal("29")
            )
        ]
        await self._connector.update_order_status(successful_records)
        fake_records: List[GatewayInFlightOrder] = [
            create_order_record(
                "DAI-WETH",
                TradeType.BUY,
                "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e17",       # noqa: mock
                Decimal("0.00267589"),
                Decimal("1000"),
                Decimal("29")
            )
        ]
        await self._connector.update_order_status(fake_records)
        print("done")

    async def collect_get_price(self):
        print("Getting current prices...\t\t", end="", flush=True)
        await self._connector.get_quote_price("DAI-WETH", True, Decimal(1000))
        await self._connector.get_quote_price("DAI-WETH", False, Decimal(1000))
        print("done")

    async def collect_approve_token(self):
        print("Approving tokens...")
        weth_in_flight_order: GatewayInFlightOrder = await self._connector.approve_token("WETH")
        dai_in_flight_order: GatewayInFlightOrder = await self._connector.approve_token("DAI")
        print(f"\tSent WETH approval with txHash: {weth_in_flight_order.exchange_order_id}")
        print(f"\tSent DAI approval with txHash: {dai_in_flight_order.exchange_order_id}")
        while len(self._connector.approval_orders) > 0:
            await asyncio.sleep(5)
            await self._connector.update_token_approval_status(self._connector.approval_orders)
        print("\tdone")

    async def collect_buy_order(self):
        print("Buying DAI tokens...")
        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(MarketEvent.BuyOrderCreated, event_logger)
        self._connector.add_listener(MarketEvent.OrderFilled, event_logger)
        async with self.run_clock():
            try:
                price: Decimal = await self._connector.get_quote_price("DAI-WETH", True, Decimal(100))
                price *= Decimal("1.005")
                self._connector.buy("DAI-WETH", Decimal(100), OrderType.LIMIT, price)
                buy_order_event: BuyOrderCreatedEvent = await event_logger.wait_for(BuyOrderCreatedEvent)
                print(f"\tSent buy order with txHash: {buy_order_event.exchange_order_id}")
                await event_logger.wait_for(OrderFilledEvent, timeout_seconds=600)
            finally:
                self._connector.remove_listener(MarketEvent.BuyOrderCreated, event_logger)
                self._connector.remove_listener(MarketEvent.OrderFilled, event_logger)
        print("\tdone")

    async def collect_sell_order(self):
        print("Selling DAI tokens...")
        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(MarketEvent.SellOrderCreated, event_logger)
        self._connector.add_listener(MarketEvent.OrderFilled, event_logger)
        async with self.run_clock():
            try:
                price: Decimal = await self._connector.get_quote_price("DAI-WETH", False, Decimal(100))
                price *= Decimal("0.995")
                self._connector.sell("DAI-WETH", Decimal(100), OrderType.LIMIT, price)
                sell_order_event: SellOrderCreatedEvent = await event_logger.wait_for(SellOrderCreatedEvent)
                print(f"\tSent sell order with txHash: {sell_order_event.exchange_order_id}")
                await event_logger.wait_for(OrderFilledEvent, timeout_seconds=600)
            finally:
                self._connector.remove_listener(MarketEvent.SellOrderCreated, event_logger)
                self._connector.remove_listener(MarketEvent.OrderFilled, event_logger)
        print("\tdone")


if __name__ == "__main__":
    data_collector: GatewayEthereumAMMDataCollector = GatewayEthereumAMMDataCollector()
    ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    try:
        ev_loop.run_until_complete(data_collector.main())
    except KeyboardInterrupt:
        pass
