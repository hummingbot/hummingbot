import unittest
from decimal import Decimal

from hummingbot.strategy_v2.executors.position_executor.data_types import TripleBarrierConfig
from hummingbot.strategy_v2.utils.order_level_builder import OrderLevelBuilder


class TestOrderLevelBuilder(unittest.TestCase):

    def setUp(self):
        self.builder = OrderLevelBuilder(3)

    def test_resolve_input_single_value(self):
        result = self.builder.resolve_input(10.5)
        self.assertEqual(result, [10.5, 10.5, 10.5])

    def test_resolve_input_list(self):
        input_list = [10.5, 20.5, 30.5]
        result = self.builder.resolve_input(input_list)
        self.assertEqual(result, input_list)

    def test_resolve_input_dict(self):
        input_dict = {"method": "linear", "params": {"start": 0, "end": 3}}
        result = self.builder.resolve_input(input_dict)
        self.assertEqual(result, [Decimal(0), Decimal(1.5), Decimal(3)])

    def test_resolve_input_invalid_list(self):
        with self.assertRaises(ValueError):
            self.builder.resolve_input([10.5, 20.5])

    def test_resolve_input_invalid_dict(self):
        with self.assertRaises(ValueError):
            self.builder.resolve_input({"method": "unknown_method", "params": {}})

    def test_build_order_levels(self):
        amounts = [Decimal("100"), Decimal("200"), Decimal("300")]
        spreads = [Decimal("0.01"), Decimal("0.02"), Decimal("0.03")]
        triple_barrier_confs = TripleBarrierConfig()  # Assume a default instance is enough.
        result = self.builder.build_order_levels(amounts, spreads, triple_barrier_confs)

        self.assertEqual(len(result), 6)  # 3 levels * 2 sides
        self.assertEqual(result[0].order_amount_usd, Decimal("100"))
        self.assertEqual(result[0].spread_factor, Decimal("0.01"))
