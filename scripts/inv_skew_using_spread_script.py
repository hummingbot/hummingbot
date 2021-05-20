
from hummingbot.core.event.events import BuyOrderCompletedEvent, SellOrderCompletedEvent
from hummingbot.script.script_base import ScriptBase
from decimal import Decimal

# Enter the inventory % threshold. When the % of an asset goes below this value, the script will change the spread value
inv_pct_limit = 0.10
# Enter the spread value to be used if the inventory % threshold is reached
new_spread = Decimal("0.005")


class InventorySkewUsingSpread(ScriptBase):

    def __init__(self):
        super().__init__()
        # Declaration of variables used by the script
        self.base_asset = None
        self.quote_asset = None
        self.base_balance = Decimal("0.0000")
        self.quote_balance = Decimal("0.0000")
        self.original_bid_spread = None
        self.original_ask_spread = None
        self.base_inv_value = Decimal("0.0000")
        self.quote_pct = Decimal("0.0000")
        self.base_pct = Decimal("0.0000")
        self.ask_skew_active = False
        self.bid_skew_active = False
        self.total_inv_value = None

    def on_tick(self):

        # Separate and store the assets of the market the bot is working on
        if self.base_asset is None or self.quote_asset is None:
            self.base_asset, self.quote_asset = self.pmm_market_info.trading_pair.split("-")

        # Check what is the current balance of each asset
        self.base_balance = self.all_total_balances[f"{self.pmm_market_info.exchange}"].get(self.base_asset, self.base_balance)
        self.quote_balance = self.all_total_balances[f"{self.pmm_market_info.exchange}"].get(self.quote_asset, self.quote_balance)

        # At the script start, the values of the original configuration bid and ask spread is stored for later use
        if self.original_bid_spread is None or self.original_ask_spread is None:
            self.original_bid_spread = self.pmm_parameters.bid_spread
            self.original_ask_spread = self.pmm_parameters.ask_spread

        if self.ask_skew_active is False:
            self.original_ask_spread = self.pmm_parameters.ask_spread

        if self.bid_skew_active is False:
            self.original_bid_spread = self.pmm_parameters.bid_spread

        # calculate the total % value and it's proportion
        self.base_inv_value = self.base_balance * self.mid_price
        self.total_inv_value = self.base_inv_value + self.quote_balance
        self.base_pct = self.base_inv_value / self.total_inv_value
        self.quote_pct = self.quote_balance / self.total_inv_value

        # check if the inventory value % of an asset is below the chosen threshold to define what spread will be used
        if self.quote_pct < inv_pct_limit:
            self.ask_skew_active = True
            self.pmm_parameters.ask_spread = new_spread
            # self.log(f"{self.base_asset} inventory % below {inv_pct_limit:.2%}. Changing ask_spread to {new_spread:.2%}")
        else:
            self.ask_skew_active = False
            self.pmm_parameters.ask_spread = self.original_ask_spread
        if self.base_pct < inv_pct_limit:
            self.bid_skew_active = True
            self.pmm_parameters.bid_spread = new_spread
            # self.log(f"{self.quote_asset} inventory % below {inv_pct_limit:.2%}. Changing bid_spread to {new_spread:.2%}")
        else:
            self.bid_skew_active = False
            self.pmm_parameters.bid_spread = self.original_bid_spread

        return

    def on_buy_order_completed(self, event: BuyOrderCompletedEvent):
        return

    def on_sell_order_completed(self, event: SellOrderCompletedEvent):
        return

    def on_status(self) -> str:
        # Show the current values when using the `status` command
        return f"\n"\
               f"original bid spread = {self.original_bid_spread:.2%} \n" \
               f"original ask spread = {self.original_ask_spread:.2%} \n" \
               f"ask skew active? = {self.ask_skew_active} \n" \
               f"current ask spread = {self.pmm_parameters.ask_spread:.2%} \n" \
               f"bid skew active? = {self.bid_skew_active} \n" \
               f"current bid spread = {self.pmm_parameters.bid_spread:.2%}"

    # ---------------
