from typing import Dict

from hummingbot.client.config.config_methods import new_fee_config_var
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import AllConnectorSettings

fee_overrides_config_map: Dict[str, ConfigVar] = {}


def fee_overrides_dict() -> Dict[str, ConfigVar]:
    all_configs: Dict[str, ConfigVar] = {}
    for name in AllConnectorSettings.get_connector_settings().keys():
        all_configs.update({
            f"{name}_percent_fee_token": new_fee_config_var(f"{name}_percent_fee_token", type_str="str"),
            f"{name}_maker_percent_fee": new_fee_config_var(f"{name}_maker_percent_fee", type_str="decimal"),
            f"{name}_taker_percent_fee": new_fee_config_var(f"{name}_taker_percent_fee", type_str="decimal"),
            f"{name}_buy_percent_fee_deducted_from_returns": new_fee_config_var(
                f"{name}_buy_percent_fee_deducted_from_returns", type_str="bool"
            ),
            f"{name}_maker_fixed_fees": new_fee_config_var(f"{name}_maker_fixed_fees", type_str="list"),
            f"{name}_taker_fixed_fees": new_fee_config_var(f"{name}_taker_fixed_fees", type_str="list"),
        })
    return all_configs


def init_fee_overrides_config():
    global fee_overrides_config_map
    fee_overrides_config_map.clear()
    fee_overrides_config_map.update(fee_overrides_dict())


init_fee_overrides_config()
