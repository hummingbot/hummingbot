from decimal import Decimal
from unittest import TestCase

from pyinjective.utils.denom import Denom

from hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_utils import (
    derivative_price_to_backend,
    derivative_quantity_to_backend,
    floor_to,
)


class InjectiveUtilsTests(TestCase):

    def test_floor_to_utility_method(self):
        original_value = Decimal("123.0123456789")

        result = floor_to(value=original_value, target=Decimal("0.001"))
        self.assertEqual(Decimal("123.012"), result)

        result = floor_to(value=original_value, target=Decimal("1"))
        self.assertEqual(Decimal("123"), result)

    def test_derivative_quantity_to_backend_utility_method(self):
        denom = Denom(
            description="Fixed denom",
            base=2,
            quote=6,
            min_price_tick_size=1000,
            min_quantity_tick_size=100,
            min_notional=0,
        )

        backend_quantity = derivative_quantity_to_backend(quantity=Decimal("1"), denom=denom)

        self.assertEqual(100000000000000000000, backend_quantity)

    def test_derivative_price_to_backend_utility_method(self):
        denom = Denom(
            description="Fixed denom",
            base=2,
            quote=6,
            min_price_tick_size=1000,
            min_quantity_tick_size=100,
            min_notional=0,
        )

        backend_quantity = derivative_price_to_backend(price=Decimal("123.45"), denom=denom)

        self.assertEqual(123450000000000000000000000, backend_quantity)
