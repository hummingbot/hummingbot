from os import scandir
import importlib


def fee_overrides_dict():
    all_dict = {}
    invalid_names = ["__pycache__", "paper_trade"]
    connector_types = ["exchange", "derivative"]
    for connector_type in connector_types:
        try:
            connectors = [f.name for f in scandir(f'./hummingbot/connector/{connector_type}') if f.is_dir() and f.name not in invalid_names]
        except Exception:
            continue
        for connector in connectors:
            try:
                module_path = f"hummingbot.connector.{connector_type}.{connector}.{connector}_utils"
                all_dict.update(getattr(importlib.import_module(module_path), "FEE_OVERRIDE_MAP"))
            except Exception:
                continue
    return all_dict


fee_overrides_config_map = fee_overrides_dict()
