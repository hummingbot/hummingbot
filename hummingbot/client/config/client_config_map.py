import json
import random
import re
from abc import ABC, abstractmethod
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Union

from pydantic import BaseModel, Field, SecretStr, root_validator, validator
from tabulate import tabulate_formats

from hummingbot.client.config.config_data_types import BaseClientModel, ClientConfigEnum, ClientFieldData
from hummingbot.client.config.config_methods import using_exchange as using_exchange_pointer
from hummingbot.client.config.config_validators import validate_bool, validate_float
from hummingbot.client.settings import DEFAULT_GATEWAY_CERTS_PATH, DEFAULT_LOG_FILE_PATH, AllConnectorSettings
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.connector_metrics_collector import (
    DummyMetricsCollector,
    MetricsCollector,
    TradeVolumeMetricCollector,
)
from hummingbot.connector.exchange.binance.binance_utils import BinanceConfigMap
from hummingbot.connector.exchange.gate_io.gate_io_utils import GateIOConfigMap
from hummingbot.connector.exchange.kraken.kraken_utils import KrakenConfigMap
from hummingbot.connector.exchange.kucoin.kucoin_utils import KuCoinConfigMap
from hummingbot.core.rate_oracle.rate_oracle import RATE_ORACLE_SOURCES, RateOracle
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils.kill_switch import ActiveKillSwitch, KillSwitch, PassThroughKillSwitch
from hummingbot.notifier.telegram_notifier import TelegramNotifier

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication

PMM_SCRIPT_ENABLED_KEY = "pmm_script_enabled"
PMM_SCRIPT_FILE_PATH_KEY = "pmm_script_file_path"


def generate_client_id() -> str:
    vals = [random.choice(range(0, 256)) for i in range(0, 20)]
    return "".join([f"{val:02x}" for val in vals])


def using_exchange(exchange: str) -> Callable:
    return using_exchange_pointer(exchange)


class MQTTBridgeConfigMap(BaseClientModel):
    mqtt_host: str = Field(
        default="localhost",
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Set the MQTT hostname to connect to (e.g. localhost)"
            ),
        ),
    )
    mqtt_port: int = Field(
        default=1883,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Set the MQTT port to connect to (e.g. 1883)"
            ),
        ),
    )
    mqtt_username: str = Field(
        default="",
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Set the username for connecting to the MQTT broker"
            ),
        ),
    )
    mqtt_password: str = Field(
        default="",
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Set the password for connecting to the MQTT broker"
            ),
        ),
    )
    mqtt_namespace: str = Field(
        default='hbot',
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Set the mqtt uri namespace (Default='hbot')"
            ),
        ),
    )
    mqtt_ssl: bool = Field(
        default=False,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enable/Disable SSL for MQTT connections"
            ),
        ),
    )
    mqtt_logger: bool = Field(
        default=True
    )
    mqtt_notifier: bool = Field(
        default=True,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enable/Disable MQTT Notifier"
            ),
        ),
    )
    mqtt_commands: bool = Field(
        default=True,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enable/Disable MQTT Commands"
            ),
        ),
    )
    mqtt_events: bool = Field(
        default=True,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enable/Disable Events forwarding to MQTT broker"
            ),
        ),
    )
    mqtt_external_events: bool = Field(
        default=True,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enable/Disable External MQTT Event listener"
            ),
        ),
    )
    mqtt_autostart: bool = Field(
        default=False,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enable/Disable autostart"
            ),
        ),
    )

    class Config:
        title = "mqtt_bridge"


class MarketDataCollectionConfigMap(BaseClientModel):
    market_data_collection_enabled: bool = Field(
        default=False,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enable/Disable Market Data Collection"
            ),
        ),
    )
    market_data_collection_interval: int = Field(
        default=60,
        ge=1,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Set the market data collection interval in seconds (Default=60)"
            ),
        ),
    )
    market_data_collection_depth: int = Field(
        default=20,
        ge=2,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Set the order book collection depth (Default=20)"
            ),
        ),
    )

    class Config:
        title = "market_data_collection"


class ColorConfigMap(BaseClientModel):
    top_pane: str = Field(
        default="#000000",
        client_data=ClientFieldData(
            prompt=lambda cm: "What is the background color of the top pane?",
        ),
    )
    bottom_pane: str = Field(
        default="#000000",
        client_data=ClientFieldData(
            prompt=lambda cm: "What is the background color of the bottom pane?",
        ),
    )
    output_pane: str = Field(
        default="#262626",
        client_data=ClientFieldData(
            prompt=lambda cm: "What is the background color of the output pane?",
        ),
    )
    input_pane: str = Field(
        default="#1C1C1C",
        client_data=ClientFieldData(
            prompt=lambda cm: "What is the background color of the input pane?",
        ),
    )
    logs_pane: str = Field(
        default="#121212",
        client_data=ClientFieldData(
            prompt=lambda cm: "What is the background color of the logs pane?",
        ),
    )
    terminal_primary: str = Field(
        default="#5FFFD7",
        client_data=ClientFieldData(
            prompt=lambda cm: "What is the terminal primary color?",
        ),
    )
    primary_label: str = Field(
        default="#5FFFD7",
        client_data=ClientFieldData(
            prompt=lambda cm: "What is the background color for primary label?",
        ),
    )
    secondary_label: str = Field(
        default="#FFFFFF",
        client_data=ClientFieldData(
            prompt=lambda cm: "What is the background color for secondary label?",
        ),
    )
    success_label: str = Field(
        default="#5FFFD7",
        client_data=ClientFieldData(
            prompt=lambda cm: "What is the background color for success label?",
        ),
    )
    warning_label: str = Field(
        default="#FFFF00",
        client_data=ClientFieldData(
            prompt=lambda cm: "What is the background color for warning label?",
        ),
    )
    info_label: str = Field(
        default="#5FD7FF",
        client_data=ClientFieldData(
            prompt=lambda cm: "What is the background color for info label?",
        ),
    )
    error_label: str = Field(
        default="#FF0000",
        client_data=ClientFieldData(
            prompt=lambda cm: "What is the background color for error label?",
        ),
    )
    gold_label: str = Field(
        default="#FFD700",
        client_data=ClientFieldData(
            prompt=lambda cm: "What is the background color for gold label?",
        ),
    )
    silver_label: str = Field(
        default="#C0C0C0",
        client_data=ClientFieldData(
            prompt=lambda cm: "What is the background color for silver label?",
        ),
    )
    bronze_label: str = Field(
        default="#CD7F32",
        client_data=ClientFieldData(
            prompt=lambda cm: "What is the background color for bronze label?",
        ),
    )

    @validator(
        "top_pane",
        "bottom_pane",
        "output_pane",
        "input_pane",
        "logs_pane",
        "terminal_primary",
        "primary_label",
        "secondary_label",
        "success_label",
        "warning_label",
        "info_label",
        "error_label",
        "gold_label",
        "silver_label",
        "bronze_label",
        pre=True,
    )
    def validate_color(cls, v: str):
        if not re.search(r'^#(?:[0-9a-fA-F]{2}){3}$', v):
            raise ValueError("Invalid color code")
        return v


class PaperTradeConfigMap(BaseClientModel):
    paper_trade_exchanges: List = Field(
        default=[
            BinanceConfigMap.Config.title,
            KuCoinConfigMap.Config.title,
            KrakenConfigMap.Config.title,
            GateIOConfigMap.Config.title,
        ],
    )
    paper_trade_account_balance: Dict[str, float] = Field(
        default={
            "BTC": 1,
            "USDT": 100000,
            "USDC": 100000,
            "ETH": 20,
            "WETH": 20,
            "SOL": 100,
            "DOGE": 1000000,
            "HBOT": 10000000,
        },
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enter paper trade balance settings (Input must be valid json — "
                "e.g. {\"ETH\": 10, \"USDC\": 50000})"
            ),
        ),
    )

    @validator("paper_trade_account_balance", pre=True)
    def validate_paper_trade_account_balance(cls, v: Union[str, Dict[str, float]]):
        if isinstance(v, str):
            v = json.loads(v)
        return v


class KillSwitchMode(BaseClientModel, ABC):
    @abstractmethod
    def get_kill_switch(self, hb: "HummingbotApplication") -> KillSwitch:
        ...


class KillSwitchEnabledMode(KillSwitchMode):
    kill_switch_rate: Decimal = Field(
        default=...,
        ge=Decimal(-100),
        le=Decimal(100),
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "At what profit/loss rate would you like the bot to stop?"
                " (e.g. -5 equals 5 percent loss)"
            ),
        ),
    )

    class Config:
        title = "kill_switch_enabled"

    def get_kill_switch(self, hb: "HummingbotApplication") -> ActiveKillSwitch:
        kill_switch = ActiveKillSwitch(kill_switch_rate=self.kill_switch_rate, hummingbot_application=hb)
        return kill_switch

    @validator("kill_switch_rate", pre=True)
    def validate_decimal(cls, v: str, field: Field):
        """Used for client-friendly error output."""
        return super().validate_decimal(v, field)


class KillSwitchDisabledMode(KillSwitchMode):
    class Config:
        title = "kill_switch_disabled"

    def get_kill_switch(self, hb: "HummingbotApplication") -> PassThroughKillSwitch:
        kill_switch = PassThroughKillSwitch()
        return kill_switch


KILL_SWITCH_MODES = {
    KillSwitchEnabledMode.Config.title: KillSwitchEnabledMode,
    KillSwitchDisabledMode.Config.title: KillSwitchDisabledMode,
}


class AutofillImportEnum(str, ClientConfigEnum):
    start = "start"
    config = "config"
    disabled = "disabled"


class TelegramMode(BaseClientModel, ABC):
    @abstractmethod
    def get_notifiers(self, hb: "HummingbotApplication") -> List[TelegramNotifier]:
        ...


class TelegramEnabledMode(TelegramMode):
    telegram_token: str = Field(
        default=...,
        client_data=ClientFieldData(prompt=lambda cm: "What is your telegram token?"),
    )
    telegram_chat_id: str = Field(
        default=...,
        client_data=ClientFieldData(prompt=lambda cm: "What is your telegram chat id?"),
    )

    class Config:
        title = "telegram_enabled"

    def get_notifiers(self, hb: "HummingbotApplication") -> List[TelegramNotifier]:
        notifiers = [
            TelegramNotifier(token=self.telegram_token, chat_id=self.telegram_chat_id, hb=hb)
        ]
        return notifiers


class TelegramDisabledMode(TelegramMode):
    class Config:
        title = "telegram_disabled"

    def get_notifiers(self, hb: "HummingbotApplication") -> List[TelegramNotifier]:
        return []


TELEGRAM_MODES = {
    TelegramEnabledMode.Config.title: TelegramEnabledMode,
    TelegramDisabledMode.Config.title: TelegramDisabledMode,
}


class DBMode(BaseClientModel, ABC):
    @abstractmethod
    def get_url(self, db_path: str) -> str:
        ...


class DBSqliteMode(DBMode):
    db_engine: str = Field(
        default="sqlite",
        const=True,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Please enter database engine you want to use (reference: https://docs.sqlalchemy.org/en/13/dialects/)"
            ),
        ),
    )

    class Config:
        title = "sqlite_db_engine"

    def get_url(self, db_path: str) -> str:
        return f"{self.db_engine}:///{db_path}"


class DBOtherMode(DBMode):
    db_engine: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Please enter database engine you want to use (reference: https://docs.sqlalchemy.org/en/13/dialects/)"
            ),
        ),
    )
    db_host: str = Field(
        default="127.0.0.1",
        client_data=ClientFieldData(
            prompt=lambda cm: "Please enter your DB host address",
        ),
    )
    db_port: int = Field(
        default=3306,
        client_data=ClientFieldData(
            prompt=lambda cm: "Please enter your DB port",
        ),
    )
    db_username: str = Field(
        defaul="username",
        client_data=ClientFieldData(
            prompt=lambda cm: "Please enter your DB username",
        ),
    )
    db_password: str = Field(
        default="password",
        client_data=ClientFieldData(
            prompt=lambda cm: "Please enter your DB password",
        ),
    )
    db_name: str = Field(
        default="dbname",
        client_data=ClientFieldData(
            prompt=lambda cm: "Please enter your the name of your DB",
        ),
    )

    class Config:
        title = "other_db_engine"

    def get_url(self, db_path: str) -> str:
        return f"{self.db_engine}://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @validator("db_engine")
    def validate_db_engine(cls, v: str):
        assert v != "sqlite"
        return v


DB_MODES = {
    DBSqliteMode.Config.title: DBSqliteMode,
    DBOtherMode.Config.title: DBOtherMode,
}


class GatewayConfigMap(BaseClientModel):
    gateway_api_host: str = Field(
        default="localhost",
        client_data=ClientFieldData(
            prompt=lambda cm: "Please enter your Gateway API host",
        ),
    )
    gateway_api_port: str = Field(
        default="15888",
        client_data=ClientFieldData(
            prompt=lambda cm: "Please enter your Gateway API port",
        ),
    )

    class Config:
        title = "gateway"


class GlobalTokenConfigMap(BaseClientModel):
    global_token_name: str = Field(
        default="USDT",
        client_data=ClientFieldData(
            prompt=lambda
                cm: "What is your default display token? (e.g. USD,EUR,BTC)",
        ),
    )
    global_token_symbol: str = Field(
        default="$",
        client_data=ClientFieldData(
            prompt=lambda
                cm: "What is your default display token symbol? (e.g. $,€)",
        ),
    )

    class Config:
        title = "global_token"

    @validator("global_token_name")
    def validate_global_token_name(cls, v: str) -> str:
        return v.upper()

    # === post-validations ===

    @root_validator()
    def post_validations(cls, values: Dict):
        cls.global_token_on_validated(values)
        return values

    @classmethod
    def global_token_on_validated(cls, values: Dict):
        RateOracle.get_instance().quote_token = values["global_token_name"]


class CommandsTimeoutConfigMap(BaseClientModel):
    create_command_timeout: Decimal = Field(
        default=Decimal("10"),
        gt=Decimal("0"),
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Network timeout when fetching the minimum order amount in the create command (in seconds)"
            ),
        ),
    )
    other_commands_timeout: Decimal = Field(
        default=Decimal("30"),
        gt=Decimal("0"),
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Network timeout to apply to the other commands' API calls"
                " (i.e. import, connect, balance, history; in seconds)"
            ),
        ),
    )

    class Config:
        title = "commands_timeout"

    @validator(
        "create_command_timeout",
        "other_commands_timeout",
        pre=True,
    )
    def validate_decimals(cls, v: str, field: Field):
        """Used for client-friendly error output."""
        return super().validate_decimal(v, field)


class AnonymizedMetricsMode(BaseClientModel, ABC):
    @abstractmethod
    def get_collector(
            self,
            connector: ConnectorBase,
            rate_provider: RateOracle,
            instance_id: str,
            valuation_token: str = "USDT",
    ) -> MetricsCollector:
        ...


class AnonymizedMetricsDisabledMode(AnonymizedMetricsMode):
    class Config:
        title = "anonymized_metrics_disabled"

    def get_collector(
            self,
            connector: ConnectorBase,
            rate_provider: RateOracle,
            instance_id: str,
            valuation_token: str = "USDT",
    ) -> MetricsCollector:
        return DummyMetricsCollector()


class AnonymizedMetricsEnabledMode(AnonymizedMetricsMode):
    anonymized_metrics_interval_min: Decimal = Field(
        default=Decimal("15"),
        gt=Decimal("0"),
        client_data=ClientFieldData(
            prompt=lambda cm: "How often do you want to send the anonymized metrics (Enter 5 for 5 minutes)?",
        ),
    )

    class Config:
        title = "anonymized_metrics_enabled"

    def get_collector(
            self,
            connector: ConnectorBase,
            rate_provider: RateOracle,
            instance_id: str,
            valuation_token: str = "USDT",
    ) -> MetricsCollector:
        instance = TradeVolumeMetricCollector(
            connector=connector,
            activation_interval=self.anonymized_metrics_interval_min,
            rate_provider=rate_provider,
            instance_id=instance_id,
            valuation_token=valuation_token,
        )
        return instance

    @validator("anonymized_metrics_interval_min", pre=True)
    def validate_decimal(cls, v: str, field: Field):
        """Used for client-friendly error output."""
        return super().validate_decimal(v, field)


METRICS_MODES = {
    AnonymizedMetricsDisabledMode.Config.title: AnonymizedMetricsDisabledMode,
    AnonymizedMetricsEnabledMode.Config.title: AnonymizedMetricsEnabledMode,
}


class RateSourceModeBase(BaseClientModel, ABC):
    @abstractmethod
    def build_rate_source(self) -> RateSourceBase:
        ...


class ExchangeRateSourceModeBase(RateSourceModeBase):
    def build_rate_source(self) -> RateSourceBase:
        return RATE_ORACLE_SOURCES[self.Config.title]()


class AscendExRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(
        default="ascend_ex",
        const=True,
        client_data=None,
    )

    class Config:
        title = "ascend_ex"


class BinanceRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(
        default="binance",
        const=True,
        client_data=None,
    )

    class Config:
        title = "binance"


class BinanceUSRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(
        default="binance_us",
        const=True,
        client_data=None,
    )

    class Config:
        title = "binance_us"


class CubeRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(
        default="cube",
        const=True,
        client_data=None,
    )

    class Config:
        title = "cube"


class CoinGeckoRateSourceMode(RateSourceModeBase):
    name: str = Field(
        default="coin_gecko",
        const=True,
        client_data=None,
    )

    extra_tokens: List[str] = Field(
        default=[],
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "List of comma-delimited CoinGecko token ids to always include"
                " in CoinGecko rates query (e.g. frontier-token,pax-gold,rbtc — empty to skip)"
            ),
            prompt_on_new=True,
        )
    )

    class Config:
        title = "coin_gecko"

    def build_rate_source(self) -> RateSourceBase:
        rate_source = RATE_ORACLE_SOURCES[self.Config.title](
            extra_token_ids=self.extra_tokens
        )
        rate_source.extra_token_ids = self.extra_tokens
        return rate_source

    @validator("extra_tokens", pre=True)
    def validate_extra_tokens(cls, value: Union[str, List[str]]):
        extra_tokens = value.split(",") if isinstance(value, str) else value
        return extra_tokens

    @root_validator()
    def post_validations(cls, values: Dict):
        RateOracle.get_instance().source.extra_token_ids = values["extra_tokens"]
        return values


class CoinCapRateSourceMode(RateSourceModeBase):
    name: str = Field(
        default="coin_cap",
        const=True,
        client_data=None,
    )
    assets_map: Dict[str, str] = Field(
        default=",".join(
            [
                ":".join(pair) for pair in {
                    "BTC": "bitcoin",
                    "ETH": "ethereum",
                    "USDT": "tether",
                    "CONV": "convergence",
                    "FIRO": "zcoin",
                    "BUSD": "binance-usd",
                    "ONE": "harmony",
                    "PDEX": "polkadex",
                }.items()
            ]
        ),
        description=(
            "The symbol-to-asset ID map for CoinCap. Assets IDs can be found by selecting a symbol"
            " on https://coincap.io/ and extracting the last segment of the URL path."
        ),
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "CoinCap symbol-to-asset ID map (e.g. 'BTC:bitcoin,ETH:ethereum', find IDs on https://coincap.io/"
                " by selecting a symbol and extracting the last segment of the URL path)"
            ),
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    api_key: SecretStr = Field(
        default=SecretStr(""),
        description="API key to use to request information from CoinCap (if empty public requests will be used)",
        client_data=ClientFieldData(
            prompt=lambda cm: "CoinCap API key (optional, but improves rate limits)",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "coin_cap"

    def build_rate_source(self) -> RateSourceBase:
        rate_source = RATE_ORACLE_SOURCES["coin_cap"](
            assets_map=self.assets_map, api_key=self.api_key.get_secret_value()
        )
        return rate_source

    @validator("assets_map", pre=True)
    def validate_extra_tokens(cls, value: Union[str, Dict[str, str]]):
        if isinstance(value, str):
            value = {key: val for key, val in [v.split(":") for v in value.split(",")]}
        return value

    # === post-validations ===

    @root_validator()
    def post_validations(cls, values: Dict):
        cls.rate_oracle_source_on_validated(values)
        return values

    @classmethod
    def rate_oracle_source_on_validated(cls, values: Dict):
        RateOracle.get_instance().source = cls._build_rate_source_cls(
            assets_map=values["assets_map"], api_key=values["api_key"]
        )

    @classmethod
    def _build_rate_source_cls(cls, assets_map: Dict[str, str], api_key: SecretStr) -> RateSourceBase:
        rate_source = RATE_ORACLE_SOURCES["coin_cap"](
            assets_map=assets_map, api_key=api_key.get_secret_value()
        )
        return rate_source


class KuCoinRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(
        default="kucoin",
        const=True,
        client_data=None,
    )

    class Config:
        title = "kucoin"


class GateIoRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(
        default="gate_io",
        const=True,
        client_data=None,
    )

    class Config:
        title: str = "gate_io"


class CoinbaseAdvancedTradeRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(
        default="coinbase_advanced_trade",
        const=True,
        client_data=None,
    )

    class Config:
        title: str = "coinbase_advanced_trade"


RATE_SOURCE_MODES = {
    AscendExRateSourceMode.Config.title: AscendExRateSourceMode,
    BinanceRateSourceMode.Config.title: BinanceRateSourceMode,
    BinanceUSRateSourceMode.Config.title: BinanceUSRateSourceMode,
    CoinGeckoRateSourceMode.Config.title: CoinGeckoRateSourceMode,
    CoinCapRateSourceMode.Config.title: CoinCapRateSourceMode,
    KuCoinRateSourceMode.Config.title: KuCoinRateSourceMode,
    GateIoRateSourceMode.Config.title: GateIoRateSourceMode,
    CoinbaseAdvancedTradeRateSourceMode.Config.title: CoinbaseAdvancedTradeRateSourceMode,
    CubeRateSourceMode.Config.title: CubeRateSourceMode,
}


class CommandShortcutModel(BaseModel):
    command: str
    help: str
    arguments: List[str]
    output: List[str]


class ClientConfigMap(BaseClientModel):
    instance_id: str = Field(
        default=generate_client_id(),
        client_data=ClientFieldData(
            prompt=lambda cm: "Instance UID of the bot",
        ),
    )
    fetch_pairs_from_all_exchanges: bool = Field(
        default=False,
        description="Fetch trading pairs from all exchanges if True, otherwise fetch only from connected exchanges.",
        client_data=ClientFieldData(
            prompt=lambda cm: "Would you like to fetch from all exchanges? (True/False)",
        ),
    )
    log_level: str = Field(default="INFO")
    debug_console: bool = Field(default=False)
    strategy_report_interval: float = Field(default=900)
    logger_override_whitelist: List = Field(
        default=["hummingbot.strategy.arbitrage", "hummingbot.strategy.cross_exchange_market_making", "conf"]
    )
    log_file_path: Path = Field(
        default=DEFAULT_LOG_FILE_PATH,
        client_data=ClientFieldData(
            prompt=lambda cm: f"Where would you like to save your logs? (default '{DEFAULT_LOG_FILE_PATH}')",
        ),
    )
    kill_switch_mode: Union[tuple(KILL_SWITCH_MODES.values())] = Field(
        default=KillSwitchDisabledMode(),
        client_data=ClientFieldData(
            prompt=lambda cm: f"Select your kill-switch mode ({'/'.join(list(KILL_SWITCH_MODES.keys()))})",
        ),
    )
    autofill_import: AutofillImportEnum = Field(
        default=AutofillImportEnum.disabled,
        description="What to auto-fill in the prompt after each import command (start/config)",
        client_data=ClientFieldData(
            prompt=lambda cm: (
                f"What to auto-fill in the prompt after each import command? ({'/'.join(list(AutofillImportEnum))})"
            ),
        )
    )
    telegram_mode: Union[tuple(TELEGRAM_MODES.values())] = Field(
        default=TelegramDisabledMode(),
        client_data=ClientFieldData(
            prompt=lambda cm: f"Select the desired telegram mode ({'/'.join(list(TELEGRAM_MODES.keys()))})"
        )
    )
    mqtt_bridge: MQTTBridgeConfigMap = Field(
        default=MQTTBridgeConfigMap(),
        description=('MQTT Bridge configuration.'),
    )
    send_error_logs: bool = Field(
        default=True,
        description="Error log sharing",
        client_data=ClientFieldData(
            prompt=lambda cm: "Would you like to send error logs to hummingbot? (Yes/No)",
        ),
    )
    previous_strategy: Optional[str] = Field(
        default=None,
        description="Can store the previous strategy ran for quick retrieval."
    )
    db_mode: Union[tuple(DB_MODES.values())] = Field(
        default=DBSqliteMode(),
        description=("Advanced database options, currently supports SQLAlchemy's included dialects"
                     "\nReference: https://docs.sqlalchemy.org/en/13/dialects/"
                     "\nTo use an instance of SQLite DB the required configuration is \n  db_engine: sqlite"
                     "\nTo use a DBMS the required configuration is"
                     "\n  db_host: 127.0.0.1\n  db_port: 3306\n  db_username: username\n  db_password: password"
                     "\n  db_name: dbname"),
        client_data=ClientFieldData(
            prompt=lambda cm: f"Select the desired db mode ({'/'.join(list(DB_MODES.keys()))})",
        ),
    )
    balance_asset_limit: Dict[str, Dict[str, Decimal]] = Field(
        default={exchange: {} for exchange in AllConnectorSettings.get_exchange_names()},
        description=("Balance Limit Configurations"
                     "\ne.g. Setting USDT and BTC limits on Binance."
                     "\nbalance_asset_limit:"
                     "\n  binance:"
                     "\n    BTC: 0.1"
                     "\n    USDT: 1000"),
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Use the `balance limit` command e.g. balance limit [EXCHANGE] [ASSET] [AMOUNT]"
            ),
        ),
    )
    manual_gas_price: Decimal = Field(
        default=Decimal("50"),
        description="Fixed gas price (in Gwei) for Ethereum transactions",
        gt=Decimal("0"),
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter fixed gas price (in Gwei) you want to use for Ethereum transactions",
        ),
    )
    gateway: GatewayConfigMap = Field(
        default=GatewayConfigMap(),
        description=("Gateway API Configurations"
                     "\ndefault host to only use localhost"
                     "\nPort need to match the final installation port for Gateway"),
    )
    certs_path: Path = Field(
        default=DEFAULT_GATEWAY_CERTS_PATH,
        client_data=ClientFieldData(
            prompt=lambda cm: f"Where would you like to save certificates that connect your bot to Gateway? (default '{DEFAULT_GATEWAY_CERTS_PATH}')",
        ),
    )

    anonymized_metrics_mode: Union[tuple(METRICS_MODES.values())] = Field(
        default=AnonymizedMetricsEnabledMode(),
        description="Whether to enable aggregated order and trade data collection",
        client_data=ClientFieldData(
            prompt=lambda cm: f"Select the desired metrics mode ({'/'.join(list(METRICS_MODES.keys()))})",
        ),
    )
    command_shortcuts: List[CommandShortcutModel] = Field(
        default=[
            CommandShortcutModel(
                command="spreads",
                help="Set bid and ask spread",
                arguments=["Bid Spread", "Ask Spread"],
                output=["config bid_spread $1", "config ask_spread $2"]
            )
        ],
        description=("Command Shortcuts"
                     "\nDefine abbreviations for often used commands"
                     "\nor batch grouped commands together"),
    )
    rate_oracle_source: Union[tuple(RATE_SOURCE_MODES.values())] = Field(
        default=BinanceRateSourceMode(),
        description=f"A source for rate oracle, currently {', '.join(RATE_SOURCE_MODES.keys())}",
        client_data=ClientFieldData(
            prompt=lambda cm: (
                f"What source do you want rate oracle to pull data from? ({'/'.join(RATE_SOURCE_MODES.keys())})"
            ),
        ),
    )
    global_token: GlobalTokenConfigMap = Field(
        default=GlobalTokenConfigMap(),
        description="A universal token which to display tokens values in, e.g. USD,EUR,BTC"
    )
    rate_limits_share_pct: Decimal = Field(
        default=Decimal("100"),
        description=("Percentage of API rate limits (on any exchange and any end point) allocated to this bot instance."
                     "\nEnter 50 to indicate 50%. E.g. if the API rate limit is 100 calls per second, and you allocate "
                     "\n50% to this setting, the bot will have a maximum (limit) of 50 calls per second"),
        gt=Decimal("0"),
        le=Decimal("100"),
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "What percentage of API rate limits do you want to allocate to this bot instance?"
                " (Enter 50 to indicate 50%)"
            ),
        ),
    )
    commands_timeout: CommandsTimeoutConfigMap = Field(default=CommandsTimeoutConfigMap())
    tables_format: ClientConfigEnum(
        value="TabulateFormats",  # noqa: F821
        names={e: e for e in tabulate_formats},
        type=str,
    ) = Field(
        default="psql",
        description="Tabulate table format style (https://github.com/astanin/python-tabulate#table-format)",
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "What tabulate formatting to apply to the tables?"
                " [https://github.com/astanin/python-tabulate#table-format]"
            ),
        ),
    )
    paper_trade: PaperTradeConfigMap = Field(default=PaperTradeConfigMap())
    color: ColorConfigMap = Field(default=ColorConfigMap())
    tick_size: float = Field(
        default=1.0,
        ge=0.1,
        description="The tick size is the frequency with which the clock notifies the time iterators by calling the"
                    "\nc_tick() method, that means for example that if the tick size is 1, the logic of the strategy"
                    " \nwill run every second.",
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "What tick size (in seconds) do you want to use? (Enter 0.5 to indicate 0.5 seconds)"
            ),
        ),
    )
    market_data_collection: MarketDataCollectionConfigMap = Field(default=MarketDataCollectionConfigMap())

    class Config:
        title = "client_config_map"

    @validator("kill_switch_mode", pre=True)
    def validate_kill_switch_mode(cls, v: Union[(str, Dict) + tuple(KILL_SWITCH_MODES.values())]):
        if isinstance(v, tuple(KILL_SWITCH_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in KILL_SWITCH_MODES:
            raise ValueError(
                f"Invalid kill switch mode, please choose a value from {list(KILL_SWITCH_MODES.keys())}."
            )
        else:
            sub_model = KILL_SWITCH_MODES[v].construct()
        return sub_model

    @validator("autofill_import", pre=True)
    def validate_autofill_import(cls, v: Union[str, AutofillImportEnum]):
        if isinstance(v, str) and v not in AutofillImportEnum.__members__:
            raise ValueError(f"The value must be one of {', '.join(list(AutofillImportEnum))}.")
        return v

    @validator("telegram_mode", pre=True)
    def validate_telegram_mode(cls, v: Union[(str, Dict) + tuple(TELEGRAM_MODES.values())]):
        if isinstance(v, tuple(TELEGRAM_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in TELEGRAM_MODES:
            raise ValueError(
                f"Invalid telegram mode, please choose a value from {list(TELEGRAM_MODES.keys())}."
            )
        else:
            sub_model = TELEGRAM_MODES[v].construct()
        return sub_model

    @validator("send_error_logs", "fetch_pairs_from_all_exchanges", pre=True)
    def validate_bool(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            ret = validate_bool(v)
            if ret is not None:
                raise ValueError(ret)
        return v

    @validator("db_mode", pre=True)
    def validate_db_mode(cls, v: Union[(str, Dict) + tuple(DB_MODES.values())]):
        if isinstance(v, tuple(DB_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in DB_MODES:
            raise ValueError(
                f"Invalid DB mode, please choose a value from {list(DB_MODES.keys())}."
            )
        else:
            sub_model = DB_MODES[v].construct()
        return sub_model

    @validator("anonymized_metrics_mode", pre=True)
    def validate_anonymized_metrics_mode(cls, v: Union[(str, Dict) + tuple(METRICS_MODES.values())]):
        if isinstance(v, tuple(METRICS_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in METRICS_MODES:
            raise ValueError(
                f"Invalid metrics mode, please choose a value from {list(METRICS_MODES.keys())}."
            )
        else:
            sub_model = METRICS_MODES[v].construct()
        return sub_model

    @validator("rate_oracle_source", pre=True)
    def validate_rate_oracle_source(cls, v: Union[(str, Dict) + tuple(RATE_SOURCE_MODES.values())]):
        if isinstance(v, tuple(RATE_SOURCE_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in RATE_SOURCE_MODES:
            raise ValueError(
                f"Invalid rate source, please choose a value from {list(RATE_SOURCE_MODES.keys())}."
            )
        else:
            sub_model = RATE_SOURCE_MODES[v].construct()
        return sub_model

    @validator("tables_format", pre=True)
    def validate_tables_format(cls, v: str):
        """Used for client-friendly error output."""
        if v not in tabulate_formats:
            raise ValueError("Invalid table format.")
        return v

    @validator(
        "manual_gas_price",
        "rate_limits_share_pct",
        pre=True,
    )
    def validate_decimals(cls, v: str, field: Field):
        """Used for client-friendly error output."""
        return super().validate_decimal(v, field)

    @validator("tick_size", pre=True)
    def validate_tick_size(cls, v: float):
        """Used for client-friendly error output."""
        ret = validate_float(v, min_value=0.1)
        if ret is not None:
            raise ValueError(ret)
        return v

    # === post-validations ===

    @root_validator()
    def post_validations(cls, values: Dict):
        cls.rate_oracle_source_on_validated(values)
        return values

    @classmethod
    def rate_oracle_source_on_validated(cls, values: Dict):
        rate_source_mode: RateSourceModeBase = values["rate_oracle_source"]
        RateOracle.get_instance().source = rate_source_mode.build_rate_source()
        RateOracle.get_instance().quote_token = values["global_token"].global_token_name
