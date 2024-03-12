import unittest
from decimal import Decimal

import hummingbot.connector.derivative.vega_perpetual.vega_perpetual_web_utils as utils


class VegaPerpetualWebUtilsUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    def setUp(self) -> None:
        super().setUp()

    def test_hb_time_from_vega(self):
        timestamp = "1629150000000000000"
        expected_res = 1629150000.0
        self.assertEqual(expected_res, utils.hb_time_from_vega(timestamp))

    def test_calculate_fees(self):
        quantum = Decimal(1000)
        fees = {}
        fees["infrastrucureFee"] = 1000
        fees["liquidityFee"] = 1000
        fees["makerFee"] = 1000

        fees["infrastructureFeeRefererDiscount"] = 0
        fees["infrastructureFeeVolumeDiscount"] = 0

        fees["liquidityFeeRefererDiscount"] = 0
        fees["liquidityFeeVolumeDiscount"] = 0

        fees["makerFeeRefererDiscount"] = 0
        fees["makerFeeVolumeDiscount"] = 0
        # no discounts
        self.assertEqual(Decimal(2.0), utils.calculate_fees(fees, quantum, True))

        # maker
        self.assertEqual(Decimal(-1.0), utils.calculate_fees(fees, quantum, False))

    def test_get_account_type(self):
        self.assertEqual("ACCOUNT_TYPE_INSURANCE", utils.get_account_type(1))
        self.assertEqual("ACCOUNT_TYPE_INSURANCE", utils.get_account_type("ACCOUNT_TYPE_INSURANCE"))
