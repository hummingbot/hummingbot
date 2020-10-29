from decimal import Decimal
from hummingbot.script.script_base import ScriptBase


class UpdateParametersTestScript(ScriptBase):
    """
    This script is intended for unit testing purpose only.
    """

    def __init__(self):
        super().__init__()
        self._has_updated = False

    def on_tick(self):
        if len(self.mid_prices) >= 5 and not self._has_updated:
            self.pmm_parameters.buy_levels = 1
            self.pmm_parameters.sell_levels = 2
            self.pmm_parameters.order_levels = 3
            self.pmm_parameters.bid_spread = Decimal("0.1")
            self.pmm_parameters.ask_spread = Decimal("0.2")
            self.pmm_parameters.hanging_orders_cancel_pct = Decimal("0.3")
            self.pmm_parameters.hanging_orders_enabled = True
            self.pmm_parameters.filled_order_delay = 50.0
            self.pmm_parameters.order_refresh_tolerance_pct = Decimal("0.01")
            self.pmm_parameters.order_refresh_time = 10.0
            self.pmm_parameters.order_level_amount = Decimal("4")
            self.pmm_parameters.order_level_spread = Decimal("0.05")
            self.pmm_parameters.order_amount = Decimal("20")
            self.pmm_parameters.inventory_skew_enabled = True
            self.pmm_parameters.inventory_range_multiplier = Decimal("2")
            self.pmm_parameters.inventory_target_base_pct = Decimal("0.6")
            self.pmm_parameters.order_override = {"order_1": ["buy", Decimal("0.5"), Decimal("100")],
                                                  "order_2": ["sell", Decimal("0.55"), Decimal("101")], }
            self._has_updated = True
