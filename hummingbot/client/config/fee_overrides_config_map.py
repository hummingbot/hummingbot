from hummingbot.client.settings import ALL_CONNECTORS, DEXES
from hummingbot.client.config.config_methods import new_fee_config_var


def fee_overrides_dict():
    all_dict = {}
    # all_connector_types = get_exchanges_and_derivatives()
    for connector_type, connectors in ALL_CONNECTORS.items():
        for connector in connectors:
            maker_key = f"{connector}_maker_fee_amount" if connector in DEXES else f"{connector}_maker_fee"
            taker_key = f"{connector}_taker_fee_amount" if connector in DEXES else f"{connector}_taker_fee"
            all_dict.update({maker_key: new_fee_config_var(maker_key)})
            all_dict.update({taker_key: new_fee_config_var(taker_key)})
    return all_dict


fee_overrides_config_map = fee_overrides_dict()
