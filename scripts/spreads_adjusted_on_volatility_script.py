from decimal import Decimal
from datetime import datetime
import time
from hummingbot.script.script_base import ScriptBase
from os.path import realpath, join

s_decimal_1 = Decimal("1")
LOGS_PATH = realpath(join(__file__, "../../logs/"))
SCRIPT_LOG_FILE = f"{LOGS_PATH}/logs_script.log"


def log_to_file(file_name, message):
    with open(file_name, "a+") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " - " + message + "\n")


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
    # interval is a interim which to pick historical mid price samples from, if you set it to 5, the first sample is
    # the last (current) mid price, the second sample is a past mid price 5 seconds before the last, and so on.
    interval = 5
    # short_period is how many interval to pick the samples for the average short term volatility calculation,
    # for short_period of 3, this is 3 samples (5 seconds interval), of the last 15 seconds
    short_period = 3
    # long_period is how many interval to pick the samples for the median long term volatility calculation,
    # for long_period of 10, this is 10 samples (5 seconds interval), of the last 50 seconds
    long_period = 10
    last_stats_logged = 0

    def __init__(self):
        super().__init__()
        self.original_bid_spread = None
        self.original_ask_spread = None
        self.avg_short_volatility = None
        self.median_long_volatility = None

    def volatility_msg(self, include_mid_price=False):
        if self.avg_short_volatility is None or self.median_long_volatility is None:
            return "short_volatility: N/A  long_volatility: N/A"
        mid_price_msg = f"  mid_price: {self.mid_price:<15}" if include_mid_price else ""
        return f"short_volatility: {self.avg_short_volatility:.2%}  " \
               f"long_volatility: {self.median_long_volatility:.2%}{mid_price_msg}"

    def on_tick(self):
        # First, let's keep the original spreads.
        if self.original_bid_spread is None:
            self.original_bid_spread = self.pmm_parameters.bid_spread
            self.original_ask_spread = self.pmm_parameters.ask_spread

        # Average volatility (price change) over a short period of time, this is to detect recent sudden changes.
        self.avg_short_volatility = self.avg_price_volatility(self.interval, self.short_period)
        # Median volatility over a long period of time, this is to find the market norm volatility.
        # We use median (instead of average) to find the middle volatility value - this is to avoid recent
        # spike affecting the average value.
        self.median_long_volatility = self.median_price_volatility(self.interval, self.long_period)

        # If the bot just got started, we'll not have these numbers yet as there is not enough mid_price sample size.
        # We'll start to have these numbers after interval * long_term_period.
        if self.avg_short_volatility is None or self.median_long_volatility is None:
            return

        # Let's log some stats once every 5 minutes
        if time.time() - self.last_stats_logged > 60 * 5:
            log_to_file(SCRIPT_LOG_FILE, self.volatility_msg(True))
            self.last_stats_logged = time.time()

        # This volatility delta will be used to adjust spreads.
        delta = self.avg_short_volatility - self.median_long_volatility
        # Let's round the delta into 0.25% increment to ignore noise and to avoid adjusting the spreads too often.
        spread_adjustment = self.round_by_step(delta, Decimal("0.0025"))
        # Show the user on what's going, you can remove this statement to stop the notification.
        # self.notify(f"avg_short_volatility: {avg_short_volatility} median_long_volatility: {median_long_volatility} "
        #             f"spread_adjustment: {spread_adjustment}")
        new_bid_spread = self.original_bid_spread + spread_adjustment
        # Let's not set the spreads below the originals, this is to avoid having spreads to be too close
        # to the mid price.
        new_bid_spread = max(self.original_bid_spread, new_bid_spread)
        old_bid_spread = self.pmm_parameters.bid_spread
        if new_bid_spread != self.pmm_parameters.bid_spread:
            self.pmm_parameters.bid_spread = new_bid_spread

        new_ask_spread = self.original_ask_spread + spread_adjustment
        new_ask_spread = max(self.original_ask_spread, new_ask_spread)
        if new_ask_spread != self.pmm_parameters.ask_spread:
            self.pmm_parameters.ask_spread = new_ask_spread
        if old_bid_spread != new_bid_spread:
            log_to_file(SCRIPT_LOG_FILE, self.volatility_msg(True))
            log_to_file(SCRIPT_LOG_FILE, f"spreads adjustment: Old Value: {old_bid_spread:.2%} "
                                         f"New Value: {new_bid_spread:.2%}")

    def on_status(self) -> str:
        return self.volatility_msg()
