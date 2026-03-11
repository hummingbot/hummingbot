from unittest import TestCase

from controllers.generic.pmm_v1 import PMMV1
from hummingbot.core.data_type.common import TradeType


class TestPMMV1(TestCase):
    def test_level_id_helpers_handle_none(self):
        controller = PMMV1.__new__(PMMV1)

        self.assertEqual(controller.get_trade_type_from_level_id(None), TradeType.SELL)
        self.assertEqual(controller.get_level_from_level_id(None), 0)
