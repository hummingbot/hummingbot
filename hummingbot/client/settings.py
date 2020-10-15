import importlib
from os import scandir
from os.path import (
    realpath,
    join,
)
from enum import Enum
from decimal import Decimal
from typing import List, Set, NamedTuple
from hummingbot import get_strategy_list
from pathlib import Path
from hummingbot.client.config.config_var import ConfigVar

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


class ConnectorType(Enum):
    Connector = 1
    Exchange = 2
    Derivative = 3


class ConnectorFeeType(Enum):
    Percent = 1
    FlatFee = 2


class ConnectorSetting(NamedTuple):
    name: str
    type: ConnectorType
    example_pair: str
    centralised: bool
    use_ethereum_wallet: bool
    fee_type: ConnectorFeeType
    default_fees: List[Decimal]
    config_keys: List[ConfigVar]


def _create_connector_setting_list() -> List[ConnectorSetting]:
    connector_exceptions = ["paper_trade"]
    connector_settings = []
    package_dir = Path(__file__).resolve().parent.parent.parent
    type_dirs = [f for f in scandir(f'{str(package_dir)}/hummingbot/connector') if f.is_dir()]
    for type_dir in type_dirs:
        connector_dirs = [f for f in scandir(type_dir.path) if f.is_dir()]
        for connector_dir in connector_dirs:
            if connector_dir.name.startswith("_") or \
                    connector_dir.name in connector_exceptions or \
                    not any(f.name == f"{connector_dir.name}_utils.py" for f in scandir(connector_dir.path)):
                continue
            path = f"hummingbot.connector.{type_dir.name}.{connector_dir.name}.{connector_dir.name}_utils"
            util_module = importlib.import_module(path)
            connector_settings.append(
                ConnectorSetting(
                    name=connector_dir.name,
                    type=ConnectorType[type_dir.name.capitalize()],
                    centralised=getattr(util_module, "CENTRALIZED", True),
                    example_pair=getattr(util_module, "EXAMPLE_PAIR", ""),
                    use_ethereum_wallet=getattr(util_module, "USE_ETHEREUM_WALLET", False),
                    fee_type=getattr(util_module, "FEE_TYPE", ConnectorFeeType.Percent),
                    default_fees=getattr(util_module, "DEFAULT_FEES", []),
                    config_keys=getattr(util_module, "KEYS", [])
                )
            )
    return connector_settings


def _get_exchanges(cex: bool = True) -> Set[str]:
    invalid_names = ["__pycache__", "paper_trade"]
    exchanges = set()
    package_dir = Path(__file__).resolve().parent.parent.parent
    connectors = [f.name for f in scandir(f'{str(package_dir)}/hummingbot/connector/exchange') if
                  f.is_dir() and f.name not in invalid_names]
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


def _get_derivatives() -> Set[str]:
    invalid_names = ["__pycache__"]
    derivatives = set()
    try:
        package_dir = Path(__file__).resolve().parent.parent.parent
        connectors = [f.name for f in scandir(f'{str(package_dir)}/hummingbot/connector/derivative')
                      if f.is_dir() and f.name not in invalid_names]
        derivatives.update(connectors)
    except Exception:
        pass
    return derivatives


def _get_other_connectors() -> Set[str]:
    invalid_names = ["__pycache__"]
    others = set()
    try:
        package_dir = Path(__file__).resolve().parent.parent.parent
        connectors = [f.name for f in scandir(f'{str(package_dir)}/hummingbot/connector/connector')
                      if f.is_dir() and f.name not in invalid_names]
        others.update(connectors)
    except Exception:
        pass
    return others


def _get_example_asset(pair=True):
    pairs = []
    fetched_connectors = []
    for connector_type, connectors in ALL_CONNECTORS.items():
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


MAXIMUM_OUTPUT_PANE_LINE_COUNT = 1000
MAXIMUM_LOG_PANE_LINE_COUNT = 1000
MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT = 100


# CONNECTOR_SETTINGS = _create_connector_setting_list()
# DERIVATIVES = {cs.name for cs in CONNECTOR_SETTINGS if cs.type is ConnectorType.Derivative}
# CEXES = {cs.name for cs in CONNECTOR_SETTINGS if cs.type is ConnectorType.Exchange and cs.centralised}
# DEXES = {cs.name for cs in CONNECTOR_SETTINGS if cs.type is ConnectorType.Exchange and not cs.centralised}
# OTHER_CONNECTORS = {cs.name for cs in CONNECTOR_SETTINGS if cs.type is ConnectorType.Connector}
# EXCHANGES = {cs.name for cs in CONNECTOR_SETTINGS if cs.type is ConnectorType.Exchange}
# ALL_CONNECTORS = {"exchange": EXCHANGES, "connector": OTHER_CONNECTORS, "derivative": DERIVATIVES}
# STRATEGIES: List[str] = get_strategy_list()
# EXAMPLE_PAIRS = {cs.name: [cs.example_pair] for cs in CONNECTOR_SETTINGS}
# EXAMPLE_ASSETS = {cs.name: list(cs.example_pair.split("-")) for cs in CONNECTOR_SETTINGS}

# CONNECTOR_SETTINGS = _create_connector_setting_list()
DERIVATIVES = _get_derivatives()
CEXES = _get_exchanges(True)
DEXES = _get_exchanges(False)
OTHER_CONNECTORS = _get_other_connectors()
EXCHANGES = CEXES.union(DEXES)
ALL_CONNECTORS = {"exchange": EXCHANGES, "connector": OTHER_CONNECTORS, "derivative": DERIVATIVES}
STRATEGIES: List[str] = get_strategy_list()
EXAMPLE_PAIRS = _get_example_asset()
EXAMPLE_ASSETS = _get_example_asset(False)
