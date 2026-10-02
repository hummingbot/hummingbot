import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest, LogLevel
from unittest.mock import AsyncMock, patch

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.amm_gateway_data_feed import AmmGatewayDataFeed


class TestAmmGatewayDataFeed(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data_feed = AmmGatewayDataFeed(
            network="ethereum-mainnet",
            trading_pairs={"HBOT-USDT"},
            order_amount_in_base=Decimal("1"),
        )

    def setUp(self) -> None:
        super().setUp()
        self.set_loggers(loggers=[self.data_feed.logger()])

    @patch("hummingbot.data_feed.amm_gateway_data_feed.AmmGatewayDataFeed.gateway_client", new_callable=AsyncMock)
    async def test_check_network_connected(self, gateway_client_mock: AsyncMock):
        gateway_client_mock.ping_gateway.return_value = True
        self.assertEqual(NetworkStatus.CONNECTED, await self.data_feed.check_network())

    @patch("hummingbot.data_feed.amm_gateway_data_feed.AmmGatewayDataFeed.gateway_client", new_callable=AsyncMock)
    async def test_check_network_not_connected(self, gateway_client_mock: AsyncMock):
        gateway_client_mock.ping_gateway.return_value = False
        self.assertEqual(NetworkStatus.NOT_CONNECTED, await self.data_feed.check_network())
        self.assertTrue(self.is_logged(log_level=LogLevel.WARNING,
                                       message="Gateway is not online. Please check your gateway connection.", ))

    @patch("hummingbot.data_feed.amm_gateway_data_feed.AmmGatewayDataFeed._async_sleep", new_callable=AsyncMock)
    @patch("hummingbot.data_feed.amm_gateway_data_feed.AmmGatewayDataFeed._fetch_data", new_callable=AsyncMock)
    async def test_fetch_data_loop_exception(self, fetch_data_mock: AsyncMock, _):
        fetch_data_mock.side_effect = [Exception("test exception"), asyncio.CancelledError()]
        try:
            await self.data_feed._fetch_data_loop()
        except asyncio.CancelledError:
            pass
        self.assertEqual(2, fetch_data_mock.call_count)
        self.assertTrue(
            self.is_logged(log_level=LogLevel.ERROR,
                           message="Error getting data from AmmDataFeed[ethereum-mainnet]Check network "
                                   "connection. Error: test exception"))

    @patch("hummingbot.data_feed.amm_gateway_data_feed.AmmGatewayDataFeed.gateway_client", new_callable=AsyncMock)
    async def test_fetch_data_successful(self, gateway_client_mock: AsyncMock):
        gateway_client_mock.get_default_swap_provider.return_value = "uniswap/amm"
        gateway_client_mock.quote_swap.side_effect = [{"price": "1"}, {"price": "2"}]
        try:
            await self.data_feed._fetch_data()
        except asyncio.CancelledError:
            pass
        self.assertEqual(2, gateway_client_mock.quote_swap.call_count)
        self.assertEqual(Decimal("1"), self.data_feed.price_dict["HBOT-USDT"].buy_price)
        self.assertEqual(Decimal("2"), self.data_feed.price_dict["HBOT-USDT"].sell_price)

    def test_is_ready_empty_price_dict(self):
        # Test line 76: is_ready returns False when price_dict is empty
        self.data_feed._price_dict = {}
        self.assertFalse(self.data_feed.is_ready())

    def test_is_ready_with_prices(self):
        # Test line 76: is_ready returns True when price_dict has data
        from hummingbot.data_feed.amm_gateway_data_feed import TokenBuySellPrice
        self.data_feed._price_dict = {
            "HBOT-USDT": TokenBuySellPrice(
                base="HBOT",
                quote="USDT",
                chain="ethereum",
                network="ethereum-mainnet",
                swap_provider="uniswap/amm",
                order_amount_in_base=Decimal("1"),
                buy_price=Decimal("1"),
                sell_price=Decimal("2"),
            )
        }
        self.assertTrue(self.data_feed.is_ready())

    @patch("hummingbot.data_feed.amm_gateway_data_feed.AmmGatewayDataFeed.gateway_client", new_callable=AsyncMock)
    async def test_register_token_buy_sell_price_exception(self, gateway_client_mock: AsyncMock):
        # Test lines 132-133: exception handling in _register_token_buy_sell_price
        gateway_client_mock.get_default_swap_provider.return_value = "uniswap/amm"
        gateway_client_mock.quote_swap.side_effect = Exception("API error")
        await self.data_feed._register_token_buy_sell_price("HBOT-USDT")
        self.assertTrue(
            self.is_logged(log_level=LogLevel.WARNING,
                           message="Failed to get price using quote_swap: API error"))

    @patch("hummingbot.data_feed.amm_gateway_data_feed.AmmGatewayDataFeed.gateway_client", new_callable=AsyncMock)
    async def test_request_token_price_returns_none(self, gateway_client_mock: AsyncMock):
        # Test line 151: _request_token_price returns None when price is not in response
        from hummingbot.core.data_type.common import TradeType

        gateway_client_mock.get_default_swap_provider.return_value = "uniswap/amm"

        # Case 1: Empty response
        gateway_client_mock.quote_swap.return_value = {}
        result = await self.data_feed._request_token_price("HBOT-USDT", TradeType.BUY)
        self.assertIsNone(result)

        # Case 2: Response with null price
        gateway_client_mock.quote_swap.return_value = {"price": None}
        result = await self.data_feed._request_token_price("HBOT-USDT", TradeType.BUY)
        self.assertIsNone(result)

        # Case 3: No response (None)
        gateway_client_mock.quote_swap.return_value = None
        result = await self.data_feed._request_token_price("HBOT-USDT", TradeType.BUY)
        self.assertIsNone(result)

    def test_invalid_network_format(self):
        # A bare network carries no chain, so Gateway could not route it.
        with self.assertRaises(ValueError) as context:
            AmmGatewayDataFeed(
                network="mainnet-beta",
                trading_pairs={"HBOT-USDT"},
                order_amount_in_base=Decimal("1"),
            )
        self.assertIn("Invalid network", str(context.exception))

    def test_dex_connector_rejected_as_network(self):
        # The pre-unification "jupiter/router" form names a dex, not a network. Gateway
        # picks the dex from the network config, so this has to fail loudly rather than
        # be quietly reinterpreted.
        with self.assertRaises(ValueError) as context:
            AmmGatewayDataFeed(
                network="jupiter/router",
                trading_pairs={"HBOT-USDT"},
                order_amount_in_base=Decimal("1"),
            )
        self.assertIn("Invalid network", str(context.exception))

    def test_gateway_client_lazy_initialization(self):
        # Test lines 35-37: Gateway client lazy initialization
        AmmGatewayDataFeed._gateway_client = None  # Reset class variable
        feed = AmmGatewayDataFeed(
            network="ethereum-mainnet",
            trading_pairs={"HBOT-USDT"},
            order_amount_in_base=Decimal("1"),
        )
        # First access should initialize
        client1 = feed.gateway_client
        self.assertIsNotNone(client1)
        # Second access should return same instance
        client2 = feed.gateway_client
        self.assertIs(client1, client2)

    def test_chain_network_properties(self):
        # The chain is carried by the network id, so it needs no Gateway round trip.
        feed = AmmGatewayDataFeed(
            network="solana-mainnet-beta",
            trading_pairs={"HBOT-USDT"},
            order_amount_in_base=Decimal("1"),
        )
        self.assertEqual("solana", feed.chain)
        self.assertEqual("solana-mainnet-beta", feed.network)
        # The swap provider is not known until Gateway has been asked for it.
        self.assertEqual("", feed.swap_provider)

    @patch("hummingbot.data_feed.amm_gateway_data_feed.AmmGatewayDataFeed.gateway_client", new_callable=AsyncMock)
    async def test_request_token_price_no_swap_provider(self, gateway_client_mock: AsyncMock):
        # A network with no swapProvider has nothing to quote against.
        from hummingbot.core.data_type.common import TradeType

        test_feed = AmmGatewayDataFeed(
            network="ethereum-mainnet",
            trading_pairs={"HBOT-USDT"},
            order_amount_in_base=Decimal("1"),
        )
        self.set_loggers(loggers=[test_feed.logger()])

        gateway_client_mock.get_default_swap_provider.return_value = None

        result = await test_feed._request_token_price("HBOT-USDT", TradeType.BUY)
        self.assertIsNone(result)
        gateway_client_mock.quote_swap.assert_not_called()
        self.assertTrue(
            self.is_logged(
                log_level=LogLevel.WARNING,
                message="Failed to get price using quote_swap: No swap provider configured "
                        "for network ethereum-mainnet"
            )
        )

    @patch("hummingbot.data_feed.amm_gateway_data_feed.AmmGatewayDataFeed.gateway_client", new_callable=AsyncMock)
    async def test_swap_provider_is_read_once_across_concurrent_legs(self, gateway_client_mock: AsyncMock):
        # Every pair's buy and sell leg starts together, so they all reach an empty cache
        # at the same moment. Against a live Gateway this read the network config twice
        # for one pair, and would have read it 2N times for N pairs.
        test_feed = AmmGatewayDataFeed(
            network="solana-mainnet-beta",
            trading_pairs={"SOL-USDC", "JUP-USDC", "BONK-USDC"},
            order_amount_in_base=Decimal("1"),
        )

        async def slow_lookup(_network):
            # Yield, so a resolution that is not held under a lock loses the race.
            await asyncio.sleep(0)
            return "jupiter/router"

        gateway_client_mock.get_default_swap_provider.side_effect = slow_lookup
        gateway_client_mock.quote_swap.return_value = {"price": "1"}

        await test_feed._fetch_data()
        await test_feed._fetch_data()

        self.assertEqual(1, gateway_client_mock.get_default_swap_provider.await_count)
        self.assertEqual(12, gateway_client_mock.quote_swap.await_count)

    @patch("hummingbot.data_feed.amm_gateway_data_feed.AmmGatewayDataFeed.gateway_client", new_callable=AsyncMock)
    async def test_quotes_the_networks_default_swap_provider(self, gateway_client_mock: AsyncMock):
        # The dex quoting the pair comes from the network config, and is resolved once
        # rather than re-read on every quote.
        from hummingbot.core.data_type.common import TradeType

        test_feed = AmmGatewayDataFeed(
            network="solana-mainnet-beta",
            trading_pairs={"SOL-USDC"},
            order_amount_in_base=Decimal("1"),
        )
        gateway_client_mock.get_default_swap_provider.return_value = "orca/clmm"
        gateway_client_mock.quote_swap.return_value = {"price": "3"}

        await test_feed._request_token_price("SOL-USDC", TradeType.BUY)
        await test_feed._request_token_price("SOL-USDC", TradeType.SELL)

        gateway_client_mock.get_default_swap_provider.assert_awaited_once_with("solana-mainnet-beta")
        self.assertEqual("orca/clmm", test_feed.swap_provider)
        self.assertEqual(2, gateway_client_mock.quote_swap.await_count)
        for call in gateway_client_mock.quote_swap.await_args_list:
            self.assertEqual("solana-mainnet-beta", call.kwargs["network"])
            self.assertEqual("orca", call.kwargs["dex"])
            self.assertEqual("clmm", call.kwargs["trading_type"])

    async def test_register_token_buy_sell_price_with_none_prices(self):
        # Test when _request_token_price returns None for both buy and sell
        # Clear any existing price dict
        self.data_feed._price_dict.clear()
        with patch.object(self.data_feed, '_request_token_price', return_value=None):
            await self.data_feed._register_token_buy_sell_price("HBOT-USDT")
            # Should not add to price dict
            self.assertNotIn("HBOT-USDT", self.data_feed._price_dict)
