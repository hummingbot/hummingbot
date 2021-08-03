from decimal import Decimal
from datetime import datetime
import time
from hummingbot.script.script_base import ScriptBase
from os.path import realpath, join
import statistics
import random
from typing import Optional

s_decimal_1 = Decimal("1")
LOGS_PATH = realpath(join(__file__, "../../logs/"))
SCRIPT_LOG_FILE = f"{LOGS_PATH}/logs_script.log"


def log_to_file(file_name, message):
    with open(file_name, "a+") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " - " + message + "\n")

class RewardSniping(ScriptBase):
    # Configure Parameters
    ## Moving Average
    MA_INTERVAL = 60
    SHORT_MA_LENGTH = 5
    LONG_MA_LENGTH = 20
    ## Inverted Bolinger Band
    STD_MULT = 2
    UPPER_ORDER_AMOUNT_BOUND_PCT = 0.01
    LOWER_ORDER_AMOUNT_BOUND_PCT = 0.01
    ## Envelop Band
    ENV_MULT = 2
    UPPER_ENV_PCT = 0.005
    LOWER_ENV_PCT = 0.005
    ## Max and Min spreads
    MINIMUM_LOW_SPREAD = Decimal(0.00001)
    MAXIMUM_LOW_SPREAD = Decimal(0.001)
    MIDPOINT_LOW_SPREAD = Decimal(0.0005)

    MINIMUM_HIGH_SPREAD = Decimal(0.005)
    MAXIMUM_HIGH_SPREAD = Decimal(0.01)
    MIDPOINT_HIGH_SPREAD = Decimal(0.0075)

    MINIMUM_ORDER_LEVELS_SPREAD = Decimal(0.00001)
    MAXIMUM_ORDER_LEVELS_SPREAD = Decimal(0.0015)
    MIDPOINT_ORDER_LEVELS_SPREAD = Decimal(0.0005)
    ## Update frequency:
    UPDATE_FREQ = 5
    UPDATE_INV_RATIO_DELAY = 30
    CALIBRATING_INV_FREQ = 1200
    ## Misc.
    MINIMUM_ORDER_SIZE = 5.1
    MAXIMUM_PRICE_PCT = 1

    def __init__(self):
        super().__init__()
        # Save current settings
        self.original_bid_spread = None
        self.original_ask_spread = None
        self.original_order_levels = None
        self.original_order_level_spread = None
        self.original_order_amount = None
        self.original_order_refresh_time = None
        self.original_filled_order_delay = None
        
        # Save init market parameters
        self.init_base_price = None
        self.init_base_amount = None
        self.init_quote_value = None
        self.init_total_inv_value = None
        self.base_asset = None
        self.quote_asset = None

        # Tracking key metrics
        self.starting_base_price = None
        self.starting_base_amount = None
        self.starting_quote_value = None
        self.starting_total_inv_value = None

        # Runtime parameters
        self.probability_upper_pct = None
        self.probability_lower_pct = None
        self.probability_upper_price = None
        self.probability_lower_price = None
        self.new_order_amount = None
        self.new_bid_spread = None
        self.new_ask_spread = None
        self.new_order_levels_spread = None
        self.inner_env_upper_bound = None
        self.inner_env_lower_bound = None
        self.outer_env_upper_bound = None
        self.outer_env_lower_bound = None
        self.std_basis = None
        self.env_basis = None
        self.new_order_levels = None
        self.new_buy_levels = None
        self.new_sell_levels = None
        self.new_filled_order_delay = None
        self.new_order_refresh_time = None

        # Update frequency flag:
        self.last_parameters_updated = 0
        self.last_inv_calibrating_started = 0
        self.update_inv_ratio_delay = -1
        self.is_calibrating_inventory = True

    def on_tick(self):
        # First, let's keep the original parameters:
        if self.original_bid_spread is None:
            self.original_bid_spread = self.pmm_parameters.bid_spread
            self.original_ask_spread = self.pmm_parameters.ask_spread
            self.original_order_level_spread = self.pmm_parameters.order_level_spread
            self.original_order_amount = self.pmm_parameters.order_amount
            self.original_order_refresh_time = self.pmm_parameters.order_refresh_time
            self.original_filled_order_delay = self.pmm_parameters.filled_order_delay

        # Second, let's get the base and quote asset identifier
        if self.base_asset is None or self.quote_asset is None:
            self.base_asset, self.quote_asset = self.pmm_market_info.trading_pair.split("-")

        # Third, let's keep the starting market parameters:
        if self.init_base_price is None:
            self.init_base_price = self.mid_price
            self.init_base_amount = Decimal(self.all_available_balances[f"{self.pmm_market_info.exchange}"].get(self.base_asset, Decimal("0.0000")))
            self.init_quote_value = Decimal(self.all_available_balances[f"{self.pmm_market_info.exchange}"].get(self.quote_asset, Decimal("0.0000")))
            self.init_total_inv_value = self.init_base_amount * self.init_base_price + self.init_quote_value

        # Fourth, saving starting metric for further analysis:
        if self.starting_base_price is None:
            self.starting_base_price = self.init_base_price
            self.starting_base_amount = self.init_base_amount
            self.starting_quote_value = self.init_quote_value
            self.starting_total_inv_value = self.init_total_inv_value

        # Depending on market conditions, we will modify strategy parameters to optimize trades
        if time.time() - self.last_parameters_updated > self.UPDATE_FREQ and self.is_calibrating_inventory is False:
            self.calculateNewOrderAmount()
            self.calculateNewSpread()
            self.calculateEnvelop()
            self.applyTrendBias()

            if self.new_order_amount is None:
                self.notify("Collecting midprices for moving average ...")
                self.pmm_parameters.order_levels = 0
                self.last_parameters_updated = time.time()
                return

            self.pmm_parameters.order_amount = self.new_order_amount
            self.pmm_parameters.bid_spread = self.new_bid_spread
            self.pmm_parameters.ask_spread = self.new_ask_spread
            self.pmm_parameters.order_levels = self.new_order_levels
            self.pmm_parameters.buy_levels = self.new_buy_levels
            self.pmm_parameters.sell_levels = self.new_sell_levels
            self.pmm_parameters.order_level_spread = self.new_order_levels_spread
            self.pmm_parameters.order_refresh_time = self.new_order_refresh_time
            self.pmm_parameters.filled_order_delay = self.new_filled_order_delay

            self.last_parameters_updated = time.time()

        # After for a while, we will calibrate inventory ratio to optimize trades
        ## First, stopping all order
        if time.time() - self.last_inv_calibrating_started > self.CALIBRATING_INV_FREQ:
            self.notify("Starting Inventory Calibration...")
            self.pmm_parameters.order_levels = 0
            self.update_inv_ratio_delay = self.UPDATE_INV_RATIO_DELAY
            self.is_calibrating_inventory = True
            self.last_inv_calibrating_started = time.time()
        ## Second, apply calculation to optimize inventory ratio
        if self.is_calibrating_inventory is True:
            if self.update_inv_ratio_delay < 0:
                self.notify("update_inv_ratio_delay is less than 0, resuming trading ...")
                self.is_calibrating_inventory = False
                self.last_inv_calibrating_started = time.time()
                return

            if self.update_inv_ratio_delay == 0:
                self.notify("Finished stopping orders, applying inventory control...")
                self.applyInventoryControl()
                self.is_calibrating_inventory = False
                self.notify(f"New target base pct: {self.pmm_parameters.inventory_target_base_pct}")
                self.notify("Done, resuming trading...")
            else:
                self.notify(f"Stopping orders, {self.update_inv_ratio_delay}s left...")
                self.update_inv_ratio_delay = self.update_inv_ratio_delay - 1

        # TODO: Write data collection script

    def on_status(self) -> str:
        return self.status_msg()

    def calculateNewOrderAmount(self):
        basis = self.avg_mid_price(self.MA_INTERVAL, self.SHORT_MA_LENGTH)
        dev = self.stdev_price(self.MA_INTERVAL, self.LONG_MA_LENGTH)

        if basis is None or dev is None:
            return

        dev = dev * self.STD_MULT

        upper = basis + Decimal(abs((basis + dev) - (basis * Decimal(1 + self.UPPER_ORDER_AMOUNT_BOUND_PCT))))
        lower = basis - Decimal(abs((basis - dev) - (basis * Decimal(1 - self.LOWER_ORDER_AMOUNT_BOUND_PCT))))
        upper_pct = abs(1 - upper / basis)
        lower_pct = abs(1 - lower / basis)
        price_pct = (upper_pct * 100 + lower_pct * 100) / 2

        if price_pct >= Decimal(self.MAXIMUM_PRICE_PCT):
            price_pct = Decimal(self.MAXIMUM_PRICE_PCT)

        new_order_amount = self.round_by_step(Decimal(self.original_order_amount) * price_pct, self.MINIMUM_LOW_SPREAD)
        minimum_order = Decimal(self.MINIMUM_ORDER_SIZE) / self.mid_price 

        self.new_order_amount = max(new_order_amount, minimum_order)
        self.probability_upper_pct = upper_pct
        self.probability_lower_pct = lower_pct
        self.probability_upper_price = upper
        self.probability_lower_price = lower
        self.std_basis = basis

    def calculateNewSpread(self):
        if self.probability_upper_pct is None or self.probability_lower_pct is None:
            return

        max_order_levels_spread = self.MAXIMUM_ORDER_LEVELS_SPREAD * max(self.probability_upper_pct, self.probability_lower_pct) * 100
        new_order_levels_spread = random.triangular(float(self.MINIMUM_ORDER_LEVELS_SPREAD), float(max_order_levels_spread), float(self.MIDPOINT_ORDER_LEVELS_SPREAD))

        # New random calculaiton:
        # Get High random spread:
        max_high_ask_spread = self.MAXIMUM_HIGH_SPREAD * self.probability_upper_pct * 100
        max_high_bid_spread = self.MAXIMUM_HIGH_SPREAD * self.probability_lower_pct * 100
        min_high_spread = self.MINIMUM_HIGH_SPREAD
        new_high_ask_spread = random.triangular(float(min_high_spread), float(max_high_ask_spread), float(self.MIDPOINT_HIGH_SPREAD))
        new_high_bid_spread = random.triangular(float(min_high_spread), float(max_high_bid_spread), float(self.MIDPOINT_HIGH_SPREAD))

        # Get low random spread:
        max_low_ask_spread = self.MAXIMUM_LOW_SPREAD * self.probability_upper_pct * 100
        max_low_bid_spread = self.MAXIMUM_LOW_SPREAD * self.probability_lower_pct * 100
        min_low_spread = self.MINIMUM_LOW_SPREAD
        new_low_ask_spread = random.triangular(float(min_low_spread), float(max_low_ask_spread), float(self.MIDPOINT_LOW_SPREAD))
        new_low_bid_spread = random.triangular(float(min_low_spread), float(max_low_bid_spread), float(self.MIDPOINT_LOW_SPREAD))

        new_ask_spread = new_low_ask_spread
        new_bid_spread = new_low_bid_spread
        
        is_high_spread = random.choice([0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1])
        
        if is_high_spread == 1:
            new_ask_spread = new_high_ask_spread
            new_bid_spread = new_high_bid_spread
            self.new_order_amount = self.new_order_amount * 2

        self.new_ask_spread = self.round_by_step(Decimal(new_ask_spread), self.MINIMUM_LOW_SPREAD)
        self.new_bid_spread = self.round_by_step(Decimal(new_bid_spread), self.MINIMUM_LOW_SPREAD)
        self.new_order_levels_spread = self.round_by_step(Decimal(new_order_levels_spread), self.MINIMUM_LOW_SPREAD)

    def calculateEnvelop(self):
        basis = self.avg_mid_price(self.MA_INTERVAL, self.LONG_MA_LENGTH)

        if basis is None:
            return

        inner_env_upper = basis * Decimal(1 + self.UPPER_ENV_PCT) 
        inner_env_lower = basis * Decimal(1 - self.LOWER_ENV_PCT)
        outer_env_upper = basis * Decimal(1 + self.UPPER_ENV_PCT * self.ENV_MULT) 
        outer_env_lower = basis * Decimal(1 - self.LOWER_ENV_PCT * self.ENV_MULT)

        self.inner_env_upper_bound = inner_env_upper
        self.inner_env_lower_bound = inner_env_lower
        self.outer_env_upper_bound = outer_env_upper
        self.outer_env_lower_bound = outer_env_lower
        self.env_basis = basis
    
    def applyTrendBias(self):
        order_levels = 1
        buy_levels = 1
        sell_levels = 1
        new_filled_order_delay = 10 + 30
        new_order_refresh_time = 10

        if self.inner_env_upper_bound is None:
            return

        # Fast Order Fill Configuration
        # new_filled_order_delay = 10 + 30
        # new_order_refresh_time = 10

        # Med Order Fill Configuration
        # new_filled_order_delay = 30 + 30
        # new_order_refresh_time = 5

        # Slow Order Fill Configuration
        # new_filled_order_delay = 60 + 30
        # new_order_refresh_time = 1

        if self.mid_price >= self.inner_env_upper_bound:
            sell_levels = 2
            new_filled_order_delay = 30 + 30
            new_order_refresh_time = 5
        if self.mid_price >= self.outer_env_upper_bound:
            sell_levels = 3
            new_filled_order_delay = 60 + 30
            new_order_refresh_time = 1
        if self.mid_price <= self.outer_env_lower_bound:
            sell_levels = 0

        if self.mid_price <= self.inner_env_lower_bound:
            buy_levels = 2
            new_filled_order_delay = 30 + 30
            new_order_refresh_time = 5
        if self.mid_price <= self.outer_env_lower_bound:
            buy_levels = 3
            new_filled_order_delay = 60 + 30
            new_order_refresh_time = 1
        if self.mid_price >= self.outer_env_upper_bound:
            buy_levels = 0

        self.new_order_levels = order_levels
        self.new_buy_levels = buy_levels
        self.new_sell_levels = sell_levels
        self.new_filled_order_delay = new_filled_order_delay
        self.new_order_refresh_time = new_order_refresh_time

    def applyInventoryControl(self):
        if self.init_base_price is None or self.init_base_amount is None or self.init_quote_value is None or self.init_total_inv_value is None:
            return
        
        current_price = self.mid_price
        init_current_diff = (current_price - self.init_base_price) / self.init_base_price * 100

        base_balance = Decimal(self.all_available_balances[f"{self.pmm_market_info.exchange}"].get(self.base_asset, self.init_base_amount))
        quote_balance = Decimal(self.all_available_balances[f"{self.pmm_market_info.exchange}"].get(self.quote_asset, self.init_quote_value))
        base_inv_value = base_balance * current_price
        total_inv_value = base_inv_value + quote_balance

        if total_inv_value >= self.init_total_inv_value:
            self.init_base_price = current_price
            self.init_base_amount = base_balance
            self.init_quote_value = quote_balance
            self.init_total_inv_value = total_inv_value
            self.pmm_parameters.inventory_target_base_pct = Decimal(0.5)
            return
        
        if init_current_diff <= Decimal(-0.5):
            target_base_amount = (self.init_base_price / current_price) * self.init_base_amount + (self.init_quote_value - quote_balance) / current_price
            nominal_base_value = self.init_base_price * target_base_amount
            nominal_total_value = nominal_base_value + quote_balance
            target_base_pct = nominal_base_value / nominal_total_value

            if target_base_pct > Decimal(0.95):
                target_base_pct = Decimal(0.95)

            if target_base_pct < Decimal(0.05):
                target_base_pct = Decimal(0.05)

            self.pmm_parameters.inventory_target_base_pct = target_base_pct
            return

        self.pmm_parameters.inventory_target_base_pct = Decimal(0.5)

    # Utility Methods
    def stdev_price(self, interval: int, length: int) -> Optional[Decimal]:
        samples = self.take_samples(self.mid_prices, interval, length)
        if samples is None:
            return None
        return statistics.pstdev(samples)

    def status_msg(self):
        if self.new_order_amount is None:
            return "Collecting midprices for moving average ..."

        probability_msg = f"===Inverted BB===\n" \
                        f"upper_pct: {self.probability_upper_pct*100:.2%} | lower_pct: {self.probability_lower_pct*100:.2%}\n" \
                        f"upper_price: {self.probability_upper_price:.5f} | lower_price: {self.probability_lower_price:.5f}\n" \
                        f"basis: {self.std_basis:.5f}\n"

        envelop_msg = f"===Envelop Band===\n" \
                        f"outer_upper: {self.outer_env_upper_bound:.5f}\ninner_upper: {self.inner_env_upper_bound:.5f}\n" \
                        f"basis: {self.env_basis:.5f}\n" \
                        f"inner_lower: {self.inner_env_lower_bound:.5f}\nouter_lower: {self.outer_env_lower_bound:.5f}\n"

        order_msg = f"===Order Detail===\n" \
                        f"new_order_amount: {self.new_order_amount:.5f}\n" \
                        f"new_ask_spread: {self.new_ask_spread:.2%} | new_bid_spread: {self.new_bid_spread:.2%} | new_order_levels_spread: {self.new_order_levels_spread:.2%}\n" \
                        f"new_order_levels: {self.new_order_levels} | new_buy_levels: {self.new_buy_levels} | new_sell_levels: {self.new_sell_levels}\n" \
                        f"new_filled_order_delay: {self.new_filled_order_delay} | new_order_refresh_time: {self.new_order_refresh_time}\n"

        inv_msg = f"===Inventory Detail===\n" \
                        f"starting_base_price: {self.starting_base_price:.5f} {self.quote_asset}\n" \
                        f"starting_base_amount: {self.starting_base_amount:.5f} {self.base_asset} | starting_quote_value: {self.starting_quote_value:.5f} {self.quote_asset}\n" \
                        f"starting_total_inv_value: {self.starting_total_inv_value:.5f} {self.quote_asset}\n" \
                        f"======\n" \
                        f"current_base_price: {self.init_base_price:.5f} {self.quote_asset}\n" \
                        f"current_base_amount: {self.init_base_amount:.5f} {self.base_asset} | current_quote_value: {self.init_quote_value:.5f} {self.quote_asset}\n" \
                        f"current_total_inv_value: {self.init_total_inv_value:.5f} {self.quote_asset}\n"

        return f"\n{order_msg}{probability_msg}{envelop_msg}{inv_msg}"
