"""
Define ConnectorSetting class (contains metadata about the exchanges hummingbot can interact with), and a function to
generate a dictionary of exchange names to ConnectorSettings.
"""

import importlib
from decimal import Decimal
from enum import Enum
from os import scandir
from os.path import join, realpath
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Set, Union

from hummingbot import get_strategy_list
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Global variables
required_exchanges: List[str] = []
requried_connector_trading_pairs: Dict[str, List[str]] = {}
# Set these two variables if a strategy uses oracle for rate conversion
required_rate_oracle: bool = False
rate_oracle_pairs: List[str] = []

# Global static values
KEYFILE_PREFIX = "key_file_"
KEYFILE_POSTFIX = ".json"
ENCYPTED_CONF_PREFIX = "encrypted_"
ENCYPTED_CONF_POSTFIX = ".json"
GLOBAL_CONFIG_PATH = "conf/conf_global.yml"
TRADE_FEES_CONFIG_PATH = "conf/conf_fee_overrides.yml"
DEFAULT_KEY_FILE_PATH = "conf/"
DEFAULT_LOG_FILE_PATH = "logs/"
DEFAULT_ETHEREUM_RPC_URL = "https://mainnet.coinalpha.com/hummingbot-test-node"
TEMPLATE_PATH = realpath(join(__file__, "../../templates/"))
CONF_FILE_PATH = "conf/"
CONF_PREFIX = "conf_"
CONF_POSTFIX = "_strategy"
SCRIPTS_PATH = realpath(join(__file__, "../../../scripts/"))
CERTS_PATH = "certs/"

# Certificates for securely communicating with the gateway api
GATEAWAY_CA_CERT_PATH = realpath(join(__file__, join(f"../../../{CERTS_PATH}/ca_cert.pem")))
GATEAWAY_CLIENT_CERT_PATH = realpath(join(__file__, join(f"../../../{CERTS_PATH}/client_cert.pem")))
GATEAWAY_CLIENT_KEY_PATH = realpath(join(__file__, join(f"../../../{CERTS_PATH}/client_key.pem")))


class ConnectorType(Enum):
    """
    The types of exchanges that hummingbot client can communicate with.
    """

    Connector = "connector"
    Exchange = "exchange"
    Derivative = "derivative"


class ConnectorSetting(NamedTuple):
    name: str
    type: ConnectorType
    example_pair: str
    centralised: bool
    use_ethereum_wallet: bool
    trade_fee_schema: TradeFeeSchema
    config_keys: Dict[str, ConfigVar]
    is_sub_domain: bool
    parent_name: str
    domain_parameter: str
    use_eth_gas_lookup: bool
    """
    This class has metadata data about Exchange connections. The name of the connection and the file path location of
    the connector file.
    """

    def module_name(self) -> str:
        # returns connector module name, e.g. binance_exchange
        return f"{self.base_name()}_{self.type.name.lower()}"

    def module_path(self) -> str:
        # return connector full path name, e.g. hummingbot.connector.exchange.binance.binance_exchange
        return f"hummingbot.connector.{self.type.name.lower()}.{self.base_name()}.{self.module_name()}"

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


class AllConnectorSettings:

    all_connector_settings: Dict[str, ConnectorSetting] = {}

    @classmethod
    def create_connector_settings(cls):
        """
        Iterate over files in specific Python directories to create a dictionary of exchange names to ConnectorSetting.
        """
        connector_exceptions = ["paper_trade"]

        package_dir = Path(__file__).resolve().parent.parent.parent
        type_dirs = [f for f in scandir(f"{str(package_dir)}/hummingbot/connector") if f.is_dir()]
        for type_dir in type_dirs:
            connector_dirs = [f for f in scandir(type_dir.path) if f.is_dir()]
            for connector_dir in connector_dirs:
                if connector_dir.name.startswith("_") or connector_dir.name in connector_exceptions:
                    continue
                if connector_dir.name in cls.all_connector_settings:
                    raise Exception(f"Multiple connectors with the same {connector_dir.name} name.")
                path = f"hummingbot.connector.{type_dir.name}.{connector_dir.name}.{connector_dir.name}_utils"
                try:
                    util_module = importlib.import_module(path)
                except ModuleNotFoundError:
                    continue
                trade_fee_schema = getattr(util_module, "DEFAULT_FEES", None)
                trade_fee_schema = cls._validate_trade_fee_schema(connector_dir.name, trade_fee_schema)
                cls.all_connector_settings[connector_dir.name] = ConnectorSetting(
                    name=connector_dir.name,
                    type=ConnectorType[type_dir.name.capitalize()],
                    centralised=getattr(util_module, "CENTRALIZED", True),
                    example_pair=getattr(util_module, "EXAMPLE_PAIR", ""),
                    use_ethereum_wallet=getattr(util_module, "USE_ETHEREUM_WALLET", False),
                    trade_fee_schema=trade_fee_schema,
                    config_keys=getattr(util_module, "KEYS", {}),
                    is_sub_domain=False,
                    parent_name=None,
                    domain_parameter=None,
                    use_eth_gas_lookup=getattr(util_module, "USE_ETH_GAS_LOOKUP", False),
                )
                # Adds other domains of connector
                other_domains = getattr(util_module, "OTHER_DOMAINS", [])
                for domain in other_domains:
                    trade_fee_schema = getattr(util_module, "OTHER_DOMAINS_DEFAULT_FEES")[domain]
                    trade_fee_schema = cls._validate_trade_fee_schema(domain, trade_fee_schema)
                    parent = cls.all_connector_settings[connector_dir.name]
                    cls.all_connector_settings[domain] = ConnectorSetting(
                        name=domain,
                        type=parent.type,
                        centralised=parent.centralised,
                        example_pair=getattr(util_module, "OTHER_DOMAINS_EXAMPLE_PAIR")[domain],
                        use_ethereum_wallet=parent.use_ethereum_wallet,
                        trade_fee_schema=trade_fee_schema,
                        config_keys=getattr(util_module, "OTHER_DOMAINS_KEYS")[domain],
                        is_sub_domain=True,
                        parent_name=parent.name,
                        domain_parameter=getattr(util_module, "OTHER_DOMAINS_PARAMETER")[domain],
                        use_eth_gas_lookup=parent.use_eth_gas_lookup,
                    )

        return cls.all_connector_settings

    @classmethod
    def initialize_paper_trade_settings(cls, paper_trade_exchanges: List[str]):
        for e in paper_trade_exchanges:
            base_connector_settings: Optional[ConnectorSetting] = cls.all_connector_settings.get(e, None)
            if base_connector_settings:
                paper_trade_settings = ConnectorSetting(
                    name=f"{e}_paper_trade",
                    type=base_connector_settings.type,
                    centralised=base_connector_settings.centralised,
                    example_pair=base_connector_settings.example_pair,
                    use_ethereum_wallet=base_connector_settings.use_ethereum_wallet,
                    trade_fee_schema=base_connector_settings.trade_fee_schema,
                    config_keys=base_connector_settings.config_keys,
                    is_sub_domain=False,
                    parent_name=base_connector_settings.name,
                    domain_parameter=None,
                    use_eth_gas_lookup=base_connector_settings.use_eth_gas_lookup,
                )
                cls.all_connector_settings.update({f"{e}_paper_trade": paper_trade_settings})

    @classmethod
    def get_connector_settings(cls) -> Dict[str, ConnectorSetting]:
        if len(cls.all_connector_settings) == 0:
            cls.all_connector_settings = cls.create_connector_settings()
        return cls.all_connector_settings

    @classmethod
    def get_exchange_names(cls) -> Set[str]:
        return {cs.name for cs in cls.all_connector_settings.values() if cs.type is ConnectorType.Exchange}

    @classmethod
    def get_derivative_names(cls) -> Set[str]:
        return {cs.name for cs in cls.all_connector_settings.values() if cs.type is ConnectorType.Derivative}

    @classmethod
    def get_other_connector_names(cls) -> Set[str]:
        return {cs.name for cs in cls.all_connector_settings.values() if cs.type is ConnectorType.Connector}

    @classmethod
    def get_eth_wallet_connector_names(cls) -> Set[str]:
        return {cs.name for cs in cls.all_connector_settings.values() if cs.use_ethereum_wallet}

    @classmethod
    def get_all_connectors_map(cls) -> Dict[str, str]:
        return {
            ConnectorType.Exchange.value: cls.get_exchange_names(),
            ConnectorType.Derivative.value: cls.get_derivative_names(),
            ConnectorType.Connector.value: cls.get_other_connector_names(),
        }

    @classmethod
    def get_example_pairs(cls) -> Dict[str, str]:
        return {name: cs.example_pair for name, cs in cls.get_connector_settings().items()}

    @classmethod
    def get_example_assets(cls) -> Dict[str, str]:
        return {name: cs.example_pair.split("-")[0] for name, cs in cls.get_connector_settings().items()}

    @staticmethod
    def _validate_trade_fee_schema(
        exchange_name: str, trade_fee_schema: Optional[Union[TradeFeeSchema, List[float]]]
    ) -> TradeFeeSchema:
        if not isinstance(trade_fee_schema, TradeFeeSchema):
            # backward compatibility
            maker_percent_fee_decimal = (
                Decimal(str(trade_fee_schema[0])) / Decimal("100") if trade_fee_schema is not None else Decimal("0")
            )
            taker_percent_fee_decimal = (
                Decimal(str(trade_fee_schema[1])) / Decimal("100") if trade_fee_schema is not None else Decimal("0")
            )
            trade_fee_schema = TradeFeeSchema(
                maker_percent_fee_decimal=maker_percent_fee_decimal,
                taker_percent_fee_decimal=taker_percent_fee_decimal,
            )
        return trade_fee_schema


def ethereum_wallet_required() -> bool:
    """
    Check if an Ethereum wallet is required for any of the exchanges the user's config uses.
    """
    return any(e in AllConnectorSettings.get_eth_wallet_connector_names() for e in required_exchanges)


def ethereum_gas_station_required() -> bool:
    """
    Check if the user's config needs to look up gas costs from an Ethereum gas station.
    """
    return any(name for name, con_set in AllConnectorSettings.get_connector_settings().items() if name in required_exchanges
               and con_set.use_eth_gas_lookup)


def ethereum_required_trading_pairs() -> List[str]:
    """
    Check if the trading pairs require an ethereum wallet (ERC-20 tokens).
    """
    ret_val = []
    for conn, t_pair in requried_connector_trading_pairs.items():
        if AllConnectorSettings.get_connector_settings()[conn].use_ethereum_wallet:
            ret_val += t_pair
    return ret_val


MAXIMUM_OUTPUT_PANE_LINE_COUNT = 1000
MAXIMUM_LOG_PANE_LINE_COUNT = 1000
MAXIMUM_TRADE_FILLS_DISPLAY_OUTPUT = 100

STRATEGIES: List[str] = get_strategy_list()
