from hummingbot.client.config.config_methods import new_fee_config_var

CENTRALIZED = False

EXAMPLE_PAIR = "ZRX-WETH"

DEFAULT_FEES = [0, 0.00001]

FEE_OVERRIDE_MAP = {
    "radar_relay_maker_fee_amount": new_fee_config_var("radar_relay_maker_fee_amount"),
    "radar_relay_taker_fee_amount": new_fee_config_var("radar_relay_taker_fee_amount")
}
