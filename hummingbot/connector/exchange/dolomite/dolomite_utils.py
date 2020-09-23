from hummingbot.client.config.config_methods import new_fee_config_var

CENTRALIZED = False

EXAMPLE_PAIR = "WETH-DAI"

DEFAULT_FEES = [0, 0.00001]

FEE_OVERRIDE_MAP = {
    "dolomite_maker_fee_amount": new_fee_config_var("dolomite_maker_fee_amount"),
    "dolomite_taker_fee_amount": new_fee_config_var("dolomite_taker_fee_amount")
}
