from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_decimal,
    validate_bool
)
from hummingbot.client.config.config_helpers import parse_cvar_value
import hummingbot.client.settings as settings
from decimal import Decimal
from typing import Optional


def maker_trading_pair_prompt():
    maker_market = cross_exchange_market_making_config_map.get("maker_market").value
    example = settings.AllConnectorSettings.get_example_pairs().get(maker_market)
    return "Enter the token trading pair you would like to trade on maker market: %s%s >>> " % (
        maker_market,
        f" (e.g. {example})" if example else "",
    )


def taker_trading_pair_prompt():
    taker_market = cross_exchange_market_making_config_map.get("taker_market").value
    example = settings.AllConnectorSettings.get_example_pairs().get(taker_market)
    return "Enter the token trading pair you would like to trade on taker market: %s%s >>> " % (
        taker_market,
        f" (e.g. {example})" if example else "",
    )


def top_depth_tolerance_prompt() -> str:
    maker_market = cross_exchange_market_making_config_map["maker_market_trading_pair"].value
    base_asset, quote_asset = maker_market.split("-")
    return f"What is your top depth tolerance? (in {base_asset}) >>> "


# strategy specific validators
def validate_maker_market_trading_pair(value: str) -> Optional[str]:
    maker_market = cross_exchange_market_making_config_map.get("maker_market").value
    return validate_market_trading_pair(maker_market, value)


def validate_taker_market_trading_pair(value: str) -> Optional[str]:
    taker_market = cross_exchange_market_making_config_map.get("taker_market").value
    return validate_market_trading_pair(taker_market, value)


def order_amount_prompt() -> str:
    trading_pair = cross_exchange_market_making_config_map["maker_market_trading_pair"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {base_asset} per order? >>> "


def taker_market_on_validated(value: str):
    settings.required_exchanges.append(value)


def update_oracle_settings(value: str):
    c_map = cross_exchange_market_making_config_map
    if not (c_map["use_oracle_conversion_rate"].value is not None and
            c_map["maker_market_trading_pair"].value is not None and
            c_map["taker_market_trading_pair"].value is not None):
        return
    use_oracle = parse_cvar_value(c_map["use_oracle_conversion_rate"], c_map["use_oracle_conversion_rate"].value)
    first_base, first_quote = c_map["maker_market_trading_pair"].value.split("-")
    second_base, second_quote = c_map["taker_market_trading_pair"].value.split("-")
    if use_oracle and (first_base != second_base or first_quote != second_quote):
        settings.required_rate_oracle = True
        settings.rate_oracle_pairs = []
        if first_base != second_base:
            settings.rate_oracle_pairs.append(f"{second_base}-{first_base}")
        if first_quote != second_quote:
            settings.rate_oracle_pairs.append(f"{second_quote}-{first_quote}")
    else:
        settings.required_rate_oracle = False
        settings.rate_oracle_pairs = []


cross_exchange_market_making_config_map = {
    "strategy": ConfigVar(key="strategy",
                          prompt="",
                          default="cross_exchange_market_making"
                          ),
    "maker_market": ConfigVar(
        key="maker_market",
        prompt="Enter your maker spot connector >>> ",
        prompt_on_new=True,
        validator=validate_exchange,
        on_validated=lambda value: settings.required_exchanges.append(value),
    ),
    "taker_market": ConfigVar(
        key="taker_market",
        prompt="Enter your taker spot connector >>> ",
        prompt_on_new=True,
        validator=validate_exchange,
        on_validated=taker_market_on_validated,
    ),
    "maker_market_trading_pair": ConfigVar(
        key="maker_market_trading_pair",
        prompt=maker_trading_pair_prompt,
        prompt_on_new=True,
        validator=validate_maker_market_trading_pair,
        on_validated=update_oracle_settings
    ),
    "taker_market_trading_pair": ConfigVar(
        key="taker_market_trading_pair",
        prompt=taker_trading_pair_prompt,
        prompt_on_new=True,
        validator=validate_taker_market_trading_pair,
        on_validated=update_oracle_settings
    ),
    "min_profitability": ConfigVar(
        key="min_profitability",
        prompt="What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        validator=lambda v: validate_decimal(v, Decimal(-100), Decimal("100"), inclusive=True),
        type_str="decimal",
    ),
    "order_amount": ConfigVar(
        key="order_amount",
        prompt=order_amount_prompt,
        prompt_on_new=True,
        type_str="decimal",
        validator=lambda v: validate_decimal(v, min_value=Decimal("0"), inclusive=False),
    ),
    "adjust_order_enabled": ConfigVar(
        key="adjust_order_enabled",
        prompt="Do you want to enable adjust order? (Yes/No) >>> ",
        default=True,
        type_str="bool",
        validator=validate_bool,
        required_if=lambda: False,
    ),
    "active_order_canceling": ConfigVar(
        key="active_order_canceling",
        prompt="Do you want to enable active order canceling? (Yes/No) >>> ",
        type_str="bool",
        default=True,
        required_if=lambda: False,
        validator=validate_bool,
    ),
    # Setting the default threshold to 0.05 when to active_order_canceling is disabled
    # prevent canceling orders after it has expired
    "cancel_order_threshold": ConfigVar(
        key="cancel_order_threshold",
        prompt="What is the threshold of profitability to cancel a trade? (Enter 1 to indicate 1%) >>> ",
        default=5,
        type_str="decimal",
        required_if=lambda: False,
        validator=lambda v: validate_decimal(v, min_value=Decimal(-100), max_value=Decimal(100), inclusive=False),
    ),
    "limit_order_min_expiration": ConfigVar(
        key="limit_order_min_expiration",
        prompt="How often do you want limit orders to expire (in seconds)? >>> ",
        default=130.0,
        type_str="float",
        required_if=lambda: False,
        validator=lambda v: validate_decimal(v, min_value=0, inclusive=False)
    ),
    "top_depth_tolerance": ConfigVar(
        key="top_depth_tolerance",
        prompt=top_depth_tolerance_prompt,
        default=0,
        type_str="decimal",
        required_if=lambda: False,
        validator=lambda v: validate_decimal(v, min_value=0, inclusive=True)
    ),
    "anti_hysteresis_duration": ConfigVar(
        key="anti_hysteresis_duration",
        prompt="What is the minimum time interval you want limit orders to be adjusted? (in seconds) >>> ",
        default=60,
        type_str="float",
        required_if=lambda: False,
        validator=lambda v: validate_decimal(v, min_value=0, inclusive=False)
    ),
    "order_size_taker_volume_factor": ConfigVar(
        key="order_size_taker_volume_factor",
        prompt="What percentage of hedge-able volume would you like to be traded on the taker market? "
               "(Enter 1 to indicate 1%) >>> ",
        default=25,
        type_str="decimal",
        required_if=lambda: False,
        validator=lambda v: validate_decimal(v, Decimal(0), Decimal(100), inclusive=False)
    ),
    "order_size_taker_balance_factor": ConfigVar(
        key="order_size_taker_balance_factor",
        prompt="What percentage of asset balance would you like to use for hedging trades on the taker market? "
               "(Enter 1 to indicate 1%) >>> ",
        default=Decimal("99.5"),
        type_str="decimal",
        required_if=lambda: False,
        validator=lambda v: validate_decimal(v, Decimal(0), Decimal(100), inclusive=False)
    ),
    "order_size_portfolio_ratio_limit": ConfigVar(
        key="order_size_portfolio_ratio_limit",
        prompt="What ratio of your total portfolio value would you like to trade on the maker and taker markets? "
               "Enter 50 for 50% >>> ",
        default=Decimal("16.67"),
        type_str="decimal",
        required_if=lambda: False,
        validator=lambda v: validate_decimal(v, Decimal(0), Decimal(100), inclusive=False)
    ),
    "use_oracle_conversion_rate": ConfigVar(
        key="use_oracle_conversion_rate",
        type_str="bool",
        prompt="Do you want to use rate oracle on unmatched trading pairs? (Yes/No) >>> ",
        prompt_on_new=True,
        validator=lambda v: validate_bool(v),
        on_validated=update_oracle_settings),
    "taker_to_maker_base_conversion_rate": ConfigVar(
        key="taker_to_maker_base_conversion_rate",
        prompt="Enter conversion rate for taker base asset value to maker base asset value, e.g. "
               "if maker base asset is USD and the taker is DAI, 1 DAI is valued at 1.25 USD, "
               "the conversion rate is 1.25 >>> ",
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v, Decimal(0), inclusive=False),
        type_str="decimal"
    ),
    "taker_to_maker_quote_conversion_rate": ConfigVar(
        key="taker_to_maker_quote_conversion_rate",
        prompt="Enter conversion rate for taker quote asset value to maker quote asset value, e.g. "
               "if maker quote asset is USD and the taker is DAI, 1 DAI is valued at 1.25 USD, "
               "the conversion rate is 1.25 >>> ",
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v, Decimal(0), inclusive=False),
        type_str="decimal"
    ),
    "slippage_buffer": ConfigVar(
        key="slippage_buffer",
        prompt="How much buffer do you want to add to the price to account for slippage for taker orders "
               "Enter 1 to indicate 1% >>> ",
        prompt_on_new=True,
        default=Decimal("5"),
        type_str="decimal",
        validator=lambda v: validate_decimal(v, Decimal(0), Decimal(100), inclusive=True)
    )
}
