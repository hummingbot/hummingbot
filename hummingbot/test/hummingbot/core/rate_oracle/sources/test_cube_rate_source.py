import asyncio
import json
import unittest
from typing import Awaitable

from aioresponses import aioresponses

from hummingbot.connector.exchange.cube import cube_constants as CONSTANTS, cube_web_utils as web_utils
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.cube_rate_source import CubeRateSource


class CubeRateSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_token = "SOL"
        cls.quote_token = "USDC"
        cls.cube_pair = f"{cls.base_token}{cls.quote_token}"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.base_token, quote=cls.quote_token)
        cls.base_test_token = "TSOL"
        cls.quote_test_token = "TUSDC"
        cls.cube_test_pair = f"{cls.base_test_token}{cls.quote_test_token}"
        cls.cube_test_trading_pair = combine_to_hb_trading_pair(base=cls.base_test_token, quote=cls.quote_test_token)
        cls.cube_ignored_pair = "SOMEPAIR"
        cls.ignored_trading_pair = combine_to_hb_trading_pair(base="SOME", quote="PAIR")

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 5):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def setup_cube_responses(self, mock_api, expected_rate: float):
        pairs_test_url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain="staging")
        pairs_url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain="live")
        symbols_response = {
            "result": {
                "assets": [
                    {
                        "assetId": 5,
                        "symbol": "SOL",
                        "decimals": 9,
                        "displayDecimals": 2,
                        "settles": "true",
                        "assetType": "Crypto",
                        "sourceId": 3,
                        "metadata": {
                            "dustAmount": 0
                        },
                        "status": 1
                    },
                    {
                        "assetId": 7,
                        "symbol": "USDC",
                        "decimals": 6,
                        "displayDecimals": 2,
                        "settles": "true",
                        "assetType": "Crypto",
                        "sourceId": 3,
                        "metadata": {
                            "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                        },
                        "status": 1
                    },
                    {
                        "assetId": 80005,
                        "symbol": "tSOL",
                        "decimals": 9,
                        "displayDecimals": 2,
                        "settles": "true",
                        "assetType": "Crypto",
                        "sourceId": 103,
                        "metadata": {
                            "dustAmount": 0
                        },
                        "status": 1
                    },
                    {
                        "assetId": 80007,
                        "symbol": "tUSDC",
                        "decimals": 6,
                        "displayDecimals": 2,
                        "settles": "true",
                        "assetType": "Crypto",
                        "sourceId": 103,
                        "metadata": {
                            "mint": "BD3N3usiKUecAMRcnQJMaoZXG7RzaxeN58Qqkd3oNKrb"
                        },
                        "status": 1
                    }
                ],
                "sources": [
                    {
                        "sourceId": 3,
                        "name": "solana",
                        "transactionExplorer": "https://explorer.solana.com/tx/{}",
                        "addressExplorer": "https://explorer.solana.com/address/{}",
                        "metadata": {
                            "chainId": "solana:mainnet",
                            "scope": "solana",
                            "type": "mainnet"
                        }
                    }
                ],
                "markets": [
                    {
                        "marketId": 200007,
                        "symbol": "tSOLtUSDC",
                        "baseAssetId": 80005,
                        "baseLotSize": "10000000",
                        "quoteAssetId": 80007,
                        "quoteLotSize": "100",
                        "priceDisplayDecimals": 2,
                        "protectionPriceLevels": 1000,
                        "priceBandBidPct": 25,
                        "priceBandAskPct": 400,
                        "minOrderQty": "null",
                        "maxOrderQty": "null",
                        "priceTickSize": "0.01",
                        "quantityTickSize": "0.01",
                        "status": 1,
                        "feeTableId": 2
                    },
                    {
                        "marketId": 200008,
                        "symbol": "tSOLtUSDC",
                        "baseAssetId": 80005,
                        "baseLotSize": "10000000",
                        "quoteAssetId": 80007,
                        "quoteLotSize": "100",
                        "priceDisplayDecimals": 2,
                        "protectionPriceLevels": 1000,
                        "priceBandBidPct": 25,
                        "priceBandAskPct": 400,
                        "minOrderQty": "null",
                        "maxOrderQty": "null",
                        "priceTickSize": "0.01",
                        "quantityTickSize": "0.01",
                        "status": 1,
                        "feeTableId": 2
                    },
                    {
                        "marketId": 100006,
                        "symbol": "SOLUSDC",
                        "baseAssetId": 5,
                        "baseLotSize": "10000000",
                        "quoteAssetId": 7,
                        "quoteLotSize": "100",
                        "priceDisplayDecimals": 2,
                        "protectionPriceLevels": 1000,
                        "priceBandBidPct": 25,
                        "priceBandAskPct": 400,
                        "priceTickSize": "0.01",
                        "quantityTickSize": "0.01",
                        "status": 1,
                        "feeTableId": 2
                    }
                ],
                "feeTables": [
                    {
                        "feeTableId": 1,
                        "feeTiers": [
                            {
                                "priority": 0,
                                "makerFeeRatio": 0.0,
                                "takerFeeRatio": 0.0
                            }
                        ]
                    },
                    {
                        "feeTableId": 2,
                        "feeTiers": [
                            {
                                "priority": 0,
                                "makerFeeRatio": 0.0004,
                                "takerFeeRatio": 0.0008
                            }
                        ]
                    }
                ]
            }
        }
        cube_prices_test_url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_BOOK_PATH_URL, domain="staging")
        cube_prices_test_response = {
            "result": [
                {
                    "ticker_id": "tSOLtUSDC",
                    "base_currency": "tSOL",
                    "quote_currency": "tUSDC",
                    "timestamp": 1710832381124,
                    "last_price": expected_rate,
                    "base_volume": 59482.84,
                    "quote_volume": 11797004.1497,
                    "bid": expected_rate,
                    "ask": expected_rate,
                    "high": expected_rate,
                    "low": expected_rate,
                    "open": expected_rate
                }
            ]
        }
        cube_prices_live_url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_BOOK_PATH_URL, domain="live")
        cube_prices_live_response = {
            "result": [
                {
                    "ticker_id": "SOLUSDC",
                    "base_currency": "SOL",
                    "quote_currency": "USDC",
                    "last_price": expected_rate,
                    "base_volume": 14981.11,
                    "quote_volume": 2892149.2852,
                    "bid": expected_rate,
                    "ask": expected_rate,
                    "high": expected_rate,
                    "low": expected_rate,
                    "open": expected_rate
                }
            ]
        }
        mock_api.get(pairs_test_url, body=json.dumps(symbols_response))
        mock_api.get(pairs_url, body=json.dumps(symbols_response))
        mock_api.get(cube_prices_test_url, body=json.dumps(cube_prices_test_response))
        mock_api.get(cube_prices_live_url, body=json.dumps(cube_prices_live_response))

    @aioresponses()
    def test_get_cube_prices(self, mock_api):
        expected_rate = 10
        self.setup_cube_responses(mock_api=mock_api, expected_rate=expected_rate)

        rate_source = CubeRateSource()
        prices = self.async_run_with_timeout(rate_source.get_prices())

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])
        self.assertIn(self.cube_test_trading_pair, prices)
        self.assertNotIn(self.ignored_trading_pair, prices)
