#!/usr/bin/env python

from os.path import join, realpath
import sys;
from unittest.mock import create_autospec

sys.path.insert(0, realpath(join(__file__, "../../")))

from hummingbot.strategy.discovery import DiscoveryStrategy, DiscoveryMarketPair
import logging; logging.basicConfig(level=logging.ERROR)
import pandas as pd
from typing import List
import unittest
from hummingsim.backtest.backtest_market import BacktestMarket
from hummingbot.market.radar_relay.radar_relay_api_order_book_data_source import RadarRelayAPIOrderBookDataSource
from hummingbot.market.bamboo_relay.bamboo_relay_api_order_book_data_source import BambooRelayAPIOrderBookDataSource
from hummingbot.market.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource
from hummingbot.market.ddex.ddex_api_order_book_data_source import DDEXAPIOrderBookDataSource
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class DiscoveryUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    maker_symbols: List[str] = ["COINALPHA-WETH", "COINALPHA", "WETH"]
    taker_symbols: List[str] = ["coinalpha/eth", "COINALPHA", "ETH"]

    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        self.mock_ddex_active_markets = {
            'baseAsset': {'WETH-DAI': 'WETH', 'WETH-TUSD': 'WETH', 'WETH-USDC': 'WETH', 'WETH-PAX': 'WETH'},
            'quoteAsset': {'WETH-DAI': 'DAI', 'WETH-TUSD': 'TUSD', 'WETH-USDC': 'USDC', 'WETH-PAX': 'PAX'},
            'volume': {'WETH-DAI': '206.22', 'WETH-TUSD': '3.73', 'WETH-USDC': '1.1226', 'WETH-PAX': '0.8'},
            'USDVolume': {'WETH-DAI': 57.58657081548, 'WETH-TUSD': 3.73, 'WETH-USDC': 1.1226, 'WETH-PAX': 0.8}}
        self.mock_binance_active_markets = {
            'baseAsset': {'ETHUSDT': 'ETH', 'ETHPAX': 'ETH', 'ETHUSDC': 'ETH', 'ETHTUSD': 'ETH'},
            'quoteAsset': {'ETHUSDT': 'USDT', 'ETHPAX': 'PAX', 'ETHUSDC': 'USDC', 'ETHTUSD': 'TUSD'},
            'volume': {'ETHUSDT': '37749967.77544020', 'ETHPAX': '2269572.85440670', 'ETHUSDC': '1019692.71318160', 'ETHTUSD': '779007.75098360'},
            'USDVolume': {'ETHUSDT': 37749967.7754402, 'ETHPAX': 2269572.8544067, 'ETHUSDC': 1019692.7131816, 'ETHTUSD': 779007.7509836}}

        async def mock_ddex_active_markets_func():
            return pd.DataFrame.from_dict(self.mock_ddex_active_markets)

        async def mock_binance_active_markets_func():
            return pd.DataFrame.from_dict(self.mock_binance_active_markets)

        self.target_symbols = [('WETH', 'TUSD'), ('WETH', 'DAI'), ('ETH', 'USDC'), ('ETH', 'TUSD')]
        self.equivalent_token = [['USDT', 'USDC', 'USDS', 'DAI', 'PAX', 'TUSD', 'USD'],
                                 ['ETH', 'WETH'],
                                 ['BTC', 'WBTC']]

        self.binance_market = create_autospec(BacktestMarket)
        self.ddex_market = create_autospec(BacktestMarket)

        self.market_pair = DiscoveryMarketPair(
            *([self.binance_market, mock_binance_active_markets_func] +
              [self.ddex_market, mock_ddex_active_markets_func])
        )

        self.strategy = DiscoveryStrategy(market_pairs=[self.market_pair],
                                          target_symbols=self.target_symbols,
                                          equivalent_token=self.equivalent_token
                                          )

    def test_market_info_spec(self):
        exchange_get_market_func_list = [
            RadarRelayAPIOrderBookDataSource.get_active_exchange_markets,
            BambooRelayAPIOrderBookDataSource.get_active_exchange_markets,
            BinanceAPIOrderBookDataSource.get_active_exchange_markets,
            DDEXAPIOrderBookDataSource.get_active_exchange_markets
        ]
        for get_active_exchange_markets_func in exchange_get_market_func_list:
            df = run(get_active_exchange_markets_func())
            self.assertTrue(hasattr(df, "baseAsset"))
            self.assertTrue(hasattr(df, "quoteAsset"))
            self.assertTrue(hasattr(df, "volume"))

    def test_filter_trading_pairs(self):
        expected_output_match_all = ["WETH-DAI", "WETH-PAX", "WETH-TUSD", "WETH-USDC"]
        self.assertTrue(expected_output_match_all == list(self.strategy.filter_trading_pairs(
            [["DAI"]],
            pd.DataFrame.from_dict(self.mock_ddex_active_markets),
            [["DAI", "PAX", "TUSD", "USDC"]]).index))
        self.assertTrue(expected_output_match_all == list(self.strategy.filter_trading_pairs(
            [["ETH"]],
            pd.DataFrame.from_dict(self.mock_ddex_active_markets),
            [["ETH", "WETH"]]).index))

        expected_output_match_single = ["WETH-DAI"]
        self.assertTrue(expected_output_match_single == list(self.strategy.filter_trading_pairs(
            [["WETH", "DAI"]],
            pd.DataFrame.from_dict(self.mock_ddex_active_markets),
            []).index))
        self.assertTrue(expected_output_match_single == list(self.strategy.filter_trading_pairs(
            [["ETH", "DAI"]],
            pd.DataFrame.from_dict(self.mock_ddex_active_markets),
            [["ETH", "WETH"]]).index))

        self.assertTrue([] == list(self.strategy.filter_trading_pairs(
            [["ETH"]],
            pd.DataFrame.from_dict(self.mock_ddex_active_markets),
            []).index))

    def test_matching_pairs(self):
        expected_pair = {(('ETHPAX', 'ETH', 'PAX'), ('WETH-TUSD', 'WETH', 'TUSD')),
                         (('ETHTUSD', 'ETH', 'TUSD'), ('WETH-DAI', 'WETH', 'DAI')),
                         (('ETHTUSD', 'ETH', 'TUSD'), ('WETH-PAX', 'WETH', 'PAX')),
                         (('ETHUSDT', 'ETH', 'USDT'), ('WETH-PAX', 'WETH', 'PAX')),
                         (('ETHTUSD', 'ETH', 'TUSD'), ('WETH-USDC', 'WETH', 'USDC')),
                         (('ETHUSDT', 'ETH', 'USDT'), ('WETH-USDC', 'WETH', 'USDC')),
                         (('ETHUSDT', 'ETH', 'USDT'), ('WETH-DAI', 'WETH', 'DAI')),
                         (('ETHUSDC', 'ETH', 'USDC'), ('WETH-TUSD', 'WETH', 'TUSD')),
                         (('ETHUSDC', 'ETH', 'USDC'), ('WETH-DAI', 'WETH', 'DAI')),
                         (('ETHTUSD', 'ETH', 'TUSD'), ('WETH-TUSD', 'WETH', 'TUSD')),
                         (('ETHPAX', 'ETH', 'PAX'), ('WETH-DAI', 'WETH', 'DAI')),
                         (('ETHPAX', 'ETH', 'PAX'), ('WETH-PAX', 'WETH', 'PAX')),
                         (('ETHPAX', 'ETH', 'PAX'), ('WETH-USDC', 'WETH', 'USDC')),
                         (('ETHUSDT', 'ETH', 'USDT'), ('WETH-TUSD', 'WETH', 'TUSD')),
                         (('ETHUSDC', 'ETH', 'USDC'), ('WETH-USDC', 'WETH', 'USDC')),
                         (('ETHUSDC', 'ETH', 'USDC'), ('WETH-PAX', 'WETH', 'PAX'))}

        run(self.strategy.fetch_market_info(self.market_pair))
        self.assertTrue(self.strategy.get_matching_pair(self.market_pair) == expected_pair)

def main():
    unittest.main()


if __name__ == "__main__":
    main()
