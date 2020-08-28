from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import validate_decimal
from decimal import Decimal


def new_fee_config_var(key):
    return ConfigVar(key=key,
                     prompt=None,
                     required_if=lambda x: x is not None,
                     type_str="decimal",
                     validator=lambda v: validate_decimal(v, Decimal(-0.1), Decimal(0.1)))


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
    "kucoin_taker_fee": new_fee_config_var("kucoin_taker_fee"),
    "kraken_maker_fee": new_fee_config_var("kraken_maker_fee"),
    "kraken_taker_fee": new_fee_config_var("kraken_taker_fee"),
    "eterbase_maker_fee": new_fee_config_var("eterbase_maker_fee"),
    "eterbase_taker_fee": new_fee_config_var("eterbase_taker_fee"),
    "dolomite_maker_fee_amount": new_fee_config_var("dolomite_maker_fee_amount"),
    "dolomite_taker_fee_amount": new_fee_config_var("dolomite_taker_fee_amount"),
    "bamboo_relay_maker_fee_amount": new_fee_config_var("bamboo_relay_maker_fee_amount"),
    "bamboo_relay_taker_fee_amount": new_fee_config_var("bamboo_relay_taker_fee_amount"),
    "radar_relay_maker_fee_amount": new_fee_config_var("radar_relay_maker_fee_amount"),
    "radar_relay_taker_fee_amount": new_fee_config_var("radar_relay_taker_fee_amount")
}
