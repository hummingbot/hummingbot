import asyncio
import json
import unittest
from decimal import Decimal
from typing import Awaitable

from aioresponses import aioresponses

from hummingbot.connector.exchange.hyperliquid import (
    hyperliquid_constants as CONSTANTS,
    hyperliquid_web_utils as web_utils,
)
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.hyperliquid_rate_source import HyperliquidRateSource


class HyperliquidRateSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.target_token = "COINALPHA"
        cls.global_token = "USDC"
        cls.hyperliquid_pair = f"{cls.target_token}-{cls.global_token}"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)
        cls.hyperliquid_ignored_pair = "SOMEPAIR"
        cls.ignored_trading_pair = combine_to_hb_trading_pair(base="SOME", quote="PAIR")

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def setup_hyperliquid_responses(self, mock_api, expected_rate: Decimal):
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
                    'midPx': '105',
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
                    'midPx': '105',
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
        # mock_api.get(pairs_us_url, body=json.dumps(symbols_response))
        mock_api.post(pairs_url, body=json.dumps(symbols_response))
        # mock_api.post(hyperliquid_prices_us_url, body=json.dumps(hyperliquid_prices_us_response))
        mock_api.post(hyperliquid_prices_global_url, body=json.dumps(hyperliquid_prices_global_response))

    @aioresponses()
    def test_get_hyperliquid_prices(self, mock_api):
        expected_rate = Decimal("10")
        self.setup_hyperliquid_responses(mock_api=mock_api, expected_rate=expected_rate)

        rate_source = HyperliquidRateSource()
        prices = self.async_run_with_timeout(rate_source.get_prices())

        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])
        # self.assertIn(self.us_trading_pair, prices)
        self.assertNotIn(self.ignored_trading_pair, prices)
