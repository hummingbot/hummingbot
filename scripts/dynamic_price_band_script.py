from decimal import Decimal
from hummingbot.script.script_base import ScriptBase

s_decimal_1 = Decimal("1")


class DynamicPriceBandScript(ScriptBase):
    """
    Demonstrates how to set a band around a mid price moving average, the strategy is to stop buying when the mid price
    reaches the upper bound of the band and to stop selling when the mid price breaches the lower bound.
    """

    # Let's set the upper bound of the band to 5% away from the mid price moving average
    band_upper_bound_pct = Decimal("0.05")
    # Let's set the lower bound of the band to 3% away from the mid price moving average
    band_lower_bound_pct = Decimal("0.03")
    # Let's sample mid prices once every 10 seconds
    avg_interval = 10
    # Let's average the last 5 samples
    avg_length = 5

    def __init__(self):
        super().__init__()

    def on_tick(self):
        avg_mid_price = self.avg_mid_price(self.avg_interval, self.avg_length)
        # The avg can be None when the bot just started as there are not enough mid prices to sample values from.
        if avg_mid_price is None:
            return
        upper_bound = avg_mid_price * (s_decimal_1 + self.band_upper_bound_pct)
        lower_bound = avg_mid_price * (s_decimal_1 - self.band_lower_bound_pct)
        # When mid_price reaches the upper bound, we expect the price to bounce back as such we don't want be a buyer
        # (as we can probably buy back at a cheaper price later).
        # If you anticipate the opposite, i.e. the price breaks out on a run away move, you can protect your inventory
        # by stop selling (setting the sell_levels to 0).
        if self.mid_price >= upper_bound:
            self.pmm_parameters.buy_levels = 0
        else:
            self.pmm_parameters.buy_levels = self.pmm_parameters.order_levels
        # When mid_price reaches the lower bound, we don't want to be a seller.
        if self.mid_price <= lower_bound:
            self.pmm_parameters.sell_levels = 0
        else:
            self.pmm_parameters.sell_levels = self.pmm_parameters.order_levels
