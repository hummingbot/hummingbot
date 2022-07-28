#!/usr/bin/env python
import unittest
from decimal import Decimal
from hummingbot.strategy.pure_market_making.moving_price_band import MovingPriceBand


class MovingPriceBandUnitTest(unittest.TestCase):
    def setUp(self):
        self.current_timestamp = 1
        self.moving_price_band = MovingPriceBand(
            price_floor_pct=Decimal("-1"),
            price_ceiling_pct=Decimal("1"),
            price_band_refresh_time=86400,
        )
        self.price = 100

    def test_update(self):
        self.moving_price_band.update(self.current_timestamp, self.price)
        self.assertEqual(self.moving_price_band.price_floor, Decimal("99"))
        self.assertEqual(self.moving_price_band.price_ceiling, Decimal("101"))
        self.assertGreater(self.moving_price_band._set_time, 0)

    def test_check_and_update_price_band(self):
        self.moving_price_band.update(self.current_timestamp, self.price)
        self.moving_price_band.check_and_update_price_band(self.current_timestamp, Decimal("100"))
        self.assertEqual(self.moving_price_band.price_floor, Decimal("99"))
        self.assertEqual(self.moving_price_band.price_ceiling, Decimal("101"))
        self.moving_price_band.check_and_update_price_band(self.current_timestamp, Decimal("200"))
        self.assertEqual(self.moving_price_band.price_floor, Decimal("99"))
        self.assertEqual(self.moving_price_band.price_ceiling, Decimal("101"))
        self.current_timestamp = 86401
        self.moving_price_band.check_and_update_price_band(self.current_timestamp, Decimal("200"))
        self.assertEqual(self.moving_price_band.price_floor, Decimal("198"))
        self.assertEqual(self.moving_price_band.price_ceiling, Decimal("202"))

    def test_switch_moving_price_band(self):
        self.moving_price_band.switch(True)
        self.assertEqual(self.moving_price_band.enabled, True)
        self.moving_price_band.switch(False)
        self.assertEqual(self.moving_price_band.enabled, False)


if __name__ == "__main__":
    unittest.main()
