from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, patch

from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient


class GatewayHttpClientTokenRouteTest(IsolatedAsyncioWrapperTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.client = GatewayHttpClient.get_instance()

    async def test_add_token_by_address_uses_save_route_with_chain_network_query(self):
        address = "A7bdiYdS5GjqGFtxf17ppRHtDKPkkRqbKtR27dxvQXaS"
        response = {"message": "saved", "token": {"address": address, "symbol": "ZEC"}}

        with patch.object(self.client, "api_request", new=AsyncMock(return_value=response)) as mock_request:
            result = await self.client.add_token_by_address(address, "solana", "mainnet-beta")

        self.assertEqual(response, result)
        mock_request.assert_awaited_once_with(
            "post",
            f"tokens/save/{address}?chainNetwork=solana-mainnet-beta",
        )
