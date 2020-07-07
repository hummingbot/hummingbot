from decimal import Decimal
from hummingbot.script.script_base import ScriptBase

s_decimal_1 = Decimal("1")


class SpreadsAdjustedOnVolatility(ScriptBase):
    """
    Demonstrates how to adjust bid and ask spreads based on price volatility.
    The volatility, in this example, is simply a price change compared to the previous cycle regardless of its
    direction, e.g. if price changes -3% (or 3%), the volatility is 3%.
    To update our pure market making spreads, we're gonna smooth out the volatility by averaging it over a short period
    (short_period), and we need a benchmark to compare its value against. In this example the benchmark is a median
    long period price volatility (you can also use a fixed number, e.g. 3% - if you expect this to be the norm for your
    market).
    For example, if our bid_spread and ask_spread are at 0.8%, and the median long term volatility is 1.5%.
    Recently the volatility jumps to 2.6% (on short term average), we're gonna adjust both our bid and ask spreads to
    1.9%  (the original spread - 0.8% plus the volatility delta - 1.1%). Then after a short while the volatility drops
    back to 1.5%, our spreads are now adjusted back to 0.8%.
    """

    # Let's set interval and sample sizes as below.
    # These numbers are for testing purposes only (in reality, they should be larger numbers)
    interval = 5
    short_period = 3
    long_period = 30

    def __init__(self):
        super().__init__()
        self.original_bid_spread = None
        self.original_ask_spread = None

    def on_tick(self):
        # First, let's keep the original spreads.
        if self.original_bid_spread is None:
            self.original_bid_spread = self.pmm_parameters.bid_spread
            self.original_ask_spread = self.pmm_parameters.ask_spread

        # Average volatility (price change) over a short period of time, this is to detect recent sudden changes.
        avg_short_volatility = self.avg_price_volatility(self.interval, self.short_period)
        # Median volatility over a long period of time, this is to find the market norm volatility.
        # We use median (instead of average) to find the middle volatility value - this is to avoid recent
        # spike affecting the average value.
        median_long_volatility = self.median_price_volatility(self.interval, self.long_period)

        # If the bot just got started, we'll not have these numbers yet as there is not enough mid_price sample size.
        # We'll start to have these numbers after interval * long_term_period (150 seconds in this example).
        if avg_short_volatility is None or median_long_volatility is None:
            return

        # This volatility delta will be used to adjust spreads.
        delta = avg_short_volatility - median_long_volatility
        # Let's round the delta into 0.25% increment to ignore noise and to avoid adjusting the spreads too often.
        spread_adjustment = self.round_by_step(delta, Decimal("0.0025"))
        # Show the user on what's going, you can remove this statement to stop the notification.
        self.notify(f"avg_short_volatility: {avg_short_volatility} median_long_volatility: {median_long_volatility} "
                    f"spread_adjustment: {spread_adjustment}")
        new_bid_spread = self.original_bid_spread + spread_adjustment
        # Let's not set the spreads below the originals, this is to avoid having spreads to be too close
        # to the mid price.
        self.pmm_parameters.bid_spread = max(self.original_bid_spread, new_bid_spread)
        new_ask_spread = self.original_ask_spread + spread_adjustment
        self.pmm_parameters.ask_spread = max(self.original_ask_spread, new_ask_spread)
