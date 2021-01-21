from decimal import Decimal

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_decimal,
    validate_bool
)
from hummingbot.client.settings import (
    required_exchanges,
)


def exchange_on_validated(value: str) -> None:
    required_exchanges.append(value)


def auto_campaigns_participation_on_validated(value: bool) -> None:
    if value:
        liquidity_mining_config_map["markets"].value = "HARD-USDT,RLC-USDT,AVAX-USDT,ALGO-USDT,XEM-USDT,MFT-USDT,ETH-USDT"


liquidity_mining_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="liquidity_mining"),
    "exchange":
        ConfigVar(key="exchange",
                  prompt="Enter your liquidity mining exchange name >>> ",
                  validator=validate_exchange,
                  on_validated=exchange_on_validated,
                  prompt_on_new=True),
    "auto_campaigns_participation":
        ConfigVar(key="auto_campaigns_participation",
                  prompt="Do you want the bot to automatically participate in as many mining campaign as possible "
                         "(Yes/No)  >>> ",
                  type_str="bool",
                  validator=validate_bool,
                  on_validated=auto_campaigns_participation_on_validated,
                  prompt_on_new=True),
    "markets":
        ConfigVar(key="markets",
                  prompt="Enter a list of markets >>> ",
                  required_if=lambda: not liquidity_mining_config_map.get("auto_campaigns_participation").value,
                  prompt_on_new=True),
    "reserved_balances":
        ConfigVar(key="reserved_balances",
                  prompt="Enter a list of tokens and their reserved balance (to not be used by the bot), "
                         "This can be used for an asset amount you want to set a side to pay for fee (e.g. BNB for "
                         "Binance), to limit exposure or in anticipation of withdrawal, e.g. BTC:0.1,BNB:1 >>> ",
                  type_str="str",
                  default="",
                  validator=lambda s: None,
                  prompt_on_new=True),
    "auto_assign_campaign_budgets":
        ConfigVar(key="auto_assign_campaign_budgets",
                  prompt="Do you want the bot to automatically assign budgets (equal weight) for all campaign markets? "
                         "The assignment assumes full allocation of your assets (after accounting for reserved balance)"
                         " (Yes/No)  >>> ",
                  type_str="bool",
                  validator=validate_bool,
                  prompt_on_new=True),
    "campaign_budgets":
        ConfigVar(key="campaign_budgets",
                  prompt="Enter a list of campaigns and their buy and sell budgets. For example "
                         "XEM-ETH:500-2, XEM-USDT:300-250 (this means on XEM-ETH campaign sell budget is 500 XEM, "
                         "and buy budget is 2 ETH) >>> ",
                  required_if=lambda: not liquidity_mining_config_map.get("auto_assign_campaign_budgets").value,
                  type_str="json"),
    "spread_level":
        ConfigVar(key="spread_level",
                  prompt="Enter spread level (tight/medium/wide/custom) >>> ",
                  type_str="str",
                  default="medium",
                  validator=lambda s: None if s in {"tight", "medium", "wide", "custom"} else "Invalid spread level.",
                  prompt_on_new=True),
    "custom_spread_pct":
        ConfigVar(key="custom_spread_pct",
                  prompt="How far away from the mid price do you want to place bid order and ask order? "
                         "(Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  required_if=lambda: liquidity_mining_config_map.get("spread_level").value == "custom",
                  validator=lambda v: validate_decimal(v, 0, 100, inclusive=False),
                  prompt_on_new=True),
    "order_refresh_time":
        ConfigVar(key="order_refresh_time",
                  prompt="How often do you want to cancel and replace bids and asks "
                         "(in seconds)? >>> ",
                  type_str="float",
                  validator=lambda v: validate_decimal(v, 0, inclusive=False),
                  default=5.),
    "order_refresh_tolerance_pct":
        ConfigVar(key="order_refresh_tolerance_pct",
                  prompt="Enter the percent change in price needed to refresh orders at each cycle "
                         "(Enter 1 to indicate 1%) >>> ",
                  type_str="decimal",
                  default=Decimal("0.2"),
                  validator=lambda v: validate_decimal(v, -10, 10, inclusive=True)),

}
