from decimal import Decimal
from hummingbot.core.event.events import TradeFee, TradeFeeType
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
from hummingbot.client.settings import CONNECTOR_SETTINGS


def estimate_fee(exchange: str, is_maker: bool) -> TradeFee:
    if exchange not in CONNECTOR_SETTINGS:
        raise Exception(f"Invalid connector. {exchange} does not exist in CONNECTOR_SETTINGS")
    fee_type = CONNECTOR_SETTINGS[exchange].fee_type
    fee_token = CONNECTOR_SETTINGS[exchange].fee_token
    default_fees = CONNECTOR_SETTINGS[exchange].default_fees
    fee_side = "maker" if is_maker else "taker"
    fee_configs = [f for f in fee_overrides_config_map.keys() if exchange in f and fee_side in f]
    if len(fee_configs) > 1:
        raise Exception(f"Invalid fee override config map, there are multiple {exchange} {fee_side} fees settings.")
    fee = default_fees[0] if is_maker else default_fees[1]
    if len(fee_configs) == 1 and fee_overrides_config_map[fee_configs[0]].value is not None:
        fee = fee_overrides_config_map[fee_configs[0]].value
    fee = Decimal(str(fee))
    if fee_type is TradeFeeType.Percent:
        return TradeFee(percent=fee / Decimal("100"))
    elif fee_type is TradeFeeType.FlatFee:
        return TradeFee(flat_fees=[(fee_token, fee)])
