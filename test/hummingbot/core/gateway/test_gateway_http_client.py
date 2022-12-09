import asyncio
import unittest
from contextlib import ExitStack
from decimal import Decimal
from os.path import join, realpath
from test.mock.http_recorder import HttpPlayer
from typing import Any, Dict, List
from unittest.mock import patch

from aiohttp import ClientSession
from aiounittest import async_test

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
        cls._db_path = realpath(join(__file__, "../fixtures/gateway_http_client_fixture.db"))
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
    async def test_ping_gateway(self):
        result: bool = await GatewayHttpClient.get_instance().ping_gateway()
        self.assertTrue(result)

    @async_test(loop=ev_loop)
    async def test_get_gateway_status(self):
        result: List[Dict[str, Any]] = await GatewayHttpClient.get_instance().get_gateway_status()
        self.assertIsInstance(result, list)
        self.assertEqual(1, len(result))

        first_entry: Dict[str, Any] = result[0]
        self.assertEqual(3, first_entry["chainId"])

    @async_test(loop=ev_loop)
    async def test_add_wallet(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().add_wallet(
            "ethereum",
            "ropsten",
            "0000000000000000000000000000000000000000000000000000000000000001"      # noqa: mock
        )
        self.assertTrue(isinstance(result, dict))
        self.assertEqual("0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf", result["address"])

    @async_test(loop=ev_loop)
    async def test_get_wallets(self):
        result: List[Dict[str, Any]] = await GatewayHttpClient.get_instance().get_wallets()
        self.assertIsInstance(result, list)

        first_entry: Dict[str, Any] = result[0]
        self.assertIn("chain", first_entry)
        self.assertIn("walletAddresses", first_entry)

    @async_test(loop=ev_loop)
    async def test_get_connectors(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().get_connectors()
        self.assertIn("connectors", result)

        uniswap: Dict[str, Any] = result["connectors"][0]
        self.assertEqual("uniswap", uniswap["name"])
        self.assertEqual(["EVM_AMM"], uniswap["trading_type"])

    @async_test(loop=ev_loop)
    async def test_get_configuration(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().get_configuration()
        self.assertIn("avalanche", result)
        self.assertIn("ethereum", result)

    @async_test(loop=ev_loop)
    async def test_update_configuration(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().update_config("telemetry.enabled", False)
        self.assertIn("message", result)

    @async_test(loop=ev_loop)
    async def test_get_tokens(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().get_tokens("ethereum", "ropsten")
        self.assertIn("tokens", result)
        self.assertIsInstance(result["tokens"], list)
        self.assertEqual("WETH", result["tokens"][0]["symbol"])
        self.assertEqual("DAI", result["tokens"][1]["symbol"])

    @async_test(loop=ev_loop)
    async def test_get_network_status(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().get_network_status("ethereum", "ropsten")
        self.assertEqual(3, result["chainId"])
        self.assertEqual(12067035, result["currentBlockNumber"])

    @async_test(loop=ev_loop)
    async def test_get_price(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().get_price(
            "ethereum",
            "ropsten",
            "uniswap",
            "DAI",
            "WETH",
            Decimal(1000),
            TradeType.BUY
        )
        self.assertEqual("1000.000000000000000000", result["amount"])
        self.assertEqual("1000000000000000000000", result["rawAmount"])
        self.assertEqual("0.00262343", result["price"])

    @async_test(loop=ev_loop)
    async def test_get_balances(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().get_balances(
            "ethereum",
            "ropsten",
            "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92",
            ["WETH", "DAI"],
        )
        self.assertIn("balances", result)
        self.assertEqual("21.000000000000000000", result["balances"]["WETH"])
        self.assertEqual("0.000000000000000000", result["balances"]["DAI"])

    @async_test(loop=ev_loop)
    async def test_successful_get_transaction(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().get_transaction_status(
            "ethereum",
            "ropsten",
            "0xa8d428627dc7f453be79a32129dc18ea29d1a715249a4a5762ca6273da5d96e3"        # noqa: mock
        )
        self.assertEqual(1, result["txStatus"])
        self.assertIsNotNone(result["txData"])

    @async_test(loop=ev_loop)
    async def test_failed_get_transaction(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().get_transaction_status(
            "ethereum",
            "ropsten",
            "0xa8d428627dc7f453be79a32129dc18ea29d1a715249a4a5762ca6273da5d96e1"        # noqa: mock
        )
        self.assertEqual(-1, result["txStatus"])
        self.assertIsNone(result["txData"])

    @async_test(loop=ev_loop)
    async def test_get_evm_nonce(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().get_evm_nonce(
            "ethereum",
            "ropsten",
            "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92"
        )
        self.assertEqual(2, result["nonce"])

    @async_test(loop=ev_loop)
    async def test_approve_token(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().approve_token(
            "ethereum",
            "ropsten",
            "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92",
            "WETH",
            "uniswap",
            2
        )
        self.assertEqual("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", result["spender"])
        self.assertEqual("0x66b533792f45780fc38573bfd60d6043ab266471607848fb71284cd0d9eecff9",      # noqa: mock
                         result["approval"]["hash"])

    @async_test(loop=ev_loop)
    async def test_get_allowances(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().get_allowances(
            "ethereum",
            "ropsten",
            "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92",
            ["WETH", "DAI"],
            "uniswap"
        )
        self.assertIn("approvals", result)
        self.assertEqual("115792089237316195423570985008687907853269984665640564039457.584007913129639935",
                         result["approvals"]["DAI"])
        self.assertEqual("115792089237316195423570985008687907853269984665640564039457.584007913129639935",
                         result["approvals"]["WETH"])

    @async_test(loop=ev_loop)
    async def test_amm_trade(self):
        result: Dict[str, Any] = await GatewayHttpClient.get_instance().amm_trade(
            "ethereum",
            "ropsten",
            "uniswap",
            "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92",
            "DAI",
            "WETH",
            TradeType.BUY,
            Decimal(1000),
            Decimal("0.00266"),
            4
        )
        self.assertEqual("1000.000000000000000000", result["amount"])
        self.assertEqual("1000000000000000000000", result["rawAmount"])
        self.assertEqual("0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18",      # noqa: mock
                         result["txHash"])

    @async_test(loop=ev_loop)
    async def test_solana_get_root(self):
        network = 'testnet'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().solana_post_root(
            network
        )

        self.assertEqual(network, result["network"])
        self.assertEqual("https://api.testnet.solana.com", result["rpcUrl"])
        self.assertTrue(result["connection"])
        self.assertGreater(result["timestamp"], 0)

    @async_test(loop=ev_loop)
    async def test_solana_get_balances(self):
        network = 'testnet'
        address = ''
        token_symbols = ['']

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().solana_get_balances(
            network,
            address,
            token_symbols
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_solana_get_token(self):
        network = 'testnet'
        address = ''
        token = ''

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().solana_get_token(
            network,
            address,
            token
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_solana_post_token(self):
        network = 'testnet'
        address = ''
        token = ''

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().solana_post_token(
            network,
            address,
            token
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_solana_post_poll(self):
        network = 'testnet'
        tx_hash = ''

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().solana_post_poll(
            network,
            tx_hash
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_clob_get_root(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_get_root(
            chain,
            network,
            connector
        )

        self.assertEqual(chain, result["chain"])
        self.assertEqual(network, result["network"])
        self.assertEqual(connector, result["connector"])
        self.assertTrue(result["connection"])
        self.assertGreater(result["timestamp"], 0)

    @async_test(loop=ev_loop)
    async def test_clob_get_markets(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_get_markets(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_clob_get_order_books(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_get_order_books(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_clob_get_tickers(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_get_tickers(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_clob_get_orders(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_get_orders(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_clob_post_orders(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        orders = []

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_post_orders(
            chain,
            network,
            connector,
            orders
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_clob_delete_orders(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_delete_orders(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_clob_get_open_orders(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_get_open_orders(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_clob_get_filled_orders(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_get_filled_orders(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_clob_post_settle_funds(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().clob_post_settle_funds(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_serum_get_root(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().serum_get_root(
            chain,
            network,
            connector
        )

        self.assertEqual(chain, result["chain"])
        self.assertEqual(network, result["network"])
        self.assertEqual(connector, result["connector"])
        self.assertTrue(result["connection"])
        self.assertGreater(result["timestamp"], 0)

    @async_test(loop=ev_loop)
    async def test_serum_get_markets(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().serum_get_markets(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_serum_get_order_books(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().serum_get_order_books(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_serum_get_tickers(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().serum_get_tickers(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_serum_get_orders(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().serum_get_orders(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_serum_post_orders(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        orders = []

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().serum_post_orders(
            chain,
            network,
            connector,
            orders
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_serum_delete_orders(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().serum_delete_orders(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_serum_get_open_orders(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().serum_get_open_orders(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_serum_get_filled_orders(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().serum_get_filled_orders(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)

    @async_test(loop=ev_loop)
    async def test_serum_post_settle_funds(self):
        chain = 'solana'
        network = 'testnet'
        connector = 'serum'

        result: Dict[str, Any] = await GatewayHttpClient.get_instance().serum_post_settle_funds(
            chain,
            network,
            connector
        )

        self.assertTrue(len(result) > 0)
