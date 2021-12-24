from hummingbot.client.settings import AllConnectorSettings
from hummingbot.client.config.config_methods import new_fee_config_var


def fee_overrides_dict():
    all_dict = {}
    # all_connector_types = get_exchanges_and_derivatives()
    for name in AllConnectorSettings.get_connector_settings().keys():
        all_dict.update({f"{name}_percent_fee_token": new_fee_config_var(f"{name}_percent_fee_token", type_str="str")})
        all_dict.update(
            {f"{name}_maker_percent_fee": new_fee_config_var(f"{name}_maker_percent_fee", type_str="decimal")}
        )
        all_dict.update(
            {f"{name}_taker_percent_fee": new_fee_config_var(f"{name}_taker_percent_fee", type_str="decimal")}
        )
        fee_application = f"{name}_buy_percent_fee_deducted_from_returns"
        all_dict.update({fee_application: new_fee_config_var(fee_application, type_str="bool")})
        all_dict.update(
            {f"{name}_maker_fixed_fees": new_fee_config_var(f"{name}_maker_fixed_fees", type_str="list")}
        )
        all_dict.update(
            {f"{name}_taker_fixed_fees": new_fee_config_var(f"{name}_taker_fixed_fees", type_str="list")}
        )
    return all_dict


fee_overrides_config_map = fee_overrides_dict()
