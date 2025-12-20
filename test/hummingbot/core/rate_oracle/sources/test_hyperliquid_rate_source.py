import json
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase

from aioresponses import aioresponses

from hummingbot.connector.exchange.hyperliquid import (
    hyperliquid_constants as CONSTANTS,
    hyperliquid_web_utils as web_utils,
)
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.hyperliquid_rate_source import HyperliquidRateSource


class HyperliquidRateSourceTest(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.target_token = "COINALPHA"
        cls.global_token = "USDC"
        cls.hyperliquid_pair = f"{cls.target_token}-{cls.global_token}"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)
        cls.hyperliquid_ignored_pair = "SOMEPAIR"
        cls.ignored_trading_pair = combine_to_hb_trading_pair(base="SOME", quote="PAIR")

    def setup_hyperliquid_responses(self, mock_api, mock_second_api, expected_rate: Decimal):
        pairs_url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL)

        symbols_response = [
            {
                "tokens": [
                    {
                        "name": "USDC",
                        "szDecimals": 8,
                        "weiDecimals": 8,
                        "index": 0,
                        "tokenId": "0x6d1e7cde53ba9467b783cb7c530ce054",
                        "isCanonical": True,
                        "evmContract": None,
                        "fullName": None
                    },
                    {
                        "name": "COINALPHA",
                        "szDecimals": 0,
                        "weiDecimals": 5,
                        "index": 1,
                        "tokenId": "0xc1fb593aeffbeb02f85e0308e9956a90",
                        "isCanonical": True,
                        "evmContract": None,
                        "fullName": None
                    },
                    {
                        "name": "SOME",
                        "szDecimals": 0,
                        "weiDecimals": 5,
                        "index": 2,
                        "tokenId": "0xc1fb593aeffbeb02f85e0308e9956a90",
                        "isCanonical": True,
                        "evmContract": None,
                        "fullName": None
                    }
                ],
                "universe": [
                    {
                        "name": "COINALPHA/USDC",
                        "tokens": [1, 0],
                        "index": 0,
                        "isCanonical": True
                    },
                    {
                        "name": self.ignored_trading_pair,
                        "tokens": [2, 0],
                        "index": 1,
                        "isCanonical": True
                    },
                ]
            },
            [
                {
                    'prevDayPx': "COINALPHA/USDC",
                    'dayNtlVlm': '4265022.87833',
                    'markPx': '10',
                    'midPx': '10',
                    'circulatingSupply': '598274922.83822',
                    'coin': "COINALPHA/USDC",
                },
                {
                    'prevDayPx': '25.236',
                    'dayNtlVlm': '315299.16652',
                    'markPx': '25.011',
                    'midPx': '24.9835',
                    'circulatingSupply': '997372.88712882',
                    'coin': self.ignored_trading_pair,
                }
            ]
        ]

        dex_markets = {
            'name': 'xyz', 'fullName': 'XYZ', 'deployer': '0x88806a71d74ad0a510b350545c9ae490912f0888', 'oracleUpdater': None, 'feeRecipient': '0x97f46f90c04efb91d0d740bd263e76683ca6f904',
            'assetToStreamingOiCap': [['xyz:AAPL', '25000000.0'], ['xyz:AMD', '25000000.0'], ['xyz:AMZN', '25000000.0'], ['xyz:COIN', '25000000.0'], ['xyz:COST', '25000000.0'], ['xyz:CRCL', '25000000.0'], ['xyz:EUR', '25000000.0'], ['xyz:GOLD', '25000000.0'], ['xyz:GOOGL', '50000000.0'], ['xyz:HOOD', '25000000.0'], ['xyz:INTC', '25000000.0'], ['xyz:JPY', '25000000.0'], ['xyz:LLY', '25000000.0'], ['xyz:META', '25000000.0'], ['xyz:MSFT', '25000000.0'], ['xyz:MSTR', '25000000.0'], ['xyz:MU', '25000000.0'], ['xyz:NFLX', '25000000.0'], ['xyz:NVDA', '50000000.0'], ['xyz:ORCL', '25000000.0'], ['xyz:PLTR', '25000000.0'], ['xyz:SKHX', '25000000.0'], ['xyz:SNDK', '25000000.0'], ['xyz:TSLA', '50000000.0'], ['xyz:TSM', '25000000.0'], ['xyz:XYZ100', '150000000.0']], 'subDeployers': [['setOracle', ['0x1234567890545d1df9ee64b35fdd16966e08acec']]], 'deployerFeeScale': '1.0', 'lastDeployerFeeScaleChangeTime': '1970-01-01T00:00:00', 'assetToFundingMultiplier': [['xyz:AAPL', '0.5'], ['xyz:AMD', '0.5'], ['xyz:AMZN', '0.5'], ['xyz:COIN', '0.5'], ['xyz:COST', '0.5'], ['xyz:CRCL', '0.5'], ['xyz:EUR', '0.5'], ['xyz:GOLD', '0.5'], ['xyz:GOOGL', '0.5'], ['xyz:HOOD', '0.5'], ['xyz:INTC', '0.5'], ['xyz:JPY', '0.5'], ['xyz:LLY', '0.5'], ['xyz:META', '0.5'], ['xyz:MSFT', '0.5'], ['xyz:MSTR', '0.5'], ['xyz:MU', '0.5'], ['xyz:NFLX', '0.5'], ['xyz:NVDA', '0.5'], ['xyz:ORCL', '0.5'], ['xyz:PLTR', '0.5'], ['xyz:SKHX', '0.5'], ['xyz:SNDK', '0.5'], ['xyz:TSLA', '0.5'], ['xyz:TSM', '0.5'], ['xyz:XYZ100', '0.5']]
        },
        {
            'name': 'flx', 'fullName': 'Felix Exchange', 'deployer': '0x2fab552502a6d45920d5741a2f3ebf4c35536352', 'oracleUpdater': '0x94757f8dcb4bf73b850195660e959d1105cfedd5', 'feeRecipient': '0xe2872b5ae7dcbba40cc4510d08c8bbea95b42d43',
            'assetToStreamingOiCap': [['flx:COIN', '8000000.0'], ['flx:CRCL', '5000000.0'], ['flx:GOLD', '10000000.0'], ['flx:SILVER', '5000000.0'], ['flx:TSLA', '8000000.0'], ['flx:XMR', '5000000.0']], 'subDeployers': [['registerAsset', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']],
                                                                                                                                                                                                                            ['setOracle', ['0x94757f8dcb4bf73b850195660e959d1105cfedd5', '0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['insertMarginTable', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['setFeeRecipient', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['haltTrading', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['setMarginTableIds', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['setOpenInterestCaps', ['0x17f5d164a9fa8ed292cdc91e34c0edeed6fc9b90', '0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['setFundingMultipliers', ['0xae083732032a813f9142733cdf380e1bc9e518af', '0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['setMarginModes', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['setFeeScale', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['setGrowthModes', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']]], 'deployerFeeScale': '1.0', 'lastDeployerFeeScaleChangeTime': '1970-01-01T00:00:00', 'assetToFundingMultiplier': [['flx:COIN', '0.0171109726'], ['flx:CRCL', '0.0095128887'], ['flx:GOLD', '0.6849327169'], ['flx:SILVER', '0.6849280069'], ['flx:TSLA', '0.0389529176']]},
        {
            'name': 'vntl', 'fullName': 'Ventuals', 'deployer': '0x8888888192a4a0593c13532ba48449fc24c3beda', 'oracleUpdater': None, 'feeRecipient': '0x5afe865300895b96d20132a8d9fa8e7829334b52',
            'assetToStreamingOiCap': [['vntl:ANTHROPIC', '3000000.0'], ['vntl:MAG7', '10000000.0'], ['vntl:OPENAI', '3000000.0'], ['vntl:SPACEX', '3000000.0']], 'subDeployers': [['registerAsset', ['0xdfc9f8b03664fb312c51ebf820eaefb6732f495a']], ['setOracle', ['0x0ac1e81a640f1492c286d71031af5af27a9b712e']], ['setMarginTableIds', ['0x6bdf4b47b638a8bb8ba630fbf867dc0f458d953e']], ['setOpenInterestCaps', ['0x6bdf4b47b638a8bb8ba630fbf867dc0f458d953e']], ['setFundingMultipliers', ['0x6bdf4b47b638a8bb8ba630fbf867dc0f458d953e', '0x9f82ce39734468c213f46834d0189222e1fadf5b']]], 'deployerFeeScale': '1.0', 'lastDeployerFeeScaleChangeTime': '1970-01-01T00:00:00', 'assetToFundingMultiplier': [['vntl:ANTHROPIC', '0.0032657399'], ['vntl:MAG7', '1.0'], ['vntl:OPENAI', '0.0030000042'], ['vntl:SPACEX', '0.0030000066']]},
        {
            'name': 'hyna', 'fullName': 'HyENA', 'deployer': '0x53e655101ea361537124ef814ad4e654b54d0637', 'oracleUpdater': '0xaab93501e78f5105e265a1eafda10ce6530de17e', 'feeRecipient': None,
            'assetToStreamingOiCap': [['hyna:BTC', '25000000.0'], ['hyna:ETH', '25000000.0'], ['hyna:HYPE', '10000000.0'], ['hyna:LIT', '1000.0'], ['hyna:SOL', '10000000.0'], ['hyna:ZEC', '10000000.0']], 'subDeployers': [['setOracle', ['0xaab93501e78f5105e265a1eafda10ce6530de17e']]], 'deployerFeeScale': '1.0', 'lastDeployerFeeScaleChangeTime': '2025-12-03T10:32:09.252520621', 'assetToFundingMultiplier': []
        }

        perp_dex = {
            'universe': [
                {'szDecimals': 4, 'name': 'xyz:XYZ100', 'maxLeverage': 20, 'marginTableId': 20, 'onlyIsolated': True, 'marginMode': 'strictIsolated', 'growthMode': 'enabled', 'lastGrowthModeChangeTime': '2025-11-23T17:37:10.033211662'},
                {'szDecimals': 3, 'name': 'xyz:TSLA', 'maxLeverage': 10, 'marginTableId': 10, 'onlyIsolated': True, 'marginMode': 'strictIsolated', 'growthMode': 'enabled', 'lastGrowthModeChangeTime': '2025-11-23T17:37:10.033211662'}],
            'assetCtxs': [
                {'funding': '0.00000625', 'openInterest': '2994.5222', 'prevDayPx': '25004.0', 'dayNtlVlm': '159393702.057199955', 'premium': '0.0000394493', 'oraclePx': '25349.0', 'markPx': '25349.0', 'midPx': '25350.0', 'impactPxs': ['25349.0', '25351.0'], 'dayBaseVlm': '6334.6544'},
                {'funding': '0.00000625', 'openInterest': '61339.114', 'prevDayPx': '483.99', 'dayNtlVlm': '14785221.9612099975', 'premium': '0.0002288211', 'oraclePx': '482.91', 'markPx': '483.02', 'midPx': '483.025', 'impactPxs': ['482.973', '483.068'], 'dayBaseVlm': '30504.829'}],
        }

        hyperliquid_prices_global_url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL)
        hyperliquid_prices_global_response = [
            {
                "tokens": [
                    {
                        "name": "USDC",
                        "szDecimals": 8,
                        "weiDecimals": 8,
                        "index": 0,
                        "tokenId": "0x6d1e7cde53ba9467b783cb7c530ce054",
                        "isCanonical": True,
                        "evmContract": None,
                        "fullName": None
                    },
                    {
                        "name": "COINALPHA",
                        "szDecimals": 0,
                        "weiDecimals": 5,
                        "index": 1,
                        "tokenId": "0xc1fb593aeffbeb02f85e0308e9956a90",
                        "isCanonical": True,
                        "evmContract": None,
                        "fullName": None
                    },
                    {
                        "name": "SOME",
                        "szDecimals": 0,
                        "weiDecimals": 5,
                        "index": 2,
                        "tokenId": "0xc1fb593aeffbeb02f85e0308e9956a90",
                        "isCanonical": True,
                        "evmContract": None,
                        "fullName": None
                    }
                ],
                "universe": [
                    {
                        "name": "COINALPHA/USDC",
                        "tokens": [1, 0],
                        "index": 0,
                        "isCanonical": True
                    },
                    {
                        "name": self.ignored_trading_pair,
                        "tokens": [2, 0],
                        "index": 1,
                        "isCanonical": True
                    },
                ]
            },
            [
                {
                    'prevDayPx': '0.22916',
                    'dayNtlVlm': '4265022.87833',
                    'markPx': '10',
                    'midPx': '10',
                    'circulatingSupply': '598274922.83822',
                    'coin': "COINALPHA/USDC"
                },
                {
                    'prevDayPx': '25.236',
                    'dayNtlVlm': '315299.16652',
                    'markPx': '25.011',
                    'midPx': '24.9835',
                    'circulatingSupply': '997372.88712882',
                    'coin': self.ignored_trading_pair
                }
            ]
        ]

        hyperliquid_perps_prices_global_response = {'name': 'xyz', 'fullName': 'XYZ', 'deployer': '0x88806a71d74ad0a510b350545c9ae490912f0888', 'oracleUpdater': None, 'feeRecipient': '0x97f46f90c04efb91d0d740bd263e76683ca6f904', 'assetToStreamingOiCap': [['xyz:AAPL', '25000000.0'], ['xyz:AMD', '25000000.0'], ['xyz:AMZN', '25000000.0'], ['xyz:COIN', '25000000.0'], ['xyz:COST', '25000000.0'], ['xyz:CRCL', '25000000.0'], ['xyz:EUR', '25000000.0'], ['xyz:GOLD', '25000000.0'], ['xyz:GOOGL', '50000000.0'], ['xyz:HOOD', '25000000.0'], ['xyz:INTC', '25000000.0'], ['xyz:JPY', '25000000.0'], ['xyz:LLY', '25000000.0'], ['xyz:META', '25000000.0'], ['xyz:MSFT', '25000000.0'], ['xyz:MSTR', '25000000.0'], ['xyz:MU', '25000000.0'], ['xyz:NFLX', '25000000.0'], ['xyz:NVDA', '50000000.0'], ['xyz:ORCL', '25000000.0'], ['xyz:PLTR', '25000000.0'], ['xyz:SKHX', '25000000.0'], ['xyz:SNDK', '25000000.0'], ['xyz:TSLA', '50000000.0'], ['xyz:TSM', '25000000.0'], ['xyz:XYZ100', '150000000.0']], 'subDeployers': [['setOracle', ['0x1234567890545d1df9ee64b35fdd16966e08acec']]], 'deployerFeeScale': '1.0', 'lastDeployerFeeScaleChangeTime': '1970-01-01T00:00:00', 'assetToFundingMultiplier': [['xyz:AAPL', '0.5'], ['xyz:AMD', '0.5'], ['xyz:AMZN', '0.5'], ['xyz:COIN', '0.5'], ['xyz:COST', '0.5'], ['xyz:CRCL', '0.5'], ['xyz:EUR', '0.5'], ['xyz:GOLD', '0.5'], ['xyz:GOOGL', '0.5'], ['xyz:HOOD', '0.5'], ['xyz:INTC', '0.5'], ['xyz:JPY', '0.5'], ['xyz:LLY', '0.5'], ['xyz:META', '0.5'], ['xyz:MSFT', '0.5'], ['xyz:MSTR', '0.5'], ['xyz:MU', '0.5'], ['xyz:NFLX', '0.5'], ['xyz:NVDA', '0.5'], ['xyz:ORCL', '0.5'], ['xyz:PLTR', '0.5'], ['xyz:SKHX', '0.5'], ['xyz:SNDK', '0.5'], ['xyz:TSLA', '0.5'], ['xyz:TSM', '0.5'], ['xyz:XYZ100', '0.5']]}, {'name': 'flx', 'fullName': 'Felix Exchange', 'deployer': '0x2fab552502a6d45920d5741a2f3ebf4c35536352', 'oracleUpdater': '0x94757f8dcb4bf73b850195660e959d1105cfedd5', 'feeRecipient': '0xe2872b5ae7dcbba40cc4510d08c8bbea95b42d43', 'assetToStreamingOiCap': [['flx:COIN', '8000000.0'], ['flx:CRCL', '5000000.0'], ['flx:GOLD', '10000000.0'], ['flx:SILVER', '5000000.0'], ['flx:TSLA', '8000000.0'], ['flx:XMR', '5000000.0']], 'subDeployers': [['registerAsset', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['setOracle', ['0x94757f8dcb4bf73b850195660e959d1105cfedd5', '0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['insertMarginTable', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['setFeeRecipient', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['haltTrading', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['setMarginTableIds', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['setOpenInterestCaps', ['0x17f5d164a9fa8ed292cdc91e34c0edeed6fc9b90', '0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['setFundingMultipliers', ['0xae083732032a813f9142733cdf380e1bc9e518af', '0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['setMarginModes', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['setFeeScale', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']], ['setGrowthModes', ['0xd0d4ef34424af3da883672b8cdeca751293655a5']]], 'deployerFeeScale': '1.0', 'lastDeployerFeeScaleChangeTime': '1970-01-01T00:00:00', 'assetToFundingMultiplier': [['flx:COIN', '0.0171109726'], ['flx:CRCL', '0.0095128887'], ['flx:GOLD', '0.6849327169'], ['flx:SILVER', '0.6849280069'], ['flx:TSLA', '0.0389529176']]}, {'name': 'vntl', 'fullName': 'Ventuals', 'deployer': '0x8888888192a4a0593c13532ba48449fc24c3beda', 'oracleUpdater': None, 'feeRecipient': '0x5afe865300895b96d20132a8d9fa8e7829334b52', 'assetToStreamingOiCap': [['vntl:ANTHROPIC', '3000000.0'], ['vntl:MAG7', '10000000.0'], ['vntl:OPENAI', '3000000.0'], ['vntl:SPACEX', '3000000.0']], 'subDeployers': [['registerAsset', ['0xdfc9f8b03664fb312c51ebf820eaefb6732f495a']], ['setOracle', ['0x0ac1e81a640f1492c286d71031af5af27a9b712e']], ['setMarginTableIds', ['0x6bdf4b47b638a8bb8ba630fbf867dc0f458d953e']], ['setOpenInterestCaps', ['0x6bdf4b47b638a8bb8ba630fbf867dc0f458d953e']], ['setFundingMultipliers', ['0x6bdf4b47b638a8bb8ba630fbf867dc0f458d953e', '0x9f82ce39734468c213f46834d0189222e1fadf5b']]], 'deployerFeeScale': '1.0', 'lastDeployerFeeScaleChangeTime': '1970-01-01T00:00:00', 'assetToFundingMultiplier': [['vntl:ANTHROPIC', '0.0032657399'], ['vntl:MAG7', '1.0'], ['vntl:OPENAI', '0.0030000042'], ['vntl:SPACEX', '0.0030000066']]}, {'name': 'hyna', 'fullName': 'HyENA', 'deployer': '0x53e655101ea361537124ef814ad4e654b54d0637', 'oracleUpdater': '0xaab93501e78f5105e265a1eafda10ce6530de17e', 'feeRecipient': None, 'assetToStreamingOiCap': [['hyna:BTC', '25000000.0'], ['hyna:ETH', '25000000.0'], ['hyna:HYPE', '10000000.0'], ['hyna:LIT', '1000.0'], ['hyna:SOL', '10000000.0'], ['hyna:ZEC', '10000000.0']], 'subDeployers': [['setOracle', ['0xaab93501e78f5105e265a1eafda10ce6530de17e']]], 'deployerFeeScale': '1.0', 'lastDeployerFeeScaleChangeTime': '2025-12-03T10:32:09.252520621', 'assetToFundingMultiplier': []}
        hyperliquid_perps_prices_global_response_perp_dex = {
            'universe': [
                {'szDecimals': 4, 'name': 'xyz:XYZ100', 'maxLeverage': 20, 'marginTableId': 20, 'onlyIsolated': True, 'marginMode': 'strictIsolated', 'growthMode': 'enabled', 'lastGrowthModeChangeTime': '2025-11-23T17:37:10.033211662'},
                {'szDecimals': 3, 'name': 'xyz:TSLA', 'maxLeverage': 10, 'marginTableId': 10, 'onlyIsolated': True, 'marginMode': 'strictIsolated', 'growthMode': 'enabled', 'lastGrowthModeChangeTime': '2025-11-23T17:37:10.033211662'}],
            'assetCtxs': [
                {'funding': '0.00000625', 'openInterest': '2994.5222', 'prevDayPx': '25004.0', 'dayNtlVlm': '159393702.057199955', 'premium': '0.0000394493', 'oraclePx': '25349.0', 'markPx': '25349.0', 'midPx': '25350.0', 'impactPxs': ['25349.0', '25351.0'], 'dayBaseVlm': '6334.6544'},
                {'funding': '0.00000625', 'openInterest': '61339.114', 'prevDayPx': '483.99', 'dayNtlVlm': '14785221.9612099975', 'premium': '0.0002288211', 'oraclePx': '482.91', 'markPx': '483.02', 'midPx': '483.025', 'impactPxs': ['482.973', '483.068'], 'dayBaseVlm': '30504.829'}],
        }

        # mock_api.get(pairs_us_url, body=json.dumps(symbols_response))
        mock_api.post(pairs_url, body=json.dumps(symbols_response))
        mock_second_api.post(pairs_url, body=json.dumps(dex_markets))
        mock_second_api.post(pairs_url, body=json.dumps(perp_dex))
        # mock_api.post(hyperliquid_prices_us_url, body=json.dumps(hyperliquid_prices_us_response))

        mock_api.post(hyperliquid_prices_global_url, body=json.dumps(hyperliquid_prices_global_response))
        mock_second_api.post(hyperliquid_prices_global_url, body=json.dumps(hyperliquid_perps_prices_global_response))
        mock_second_api.post(hyperliquid_prices_global_url, body=json.dumps(hyperliquid_perps_prices_global_response_perp_dex))

    @aioresponses()
    async def test_get_hyperliquid_prices(self, mock_api):
        expected_rate = Decimal("10")
        self.setup_hyperliquid_responses(mock_api=mock_api, mock_second_api=mock_api, expected_rate=expected_rate)

        rate_source = HyperliquidRateSource()
        prices = await rate_source.get_prices()

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])
        # self.assertIn(self.us_trading_pair, prices)
        self.assertNotIn(self.ignored_trading_pair, prices)
