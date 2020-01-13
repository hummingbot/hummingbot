from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    is_exchange,
    is_valid_market_trading_pair,
    is_valid_percent
)
from hummingbot.client.settings import (
    required_exchanges,
    EXAMPLE_PAIRS,
)
from hummingbot.client.config.global_config_map import (
    using_bamboo_coordinator_mode,
    using_exchange,
)


def maker_trading_pair_prompt():
    maker_market = pure_market_making_config_map.get("maker_market").value
    example = EXAMPLE_PAIRS.get(maker_market)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (maker_market, f" (e.g. {example})" if example else "")


# strategy specific validators
def is_valid_maker_market_trading_pair(value: str) -> bool:
    maker_market = pure_market_making_config_map.get("maker_market").value
    return is_valid_market_trading_pair(maker_market, value)


pure_market_making_config_map = {
    "maker_market":
        ConfigVar(key="maker_market",
                  prompt="Enter your maker exchange name >>> ",
                  validator=is_exchange,
                  on_validated=lambda value: required_exchanges.append(value)),
    "maker_market_trading_pair":
        ConfigVar(key="primary_market_trading_pair",
                  prompt=maker_trading_pair_prompt,
                  validator=is_valid_maker_market_trading_pair),
    "mode":
        ConfigVar(key="mode",
                  prompt="Enter quantity of bid/ask orders per side (single/multiple) (Default is single) >>> ",
                  type_str="str",
                  validator=lambda v: v in {"single", "multiple"},
                  default="single"),
    "bid_place_threshold":
        ConfigVar(key="bid_place_threshold",
                  prompt="How far away from the mid price do you want to place the "
                         "first bid order? (Enter 0.01 to indicate 1%) >>> ",
                  type_str="decimal",
                  validator=is_valid_percent),
    "ask_place_threshold":
        ConfigVar(key="ask_place_threshold",
                  prompt="How far away from the mid price do you want to place the "
                         "first ask order? (Enter 0.01 to indicate 1%) >>> ",
                  type_str="decimal",
                  validator=is_valid_percent),
    "expiration_seconds":
        ConfigVar(key="expiration_seconds",
                  prompt="How long should your limit orders remain valid until they "
                         "expire and are replaced? (Minimum / Default is 130 seconds) >>> ",
                  default=130.0,
                  required_if=lambda: using_exchange("radar_relay")() or
                  (using_exchange("bamboo_relay")() and not using_bamboo_coordinator_mode()),
                  type_str="float",
                  validator=lambda input: float(input) >= 130.0),
    "cancel_order_wait_time":
        ConfigVar(key="cancel_order_wait_time",
                  prompt="How often do you want to cancel and replace bids and asks "
                         "(in seconds)? (Default is 60 seconds) >>> ",
                  default=60.0,
                  required_if=lambda: not (
                      using_exchange("radar_relay")()
                      or (using_exchange("bamboo_relay")() and not using_bamboo_coordinator_mode())
                  ),
                  type_str="float"),
    "order_amount":
        ConfigVar(key="order_amount",
                  prompt="What is your preferred quantity per order? (Denominated in "
                         "the base asset, default is 1) >>> ",
                  default=1.0,
                  required_if=lambda: pure_market_making_config_map.get("mode").value == "single",
                  type_str="decimal"),
    "number_of_orders":
        ConfigVar(key="number_of_orders",
                  prompt="How many orders do you want to place on both sides?"
                         " (Default is 1) >>> ",
                  required_if=lambda: pure_market_making_config_map.get("mode").value == "multiple",
                  type_str="int",
                  default=1),
    "order_start_size":
        ConfigVar(key="order_start_size",
                  prompt="What is the size of the first bid and ask order?"
                  " (Default is 1) >>> ",
                  required_if=lambda: pure_market_making_config_map.get("mode").value == "multiple",
                  type_str="decimal",
                  default=1),
    "order_step_size":
        ConfigVar(key="order_step_size",
                  prompt="How much do you want to increase the order size for each "
                         "additional order? (Default is 0) >>> ",
                  required_if=lambda: pure_market_making_config_map.get("mode").value == "multiple",
                  type_str="decimal",
                  default=0),
    "order_interval_percent":
        ConfigVar(key="order_interval_percent",
                  prompt="Enter the price increments (as percentage) for subsequent "
                         "orders? (Enter 0.01 to indicate 1%) >>> ",
                  required_if=lambda: pure_market_making_config_map.get("mode").value == "multiple",
                  type_str="decimal",
                  validator=is_valid_percent,
                  default=0.01),
    "inventory_skew_enabled":
        ConfigVar(key="inventory_skew_enabled",
                  prompt="Would you like to enable inventory skew? (y/n) (Default is no) >>> ",
                  type_str="bool",
                  default=False),
    "inventory_target_base_percent":
        ConfigVar(key="inventory_target_base_percent",
                  prompt="What is your target base asset inventory percentage? "
                         "(Enter 0.01 to indicate 1%, default is 0.5 (50%) >>> ",
                  required_if=lambda: pure_market_making_config_map.get("inventory_skew_enabled").value,
                  type_str="decimal",
                  validator=is_valid_percent,
                  default=0.5),
    "filled_order_replenish_wait_time":
        ConfigVar(key="filled_order_replenish_wait_time",
                  prompt="How long do you want to wait before placing the next order "
                         "if your order gets filled (in seconds)? "
                         "(Default is 10 seconds) >>> ",
                  type_str="float",
                  default=10),
    "enable_order_filled_stop_cancellation":
        ConfigVar(key="enable_order_filled_stop_cancellation",
                  prompt="Do you want to enable order_filled_stop_cancellation? "
                         "If enabled, when orders are completely filled, the other "
                         "side remains uncanceled. (Default is False) >>> ",
                  type_str="bool",
                  default=False),
    "best_bid_ask_jump_mode":
        ConfigVar(key="best_bid_ask_jump_mode",
                  prompt="Do you want to enable best bid ask jumping ? "
                         "If enabled, when the top bid price is lesser than your order price, "
                         "buy order will jump below to one tick above top bid price "
                         "& vice versa for sell order. "
                         "(Default is False) >>> ",
                  type_str="bool",
                  default=False),
    "best_bid_ask_jump_orders_depth":
        ConfigVar(key="best_bid_ask_jump_orders_depth",
                  prompt="How deep do you want to go into the order book for calculating "
                         "the top bid and ask, ignoring dust orders on the top "
                         "(expressed in base currency)? (Default is 0) >>> ",
                  required_if=lambda: pure_market_making_config_map.get("best_bid_ask_jump_mode").value,
                  type_str="decimal",
                  default=0),
    "add_transaction_costs":
        ConfigVar(key="add_transaction_costs",
                  prompt="Do you want to add transaction costs automatically to order prices? "
                         "(Default is True) >>> ",
                  type_str="bool",
                  default=True),
    "external_pricing_source": ConfigVar(key="external_pricing_source",
                                         prompt="Would you like to use an external pricing source for mid-market "
                                                "price? (y/n) (Default is no) >>> ",
                                         type_str="bool",
                                         default=False),
    "external_price_source_type": ConfigVar(key="external_price_source_type",
                                            prompt="Which type of external price source to use? "
                                                   "(exchange/feed/custom_api) >>> ",
                                            required_if=lambda: pure_market_making_config_map.get(
                                                "external_pricing_source").value,
                                            type_str="str",
                                            validator=lambda s: s in {"exchange", "feed", "custom_api"}),
    "external_price_source_exchange": ConfigVar(key="external_price_source_exchange",
                                                prompt="Enter exchange name >>> ",
                                                required_if=lambda: pure_market_making_config_map.get(
                                                    "external_price_source_type").value == "exchange",
                                                type_str="str",
                                                validator=lambda s: s != pure_market_making_config_map.get(
                                                    "maker_market").value and is_exchange(s)),
    "external_price_source_feed_base_asset": ConfigVar(key="external_price_source_feed_base_asset",
                                                       prompt="Reference base asset from data feed? (e.g. ETH) >>> ",
                                                       required_if=lambda: pure_market_making_config_map.get(
                                                           "external_price_source_type").value == "feed",
                                                       type_str="str"),
    "external_price_source_feed_quote_asset": ConfigVar(key="external_price_source_feed_quote_asset",
                                                        prompt="Reference quote asset from data feed? (e.g. USD) >>> ",
                                                        required_if=lambda: pure_market_making_config_map.get(
                                                            "external_price_source_type").value == "feed",
                                                        type_str="str"),
    "external_price_source_custom_api": ConfigVar(key="external_price_source_custom_api",
                                                  prompt="Enter pricing API URL >>> ",
                                                  required_if=lambda: pure_market_making_config_map.get(
                                                      "external_price_source_type").value == "custom_api",
                                                  type_str="str")
}
