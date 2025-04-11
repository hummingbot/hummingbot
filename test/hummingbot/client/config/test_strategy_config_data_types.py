from unittest import TestCase

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.client.config.config_helpers import ClientConfigAdapter


class BaseStrategyConfigMapTest(TestCase):
    def test_generate_yml_output_dict_title(self):
        class DummyStrategy(BaseClientModel):
            class Config:
                title = "pure_market_making"

            strategy: str = "pure_market_making"

        instance = ClientConfigAdapter(DummyStrategy())
        res_str = instance.generate_yml_output_str_with_comments()

        expected_str = """\
#####################################
###   pure_market_making config   ###
#####################################

strategy: pure_market_making
"""

        self.assertEqual(expected_str, res_str)
