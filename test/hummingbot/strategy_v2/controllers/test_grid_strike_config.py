import unittest

from controllers.generic.grid_strike import GridStrikeConfig


class GridStrikeConfigTest(unittest.TestCase):
    def test_grid_strike_fields_include_prompts_for_create_flow(self):
        expected_prompt_fields = [
            "leverage",
            "position_mode",
            "connector_name",
            "trading_pair",
            "side",
            "start_price",
            "end_price",
            "limit_price",
            "total_amount_quote",
            "min_spread_between_orders",
            "min_order_amount_quote",
            "max_open_orders",
            "max_orders_per_batch",
            "order_frequency",
            "activation_bounds",
            "keep_position",
        ]

        for field_name in expected_prompt_fields:
            schema_extra = GridStrikeConfig.model_fields[field_name].json_schema_extra or {}
            self.assertIn("prompt", schema_extra, f"'{field_name}' is missing prompt metadata")
            self.assertTrue(schema_extra.get("prompt_on_new"), f"'{field_name}' should prompt on new config creation")
