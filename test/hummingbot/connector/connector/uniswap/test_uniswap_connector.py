import asyncio
import json
import unittest
from collections import Awaitable
from decimal import Decimal
from unittest.mock import patch, AsyncMock

import aiohttp
from aioresponses import aioresponses

from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.connector.connector.uniswap.uniswap_connector import UniswapConnector
from hummingbot.core.data_type.trade_fee import TokenAmount


class UniswapConnectorTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.base = "COINALHPA"
        self.quote = "HBOT"
        self.trading_pair = f"{self.base}-{self.quote}"
        self.wallet_key = "someWalletKey"
        self.gateway_host = "gtw_host"
        self.gateway_port = 123
        global_config_map["gateway_api_host"].value = self.gateway_host
        global_config_map["gateway_api_port"].value = self.gateway_port
        self.connector = UniswapConnector(
            trading_pairs=[self.trading_pair],
            wallet_private_key=self.wallet_key,
            ethereum_rpc_url="https://<network>.infura.io/v3/YOUR-PROJECT-ID",
        )
        self.ev_loop = asyncio.get_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    @patch(
        "hummingbot.connector.connector.uniswap.uniswap_connector.UniswapConnector._http_client",
        new_callable=AsyncMock
    )
    def test_get_quote_price_updates_fee_overrides_config_map(self, mocked_api, mocked_http_client):
        mocked_http_client.return_value = aiohttp.ClientSession()
        url = f"https://{self.gateway_host}:{self.gateway_port}/eth/uniswap/price"
        mock_response = {
            "price": 10,
            "gasLimit": 30000,
            "gasPrice": 1,
            "gasCost": 2,
            "swaps": [],
        }
        mocked_api.post(url, body=json.dumps(mock_response))

        self.connector._account_balances = {"ETH": Decimal("10000")}
        self.connector._allowances = {self.quote: Decimal("10000")}

        self.async_run_with_timeout(
            self.connector.get_quote_price(self.trading_pair, is_buy=True, amount=Decimal("2"))
        )

        self.assertEqual(
            fee_overrides_config_map["uniswap_maker_fixed_fees"].value, [TokenAmount("ETH", Decimal(str("2")))]
        )
        self.assertEqual(
            fee_overrides_config_map["uniswap_taker_fixed_fees"].value, [TokenAmount("ETH", Decimal(str("2")))]
        )
