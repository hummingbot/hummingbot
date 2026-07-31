import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase

from controllers.generic.stat_arb import StatArb, StatArbConfig


class TestStatArbController(TestCase):
    def test_stat_arb_config_can_be_constructed(self):
        config = StatArbConfig.model_construct()

        self.assertEqual(config.controller_name, "stat_arb")

    def test_format_status_handles_unpopulated_processed_data(self):
        controller = StatArb.__new__(StatArb)
        controller.config = SimpleNamespace(
            connector_pair_dominant="dominant",
            connector_pair_hedge="hedge",
            interval="1m",
            lookback_period=300,
            entry_threshold=Decimal("2.0"),
            pos_hedge_ratio=Decimal("1.0"),
        )
        controller.theoretical_dominant_quote = Decimal("50")
        controller.theoretical_hedge_quote = Decimal("50")
        controller.processed_data = {}

        status = controller.to_format_status()

        self.assertEqual(1, len(status))
        self.assertIn("Position Dominant            : 0.00", status[0])
        self.assertIn("Signal: 0.00", status[0])

    def test_update_processed_data_stays_idle_when_spread_is_unavailable(self):
        controller = StatArb.__new__(StatArb)
        controller.processed_data = {"signal": 1}
        controller.get_spread_and_z_score = lambda: None

        asyncio.run(controller.update_processed_data())

        self.assertEqual(0, controller.processed_data["signal"])
