import asyncio
import json
import re
from decimal import Decimal

from typing import Awaitable, Optional, Union
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict
from substrateinterface import Keypair

from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_source import ChainflipLPDataSource



from test.hummingbot.connector.exchange.chainflip_lp.mock_rpc_executor import MockRPCExecutor

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_exchange import ChainflipLpExchange
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_formatter import DataFormatter
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.common import TradeType


class ChainflipLpDataSourceTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_asset_dict = {"chain":"Ethereum", "asset":"ETH"}
        cls.quote_asset_dict = {"chain": "Ethereum","asset":"USDC"}
        cls.base_asset = "ETH"
        cls.quote_asset = "USDC"
        cls.trading_pair = f'{cls.base_asset}-{cls.quote_asset}'
        cls.ex_trading_pair = f'{cls.base_asset}-{cls.quote_asset}'

    def setUp(self) -> None:
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        self.async_tasks = []
        asyncio.set_event_loop(self.async_loop)
        self.mocking_assistant = NetworkMockingAssistant()
        

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.address = Keypair.create_from_mnemonic(Keypair.generate_mnemonic()).ss58_address
        self.connector = ChainflipLpExchange(
            client_config_map=client_config_map,
            chainflip_lp_api_url="http://localhost:80",
            chainflip_lp_address= self.address,
            chainflip_eth_chain="Ethereum",
            chainflip_usdc_chain="Ethereum",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.data_source = ChainflipLPDataSource(
            connector=self.connector,
            address=self.address,
            rpc_api_url="",
            trading_pairs=[self.trading_pair],
            trading_required=False
        )
        self.data_source._rpc_executor = MockRPCExecutor()
    


