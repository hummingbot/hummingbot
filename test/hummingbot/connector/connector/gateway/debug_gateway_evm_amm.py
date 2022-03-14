#!/usr/bin/env python

"""
Fixture data collection script for GatewayEVMAMM unit test cases.

This is included for record only - if you need to run this to collect another batch of fixture data, you'll need to
change the wallet address and transaction hashes.
"""

from bin import path_util       # noqa: F401

import asyncio
from decimal import Decimal
from os.path import join, realpath
import time
from typing import List

from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.connector.gateway_EVM_AMM import GatewayEVMAMM
from hummingbot.connector.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.core.gateway import gateway_http_client
from test.mock.http_recorder import HttpRecorder

s_decimal_0 = Decimal(0)


class GatewayEVMAMMDataCollector:
    fixture_path: str = realpath(join(__file__, "../fixtures/gateway_evm_amm_fixture.db"))

    def __init__(self):
        self._clock: Clock = Clock(ClockMode.REALTIME)
        self._connector: GatewayEVMAMM = GatewayEVMAMM(
            "uniswap",
            "ethereum",
            "ropsten",
            "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92",
            trading_pairs=["DAI-WETH"],
            trading_required=True
        )
        self._clock.add_iterator(self._connector)
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

    async def wait_til_ready(self):
        print("Waiting til ready...\t\t", end="")
        while True:
            now: float = time.time()
            next_iteration = now // 1.0 + 1
            if self._connector.ready:
                break
            else:
                await self._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)
        print("done")

    async def collect_testing_data(self):
        with self._http_recorder.patch_aiohttp_client():
            await self.collect_update_balances()
            await self.collect_approval_status()
            await self.collect_order_status()
            await self.collect_get_price()

    async def collect_update_balances(self):
        print("Updating balances...\t\t", end="")
        await self._connector._update_balances(on_interval=False)
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
        print("Getting token approval status...\t\t", end="")
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
        await self._connector._update_token_approval_status(successful_records)
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
        await self._connector._update_token_approval_status(fake_records)
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
        print("Getting uniswap order status...\t\t", end="")
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
        await self._connector._update_order_status(successful_records)
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
        await self._connector._update_order_status(fake_records)
        print("done")

    async def collect_get_price(self):
        print("Getting current prices...\t\t", end="")
        await self._connector.get_quote_price("DAI-WETH", True, Decimal(1000))
        await self._connector.get_quote_price("DAI-WETH", False, Decimal(1000))
        print("done")


if __name__ == "__main__":
    data_collector: GatewayEVMAMMDataCollector = GatewayEVMAMMDataCollector()
    asyncio.run(data_collector.main())
