from copy import deepcopy
from typing import List, Dict, Any, Optional


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


def find_key_ignore_case(a_dict: Dict[str, Any], key: str) -> Optional[str]:
    matched_keys = [k for k in a_dict.keys() if k.lower() == key.lower()]
    if matched_keys:
        return matched_keys[0]


def search_configs(config_dict: Dict[str, Any], namespace_key: str, ignore_case: bool = False) \
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
    def find_matched_key(a_dict: Dict[str, Any], a_key: str) -> Optional[str]:
        if not ignore_case and a_key in a_dict:
            return a_key
        if ignore_case:
            return find_key_ignore_case(a_dict, a_key)
    key_parts = namespace_key.split(".")
    matched_key = find_matched_key(config_dict, key_parts[0])
    if not matched_key:
        return
    result: Dict[str, Any] = {matched_key: deepcopy(config_dict[matched_key])}
    result_val = result[matched_key]
    for key_part in key_parts[1:]:
        if not isinstance(result_val, Dict):
            return
        matched_key = find_matched_key(result_val, key_part)
        if not matched_key:
            return
        temp = deepcopy(result_val[matched_key])
        result_val.clear()
        result_val[matched_key] = temp
        result_val = result_val[matched_key]
    return result
