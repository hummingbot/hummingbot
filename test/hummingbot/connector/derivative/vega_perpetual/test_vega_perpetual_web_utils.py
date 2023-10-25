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
        self.assertEqual(Decimal(3.0), utils.calculate_fees(fees, quantum))

        # all discounts
        fees["infrastructureFeeRefererDiscount"] = 500
        fees["infrastructureFeeVolumeDiscount"] = 500
        fees["liquidityFeeRefererDiscount"] = 500
        fees["liquidityFeeVolumeDiscount"] = 500

        fees["makerFeeRefererDiscount"] = 500
        fees["makerFeeVolumeDiscount"] = 500
        self.assertEqual(Decimal(0), utils.calculate_fees(fees, quantum))

        # TOO MUCH all discounts
        fees["infrastructureFeeRefererDiscount"] = 1000
        fees["infrastructureFeeVolumeDiscount"] = 10000
        fees["liquidityFeeRefererDiscount"] = 10000
        fees["liquidityFeeVolumeDiscount"] = 10000

        fees["makerFeeRefererDiscount"] = 10000
        fees["makerFeeVolumeDiscount"] = 10000
        self.assertEqual(Decimal(0), utils.calculate_fees(fees, quantum))

    def test_get_account_type(self):
        self.assertEqual("ACCOUNT_TYPE_INSURANCE", utils.get_account_type(1))
        self.assertEqual("ACCOUNT_TYPE_INSURANCE", utils.get_account_type("ACCOUNT_TYPE_INSURANCE"))
