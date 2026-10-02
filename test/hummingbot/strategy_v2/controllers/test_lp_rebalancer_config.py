from unittest import TestCase

from controllers.generic.lp_rebalancer.lp_rebalancer import LPRebalancerConfig
from hummingbot.cli.strategy_configs import controller_updatable_fields


class TestLPRebalancerConfig(TestCase):

    def test_position_refresh_interval_is_not_live_updatable(self):
        self.assertNotIn("position_refresh_interval", controller_updatable_fields(LPRebalancerConfig))
