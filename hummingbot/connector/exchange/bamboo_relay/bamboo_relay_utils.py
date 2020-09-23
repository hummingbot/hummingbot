from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import validate_bool
from hummingbot.client.config.config_methods import new_fee_config_var

CENTRALIZED = False

EXAMPLE_PAIR = "ZRX-WETH"

DEFAULT_FEES = [0, 0.00001]

FEE_OVERRIDE_MAP = {
    "bamboo_relay_maker_fee_amount": new_fee_config_var("bamboo_relay_maker_fee_amount"),
    "bamboo_relay_taker_fee_amount": new_fee_config_var("bamboo_relay_taker_fee_amount")
}

KEYS = {
    "bamboo_relay_use_coordinator":
        ConfigVar(key="bamboo_relay_use_coordinator",
                  prompt="Would you like to use the Bamboo Relay Coordinator? (Yes/No) >>> ",
                  required_if=lambda: False,
                  type_str="bool",
                  default=False,
                  validator=validate_bool),
    "bamboo_relay_pre_emptive_soft_cancels":
        ConfigVar(key="bamboo_relay_pre_emptive_soft_cancels",
                  prompt="Would you like to pre-emptively soft cancel orders? (Yes/No) >>> ",
                  required_if=lambda: False,
                  type_str="bool",
                  default=False,
                  validator=validate_bool),
}
