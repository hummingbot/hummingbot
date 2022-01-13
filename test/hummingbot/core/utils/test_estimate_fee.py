# -*- coding: utf-8 -*-

"""
unit tests for hummingbot.core.utils.estimate_fee
"""

import unittest
from decimal import Decimal
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.utils.estimate_fee import estimate_fee


class EstimateFeeTest(unittest.TestCase):

    def test_estimate_fee(self):
        """
        test the estimate_fee function
        """

        # test against centralized exchanges
        self.assertEqual(estimate_fee("kucoin", True), AddedToCostTradeFee(percent=Decimal('0.001'), flat_fees=[]))
        self.assertEqual(estimate_fee("kucoin", False), AddedToCostTradeFee(percent=Decimal('0.001'), flat_fees=[]))
        self.assertEqual(estimate_fee("binance", True), AddedToCostTradeFee(percent=Decimal('0.001'), flat_fees=[]))
        self.assertEqual(estimate_fee("binance", False), AddedToCostTradeFee(percent=Decimal('0.001'), flat_fees=[]))

        # test against decentralized exchanges
        self.assertEqual(estimate_fee("beaxy", True), AddedToCostTradeFee(percent=Decimal('0.0015'), flat_fees=[]))
        self.assertEqual(estimate_fee("beaxy", False), AddedToCostTradeFee(percent=Decimal('0.0025'), flat_fees=[]))

        # test against exchanges that do not exist in hummingbot.client.settings.CONNECTOR_SETTINGS
        self.assertRaisesRegex(Exception, "^Invalid connector", estimate_fee, "does_not_exist", True)
        self.assertRaisesRegex(Exception, "Invalid connector", estimate_fee, "does_not_exist", False)
