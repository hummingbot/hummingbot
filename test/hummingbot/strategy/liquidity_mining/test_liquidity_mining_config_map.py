from unittest import TestCase

import hummingbot.strategy.liquidity_mining.liquidity_mining_config_map as liquidity_mining_config_map_module
from hummingbot.strategy.liquidity_mining.liquidity_mining_config_map import (
    liquidity_mining_config_map as strategy_cmap
)
from test.hummingbot.strategy import assign_config_default


class LiquidityMiningConfigMapTests(TestCase):

    def test_markets_validation(self):
        # Correct markets
        self.assertEqual(liquidity_mining_config_map_module.market_validate("BTC-USDT"), None)
        self.assertEqual(liquidity_mining_config_map_module.market_validate("BTC-USDT,ETH-USDT"), None)
        self.assertEqual(liquidity_mining_config_map_module.market_validate("BTC-USDT, ETH-USDT"), None)
        self.assertEqual(liquidity_mining_config_map_module.market_validate("BTC-USDT , ETH-USDT"), None)
        self.assertEqual(liquidity_mining_config_map_module.market_validate("btc-usdt"), None)
        self.assertEqual(liquidity_mining_config_map_module.market_validate("BTC-usdt"), None)
        self.assertEqual(liquidity_mining_config_map_module.market_validate("btc-USDT"), None)

        # Incorrect markets
        self.assertEqual(liquidity_mining_config_map_module.market_validate(""), "Invalid market(s). The given entry is empty.")

        self.assertEqual(liquidity_mining_config_map_module.market_validate("BTC-USDT,"), "Invalid markets. The given entry contains an empty market.")
        self.assertEqual(liquidity_mining_config_map_module.market_validate("BTC-USDT,,"), "Invalid markets. The given entry contains an empty market.")
        self.assertEqual(liquidity_mining_config_map_module.market_validate("BTC-USDT,,ETH-USDT"), "Invalid markets. The given entry contains an empty market.")

        self.assertEqual(liquidity_mining_config_map_module.market_validate("BTC-USDT-ETH"), "Invalid market. BTC-USDT-ETH doesn't contain exactly 2 tickers.")
        self.assertEqual(liquidity_mining_config_map_module.market_validate("BTC-USDT,BTC-USDT-ETH"), "Invalid market. BTC-USDT-ETH doesn't contain exactly 2 tickers.")
        self.assertEqual(liquidity_mining_config_map_module.market_validate("btc-usdt-eth"), "Invalid market. BTC-USDT-ETH doesn't contain exactly 2 tickers.")

        self.assertEqual(liquidity_mining_config_map_module.market_validate("BTC- "), "Invalid market. Ticker  has an invalid length.")
        self.assertEqual(liquidity_mining_config_map_module.market_validate("BTC-USDT,BTC- "), "Invalid market. Ticker  has an invalid length.")

        self.assertEqual(liquidity_mining_config_map_module.market_validate("BTC-US#DT"), "Invalid market. Ticker US#DT contains invalid characters.")
        self.assertEqual(liquidity_mining_config_map_module.market_validate("BTC-USDT,BTC-ETH^"), "Invalid market. Ticker ETH^ contains invalid characters.")

        self.assertEqual(liquidity_mining_config_map_module.market_validate("BTC-USDT,BTC-ETH,BTC-USDT"), "Duplicate market BTC-USDT.")

    def test_token_validation(self):
        assign_config_default(strategy_cmap)

        # Correct tokens
        strategy_cmap.get("markets").value = "BTC-USDT"
        self.assertEqual(liquidity_mining_config_map_module.token_validate("BTC"), None)
        self.assertEqual(liquidity_mining_config_map_module.token_validate("btc"), None)

        strategy_cmap.get("markets").value = "BTC-USDT,ETH-USDT"
        self.assertEqual(liquidity_mining_config_map_module.token_validate("BTC"), None)
        self.assertEqual(liquidity_mining_config_map_module.token_validate("btc"), None)

        strategy_cmap.get("markets").value = "BTC-USDT, ETH-USDT"
        self.assertEqual(liquidity_mining_config_map_module.token_validate("BTC"), None)
        self.assertEqual(liquidity_mining_config_map_module.token_validate("btc"), None)

        strategy_cmap.get("markets").value = "BTC-USDT , ETH-USDT"
        self.assertEqual(liquidity_mining_config_map_module.token_validate("BTC"), None)
        self.assertEqual(liquidity_mining_config_map_module.token_validate("btc"), None)

        strategy_cmap.get("markets").value = "btc-usdt"
        self.assertEqual(liquidity_mining_config_map_module.token_validate("BTC"), None)
        self.assertEqual(liquidity_mining_config_map_module.token_validate("btc"), None)

        strategy_cmap.get("markets").value = "BTC-usdt"
        self.assertEqual(liquidity_mining_config_map_module.token_validate("BTC"), None)
        self.assertEqual(liquidity_mining_config_map_module.token_validate("btc"), None)

        strategy_cmap.get("markets").value = "btc-USDT"
        self.assertEqual(liquidity_mining_config_map_module.token_validate("BTC"), None)
        self.assertEqual(liquidity_mining_config_map_module.token_validate("btc"), None)

        # Incorrect tokens
        strategy_cmap.get("markets").value = "BTC-USDT"
        self.assertEqual(liquidity_mining_config_map_module.token_validate("ETH"), "Invalid token. ETH is not one of BTC,USDT")
        self.assertEqual(liquidity_mining_config_map_module.token_validate("eth"), "Invalid token. ETH is not one of BTC,USDT")

        strategy_cmap.get("markets").value = "btc-usdt"
        self.assertEqual(liquidity_mining_config_map_module.token_validate("ETH"), "Invalid token. ETH is not one of BTC,USDT")
        self.assertEqual(liquidity_mining_config_map_module.token_validate("eth"), "Invalid token. ETH is not one of BTC,USDT")
