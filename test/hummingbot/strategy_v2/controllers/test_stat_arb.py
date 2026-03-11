from unittest import TestCase

from controllers.generic.stat_arb import StatArbConfig


class TestStatArbController(TestCase):
    def test_stat_arb_config_can_be_constructed(self):
        config = StatArbConfig.model_construct()

        self.assertEqual(config.controller_name, "stat_arb")
