from hummingbot.script.script_base import ScriptBase


class PriceBandScript(ScriptBase):
    """
    Demonstrates how to set a fixed band, the strategy is to stop buying when the mid price reaches the upper bound
    of the band and to stop selling when the mid price breaches the lower bound.
    """

    band_upper_bound = 105
    band_lower_bound = 95

    def __init__(self):
        super().__init__()

    def on_tick(self):
        # When mid_price reaches the upper bound, we expect the price to bounce back as such we don't want be a buyer
        # (as we can probably buy back at a cheaper price later).
        # If you anticipate the opposite, i.e. the price breaks out on a run away move, you can protect your inventory
        # by stop selling (setting the sell_levels to 0).
        if self.mid_price >= self.band_upper_bound:
            self.pmm_parameters.buy_levels = 0
        else:
            self.pmm_parameters.buy_levels = self.pmm_parameters.order_levels
        # When mid_price breaches the lower bound, we don't want to be a seller.
        if self.mid_price <= self.band_lower_bound:
            self.pmm_parameters.sell_levels = 0
        else:
            self.pmm_parameters.sell_levels = self.pmm_parameters.order_levels
