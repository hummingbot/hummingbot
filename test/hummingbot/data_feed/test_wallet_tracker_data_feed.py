import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest, LogLevel
from unittest.mock import AsyncMock, patch

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.wallet_tracker_data_feed import WalletTrackerDataFeed


class TestWalletTrackerDataFeed(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data_feed = WalletTrackerDataFeed(
            chain="chain",
            network="network",
            wallets={"wallet"},
            tokens={"token1", "token2"},
        )

    def setUp(self) -> None:
        super().setUp()
        self.set_loggers(loggers=[self.data_feed.logger()])

    @patch("hummingbot.data_feed.wallet_tracker_data_feed.WalletTrackerDataFeed.gateway_client", new_callable=AsyncMock)
    async def test_check_network_connected(self, gateway_client_mock: AsyncMock):
        gateway_client_mock.ping_gateway.return_value = True
        self.assertEqual(NetworkStatus.CONNECTED, await self.data_feed.check_network())

    @patch("hummingbot.data_feed.wallet_tracker_data_feed.WalletTrackerDataFeed.gateway_client", new_callable=AsyncMock)
    async def test_check_network_not_connected(self, gateway_client_mock: AsyncMock):
        gateway_client_mock.ping_gateway.return_value = False
        self.assertEqual(NetworkStatus.NOT_CONNECTED, await self.data_feed.check_network())
        self.assertTrue(self.is_logged(log_level=LogLevel.WARNING,
                                       message="Gateway is not online. Please check your gateway connection.", ))

    @patch("hummingbot.data_feed.wallet_tracker_data_feed.WalletTrackerDataFeed._async_sleep", new_callable=AsyncMock)
    @patch("hummingbot.data_feed.wallet_tracker_data_feed.WalletTrackerDataFeed._fetch_data", new_callable=AsyncMock)
    async def test_fetch_data_loop_exception(self, fetch_data_mock: AsyncMock, _):
        fetch_data_mock.side_effect = [Exception("test exception"), asyncio.CancelledError()]
        try:
            await self.data_feed._fetch_data_loop()
        except asyncio.CancelledError:
            pass
        self.assertEqual(2, fetch_data_mock.call_count)
        self.assertTrue(
            self.is_logged(log_level=LogLevel.ERROR,
                           message="Error getting data from WalletTrackerDataFeed[chain-network]Check network "
                                   "connection. Error: test exception"))

    @patch("hummingbot.data_feed.wallet_tracker_data_feed.WalletTrackerDataFeed.gateway_client", new_callable=AsyncMock)
    async def test_fetch_data_successful(self, gateway_client_mock: AsyncMock):
        gateway_client_mock.get_balances.return_value = {"balances": {"token": 1, "token2": 2}}
        try:
            await self.data_feed._fetch_data()
        except asyncio.CancelledError:
            pass
        self.assertEqual(1, gateway_client_mock.get_balances.call_count)
        self.assertEqual(Decimal("1"), self.data_feed.wallet_balances["wallet"]["token"])
        self.assertEqual(Decimal("2"), self.data_feed.wallet_balances["wallet"]["token2"])
        self.assertEqual(Decimal("1"), self.data_feed.wallet_balances_df.loc["wallet", "token"])
        self.assertEqual(Decimal("2"), self.data_feed.wallet_balances_df.loc["wallet", "token2"])

    @patch("hummingbot.data_feed.wallet_tracker_data_feed.GatewayHttpClient.get_instance")
    def test_gateway_client_property(self, get_instance_mock):
        # Reset the gateway client to None
        self.data_feed._gateway_client = None

        # Create a mock instance
        mock_client = AsyncMock()
        get_instance_mock.return_value = mock_client

        # Access the property
        client = self.data_feed.gateway_client

        # Verify the client was initialized correctly
        self.assertEqual(client, mock_client)
        get_instance_mock.assert_called_once()

        # Verify subsequent calls return the same instance
        self.assertEqual(self.data_feed.gateway_client, mock_client)
        get_instance_mock.assert_called_once()  # Should not be called again
