import importlib
from os import scandir
from os.path import (
    realpath,
    join,
)
from enum import Enum
from decimal import Decimal
from typing import List, NamedTuple, Dict, Any
from hummingbot import get_strategy_list
from pathlib import Path
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.event.events import TradeFeeType

# Global variables
required_exchanges: List[str] = []
requried_connector_trading_pairs: Dict[str, List[str]] = {}

# Global static values
KEYFILE_PREFIX = "key_file_"
KEYFILE_POSTFIX = ".json"
ENCYPTED_CONF_PREFIX = "encrypted_"
ENCYPTED_CONF_POSTFIX = ".json"
GLOBAL_CONFIG_PATH = "conf/conf_global.yml"
TRADE_FEES_CONFIG_PATH = "conf/conf_fee_overrides.yml"
TOKEN_ADDRESSES_FILE_PATH = "conf/erc20_tokens_override.json"
DEFAULT_KEY_FILE_PATH = "conf/"
DEFAULT_LOG_FILE_PATH = "logs/"
DEFAULT_ETHEREUM_RPC_URL = "https://mainnet.coinalpha.com/hummingbot-test-node"
TEMPLATE_PATH = realpath(join(__file__, "../../templates/"))
CONF_FILE_PATH = "conf/"
CONF_PREFIX = "conf_"
CONF_POSTFIX = "_strategy"
SCRIPTS_PATH = realpath(join(__file__, "../../../scripts/"))
CERTS_PATH = "certs/"

GATEAWAY_CA_CERT_PATH = realpath(join(__file__, join(f"../../../{CERTS_PATH}/ca_cert.pem")))
GATEAWAY_CLIENT_CERT_PATH = realpath(join(__file__, join(f"../../../{CERTS_PATH}/client_cert.pem")))
GATEAWAY_CLIENT_KEY_PATH = realpath(join(__file__, join(f"../../../{CERTS_PATH}/client_key.pem")))


class ConnectorType(Enum):
    Connector = 1
    Exchange = 2
    Derivative = 3


class ConnectorSetting(NamedTuple):
    name: str
    type: ConnectorType
    example_pair: str
    centralised: bool
    use_ethereum_wallet: bool
    fee_type: TradeFeeType
    fee_token: str
    default_fees: List[Decimal]
    config_keys: Dict[str, ConfigVar]
    is_sub_domain: bool
    parent_name: str
    domain_parameter: str
    use_eth_gas_lookup: bool

    def module_name(self) -> str:
        # returns connector module name, e.g. binance_exchange
        return f'{self.base_name()}_{self.type.name.lower()}'

    def module_path(self) -> str:
        # return connector full path name, e.g. hummingbot.connector.exchange.binance.binance_exchange
        return f'hummingbot.connector.{self.type.name.lower()}.{self.base_name()}.{self.module_name()}'

    def class_name(self) -> str:
        # return connector class name, e.g. BinanceExchange
        return "".join([o.capitalize() for o in self.module_name().split("_")])

    def conn_init_parameters(self, api_keys: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_sub_domain:
            return api_keys
        else:
            params = {k.replace(self.name, self.parent_name): v for k, v in api_keys.items()}
            params["domain"] = self.domain_parameter
            return params

    def add_domain_parameter(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_sub_domain:
            return params
        else:
            params["domain"] = self.domain_parameter
            return params

    def base_name(self) -> str:
        if self.is_sub_domain:
            return self.parent_name
        else:
            return self.name


def _create_connector_settings() -> Dict[str, ConnectorSetting]:
    connector_exceptions = ["paper_trade"]
    connector_settings = {}
    package_dir = Path(__file__).resolve().parent.parent.parent
    type_dirs = [f for f in scandir(f'{str(package_dir)}/hummingbot/connector') if f.is_dir()]
    for type_dir in type_dirs:
        connector_dirs = [f for f in scandir(type_dir.path) if f.is_dir()]
        for connector_dir in connector_dirs:
            if connector_dir.name.startswith("_") or \
                    connector_dir.name in connector_exceptions:
                continue
            if connector_dir.name in connector_settings:
                raise Exception(f"Multiple connectors with the same {connector_dir.name} name.")
            path = f"hummingbot.connector.{type_dir.name}.{connector_dir.name}.{connector_dir.name}_utils"
            try:
                util_module = importlib.import_module(path)
            except ModuleNotFoundError:
                continue
            fee_type = TradeFeeType.Percent
            fee_type_setting = getattr(util_module, "FEE_TYPE", None)
            if fee_type_setting is not None:
                fee_type = TradeFeeType[fee_type_setting]
            connector_settings[connector_dir.name] = ConnectorSetting(
                name=connector_dir.name,
                type=ConnectorType[type_dir.name.capitalize()],
                centralised=getattr(util_module, "CENTRALIZED", True),
                example_pair=getattr(util_module, "EXAMPLE_PAIR", ""),
                use_ethereum_wallet=getattr(util_module, "USE_ETHEREUM_WALLET", False),
                fee_type=fee_type,
                fee_token=getattr(util_module, "FEE_TOKEN", ""),
                default_fees=getattr(util_module, "DEFAULT_FEES", []),
                config_keys=getattr(util_module, "KEYS", {}),
                is_sub_domain=False,
                parent_name=None,
                domain_parameter=None,
                use_eth_gas_lookup=getattr(util_module, "USE_ETH_GAS_LOOKUP", False)
            )
            other_domains = getattr(util_module, "OTHER_DOMAINS", [])
            for domain in other_domains:
                parent = connector_settings[connector_dir.name]
                connector_settings[domain] = ConnectorSetting(
                    name=domain,
                    type=parent.type,
                    centralised=parent.centralised,
                    example_pair=util_module.OTHER_DOMAINS_EXAMPLE_PAIR[domain],
                    use_ethereum_wallet=parent.use_ethereum_wallet,
                    fee_type=parent.fee_type,
                    fee_token=parent.fee_token,
                    default_fees=util_module.OTHER_DOMAINS_DEFAULT_FEES[domain],
                    config_keys=util_module.OTHER_DOMAINS_KEYS[domain],
                    is_sub_domain=True,
                    parent_name=parent.name,
                    domain_parameter=util_module.OTHER_DOMAINS_PARAMETER[domain],
                    use_eth_gas_lookup=parent.use_eth_gas_lookup
                )
    return connector_settings


def ethereum_wallet_required() -> bool:
    return any(e in ETH_WALLET_CONNECTORS for e in required_exchanges)


def ethereum_gas_station_required() -> bool:
    return any(name for name, con_set in CONNECTOR_SETTINGS.items() if name in required_exchanges
               and con_set.use_eth_gas_lookup)


def ethereum_required_trading_pairs() -> List[str]:
    ret_val = []
    for conn, t_pair in requried_connector_trading_pairs.items():
        if CONNECTOR_SETTINGS[conn].use_ethereum_wallet:
            ret_val += t_pair
    return ret_val


MAXIMUM_OUTPUT_PANE_LINE_COUNT = 1000
MAXIMUM_LOG_PANE_LINE_COUNT = 1000
MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT = 100


CONNECTOR_SETTINGS = _create_connector_settings()
DERIVATIVES = {cs.name for cs in CONNECTOR_SETTINGS.values() if cs.type is ConnectorType.Derivative}
EXCHANGES = {cs.name for cs in CONNECTOR_SETTINGS.values() if cs.type is ConnectorType.Exchange}
OTHER_CONNECTORS = {cs.name for cs in CONNECTOR_SETTINGS.values() if cs.type is ConnectorType.Connector}
ETH_WALLET_CONNECTORS = {cs.name for cs in CONNECTOR_SETTINGS.values() if cs.use_ethereum_wallet}
ALL_CONNECTORS = {"exchange": EXCHANGES, "connector": OTHER_CONNECTORS, "derivative": DERIVATIVES}
EXAMPLE_PAIRS = {name: cs.example_pair for name, cs in CONNECTOR_SETTINGS.items()}
EXAMPLE_ASSETS = {name: cs.example_pair.split("-")[0] for name, cs in CONNECTOR_SETTINGS.items()}

STRATEGIES: List[str] = get_strategy_list()
