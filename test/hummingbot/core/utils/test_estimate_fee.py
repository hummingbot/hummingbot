# -*- coding: utf-8 -*-

"""
unit tests for hummingbot.core.utils.estimate_fee
"""

import unittest
from decimal import Decimal
from hummingbot.core.event.events import TradeFee
from hummingbot.core.utils.estimate_fee import estimate_fee


class EstimateFeeTest(unittest.TestCase):

    def test_estimate_fee(self):
        """
        test the estimate_fee function
        """

        # test against centralized exchanges
        self.assertEqual(estimate_fee("kucoin", True), TradeFee(percent=Decimal('0.001'), flat_fees=[]))
        self.assertEqual(estimate_fee("kucoin", False), TradeFee(percent=Decimal('0.001'), flat_fees=[]))
        self.assertEqual(estimate_fee("binance", True), TradeFee(percent=Decimal('0.001'), flat_fees=[]))
        self.assertEqual(estimate_fee("binance", False), TradeFee(percent=Decimal('0.001'), flat_fees=[]))

        # test against decentralized exchanges
        self.assertEqual(estimate_fee("beaxy", True), TradeFee(percent=Decimal('0.0015'), flat_fees=[]))
        self.assertEqual(estimate_fee("beaxy", False), TradeFee(percent=Decimal('0.0025'), flat_fees=[]))

        # test against an exchange with flat fees
        self.assertEqual(estimate_fee("bamboo_relay", True), TradeFee(percent=Decimal(0), flat_fees=[('ETH', Decimal('0'))]))
        self.assertEqual(estimate_fee("bamboo_relay", False), TradeFee(percent=Decimal(0), flat_fees=[('ETH', Decimal('0.00001'))]))

        # test against exchanges that do not exist in hummingbot.client.settings.CONNECTOR_SETTINGS
        self.assertRaisesRegex(Exception, "^Invalid connector", estimate_fee, "does_not_exist", True)
        self.assertRaisesRegex(Exception, "Invalid connector", estimate_fee, "does_not_exist", False)
