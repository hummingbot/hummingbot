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

from hummingbot.core.data_type.common import PositionSide
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient

ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()


class GatewayHttpClientUnitTest(unittest.TestCase):
    _db_path: str
    _http_player: HttpPlayer
    _patch_stack: ExitStack

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._db_path = realpath(join(__file__, "../fixtures/gateway_perp_http_client_fixture.db"))
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
    async def test_gateway_list(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().get_perp_markets(
            "ethereum",
            "optimism",
            "perp",
        )
        self.assertTrue(isinstance(result["pairs"], list))

    @async_test(loop=ev_loop)
    async def test_gateway_status(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().get_perp_market_status(
            "ethereum",
            "optimism",
            "perp",
            "AAVE",
            "USD",
        )
        self.assertTrue(isinstance(result, dict))
        self.assertTrue(result["isActive"])

    @async_test(loop=ev_loop)
    async def test_gateway_price(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().get_perp_market_price(
            "ethereum",
            "optimism",
            "perp",
            "AAVE",
            "USD",
            Decimal("0.1"),
            PositionSide.LONG,
        )
        self.assertTrue(isinstance(result, dict))
        self.assertEqual("60.9056073563350272054334195984747494008896", result["markPrice"])
        self.assertEqual("61.0768053", result["indexPrice"])
        self.assertEqual("61.01013608", result["indexTwapPrice"])

    @async_test(loop=ev_loop)
    async def test_perp_open(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().amm_perp_open(
            "ethereum",
            "optimism",
            "perp",
            "0xefB7Be8631d154d4C0ad8676FEC0897B2894FE8F",
            "AAVE",
            "USD",
            PositionSide.LONG,
            Decimal("0.1"),
            Decimal("63"),
        )
        self.assertEqual("0.100000000000000000", result["amount"])
        self.assertEqual("0xd7b9f055cdedfce6cda65ff9ec39b6645b7158b9470e2198943811ec902e05f6",      # noqa: mock
                         result["txHash"])

    @async_test(loop=ev_loop)
    async def test_gateway_perp_position(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().get_perp_position(
            "ethereum",
            "optimism",
            "perp",
            "0xefB7Be8631d154d4C0ad8676FEC0897B2894FE8F",
            "AAVE",
            "USD",
        )
        self.assertTrue(isinstance(result, dict))
        self.assertEqual("LONG", result["positionSide"])
        self.assertEqual("AAVEUSD", result["tickerSymbol"])
        self.assertEqual("60.94100260746568610616", result["entryPrice"])

    @async_test(loop=ev_loop)
    async def test_perp_close(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().amm_perp_close(
            "ethereum",
            "optimism",
            "perp",
            "0xefB7Be8631d154d4C0ad8676FEC0897B2894FE8F",
            "AAVE",
            "USD",
        )
        self.assertEqual("0xc400ac0b5156c90b39a3fa379b4a1099e1fd4312951925ab753655699f5d21a1",      # noqa: mock
                         result["txHash"])
