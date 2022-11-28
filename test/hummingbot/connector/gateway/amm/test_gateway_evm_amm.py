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
from hummingbot.connector.gateway.amm.evm_in_flight_order import EVMInFlightOrder
from hummingbot.connector.gateway.amm.gateway_evm_amm import GatewayEVMAMM
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCreatedEvent,
    MarketEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCreatedEvent,
    TokenApprovalEvent,
    TokenApprovalSuccessEvent,
    TradeType,
)
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future

ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
s_decimal_0: Decimal = Decimal(0)


class GatewayEVMAMMConnectorUnitTest(unittest.TestCase):
    _db_path: str
    _http_player: HttpPlayer
    _patch_stack: ExitStack
    _clock: Clock
    _connector: GatewayEVMAMM

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        GatewayHttpClient.__instance = None
        cls._db_path = realpath(join(__file__, "../fixtures/gateway_evm_amm_fixture.db"))
        cls._http_player = HttpPlayer(cls._db_path)
        cls._clock: Clock = Clock(ClockMode.REALTIME)
        cls._client_config_map = ClientConfigAdapter(ClientConfigMap())
        cls._connector: GatewayEVMAMM = GatewayEVMAMM(
            client_config_map=cls._client_config_map,
            connector_name="uniswap",
            chain="ethereum",
            network="ropsten",
            wallet_address="0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92",
            trading_pairs=["DAI-WETH"],
            trading_required=True
        )
        cls._connector._amount_quantum_dict = {"WETH": Decimal(str(1e-15)), "DAI": Decimal(str(1e-15))}
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
        GatewayHttpClient.__instance = None
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
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
        self.assertAlmostEqual(Decimal("58.903990239981237338"), self._connector.get_balance("ETH"))
        self.assertAlmostEqual(Decimal("1015.242427495432379422"), self._connector.get_balance("DAI"))

    @async_test(loop=ev_loop)
    async def test_get_allowances(self):
        big_num: Decimal = Decimal("1000000000000000000000000000")
        allowances: Dict[str, Decimal] = await self._connector.get_allowances()
        self.assertEqual(2, len(allowances))
        self.assertGreater(allowances.get("WETH"), big_num)
        self.assertGreater(allowances.get("DAI"), big_num)

    @async_test(loop=ev_loop)
    async def test_get_chain_info(self):
        self._connector._chain_info.clear()
        await self._connector.get_chain_info()
        self.assertGreater(len(self._connector._chain_info), 2)
        self.assertEqual("ETH", self._connector._chain_info.get("nativeCurrency"))

    @async_test(loop=ev_loop)
    async def test_update_approval_status(self):
        def create_approval_record(token_symbol: str, tx_hash: str) -> EVMInFlightOrder:
            return EVMInFlightOrder(
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
        successful_records: List[EVMInFlightOrder] = [
            create_approval_record(
                "WETH",
                "0x66b533792f45780fc38573bfd60d6043ab266471607848fb71284cd0d9eecff9"        # noqa: mock
            ),
            create_approval_record(
                "DAI",
                "0x4f81aa904fcb16a8938c0e0a76bf848df32ce6378e9e0060f7afc4b2955de405"        # noqa: mock
            ),
        ]
        fake_records: List[EVMInFlightOrder] = [
            create_approval_record(
                "WETH",
                "0x66b533792f45780fc38573bfd60d6043ab266471607848fb71284cd0d9eecff8"        # noqa: mock
            ),
            create_approval_record(
                "DAI",
                "0x4f81aa904fcb16a8938c0e0a76bf848df32ce6378e9e0060f7afc4b2955de404"        # noqa: mock
            ),
        ]

        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(TokenApprovalEvent.ApprovalSuccessful, event_logger)
        self._connector.add_listener(TokenApprovalEvent.ApprovalFailed, event_logger)

        try:
            await self._connector.update_token_approval_status(successful_records + fake_records)
            self.assertEqual(2, len(event_logger.event_log))
            self.assertEqual(
                {"WETH", "DAI"},
                set(e.token_symbol for e in event_logger.event_log)
            )
        finally:
            self._connector.remove_listener(TokenApprovalEvent.ApprovalSuccessful, event_logger)
            self._connector.remove_listener(TokenApprovalEvent.ApprovalFailed, event_logger)

    @async_test(loop=ev_loop)
    async def test_update_order_status(self):
        def create_order_record(
                trading_pair: str,
                trade_type: TradeType,
                tx_hash: str,
                price: Decimal,
                amount: Decimal,
                gas_price: Decimal) -> EVMInFlightOrder:
            order: EVMInFlightOrder = EVMInFlightOrder(
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
            order.fee_asset = self._connector._native_currency
            self._connector._order_tracker.start_tracking_order(order)
            return order
        successful_records: List[EVMInFlightOrder] = [
            create_order_record(
                "DAI-WETH",
                TradeType.BUY,
                "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18",  # noqa: mock
                Decimal("0.00267589"),
                Decimal("1000"),
                Decimal("29")
            )
        ]
        fake_records: List[EVMInFlightOrder] = [
            create_order_record(
                "DAI-WETH",
                TradeType.BUY,
                "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e17",       # noqa: mock
                Decimal("0.00267589"),
                Decimal("1000"),
                Decimal("29")
            )
        ]

        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(MarketEvent.OrderFilled, event_logger)

        try:
            await self._connector.update_order_status(successful_records + fake_records)
            async with timeout(10):
                while len(event_logger.event_log) < 1:
                    await event_logger.wait_for(OrderFilledEvent)
            filled_event: OrderFilledEvent = event_logger.event_log[0]
            self.assertEqual(
                "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18",       # noqa: mock
                filled_event.exchange_trade_id)
        finally:
            self._connector.remove_listener(MarketEvent.OrderFilled, event_logger)

    @async_test(loop=ev_loop)
    async def test_get_quote_price(self):
        buy_price: Decimal = await self._connector.get_quote_price("DAI-WETH", True, Decimal(1000))
        sell_price: Decimal = await self._connector.get_quote_price("DAI-WETH", False, Decimal(1000))
        self.assertEqual(Decimal("0.002684496"), buy_price)
        self.assertEqual(Decimal("0.002684496"), sell_price)

    @async_test(loop=ev_loop)
    async def test_approve_token(self):
        self._http_player.replay_timestamp_ms = 1648499867736
        weth_in_flight_order: EVMInFlightOrder = await self._connector.approve_token("WETH")
        self._http_player.replay_timestamp_ms = 1648499871595
        dai_in_flight_order: EVMInFlightOrder = await self._connector.approve_token("DAI")

        self.assertEqual(
            "0x6c975ba8c1d35e8542ffd05956d9ec227c1ac234ae4d5f69819aa24bae784321",       # noqa: mock
            weth_in_flight_order.exchange_order_id
        )
        self.assertEqual(
            "0x919438daa20dc2f5381fdf25b6b89a189d055b3a1d6d848c44e53dc10f49168c",       # noqa: mock
            dai_in_flight_order.exchange_order_id
        )

        clock_task: asyncio.Task = safe_ensure_future(self.run_clock())
        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(TokenApprovalEvent.ApprovalSuccessful, event_logger)

        self._http_player.replay_timestamp_ms = 1648500060232
        try:
            async with timeout(10):
                while len(event_logger.event_log) < 2:
                    await event_logger.wait_for(TokenApprovalSuccessEvent)
            self.assertEqual(2, len(event_logger.event_log))
            self.assertEqual(
                {"WETH", "DAI"},
                set(e.token_symbol for e in event_logger.event_log)
            )
        finally:
            clock_task.cancel()
            try:
                await clock_task
            except asyncio.CancelledError:
                pass

    @async_test(loop=ev_loop)
    async def test_buy_order(self):
        self._http_player.replay_timestamp_ms = 1648500060561
        clock_task: asyncio.Task = safe_ensure_future(self.run_clock())
        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(MarketEvent.BuyOrderCreated, event_logger)
        self._connector.add_listener(MarketEvent.OrderFilled, event_logger)

        try:
            self._connector.buy("DAI-WETH", Decimal(100), OrderType.LIMIT, Decimal("0.002861464039500"))
            order_created_event: BuyOrderCreatedEvent = await event_logger.wait_for(
                BuyOrderCreatedEvent,
                timeout_seconds=5
            )
            self.assertEqual(
                "0xc3d3166e6142c479b26c21e007b68e2b7fb1d28c1954ab344b45d7390139654f",       # noqa: mock
                order_created_event.exchange_order_id
            )
            self._http_player.replay_timestamp_ms = 1648500097569
            order_filled_event: OrderFilledEvent = await event_logger.wait_for(OrderFilledEvent, timeout_seconds=5)
            self.assertEqual(
                "0xc3d3166e6142c479b26c21e007b68e2b7fb1d28c1954ab344b45d7390139654f",       # noqa: mock
                order_filled_event.exchange_trade_id
            )
        finally:
            clock_task.cancel()
            try:
                await clock_task
            except asyncio.CancelledError:
                pass

    @async_test(loop=ev_loop)
    async def test_sell_order(self):
        self._http_player.replay_timestamp_ms = 1648500097825
        clock_task: asyncio.Task = safe_ensure_future(self.run_clock())
        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(MarketEvent.SellOrderCreated, event_logger)
        self._connector.add_listener(MarketEvent.OrderFilled, event_logger)

        try:
            self._connector.sell("DAI-WETH", Decimal(100), OrderType.LIMIT, Decimal("0.002816023229500"))
            order_created_event: SellOrderCreatedEvent = await event_logger.wait_for(
                SellOrderCreatedEvent,
                timeout_seconds=5
            )
            self.assertEqual(
                "0x63c7ffaf8dcede44c51cc2ea7ab3a5c0ea4915c9dab57dfcb432ea92ad174391",       # noqa: mock
                order_created_event.exchange_order_id
            )
            self._http_player.replay_timestamp_ms = 1648500133889
            order_filled_event: OrderFilledEvent = await event_logger.wait_for(OrderFilledEvent, timeout_seconds=5)
            self.assertEqual(
                "0x63c7ffaf8dcede44c51cc2ea7ab3a5c0ea4915c9dab57dfcb432ea92ad174391",       # noqa: mock
                order_filled_event.exchange_trade_id
            )
        finally:
            clock_task.cancel()
            try:
                await clock_task
            except asyncio.CancelledError:
                pass
