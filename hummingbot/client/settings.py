import importlib
from os import scandir
from os.path import (
    realpath,
    join,
)
from typing import List

from hummingbot import get_strategy_list

# Global variables
required_exchanges: List[str] = []

# Global static values
KEYFILE_PREFIX = "key_file_"
KEYFILE_POSTFIX = ".json"
ENCYPTED_CONF_PREFIX = "encrypted_"
ENCYPTED_CONF_POSTFIX = ".json"
GLOBAL_CONFIG_PATH = "conf/conf_global.yml"
TRADE_FEES_CONFIG_PATH = "conf/conf_fee_overrides.yml"
TOKEN_ADDRESSES_FILE_PATH = realpath(join(__file__, "../../wallet/ethereum/erc20_tokens.json"))
DEFAULT_KEY_FILE_PATH = "conf/"
DEFAULT_LOG_FILE_PATH = "logs/"
DEFAULT_ETHEREUM_RPC_URL = "https://mainnet.coinalpha.com/hummingbot-test-node"
TEMPLATE_PATH = realpath(join(__file__, "../../templates/"))
CONF_FILE_PATH = "conf/"
CONF_PREFIX = "conf_"
CONF_POSTFIX = "_strategy"
SCRIPTS_PATH = "scripts/"


def get_exchange_list(cex=True):
    invalid_names = ["__pycache__", "paper_trade"]
    exchanges = set()
    connectors = [f.name for f in scandir('./hummingbot/connector/exchange') if f.is_dir() and f.name not in invalid_names]
    for connector in connectors:
        try:
            path = f"hummingbot.connector.exchange.{connector}.{connector}_utils"
            is_cex = getattr(importlib.import_module(path), "CENTRALIZED")
            if cex and is_cex:
                exchanges.add(connector)
            elif not cex and not is_cex:
                exchanges.add(connector)
        except Exception:
            continue
    return exchanges


def get_derivatives():
    invalid_names = ["__pycache__"]
    derivatives = set()
    try:
        connectors = [f.name for f in scandir('./hummingbot/connector/derivative') if f.is_dir() and f.name not in invalid_names]
        derivatives.update(connectors)
    except Exception:
        pass
    return derivatives


def get_exchanges_and_derivatives():
    invalid_names = ["__pycache__", "paper_trade"]
    all_connectors = {}
    connector_types = ["exchange", "derivative"]
    for connector_type in connector_types:
        try:
            all_connectors[connector_type] = [f.name for f in scandir(f'./hummingbot/connector/{connector_type}') if f.is_dir() and f.name not in invalid_names]
        except Exception:
            continue
    return all_connectors


def get_example_asset(pair=True):
    pairs = []
    fetched_connectors = []
    all_connectors = get_exchanges_and_derivatives()
    for connector_type, connectors in all_connectors.items():
        for connector in connectors:
            module_path = f"hummingbot.connector.{connector_type}.{connector}.{connector}_utils"
            try:
                if pair:
                    pairs.append(getattr(importlib.import_module(module_path), "EXAMPLE_PAIR"))
                else:
                    pairs.append(getattr(importlib.import_module(module_path), "EXAMPLE_PAIR").split("-")[0])
            except Exception:
                continue
            fetched_connectors.append(connector)
    return dict(zip(fetched_connectors, pairs))


DERIVATIVES = get_derivatives()

DEXES = get_exchange_list(False)

# To-do: create CONNECTOR constant hold all types of connectors(i.e to replace EXCHANGES)
# So EXCHANGES only hold the name of centralized exchanges
EXCHANGES = DERIVATIVES.union(get_exchange_list()).union(DEXES)

STRATEGIES: List[str] = get_strategy_list()

EXAMPLE_PAIRS = get_example_asset()

EXAMPLE_ASSETS = get_example_asset(False)

MAXIMUM_OUTPUT_PANE_LINE_COUNT = 1000
MAXIMUM_LOG_PANE_LINE_COUNT = 1000
MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT = 100
