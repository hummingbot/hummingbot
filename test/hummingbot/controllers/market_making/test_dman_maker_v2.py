from decimal import Decimal
from unittest import TestCase

from pydantic import ValidationError

from controllers.market_making.dman_maker_v2 import DManMakerV2Config


class TestDManMakerV2Config(TestCase):
    def test_dca_amounts_reject_zero_values(self):
        with self.assertRaises(ValidationError):
            DManMakerV2Config(
                id="test",
                dca_spreads="0.01,0.02",
                dca_amounts="0,0",
            )

    def test_dca_amounts_reject_negative_values(self):
        with self.assertRaises(ValidationError):
            DManMakerV2Config(
                id="test",
                dca_spreads="0.01,0.02",
                dca_amounts="1,-1",
            )

    def test_dca_amounts_accept_positive_values(self):
        config = DManMakerV2Config(
            id="test",
            dca_spreads="0.01,0.02",
            dca_amounts="0.1,0.2",
        )

        self.assertEqual(config.dca_amounts, [Decimal("0.1"), Decimal("0.2")])
