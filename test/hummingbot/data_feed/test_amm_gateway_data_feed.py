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
            connector_chain_network="connector_chain_network",
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
                           message="Error getting data from AmmDataFeed[connector_chain_network]Check network "
                                   "connection. Error: test exception"))

    @patch("hummingbot.data_feed.amm_gateway_data_feed.AmmGatewayDataFeed.gateway_client", new_callable=AsyncMock)
    async def test_fetch_data_successful(self, gateway_client_mock: AsyncMock):
        gateway_client_mock.get_price.side_effect = [{"price": "1"}, {"price": "2"}]
        try:
            await self.data_feed._fetch_data()
        except asyncio.CancelledError:
            pass
        self.assertEqual(2, gateway_client_mock.get_price.call_count)
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
                connector="connector",
                chain="chain",
                network="network",
                order_amount_in_base=Decimal("1"),
                buy_price=Decimal("1"),
                sell_price=Decimal("2"),
            )
        }
        self.assertTrue(self.data_feed.is_ready())

    @patch("hummingbot.data_feed.amm_gateway_data_feed.AmmGatewayDataFeed.gateway_client", new_callable=AsyncMock)
    async def test_register_token_buy_sell_price_exception(self, gateway_client_mock: AsyncMock):
        # Test lines 132-133: exception handling in _register_token_buy_sell_price
        gateway_client_mock.get_price.side_effect = Exception("API error")
        await self.data_feed._register_token_buy_sell_price("HBOT-USDT")
        self.assertTrue(
            self.is_logged(log_level=LogLevel.WARNING,
                           message="Failed to get price for HBOT-USDT: API error"))

    @patch("hummingbot.data_feed.amm_gateway_data_feed.AmmGatewayDataFeed.gateway_client", new_callable=AsyncMock)
    async def test_request_token_price_returns_none(self, gateway_client_mock: AsyncMock):
        # Test line 151: _request_token_price returns None when price is not in response
        from hummingbot.core.data_type.common import TradeType

        # Case 1: Empty response
        gateway_client_mock.get_price.return_value = {}
        result = await self.data_feed._request_token_price("HBOT-USDT", TradeType.BUY)
        self.assertIsNone(result)

        # Case 2: Response with null price
        gateway_client_mock.get_price.return_value = {"price": None}
        result = await self.data_feed._request_token_price("HBOT-USDT", TradeType.BUY)
        self.assertIsNone(result)

        # Case 3: No response (None)
        gateway_client_mock.get_price.return_value = None
        result = await self.data_feed._request_token_price("HBOT-USDT", TradeType.BUY)
        self.assertIsNone(result)
