from decimal import Decimal
from unittest import TestCase

from controllers.market_making.dman_maker_v2 import DManMakerV2Config


class TestDManMakerV2Config(TestCase):
    def test_rejects_zero_sum_dca_amounts(self):
        with self.assertRaisesRegex(ValueError, "sum of dca amounts must be greater than 0"):
            DManMakerV2Config(
                id="test",
                controller_name="dman_maker_v2",
                connector_name="hyperliquid_perpetual",
                trading_pair="ETH-USDT",
                total_amount_quote=Decimal("100"),
                dca_spreads="0,0.01",
                dca_amounts="0,0",
            )

    def test_allows_zero_amount_levels_when_total_is_positive(self):
        config = DManMakerV2Config(
            id="test",
            controller_name="dman_maker_v2",
            connector_name="hyperliquid_perpetual",
            trading_pair="ETH-USDT",
            total_amount_quote=Decimal("100"),
            dca_spreads="0,0.01",
            dca_amounts="0,1",
        )

        self.assertEqual(config.dca_amounts, [0.0, 1.0])
