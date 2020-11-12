# These are the libraries used by the script
from decimal import Decimal  # Python Library used to handle floating point variables
from datetime import datetime  # Python Library used to manipulate date and time

from hummingbot.core.event.events import (           # Import function related to filled order events
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent
)
from hummingbot.script.script_base import ScriptBase  # Import the base functions required to make scripts work

# This section create a function to log script information. Can be removed if you don't want to create a log.
# -------------------
s_decimal_1 = Decimal("1")
SCRIPT_LOG_FILE = "logs/logs_script.log"  # Name of the log file


def log_to_file(file_name, message):  # log writing function
    with open(file_name, "a+") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " - " + message + "\n")

"""
# Using the log function:
#
#       log_to_file(SCRIPT_LOG_FILE, #message you want to write on the log#)
#
#   You can also add a information on the log file after a chosen time period using this:
#
#         if time.time() - self.last_stats_logged > #time between writing logs in seconds#:
#             log_to_file(SCRIPT_LOG_FILE, #message you want to write on the log#)
#             self.last_stats_logged = time.time()
# ----------
"""

class Scriptname(ScriptBase):
    """
    ----------
    This is the main script object. All the actions you want to be performed by the script
    must be created inside this class
    ----------
    Some useful Functions that can be directly called from the parent class:
    -------------------
    self.mid_price - Returns the current mid price, calculated every tick
    -----------------
    self.base_asset, self.quote_asset = self.pmm_market_info.trading_pair.split("-")  # save base and quote ticker
    self.base_balance = self.all_total_balances[f"{self.pmm_market_info.exchange}"].get(self.base_asset, self.base_balance)
    self.quote_balance = self.all_total_balances[f"{self.pmm_market_info.exchange}"].get(self.quote_asset, self.quote_balance)
    These functions will call the current pair that is being traded and its balances
    ----------
    """
    def __init__(self):
        super().__init__()
        # The init function can be used to declare the variables that will be used only by the script
        # Example:
        # self.original_bid_spread = None
        # This will create a variable named original_bid_spread

    # Events
    #
    # The functions below are used to send instructions on specific events
    # Functions that won't be used can be deleted
    # --------------

    def on_tick(self):
        # The instructions here will be called when every tick, which is every second on normal HB configuration
        return

    def on_buy_order_completed(self, event: BuyOrderCompletedEvent):
        # The instructions here will be called every time a buy order is filled
        return

    def on_sell_order_completed(self, event: SellOrderCompletedEvent):
        # The instructions here will be called every time a sell order is filled
        return

    def on_status(self) -> str:
        # The instructions here will be called every time the `status` command is executed on the Hummingbot application
        return
