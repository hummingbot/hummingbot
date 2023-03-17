import asyncio
import unittest
from contextlib import ExitStack
from decimal import Decimal
from os.path import join, realpath
from test.mock.http_recorder import HttpPlayer
from typing import Any, Dict
from unittest.mock import patch

from aiohttp import ClientSession
from aiounittest import async_test

from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.event.events import TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient

ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()


class GatewayHttpClientUnitTest(unittest.TestCase):
    _db_path: str
    _http_player: HttpPlayer
    _patch_stack: ExitStack

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._db_path = realpath(join(__file__, "../fixtures/gateway_http_client_clob_fixture.db"))
        cls._http_player = HttpPlayer(cls._db_path)
        cls._patch_stack = ExitStack()
        cls._patch_stack.enter_context(cls._http_player.patch_aiohttp_client())
        cls._patch_stack.enter_context(
            patch("hummingbot.core.gateway.gateway_http_client.GatewayHttpClient._http_client", return_value=ClientSession())
        )
        GatewayHttpClient.get_instance().base_url = "https://localhost:5000"

    @classmethod
    def tearDownClass(cls) -> None:
        cls._patch_stack.close()

    @async_test(loop=ev_loop)
    async def test_clob_place_order(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_place_order(
            connector="injective",
            chain="injective",
            network="mainnet",
            trading_pair=combine_to_hb_trading_pair(base="COIN", quote="ALPHA"),
            address="0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18",  # noqa: mock
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("10"),
            size=Decimal("2"),
        )

        self.assertEqual("mainnet", result["network"])
        self.assertEqual(1647066435595, result["timestamp"])
        self.assertEqual(2, result["latency"])
        self.assertEqual("0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf", result["txHash"])  # noqa: mock

    @async_test(loop=ev_loop)
    async def test_clob_cancel_order(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_cancel_order(
            connector="injective",
            chain="injective",
            network="mainnet",
            trading_pair=combine_to_hb_trading_pair(base="COIN", quote="ALPHA"),
            address="0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18",  # noqa: mock
            exchange_order_id="0x66b533792f45780fc38573bfd60d6043ab266471607848fb71284cd0d9eecff9",  # noqa: mock
        )

        self.assertEqual("mainnet", result["network"])
        self.assertEqual(1647066436595, result["timestamp"])
        self.assertEqual(2, result["latency"])
        self.assertEqual("0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf", result["txHash"])  # noqa: mock

    @async_test(loop=ev_loop)
    async def test_clob_batch_order_update(self):
        trading_pair = combine_to_hb_trading_pair(base="COIN", quote="ALPHA")
        order_to_create = GatewayInFlightOrder(
            client_order_id="someOrderIDCreate",
            trading_pair=trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=123123123,
            amount=Decimal("10"),
            price=Decimal("100"),
        )
        order_to_cancel = GatewayInFlightOrder(
            client_order_id="someOrderIDCancel",
            trading_pair=trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            creation_timestamp=123123123,
            price=Decimal("90"),
            amount=Decimal("9"),
        )
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_batch_order_modify(
            connector="injective",
            chain="injective",
            network="mainnet",
            address="0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18",  # noqa: mock
            orders_to_create=[order_to_create],
            orders_to_cancel=[order_to_cancel],
        )

        self.assertEqual("mainnet", result["network"])
        self.assertEqual(1647066456595, result["timestamp"])
        self.assertEqual(3, result["latency"])
        self.assertEqual("0x7E5F4552091A69125d5DfCb7b8C2659029395Ceg", result["txHash"])  # noqa: mock
