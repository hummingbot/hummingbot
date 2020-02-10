from hummingbot.client.config.config_var import ConfigVar


def is_valid_fee(value: str) -> bool:
    try:
        return -0.1 <= float(value) <= 0.1
    except ValueError:
        return False


def new_fee_config_var(key):
    return ConfigVar(key=key,
                     prompt=None,
                     required_if=lambda x: x is not None,
                     type_str="decimal",
                     validator=is_valid_fee)


# trade fees configs are not prompted during setup process

fee_overrides_config_map = {
    "binance_maker_fee": new_fee_config_var("binance_maker_fee"),
    "binance_taker_fee": new_fee_config_var("binance_taker_fee"),
    "coinbase_pro_maker_fee": new_fee_config_var("coinbase_pro_maker_fee"),
    "coinbase_pro_taker_fee": new_fee_config_var("coinbase_pro_taker_fee"),
    "huobi_maker_fee": new_fee_config_var("huobi_maker_fee"),
    "huobi_taker_fee": new_fee_config_var("huobi_taker_fee"),
    "liquid_maker_fee": new_fee_config_var("liquid_maker_fee"),
    "liquid_taker_fee": new_fee_config_var("liquid_taker_fee"),
    "bittrex_maker_fee": new_fee_config_var("bittrex_maker_fee"),
    "bittrex_taker_fee": new_fee_config_var("bittrex_taker_fee"),
    "kucoin_maker_fee": new_fee_config_var("kucoin_maker_fee"),
    "kucoin_taker_fee": new_fee_config_var("kucoin_taker_fee")
}
