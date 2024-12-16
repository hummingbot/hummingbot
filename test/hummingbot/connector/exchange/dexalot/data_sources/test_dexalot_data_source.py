import asyncio
import json
import re
from decimal import Decimal
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from web3 import AsyncWeb3

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.dexalot import dexalot_constants as CONSTANTS, dexalot_web_utils as web_utils
from hummingbot.connector.exchange.dexalot.data_sources.dexalot_data_source import DexalotClient
from hummingbot.connector.exchange.dexalot.dexalot_exchange import DexalotExchange
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.common import OrderType, TradeType


class DexalotClientTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        self.api_key = "somekey"
        self.base_asset = "AVAX"
        self.quote_asset = "USDC"
        self.trading_pair = "AVAX-USDC"

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.exchange = DexalotExchange(
            client_config_map=client_config_map,
            dexalot_api_key=self.api_key,
            dexalot_api_secret=self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        self.exchange._evm_params[self.trading_pair] = {
            "base_coin": self.base_asset,
            "quote_coin": self.quote_asset,
            "base_evmdecimals": Decimal(6),
            "quote_evmdecimals": Decimal(18),
        }
        self._tx_client = DexalotClient(
            self.api_secret,
            self.exchange
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @property
    def _token_info_request_successful_mock_response(self):
        return [{
            'env': 'production-multi-avax', 'symbol': 'AVAX', 'subnet_symbol': 'AVAX', 'name': 'Avalanche',
            'isnative': True,
            'address': '0x0000000000000000000000000000000000000000',  # noqa: mock
            'evmdecimals': 18, 'isvirtual': False,
            'chain_id': 43114,
            'status': 'deployed', 'old_symbol': None, 'auctionmode': 0, 'auctionendtime': None,
            'min_depositamnt': '0.0246467720588235293'
        }]

    @property
    def _get_balances_request_successful_mock_response(self):
        return [[
            b'AVAX\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00',
            b'USDC\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'],
            [23191212271166640, 15890000, 0, 0, 0, 0, 0, 0, 0, 0, 0,
             0, 0, 0, 0, 0],
            [23191212271166640, 15890000, 0, 0, 0, 0, 0, 0, 0, 0, 0,
             0, 0, 0, 0, 0]]

    @property
    def _order_cancelation_request_successful_mock_response(self):
        return "79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659"  # noqa: mock

    @property
    def order_creation_request_successful_mock_response(self):
        return "79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659"  # noqa: mock

    def test_get_balances(self):
        mock_web3 = MagicMock(spec=AsyncWeb3)
        mock_web3.eth = AsyncMock()
        mock_web3.eth.contract = AsyncMock()
        mock_web3.eth.contract.functions = AsyncMock()
        mock_web3.eth.contract.functions.getBalances = AsyncMock
        mock_web3.eth.contract.functions.getBalances.call = AsyncMock()
        mock_web3.eth.contract.functions.getBalances.call.return_value = \
            self._get_balances_request_successful_mock_response
        self._tx_client.portfolio_sub_manager = mock_web3.eth.contract
        result = self.async_run_with_timeout(self._tx_client.get_balances({}, {}))
        self.assertEqual(result[0]["AVAX"], Decimal('0.023191212271166640'))
        self.assertEqual(result[1]["USDC"], Decimal('15.890000'))

    @aioresponses()
    def test_get_token_info(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.TOKEN_INFO_PATH_URL, domain=self.exchange._domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self._token_info_request_successful_mock_response
        mock_api.get(regex_url, body=json.dumps(resp))
        self.async_run_with_timeout(self._tx_client._get_token_info())
        self.assertIsNotNone(self._tx_client.balance_evm_params)

    @patch(
        "hummingbot.connector.exchange.dexalot.data_sources.dexalot_data_source.DexalotClient._build_and_send_tx")
    def test_cancel_order(self, send_tx_sync_mode_mock):
        send_tx_sync_mode_mock.return_value = self._order_cancelation_request_successful_mock_response
        order = GatewayInFlightOrder(
            client_order_id="0xbdd7b2516b6da27e0f6ad078d4542154",  # noqa: mock
            exchange_order_id="0x000000000000000000000000000000000000000000000000000000006c04243c",  # noqa: mock
            trading_pair="AVAX-USDC",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=123123123,
            amount=Decimal("10"),
            price=Decimal("100"),
        )
        result = self.async_run_with_timeout(self._tx_client.cancel_order_list([order]))
        self.assertEqual("79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659", result)  # noqa: mock

    @patch(
        "hummingbot.connector.exchange.dexalot.data_sources.dexalot_data_source.DexalotClient._build_and_send_tx")
    def test_cancel_add_order(self, send_tx_sync_mode_mock):
        send_tx_sync_mode_mock.return_value = self._order_cancelation_request_successful_mock_response
        order = GatewayInFlightOrder(
            client_order_id="0xbdd7b2516b6da27e0f6ad078d4542154",  # noqa: mock
            exchange_order_id="0x000000000000000000000000000000000000000000000000000000006c04243c",  # noqa: mock
            trading_pair="AVAX-USDC",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=123123123,
            amount=Decimal("10"),
            price=Decimal("100"),
        )
        result = self.async_run_with_timeout(self._tx_client.cancel_and_add_order_list([order], []))
        self.assertEqual("79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659", result)  # noqa: mock

    @patch(
        "hummingbot.connector.exchange.dexalot.data_sources.dexalot_data_source.DexalotClient._build_and_send_tx")
    def test_place_order(self, send_tx_sync_mode_mock):
        send_tx_sync_mode_mock.return_value = self.order_creation_request_successful_mock_response
        order = GatewayInFlightOrder(
            client_order_id="0xbdd7b2516b6da27e0f6ad078d4542154",  # noqa: mock
            trading_pair="AVAX-USDC",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=123123123,
            amount=Decimal("10"),
            price=Decimal("100"),
        )
        result = self.async_run_with_timeout(self._tx_client.cancel_and_add_order_list([], [order]))
        self.assertEqual("79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659", result)  # noqa: mock
