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
            self._has_updated = True
