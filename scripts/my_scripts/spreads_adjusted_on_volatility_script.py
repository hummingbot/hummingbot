
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
    interval = 1
    # short_period is how many interval to pick the samples for the average short term volatility calculation,
    # for short_period of 3, this is 3 samples (5 seconds interval), of the last 15 seconds
    short_period = 5

    last_spread_updated = 0
    last_order_levels_updated = 0

    ema_interval = 60
    ema_short_length = 20
    ema_long_length = 40

    MIN_VOLATILITY = Decimal(0.0001)
    MAX_DURATION = Decimal(200)
    MINIMUM_SPREAD = Decimal(0.0001)

    def __init__(self):
        super().__init__()
        self.original_bid_spread = None
        self.original_ask_spread = None
        self.original_order_levels = None
        self.original_order_level_spread = None
        self.avg_short_volatility = None
        self.max_volatility = None
        self.duration = None
        self.buy_sell_spread_ratio = None

    def volatility_msg(self, include_mid_price=False):
        if self.avg_short_volatility is None:
            return "volatility: N/A "

        max_volatility_msg = f"max_volatility: {self.max_volatility:.2%} " \
            f"duration: {self.duration}" if not include_mid_price else ""

        mid_price_msg = f"  mid_price: {self.mid_price:<15}" if include_mid_price else ""
        return f"short_volatility: {self.avg_short_volatility:.2%}  " \
               f"{mid_price_msg} \n" \
               f"{max_volatility_msg}"

    def on_tick(self):
        # First, let's keep the original spreads.
        if self.original_bid_spread is None:
            self.original_bid_spread = self.pmm_parameters.bid_spread
            self.original_ask_spread = self.pmm_parameters.ask_spread
            self.original_order_levels = self.pmm_parameters.order_levels
            self.original_order_level_spread = self.pmm_parameters.order_level_spread

        if self.max_volatility is None:
            self.max_volatility = self.MIN_VOLATILITY

        if self.duration is None:
            self.duration = Decimal(0)

        if self.buy_sell_spread_ratio is None:
            self.buy_sell_spread_ratio = Decimal(1.0)

        # Average volatility (price change) over a short period of time, this is to detect recent sudden changes.
        self.avg_short_volatility = self.avg_price_volatility(self.interval, self.short_period)

        # If the bot just got started, we'll not have these numbers yet as there is not enough mid_price sample size.
        if self.avg_short_volatility is None:
            return

        if self.avg_short_volatility >= 0.0001:
            log_to_file(SCRIPT_LOG_FILE, self.volatility_msg(True))

        self.calulate_volatility()
        self.adjust_spreads()
        self.adjust_orders_on_market_trend()

    def on_status(self) -> str:
        return self.volatility_msg()

    def make_new_spread(self, volatility: Decimal):
        a = Decimal(7)
        b = Decimal(3.9)
        c = Decimal(1.2)
        x = volatility
        new_spread = a ** (10000 * x / (b * c)) / 10000

        if new_spread >= 0.0647:
            return Decimal(0.0647)

        if new_spread < 0.0:
            return Decimal(0)

        return Decimal(new_spread)

    def change_duration(self, change: Decimal) -> Decimal:
        new_duration = Decimal(self.duration) + change

        if new_duration >= self.MAX_DURATION:
            return Decimal(self.MAX_DURATION)

        if new_duration < 0:
            return Decimal(0)

        return Decimal(new_duration)

    def make_new_spread_on_duration(self) -> Decimal:
        new_spread = Decimal(self.duration / self.MAX_DURATION) * self.make_new_spread(self.max_volatility)

        if new_spread <= self.MIN_VOLATILITY:
            return self.MIN_VOLATILITY

        return new_spread

    def calulate_volatility(self):
        if self.avg_short_volatility > self.max_volatility:
            if self.max_volatility <= self.MIN_VOLATILITY:
                self.duration = self.change_duration(self.MAX_DURATION)
            else:
                self.duration = self.change_duration(30)

            self.max_volatility = self.avg_short_volatility
        else:
            self.duration = self.change_duration(-1)

        if self.duration <= 0:
            self.max_volatility = self.MIN_VOLATILITY

    def adjust_spreads(self):
        if time.time() - self.last_spread_updated > 10 or self.duration == self.MAX_DURATION:
            self.notify(f"max_volatility: {self.max_volatility:.2%} duration: {self.duration}")

            new_spread = self.make_new_spread_on_duration()
            new_spread = self.round_by_step(new_spread, Decimal("0.0001"))

            new_bid_spread = max(self.original_bid_spread, new_spread)
            if new_bid_spread != self.pmm_parameters.bid_spread:
                self.pmm_parameters.bid_spread = max(new_bid_spread * self.buy_sell_spread_ratio ** -1, self.MINIMUM_SPREAD)
                self.notify(f"Upated bid spread with: {new_bid_spread:.2%} at volatility: {self.max_volatility:.2%}, duration: {self.duration}")

            new_ask_spread = max(self.original_ask_spread, new_spread)
            if new_ask_spread != self.pmm_parameters.ask_spread:
                self.pmm_parameters.ask_spread = max(new_ask_spread * self.buy_sell_spread_ratio, self.MINIMUM_SPREAD)
                self.notify(f"Upated ask spread with: {new_ask_spread:.2%} at volatility: {self.max_volatility:.2%}, duration: {self.duration}")

            new_order_level_spread = max(self.original_order_level_spread, new_spread)
            if new_order_level_spread != self.pmm_parameters.order_level_spread:
                self.pmm_parameters.order_level_spread = max(new_order_level_spread, self.MINIMUM_SPREAD)
                self.notify(f"Upated order level spread with: {new_order_level_spread:.2%} at volatility: {self.max_volatility:.2%}, duration: {self.duration}")
            self.last_spread_updated = time.time()

    def adjust_orders_on_market_trend(self):
        if time.time() - self.last_order_levels_updated > 60:
            short_avg_mid_price = self.avg_mid_price(self.ema_interval, self.ema_short_length)
            long_avg_mid_price = self.avg_mid_price(self.ema_interval, self.ema_long_length)
            # The avg can be None when the bot just started as there are not enough mid prices to sample values from.
            if short_avg_mid_price is None or long_avg_mid_price is None:
                return

            distance_percent = abs(short_avg_mid_price - long_avg_mid_price) / long_avg_mid_price * 100

            if distance_percent <= 0.05:
                self.notify("Trend is sideway, reset order level")
                self.pmm_parameters.sell_levels = self.original_order_levels
                self.pmm_parameters.buy_levels = self.original_order_levels
                self.buy_sell_spread_ratio = Decimal(1.0)
            elif short_avg_mid_price > long_avg_mid_price:
                self.notify("Trend is uptrend, more buy less sell")
                self.pmm_parameters.buy_levels = self.original_order_levels
                self.pmm_parameters.sell_levels = self.original_order_levels // 3
                self.buy_sell_spread_ratio = Decimal(3)
            else:
                self.notify("Trend is down trend, more sell less buy")
                self.pmm_parameters.buy_levels = self.original_order_levels // 3
                self.pmm_parameters.sell_levels = self.original_order_levels
                self.buy_sell_spread_ratio = Decimal(0.33333)

            self.last_order_levels_updated = time.time()
