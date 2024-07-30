from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

native_tokens = {
    "ethereum": "ETH",
    "avalanche": "AVAX",
    "algorand": "ALGO",
    "cosmos": "ATOM",
    "celo": "CELO",
    "osmosis": "OSMO",
    "polygon": "MATIC",
    "harmony": "ONE",
    "binance-smart-chain": "BNB",
    "cronos": "CRO",
    "near": "NEAR",
    "injective": "INJ",
    "xdc": "XDC",
    "tezos": "XTZ",
    "xrpl": "XRP",
    "kujira": "KUJI",
    "telos": "TLOS"
}

SUPPORTED_CHAINS = set(native_tokens.keys())


def flatten(items):
    """
    Deep flatten any iterable item.
    """
    for x in items:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            yield from flatten(x)
        else:
            yield x


def list_gateway_wallets(wallets: List[Any], chain: str) -> List[str]:
    """
    Get the public keys for a chain supported by gateway.
    """
    return list(flatten([w["walletAddresses"] for w in wallets if w["chain"] == chain]))


def build_wallet_display(native_token: str, wallets: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Display user wallets for a particular chain as a table
    """
    columns = ["Wallet", native_token]
    data = []
    for dict in wallets:
        data.extend([[dict['address'], dict['balance']]])

    return pd.DataFrame(data=data, columns=columns)


def build_connector_display(connectors: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Display connector information as a table
    """
    columns = ["Exchange", "Network", "Wallet"]
    data = []
    for connector_spec in connectors:
        data.extend([
            [
                connector_spec["connector"],
                f"{connector_spec['chain']} - {connector_spec['network']}",
                connector_spec["wallet_address"],
            ]
        ])

    return pd.DataFrame(data=data, columns=columns)


def build_list_display(connectors: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Display connector information as a table
    """
    columns = ["Exchange", "Chains"]
    data = []
    for connector_spec in connectors:
        data.extend([
            [
                connector_spec["name"],
                ', '.join(connector_spec['chains']),
            ]
        ])

    return pd.DataFrame(data=data, columns=columns)


def build_connector_tokens_display(connectors_chain_network: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Display connector and the tokens the balance command will report on
    """
    columns = ["Exchange", "Report Token Balances"]
    data = []
    for connector_spec in connectors_chain_network:
        data.extend([
            [
                f"{connector_spec['connector']}_{connector_spec['chain']}_{connector_spec['network']}",
                connector_spec.get("tokens", ""),
            ]
        ])

    return pd.DataFrame(data=data, columns=columns)


def build_balances_allowances_display(symbols: List[str], balances: List[str], allowances: List[str]) -> pd.DataFrame:
    """
    Display balances and allowances for a list of symbols as a table
    """
    columns = ["Symbol", "Balance", "Allowances"]
    data = []
    for i in range(len(symbols)):
        data.extend([
            [
                symbols[i],
                balances[i],
                allowances[i]
            ]
        ])

    return pd.DataFrame(data=data, columns=columns)


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
