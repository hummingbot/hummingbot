from decimal import Decimal
from hummingbot.core.event.events import TradeFee
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map

default_cex_estimate = {
    # exchange: [maker_fee, taker_fee]
    "binance": [0.1, 0.1],
    "bittrex": [0.25, 0.25],
    "coinbase_pro": [0.5, 0.5],
    "huobi": [0.2, 0.2],
    "kraken": [0.16, 0.26],
    "kucoin": [0.1, 0.1],
    "liquid": [0.1, 0.1]}

default_dex_estimate = {
    "bamboo_relay": [0, 0.00001],
    "radar_relay": [0, 0.00001],
    "dolomite": [0, 0.00001]}


def estimate_fee(exchange, is_maker):
    override_config_name_suffix = "_maker_fee" if is_maker else "_taker_fee"
    override_config_name = exchange + override_config_name_suffix
    if exchange in default_dex_estimate:
        override_config_name += "_amount"
    s_decimal_0 = Decimal(0)
    s_decimal_100 = Decimal(100)

    if is_maker:
        if exchange in default_cex_estimate:
            if fee_overrides_config_map[override_config_name].value is not None:
                return TradeFee(percent=fee_overrides_config_map[override_config_name].value / s_decimal_100)
            else:
                return TradeFee(percent=Decimal(default_cex_estimate[exchange][0]) / s_decimal_100)
        else:
            if fee_overrides_config_map[override_config_name].value is not None:
                return TradeFee(percent=s_decimal_0, flat_fees=[("ETH", fee_overrides_config_map[override_config_name].value)])
            else:
                return TradeFee(percent=s_decimal_0, flat_fees=[("ETH", Decimal(default_dex_estimate[exchange][0]))])

    else:
        if exchange in default_cex_estimate:
            if fee_overrides_config_map[override_config_name].value is not None:
                return TradeFee(percent=fee_overrides_config_map[override_config_name].value / s_decimal_100)
            else:
                return TradeFee(percent=Decimal(default_cex_estimate[exchange][1]) / s_decimal_100)
        else:
            if fee_overrides_config_map[override_config_name].value is not None:
                return TradeFee(percent=s_decimal_0, flat_fees=[("ETH", fee_overrides_config_map[override_config_name].value)])
            else:
                return TradeFee(percent=s_decimal_0, flat_fees=[("ETH", Decimal(default_dex_estimate[exchange][1]))])
