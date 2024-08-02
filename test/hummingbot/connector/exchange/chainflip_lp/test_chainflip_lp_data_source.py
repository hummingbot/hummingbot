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
    @property
    def order_fills_response(self):
        return {
            "result": {
            "block_hash": "0xc65c18f81c4a9b1b5cd7e203f09eaa2288b44771e13d43791e1319a2695c72e9",
            "block_number": 67,
            "fills": [
                {
                    "range_order": {
                        "lp": "cFPdef3hF5zEwbWUG6ZaCJ3X7mTvEeAog7HxZ8QyFcCgDVGDM",
                        "base_asset": "FLIP",
                        "quote_asset": "USDC",
                        "id": "0x0",
                        "range": {
                            "start": -887272,
                            "end": 887272
                        },
                        "fees": {
                            "base": "0x13fbe85edc90000",
                            "quote": "0x1e63a"
                        },
                        "liquidity": "0x7055df27b7e148"
                    }
                },
                {
                    "limit_orders": {
                        "lp": self.address,
                        "base_asset": "FLIP",
                        "quote_asset": "USDC",
                        # The side of the order that was filled
                        "side": "buy",
                        "id": "0x0",
                        "tick": 0,
                        # The amount of the order that was used, in the units of the asset that was sold (by the order)
                        "sold": "0x1200",
                        # The amount assets bought during this fill, in the units of the bought asset
                        "bought": "0x1200",
                        # The fees earned during this fill, in units of the bought asset (Which in the asset you actually earn the fees in)
                        "fees": "0x100",
                        # The remaining amount in the order after the fill. This is in units of the sold asset.
                        "remaining": "0x100000",
                    }
                },
            ]
            }
        }
    @property
    def all_asset_response(self):
        response = {
            'result': [
                {'chain': 'Ethereum', 'asset': 'ETH'}, 
                {'chain': 'Ethereum', 'asset': 'FLIP'}, 
                {'chain': 'Ethereum', 'asset': 'USDC'}, 
                {'chain': 'Ethereum', 'asset': 'USDT'}, 
                {'chain': 'Polkadot', 'asset': 'DOT'}, 
                {'chain': 'Bitcoin', 'asset': 'BTC'}, 
                {'chain': 'Arbitrum', 'asset': 'ETH'}, 
                {'chain': 'Arbitrum', 'asset': 'USDC'}
            ]
        }
        return response
    def test_start(self):
        self.data_source._rpc_executor._all_assets_responses.put_nowait(self.all_asset_response)
        self.data_source._rpc_executor._order_fills_responses.put_nowait(self.order_fills_response)
        self.data_source.start()
        self.assertEqual(len(self.data_source._events_listening_tasks),1)
        self.assertGreater(len(self.data_source._assets_list), 1)
    



    


