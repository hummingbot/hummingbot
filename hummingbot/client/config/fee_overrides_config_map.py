from hummingbot.client.settings import CONNECTOR_SETTINGS
from hummingbot.core.event.events import TradeFeeType
from hummingbot.client.config.config_methods import new_fee_config_var


def fee_overrides_dict():
    all_dict = {}
    # all_connector_types = get_exchanges_and_derivatives()
    for name, setting in CONNECTOR_SETTINGS.items():
        key_suffix = None
        if setting.fee_type is TradeFeeType.Percent:
            key_suffix = "fee"
        elif setting.fee_type is TradeFeeType.FlatFee:
            key_suffix = "fee_amount"
        maker_key = f"{name}_maker_{key_suffix}"
        taker_key = f"{name}_taker_{key_suffix}"
        all_dict.update({maker_key: new_fee_config_var(maker_key)})
        all_dict.update({taker_key: new_fee_config_var(taker_key)})
    return all_dict


fee_overrides_config_map = fee_overrides_dict()
