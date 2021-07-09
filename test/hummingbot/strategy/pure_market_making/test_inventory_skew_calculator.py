#!/usr/bin/env python
import unittest

from hummingbot.strategy.pure_market_making.data_types import InventorySkewBidAskRatios
from hummingbot.strategy.pure_market_making.inventory_skew_calculator import \
    calculate_bid_ask_ratios_from_base_asset_ratio


class InventorySkewCalculatorUnitTest(unittest.TestCase):
    def setUp(self):
        self.base_asset: float = 85000
        self.quote_asset: float = 10000
        self.price: float = 0.0036
        self.target_ratio: float = 0.03
        self.base_range: float = 20000.0

    def test_cap_on_max_base_range(self):
        self.base_asset = 100
        self.quote_asset = 10
        self.price = 1
        self.target_ratio = 0.35
        self.base_range = 200
        bid_ask_ratios: InventorySkewBidAskRatios = calculate_bid_ask_ratios_from_base_asset_ratio(
            self.base_asset, self.quote_asset, self.price, self.target_ratio, self.base_range
        )
        self.assertAlmostEqual(0, bid_ask_ratios.bid_ratio)
        self.assertAlmostEqual(2, bid_ask_ratios.ask_ratio)

        self.base_asset = 10
        self.quote_asset = 100
        self.price = 1
        self.target_ratio = 0.75
        self.base_range = 200
        bid_ask_ratios: InventorySkewBidAskRatios = calculate_bid_ask_ratios_from_base_asset_ratio(
            self.base_asset, self.quote_asset, self.price, self.target_ratio, self.base_range
        )
        self.assertAlmostEqual(2, bid_ask_ratios.bid_ratio)
        self.assertAlmostEqual(0, bid_ask_ratios.ask_ratio)

    def test_balanced_portfolio(self):
        bid_ask_ratios: InventorySkewBidAskRatios = calculate_bid_ask_ratios_from_base_asset_ratio(
            self.base_asset, self.quote_asset, self.price, self.target_ratio, self.base_range
        )
        self.assertAlmostEqual(1.04416666, bid_ask_ratios.bid_ratio)
        self.assertAlmostEqual(0.95583333, bid_ask_ratios.ask_ratio)

    def test_heavily_skewed_portfolio(self):
        self.base_asset = 8500.0
        bid_ask_ratios: InventorySkewBidAskRatios = calculate_bid_ask_ratios_from_base_asset_ratio(
            self.base_asset, self.quote_asset, self.price, self.target_ratio, self.base_range
        )
        self.assertAlmostEqual(2.0, bid_ask_ratios.bid_ratio)
        self.assertAlmostEqual(0.0, bid_ask_ratios.ask_ratio)

        self.base_asset = 200000.0
        bid_ask_ratios: InventorySkewBidAskRatios = calculate_bid_ask_ratios_from_base_asset_ratio(
            self.base_asset, self.quote_asset, self.price, self.target_ratio, self.base_range
        )
        self.assertAlmostEqual(0.0, bid_ask_ratios.bid_ratio)
        self.assertAlmostEqual(2.0, bid_ask_ratios.ask_ratio)

        self.base_asset = 1000000.0
        self.quote_asset = 0.0
        self.assertAlmostEqual(0.0, bid_ask_ratios.bid_ratio)
        self.assertAlmostEqual(2.0, bid_ask_ratios.ask_ratio)

    def test_moderately_skewed_portfolio(self):
        self.base_asset = 95000.0
        bid_ask_ratios: InventorySkewBidAskRatios = calculate_bid_ask_ratios_from_base_asset_ratio(
            self.base_asset, self.quote_asset, self.price, self.target_ratio, self.base_range
        )
        self.assertAlmostEqual(0.55916666, bid_ask_ratios.bid_ratio)
        self.assertAlmostEqual(1.440833333, bid_ask_ratios.ask_ratio)

        self.base_asset = 70000.0
        bid_ask_ratios: InventorySkewBidAskRatios = calculate_bid_ask_ratios_from_base_asset_ratio(
            self.base_asset, self.quote_asset, self.price, self.target_ratio, self.base_range
        )
        self.assertAlmostEqual(1.77166666, bid_ask_ratios.bid_ratio)
        self.assertAlmostEqual(0.22833333, bid_ask_ratios.ask_ratio)

    def test_empty_portfolio(self):
        self.base_asset = 0.0
        self.quote_asset = 0.0
        bid_ask_ratios: InventorySkewBidAskRatios = calculate_bid_ask_ratios_from_base_asset_ratio(
            self.base_asset, self.quote_asset, self.price, self.target_ratio, self.base_range
        )
        self.assertAlmostEqual(0.0, bid_ask_ratios.bid_ratio)
        self.assertAlmostEqual(0.0, bid_ask_ratios.ask_ratio)

        self.quote_asset = 10000.0
        bid_ask_ratios: InventorySkewBidAskRatios = calculate_bid_ask_ratios_from_base_asset_ratio(
            self.base_asset, self.quote_asset, self.price, self.target_ratio, self.base_range
        )
        self.assertAlmostEqual(2.0, bid_ask_ratios.bid_ratio)
        self.assertAlmostEqual(0.0, bid_ask_ratios.ask_ratio)

        self.base_asset = 85000.0
        self.base_range = 0.0
        bid_ask_ratios: InventorySkewBidAskRatios = calculate_bid_ask_ratios_from_base_asset_ratio(
            self.base_asset, self.quote_asset, self.price, self.target_ratio, self.base_range
        )
        self.assertAlmostEqual(0.0, bid_ask_ratios.bid_ratio)
        self.assertAlmostEqual(0.0, bid_ask_ratios.ask_ratio)


if __name__ == "__main__":
    unittest.main()
