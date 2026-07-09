import asyncio
import unittest

from hummingbot.connector.exchange.hyperliquid.hyperliquid_exchange import HyperliquidExchange
from hummingbot.connector.utils import combine_to_hb_trading_pair


class HyperliquidExchangeInvalidUniverseEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "USDC"
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)

    def setUp(self) -> None:
        super().setUp()
        self.exchange = HyperliquidExchange(
            hyperliquid_secret_key="13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930",  # noqa: mock
            hyperliquid_mode="arb_wallet",
            hyperliquid_address="test-address",
            use_vault=False,
            trading_pairs=[self.trading_pair],
        )

    def async_run_with_timeout(self, coroutine, timeout: int = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_update_trading_rules_ignores_invalid_universe_entries(self):
        mocked_response = [
            {
                "tokens": [
                    {
                        "name": self.quote_asset,
                        "szDecimals": 8,
                        "weiDecimals": 8,
                        "index": 0,
                        "tokenId": "0x6d1e7cde53ba9467b783cb7c530ce054",
                        "isCanonical": True,
                        "evmContract": None,
                        "fullName": None,
                    },
                    {
                        "name": self.base_asset,
                        "szDecimals": 0,
                        "weiDecimals": 5,
                        "index": 1,
                        "tokenId": "0xc1fb593aeffbeb02f85e0308e9956a90",
                        "isCanonical": True,
                        "evmContract": None,
                        "fullName": None,
                    },
                    {
                        "name": "PURR",
                        "szDecimals": 0,
                        "weiDecimals": 5,
                        "index": 2,
                        "tokenId": "0xc1fb593aeffbeb02f85e0308e9956a90",
                        "isCanonical": True,
                        "evmContract": None,
                        "fullName": None,
                    },
                ],
                "universe": [
                    {
                        "name": "COINALPHA/USDC",
                        "tokens": [1, 0],
                        "index": 0,
                        "isCanonical": True,
                    },
                    {
                        "name": "@1",
                        "tokens": [2, 0],
                        "index": 1,
                        "isCanonical": True,
                    },
                    {
                        "name": "BROKEN/USDC",
                        "tokens": [99, 0],
                        "index": 2,
                        "isCanonical": True,
                    },
                ],
            },
            [
                {
                    "prevDayPx": "0.22916",
                    "dayNtlVlm": "4265022.87833",
                    "markPx": "0.22923",
                    "midPx": "0.229235",
                    "circulatingSupply": "598274922.83822",
                    "coin": "COINALPHA/USDC",
                },
                {
                    "prevDayPx": "25.236",
                    "dayNtlVlm": "315299.16652",
                    "markPx": "25.011",
                    "midPx": "24.9835",
                    "circulatingSupply": "997372.88712882",
                    "coin": "@1",
                },
                {
                    "prevDayPx": "1.0",
                    "dayNtlVlm": "0.0",
                    "markPx": "1.0",
                    "midPx": "1.0",
                    "circulatingSupply": "1.0",
                    "coin": "BROKEN/USDC",
                },
            ],
        ]

        self.exchange._initialize_trading_pair_symbols_from_exchange_info(mocked_response)
        trading_rules = self.async_run_with_timeout(self.exchange._format_trading_rules(mocked_response))
        trading_pair_symbol_map = self.async_run_with_timeout(self.exchange.trading_pair_symbol_map())

        self.assertIn(self.trading_pair, trading_pair_symbol_map.inverse)
        self.assertTrue(any(rule.trading_pair == self.trading_pair for rule in trading_rules))
        self.assertTrue(all(rule.trading_pair != "BROKEN-USDC" for rule in trading_rules))
