from typing import Any, Dict

from hummingbot.connector.utilities.oms_connector import oms_connector_constants as CONSTANTS


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    return (
        not exchange_info[CONSTANTS.IS_DISABLED_FIELD]
        and exchange_info[CONSTANTS.SESSION_STATUS_FIELD]
        and "ERR" not in exchange_info[CONSTANTS.SYMBOL_FIELD]
    )
