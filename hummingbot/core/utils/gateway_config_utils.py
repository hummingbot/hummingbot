from copy import deepcopy
from typing import List, Dict, Any, Optional


native_tokens = {"ethereum": "ETH", "avalanche": "AVAX", "solana": "SOL"}


def upsert_connection(connectors: List[Dict[str, Any]], connector, chain, network, wallet):
    new_connector = {"connector": connector, "chain": chain, "network": network, "trading_type": "on_chain", "wallet_address": wallet}

    updated = False

    for i, c in enumerate(connectors):
        if c["connector"] == connector and c["chain"] == chain and c["network"] == network:
            connectors[i] = new_connector
            updated = True
            break

    if updated is False:
        connectors.append(new_connector)


def build_wallet_display(lines: List[str], native_token: str, wallets: List[Dict[str, Any]]):
    """
    Display user wallets for a particular chain as a table
    """
    lines.append("+--------------|-------------------+")
    lines.append(f"| Wallet      | {native_token}       |")
    lines.append("+--------------|-------------------+")

    for dict in wallets:
        lines.append(f"| {dict['address']} | {dict['balance']} |")
    lines.append("+--------------|-------------------+")


def build_connector_display(lines: List[str], connectors: List[Dict[str, Any]]):
    """
    Display connector information as a table
    """
    lines.append("+--------------|-------------------|---------------+")
    lines.append("| Exchange     | Network           | Wallet        |")
    lines.append("+--------------|-------------------|---------------+")
    for dict in connectors:
        lines.append(f"| {dict['connector']} | {dict['chain']} - {dict['network']} | {dict['wallet_address']} |")
    lines.append("+--------------+-------------------+---------------+")


def build_config_dict_display(lines: List[str], config_dict: Dict[str, Any], level: int = 0):
    """
    Build display messages on lines for a config dictionary, this function is called recursive.
    For example:
    config_dict: {"a": 1, "b": {"ba": 2, "bb": 3}, "c": 4}
    lines will be
    a: 1
    b:
      ba: 2
      bb: 3
    c: 4
    :param lines: a list display message (lines) to be built upon.
    :param config_dict: a (Gateway) config dictionary
    :param level: a nested level.
    """
    prefix: str = "  " * level
    for k, v in config_dict.items():
        if isinstance(v, Dict):
            lines.append(f"{prefix}{k}:")
            build_config_dict_display(lines, v, level + 1)
        else:
            lines.append(f"{prefix}{k}: {v}")


def build_config_namespace_keys(namespace_keys: List[str], config_dict: Dict[str, Any], prefix: str = ""):
    """
    Build namespace keys for a config dictionary, this function is recursive.
    For example:
    config_dict: {"a": 1, "b": {"ba": 2, "bb": 3}, "c": 4}
    namepace_keys will be ["a", "b", "b.ba", "b.bb", "c"]
    :param namespace_keys: a key list to be build upon
    :param config_dict: a (Gateway) config dictionary
    :prefix: a prefix to the namespace (used when the function is called recursively.
    """
    for k, v in config_dict.items():
        namespace_keys.append(f"{prefix}{k}")
        if isinstance(v, Dict):
            build_config_namespace_keys(namespace_keys, v, f"{prefix}{k}.")


def search_configs(config_dict: Dict[str, Any], namespace_key: str) \
        -> Optional[Dict[str, Any]]:
    """
    Search the config dictionary for a given namespace key and preserve the key hierarchy.
    For example:
    config_dict:  {"a": 1, "b": {"ba": 2, "bb": 3}, "c": 4}
    searching for b will result in {"b": {"ba": 2, "bb": 3}}
    searching for b.ba will result in {"b": {"ba": 2}}
    :param config_dict: The config dictionary
    :param namespace_key: The namespace key to search for
    :return: A dictionary matching the given key, returns None if not found
    """
    key_parts = namespace_key.split(".")
    if not key_parts[0] in config_dict:
        return
    result: Dict[str, Any] = {key_parts[0]: deepcopy(config_dict[key_parts[0]])}
    result_val = result[key_parts[0]]
    for key_part in key_parts[1:]:
        if not isinstance(result_val, Dict) or key_part not in result_val:
            return
        temp = deepcopy(result_val[key_part])
        result_val.clear()
        result_val[key_part] = temp
        result_val = result_val[key_part]
    return result
