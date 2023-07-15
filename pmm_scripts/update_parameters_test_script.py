import decimal

from hummingbot.pmm_script.pmm_script_base import PMMScriptBase


class UpdateParametersTestPMMScript(PMMScriptBase):
    """
    This PMM script is intended for unit testing purpose only.
    """

    def __init__(self):
        super().__init__()
        self._has_updated: bool = False

    def on_tick(self) -> None:
        """
        Called periodically to update the pmm_parameters.
        """
        if len(self.mid_prices) >= 5 and not self._has_updated:
            pmm_parameters = {
                "buy_levels": 1,
                "sell_levels": 2,
                "order_levels": 3,
                "bid_spread": decimal.Decimal("0.1"),
                "ask_spread": decimal.Decimal("0.2"),
                "hanging_orders_cancel_pct": decimal.Decimal("0.3"),
                "hanging_orders_enabled": True,
                "filled_order_delay": 50.0,
                "order_refresh_tolerance_pct": decimal.Decimal("0.01"),
                "order_refresh_time": 10.0,
                "order_level_amount": decimal.Decimal("4"),
                "order_level_spread": decimal.Decimal("0.05"),
                "order_amount": decimal.Decimal("20"),
                "inventory_skew_enabled": True,
                "inventory_range_multiplier": decimal.Decimal("2"),
                "inventory_target_base_pct": decimal.Decimal("0.6"),
                "order_override": {
                    "order_1": ["buy", decimal.Decimal("0.5"), decimal.Decimal("100")],
                    "order_2": ["sell", decimal.Decimal("0.55"), decimal.Decimal("101")],
                },
            }
            self.pmm_parameters.update(pmm_parameters)
            self._has_updated = True
