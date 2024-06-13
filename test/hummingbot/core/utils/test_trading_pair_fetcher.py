import asyncio
import json
import unittest
from decimal import Decimal
from typing import Any, Awaitable, Dict
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.security import Security
from hummingbot.client.settings import ConnectorSetting, ConnectorType
from hummingbot.connector.exchange.binance import binance_constants as CONSTANTS, binance_web_utils
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher


class TestTradingPairFetcher(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        Security.decrypt_all()

    @classmethod
    async def wait_until_trading_pair_fetcher_ready(cls, tpf):
        while True:
            if tpf.ready:
                break
            else:
                await asyncio.sleep(0)

    def setUp(self) -> None:
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_loop)

    def tearDown(self) -> None:
        super().tearDown()
        self.async_loop.stop()
        self.async_loop.close()
        asyncio.set_event_loop(self._original_async_loop)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.async_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    class MockConnectorSetting(MagicMock):
        def __init__(self, name, parent_name=None, connector=None, *args, **kwargs) -> None:
            super().__init__(name, *args, **kwargs)
            self._name = name
            self._parent_name = parent_name
            self._connector = connector

        @property
        def name(self) -> str:
            return self._name

        @property
        def parent_name(self) -> str:
            return self._parent_name

        def base_name(self) -> str:
            return self.name

        def connector_connected(self) -> bool:
            return True

        def add_domain_parameter(*_, **__) -> Dict[str, Any]:
            return {}

        def uses_gateway_generic_connector(self) -> bool:
            return False

        def non_trading_connector_instance_with_default_configuration(self, trading_pairs = None):
            return self._connector

    @classmethod
    def tearDownClass(cls) -> None:
        # Need to reset TradingPairFetcher module so next time it gets imported it works as expected
        TradingPairFetcher._sf_shared_instance = None

    def test_trading_pair_fetcher_returns_same_instance_when_get_new_instance_once_initialized(self):
        instance = TradingPairFetcher.get_instance()
        self.assertIs(instance, TradingPairFetcher.get_instance())

    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher._all_connector_settings")
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher._sf_shared_instance")
    def test_fetched_connector_trading_pairs(self, _, mock_connector_settings):
        connector = AsyncMock()
        connector.all_trading_pairs.return_value = ["MOCK-HBOT"]
        mock_connector_settings.return_value = {
            "mock_exchange_1": self.MockConnectorSetting(name="mockConnector", connector=connector),
            "mock_paper_trade": self.MockConnectorSetting(name="mock_paper_trade", parent_name="mock_exchange_1")
        }

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        client_config_map.fetch_pairs_from_all_exchanges = True
        trading_pair_fetcher = TradingPairFetcher(client_config_map)
        self.async_run_with_timeout(self.wait_until_trading_pair_fetcher_ready(trading_pair_fetcher), 1.0)
        trading_pairs = trading_pair_fetcher.trading_pairs
        self.assertEqual(2, len(trading_pairs))
        self.assertEqual({"mockConnector": ["MOCK-HBOT"], "mock_paper_trade": ["MOCK-HBOT"]}, trading_pairs)

    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher._all_connector_settings")
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher._sf_shared_instance")
    @patch("hummingbot.client.config.security.Security.connector_config_file_exists")
    @patch("hummingbot.client.config.security.Security.wait_til_decryption_done")
    def test_fetched_connected_trading_pairs(self, _, __: MagicMock, ___: AsyncMock, mock_connector_settings):
        connector = AsyncMock()
        connector.all_trading_pairs.return_value = ["MOCK-HBOT"]
        mock_connector_settings.return_value = {
            "mock_exchange_1": self.MockConnectorSetting(name="binance", connector=connector),
            "mock_paper_trade": self.MockConnectorSetting(name="mock_paper_trade", parent_name="mock_exchange_1")
        }

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        client_config_map.fetch_pairs_from_all_exchanges = False
        self.assertTrue(Security.connector_config_file_exists("binance"))
        trading_pair_fetcher = TradingPairFetcher(client_config_map)
        self.async_run_with_timeout(self.wait_until_trading_pair_fetcher_ready(trading_pair_fetcher), 1.0)
        trading_pairs = trading_pair_fetcher.trading_pairs
        self.assertEqual(2, len(trading_pairs))
        self.assertEqual({"binance": ["MOCK-HBOT"], "mock_paper_trade": ["MOCK-HBOT"]}, trading_pairs)

    @aioresponses()
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher._all_connector_settings")
    @patch("hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.get_perp_markets")
    @patch("hummingbot.client.settings.GatewayConnectionSetting.get_connector_spec_from_market_name")
    def test_fetch_all(self, mock_api, con_spec_mock, perp_market_mock, all_connector_settings_mock, ):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        client_config_map.fetch_pairs_from_all_exchanges = True
        all_connector_settings_mock.return_value = {
            "binance": ConnectorSetting(
                name='binance',
                type=ConnectorType.Exchange,
                example_pair='ZRX-ETH',
                centralised=True,
                use_ethereum_wallet=False,
                trade_fee_schema=TradeFeeSchema(
                    percent_fee_token=None,
                    maker_percent_fee_decimal=Decimal('0.001'),
                    taker_percent_fee_decimal=Decimal('0.001'),
                    buy_percent_fee_deducted_from_returns=False,
                    maker_fixed_fees=[],
                    taker_fixed_fees=[]),
                config_keys={
                    'binance_api_key': ConfigVar(key='binance_api_key', prompt=""),
                    'binance_api_secret': ConfigVar(key='binance_api_secret', prompt="")},
                is_sub_domain=False,
                parent_name=None,
                domain_parameter=None,
                use_eth_gas_lookup=False),
            "perp_ethereum_optimism": ConnectorSetting(
                name='perp_ethereum_optimism',
                type=ConnectorType.AMM_Perpetual,
                example_pair='ZRX-ETH',
                centralised=False,
                use_ethereum_wallet=False,
                trade_fee_schema=TradeFeeSchema(
                    percent_fee_token=None,
                    maker_percent_fee_decimal=Decimal('0.001'),
                    taker_percent_fee_decimal=Decimal('0.001'),
                    buy_percent_fee_deducted_from_returns=False,
                    maker_fixed_fees=[],
                    taker_fixed_fees=[]),
                config_keys=None,
                is_sub_domain=False,
                parent_name=None,
                domain_parameter=None,
                use_eth_gas_lookup=False)
        }

        url = binance_web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL)
        mock_response: Dict[str, Any] = {
            "timezone": "UTC",
            "serverTime": 1639598493658,
            "rateLimits": [],
            "exchangeFilters": [],
            "symbols": [
                {
                    "symbol": "ETHBTC",
                    "status": "TRADING",
                    "baseAsset": "ETH",
                    "baseAssetPrecision": 8,
                    "quoteAsset": "BTC",
                    "quotePrecision": 8,
                    "quoteAssetPrecision": 8,
                    "baseCommissionPrecision": 8,
                    "quoteCommissionPrecision": 8,
                    "orderTypes": [
                        "LIMIT",
                        "LIMIT_MAKER",
                        "MARKET",
                        "STOP_LOSS_LIMIT",
                        "TAKE_PROFIT_LIMIT"
                    ],
                    "icebergAllowed": True,
                    "ocoAllowed": True,
                    "quoteOrderQtyMarketAllowed": True,
                    "isSpotTradingAllowed": True,
                    "isMarginTradingAllowed": True,
                    "filters": [],
                    "permissionSets": [[
                        "SPOT",
                        "MARGIN"
                    ]]
                },
                {
                    "symbol": "LTCBTC",
                    "status": "TRADING",
                    "baseAsset": "LTC",
                    "baseAssetPrecision": 8,
                    "quoteAsset": "BTC",
                    "quotePrecision": 8,
                    "quoteAssetPrecision": 8,
                    "baseCommissionPrecision": 8,
                    "quoteCommissionPrecision": 8,
                    "orderTypes": [
                        "LIMIT",
                        "LIMIT_MAKER",
                        "MARKET",
                        "STOP_LOSS_LIMIT",
                        "TAKE_PROFIT_LIMIT"
                    ],
                    "icebergAllowed": True,
                    "ocoAllowed": True,
                    "quoteOrderQtyMarketAllowed": True,
                    "isSpotTradingAllowed": True,
                    "isMarginTradingAllowed": True,
                    "filters": [],
                    "permissionSets": [[
                        "SPOT",
                        "MARGIN"
                    ]]
                },
                {
                    "symbol": "BNBBTC",
                    "status": "TRADING",
                    "baseAsset": "BNB",
                    "baseAssetPrecision": 8,
                    "quoteAsset": "BTC",
                    "quotePrecision": 8,
                    "quoteAssetPrecision": 8,
                    "baseCommissionPrecision": 8,
                    "quoteCommissionPrecision": 8,
                    "orderTypes": [
                        "LIMIT",
                        "LIMIT_MAKER",
                        "MARKET",
                        "STOP_LOSS_LIMIT",
                        "TAKE_PROFIT_LIMIT"
                    ],
                    "icebergAllowed": True,
                    "ocoAllowed": True,
                    "quoteOrderQtyMarketAllowed": True,
                    "isSpotTradingAllowed": True,
                    "isMarginTradingAllowed": True,
                    "filters": [],
                    "permissionSets": [[
                        "MARGIN"
                    ]]
                },
            ]
        }

        mock_api.get(url, body=json.dumps(mock_response))
        perp_market_mock.return_value = {"pairs": ["ABCUSD"]}
        con_spec_mock.return_value = {
            "connector": "perp",
            "chain": "optimism",
            "network": "ethereum",
            "trading_type": "AMM_Perpetual",
            "chain_type": "EVM",
            "wallet_address": "0x..."
        }

        fetcher = TradingPairFetcher(client_config_map)
        asyncio.get_event_loop().run_until_complete(fetcher._fetch_task)
        trading_pairs = fetcher.trading_pairs

        self.assertEqual(2, len(trading_pairs.keys()))
        self.assertIn("binance", trading_pairs)
        binance_pairs = trading_pairs["binance"]
        self.assertEqual(2, len(binance_pairs))
        self.assertIn("ETH-BTC", binance_pairs)
        self.assertIn("LTC-BTC", binance_pairs)
        self.assertNotIn("BNB-BTC", binance_pairs)
        perp_pairs = trading_pairs["perp_ethereum_optimism"]
        self.assertEqual(1, len(perp_pairs))
        self.assertIn("ABC-USD", perp_pairs)
        self.assertNotIn("WETH-USDT", perp_pairs)
