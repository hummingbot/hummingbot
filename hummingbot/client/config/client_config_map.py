import json
import random
import re
from abc import ABC, abstractmethod
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Union

from pydantic import ConfigDict, Field, SecretStr, field_validator, model_validator
from tabulate import tabulate_formats

from hummingbot.client.config.config_data_types import BaseClientModel, ClientConfigEnum
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

if TYPE_CHECKING:
    from hummingbot.core.trading_core import TradingCore


def generate_client_id() -> str:
    vals = [random.choice(range(0, 256)) for i in range(0, 20)]
    return "".join([f"{val:02x}" for val in vals])


def using_exchange(exchange: str) -> Callable:
    return using_exchange_pointer(exchange)


class MQTTBridgeConfigMap(BaseClientModel):
    mqtt_host: str = Field(
        default="localhost",
        json_schema_extra={"prompt": lambda cm: "Set the MQTT hostname to connect to (e.g. localhost)"}
    )
    mqtt_port: int = Field(
        default=1883,
        json_schema_extra={"prompt": lambda cm: "Set the MQTT port to connect to (e.g. 1883)"},
    )
    mqtt_username: str = Field(
        default="",
        json_schema_extra={"prompt": lambda cm: "Set the username for connecting to the MQTT broker"},
    )
    mqtt_password: str = Field(
        default="",
        json_schema_extra={"prompt": lambda cm: "Set the password for connecting to the MQTT broker"},
    )
    mqtt_namespace: str = Field(
        default='hbot',
        json_schema_extra={"prompt": lambda cm: "Set the MQTT namespace to connect to (e.g. hbot)"},
    )
    mqtt_ssl: bool = Field(
        default=False,
        json_schema_extra={"prompt": lambda cm: "Enable/Disable SSL for MQTT connections"},
    )
    mqtt_logger: bool = Field(default=True)
    mqtt_notifier: bool = Field(
        default=True,
        json_schema_extra={"prompt": lambda cm: "Enable/Disable MQTT Notifier"},
    )
    mqtt_commands: bool = Field(
        default=True,
        json_schema_extra={"prompt": lambda cm: "Enable/Disable MQTT Commands"},
    )
    mqtt_events: bool = Field(
        default=True,
        json_schema_extra={"prompt": lambda cm: "Enable/Disable MQTT Events"},
    )
    mqtt_external_events: bool = Field(
        default=True,
        json_schema_extra={"prompt": lambda cm: "Enable/Disable External MQTT Events"},
    )
    mqtt_autostart: bool = Field(
        default=False,
        json_schema_extra={"prompt": lambda cm: "Enable/Disable MQTT Autostart"},
    )
    model_config = ConfigDict(title="mqtt_bridge")


class MarketDataCollectionConfigMap(BaseClientModel):
    market_data_collection_enabled: bool = Field(
        default=False,
        json_schema_extra={"prompt": lambda cm: "Enable/Disable Market Data Collection"},
    )
    market_data_collection_interval: int = Field(
        default=60,
        ge=1,
        json_schema_extra={"prompt": lambda cm: "Set the market data collection interval in seconds (Default=60)"},
    )
    market_data_collection_depth: int = Field(
        default=20,
        ge=2,
        json_schema_extra={"prompt": lambda cm: "Set the order book collection depth (Default=20)"},
    )
    model_config = ConfigDict(title="market_data_collection")


class ColorConfigMap(BaseClientModel):
    top_pane: str = Field(
        default="#000000",
        json_schema_extra={"prompt": lambda cm: "What is the background color of the top pane?"},
    )
    bottom_pane: str = Field(
        default="#000000",
        json_schema_extra={"prompt": lambda cm: "What is the background color of the bottom pane?"},
    )
    output_pane: str = Field(
        default="#262626",
        json_schema_extra={"prompt": lambda cm: "What is the background color of the output pane?"},
    )
    input_pane: str = Field(
        default="#1C1C1C",
        json_schema_extra={"prompt": lambda cm: "What is the background color of the input pane?"},
    )
    logs_pane: str = Field(
        default="#121212",
        json_schema_extra={"prompt": lambda cm: "What is the background color of the logs pane?"},
    )
    terminal_primary: str = Field(
        default="#5FFFD7",
        json_schema_extra={"prompt": lambda cm: "What is the terminal primary color?"},
    )
    primary_label: str = Field(
        default="#5FFFD7",
        json_schema_extra={"prompt": lambda cm: "What is the background color for primary label?"},
    )
    secondary_label: str = Field(
        default="#FFFFFF",
        json_schema_extra={"prompt": lambda cm: "What is the background color for secondary label?"},
    )
    success_label: str = Field(
        default="#5FFFD7",
        json_schema_extra={"prompt": lambda cm: "What is the background color for success label?"},
    )
    warning_label: str = Field(
        default="#FFFF00",
        json_schema_extra={"prompt": lambda cm: "What is the background color for warning label?"},
    )
    info_label: str = Field(
        default="#5FD7FF",
        json_schema_extra={"prompt": lambda cm: "What is the background color for info label?"},
    )
    error_label: str = Field(
        default="#FF0000",
        json_schema_extra={"prompt": lambda cm: "What is the background color for error label?"},
    )
    gold_label: str = Field(
        default="#FFD700",
        json_schema_extra={"prompt": lambda cm: "What is the background color for gold label?"},
    )
    silver_label: str = Field(
        default="#C0C0C0",
        json_schema_extra={"prompt": lambda cm: "What is the background color for silver label?"},
    )
    bronze_label: str = Field(
        default="#CD7F32",
        json_schema_extra={"prompt": lambda cm: "What is the background color for bronze label?"},
    )

    @field_validator(
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
        mode="before")
    @classmethod
    def validate_color(cls, v: str):
        if not re.search(r'^#(?:[0-9a-fA-F]{2}){3}$', v):
            raise ValueError("Invalid color code")
        return v


class PaperTradeConfigMap(BaseClientModel):
    paper_trade_exchanges: List = Field(
        default=[
            BinanceConfigMap.model_config["title"],
            KuCoinConfigMap.model_config["title"],
            KrakenConfigMap.model_config["title"],
            GateIOConfigMap.model_config["title"],
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
        json_schema_extra={"prompt": lambda cm: (
            "Enter paper trade balance settings (Input must be valid json — "
            "e.g. {\"ETH\": 10, \"USDC\": 50000})"
        )},
    )

    @field_validator("paper_trade_account_balance", mode="before")
    @classmethod
    def validate_paper_trade_account_balance(cls, v: Union[str, Dict[str, float]]):
        if isinstance(v, str):
            v = json.loads(v)
        return v


class KillSwitchMode(BaseClientModel, ABC):
    @abstractmethod
    def get_kill_switch(self, trading_core: "TradingCore") -> KillSwitch:
        ...


class KillSwitchEnabledMode(KillSwitchMode):
    kill_switch_rate: Decimal = Field(
        default=Decimal("10"),
        json_schema_extra={
            "prompt": lambda cm: "At what profit/loss rate would you like the bot to stop? "
                                 "(e.g. -5 equals 5 percent loss)"
        }
    )
    model_config = ConfigDict(title="kill_switch_enabled")

    def get_kill_switch(self, trading_core: "TradingCore") -> ActiveKillSwitch:
        kill_switch = ActiveKillSwitch(kill_switch_rate=self.kill_switch_rate, trading_core=trading_core)
        return kill_switch


class KillSwitchDisabledMode(KillSwitchMode):
    model_config = ConfigDict(title="kill_switch_disabled")

    def get_kill_switch(self, trading_core: "TradingCore") -> PassThroughKillSwitch:
        kill_switch = PassThroughKillSwitch()
        return kill_switch


KILL_SWITCH_MODES = {
    KillSwitchEnabledMode.model_config["title"]: KillSwitchEnabledMode,
    KillSwitchDisabledMode.model_config["title"]: KillSwitchDisabledMode,
}


class AutofillImportEnum(str, ClientConfigEnum):
    start = "start"
    config = "config"
    disabled = "disabled"


class DBMode(BaseClientModel, ABC):
    @abstractmethod
    def get_url(self, db_path: str) -> str:
        ...


class DBSqliteMode(DBMode):
    db_engine: str = Field(
        default="sqlite",
        json_schema_extra={
            "prompt": lambda cm: "Please enter database engine you want to use "
                                 "(reference: https://docs.sqlalchemy.org/en/13/dialects/)"
        }
    )
    model_config = ConfigDict(title="sqlite_db_engine")

    def get_url(self, db_path: str) -> str:
        return f"{self.db_engine}:///{db_path}"


class DBOtherMode(DBMode):
    db_engine: str = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Please enter database engine you want to use "
        }
    )
    db_host: str = Field(
        default="127.0.0.1",
        json_schema_extra={"prompt": lambda cm: "Please enter your DB host address"},
    )
    db_port: int = Field(
        default=3306,
        json_schema_extra={"prompt": lambda cm: "Please enter your DB port"},
    )
    db_username: str = Field(
        default="username",
        json_schema_extra={"prompt": lambda cm: "Please enter your DB username"},
    )
    db_password: str = Field(
        default="password",
        json_schema_extra={"prompt": lambda cm: "Please enter your DB password"},
    )
    db_name: str = Field(
        default="dbname",
        json_schema_extra={"prompt": lambda cm: "Please enter your DB name"},
    )
    model_config = ConfigDict(title="other_db_engine")

    def get_url(self, db_path: str) -> str:
        return f"{self.db_engine}://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @field_validator("db_engine")
    @classmethod
    def validate_db_engine(cls, v: str):
        assert v != "sqlite"
        return v


DB_MODES = {
    DBSqliteMode.model_config["title"]: DBSqliteMode,
    DBOtherMode.model_config["title"]: DBOtherMode,
}


class GatewayConfigMap(BaseClientModel):
    gateway_api_host: str = Field(
        default="localhost",
        json_schema_extra={"prompt": lambda cm: "Please enter your Gateway API host"},
    )
    gateway_api_port: str = Field(
        default="15888",
        json_schema_extra={"prompt": lambda cm: "Please enter your Gateway API port"},
    )
    gateway_use_ssl: bool = Field(
        default=False,
        json_schema_extra={"prompt": lambda cm: "Enable SSL endpoints for secure Gateway connection? (True / False)"},
    )
    certs_path: Path = Field(
        default=DEFAULT_GATEWAY_CERTS_PATH,
        json_schema_extra={"prompt": lambda cm: "Where would you like to save certificates that connect your bot to "
                                                "Gateway? (default 'certs')"},
    )

    model_config = ConfigDict(title="gateway")


class GlobalTokenConfigMap(BaseClientModel):
    global_token_name: str = Field(
        default="USDT",
        json_schema_extra={"prompt": lambda cm: "What is your default display token? (e.g. USDT, BTC)"},
    )
    global_token_symbol: str = Field(
        default="$",
        json_schema_extra={"prompt": lambda cm: "What is your default display token symbol? (e.g. $,€)"},
    )
    model_config = ConfigDict(title="global_token")

    @field_validator("global_token_name")
    @classmethod
    def validate_global_token_name(cls, v: str) -> str:
        return v.upper()

    # === post-validations ===

    @model_validator(mode="after")
    def post_validations(self):
        RateOracle.get_instance().quote_token = self.global_token_name
        return self


class CommandsTimeoutConfigMap(BaseClientModel):
    create_command_timeout: Decimal = Field(
        default=Decimal("10"),
        gt=Decimal("0"),
        json_schema_extra={
            "prompt": lambda cm: "Network timeout when fetching the minimum order amount in the create command (in seconds)"
        }
    )
    other_commands_timeout: Decimal = Field(
        default=Decimal("30"),
        gt=Decimal("0"),
        json_schema_extra={
            "prompt": lambda cm: "Network timeout to apply to the other commands' API calls (in seconds)"
        }
    )
    model_config = ConfigDict(title="commands_timeout")


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
    model_config = ConfigDict(title="anonymized_metrics_disabled")

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
        json_schema_extra={"prompt": lambda cm: "How often do you want to send the anonymized metrics (in minutes)"},
    )
    model_config = ConfigDict(title="anonymized_metrics_enabled")

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


METRICS_MODES = {
    AnonymizedMetricsDisabledMode.model_config["title"]: AnonymizedMetricsDisabledMode,
    AnonymizedMetricsEnabledMode.model_config["title"]: AnonymizedMetricsEnabledMode,
}


class RateSourceModeBase(BaseClientModel, ABC):
    @abstractmethod
    def build_rate_source(self) -> RateSourceBase:
        ...


class ExchangeRateSourceModeBase(RateSourceModeBase):
    def build_rate_source(self) -> RateSourceBase:
        return RATE_ORACLE_SOURCES[self.model_config["title"]]()


class AscendExRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(default="ascend_ex")
    model_config = ConfigDict(title="ascend_ex")


class BinanceRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(default="binance")
    model_config = ConfigDict(title="binance")


class BinanceUSRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(default="binance_us")
    model_config = ConfigDict(title="binance_us")


class MexcRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(default="mexc")
    model_config = ConfigDict(title="mexc")


class CubeRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(default="cube")
    model_config = ConfigDict(title="cube")


class CoinGeckoRateSourceMode(RateSourceModeBase):
    name: str = Field(default="coin_gecko")
    extra_tokens: List[str] = Field(
        default=[],
        json_schema_extra={
            "prompt": lambda cm: (
                "List of comma-delimited CoinGecko token ids to always include"
                " in CoinGecko rates query (e.g. frontier-token,pax-gold,rbtc — empty to skip)"
            ),
        }
    )
    api_key: str = Field(
        default="",
        description="API key to use to request information from CoinGecko (if empty public API will be used)",
        json_schema_extra={
            "prompt": lambda cm: "CoinGecko API key (optional, leave empty to use public API) NOTE: will be stored in plain text due to a bug in the way hummingbot loads the config file",
            "prompt_on_new": True,
            "is_connect_key": True,
        },
    )

    api_tier: str = Field(
        default="PUBLIC",
        description="API tier for CoinGecko (PUBLIC, DEMO, or PRO)",
        json_schema_extra={
            "prompt": lambda cm: "Select CoinGecko API tier (PUBLIC/DEMO/PRO)",
            "prompt_on_new": True,
            "is_connect_key": True,
        },
    )
    model_config = ConfigDict(title="coin_gecko")

    def build_rate_source(self) -> RateSourceBase:
        return self._build_rate_source_cls(
            extra_tokens=self.extra_tokens,
            api_key=self.api_key,
            api_tier=self.api_tier
        )

    @field_validator("extra_tokens", mode="before")
    def validate_extra_tokens(cls, value: Union[str, List[str]]):
        extra_tokens = value.split(",") if isinstance(value, str) else value
        return extra_tokens

    @field_validator("api_tier", mode="before")
    def validate_api_tier(cls, v: str):
        from hummingbot.data_feed.coin_gecko_data_feed.coin_gecko_constants import CoinGeckoAPITier
        valid_tiers = [tier.name for tier in CoinGeckoAPITier]
        if v.upper() not in valid_tiers:
            return CoinGeckoAPITier.PUBLIC.name
        return v.upper()

    @model_validator(mode="after")
    def post_validations(self):
        RateOracle.get_instance().source = self.build_rate_source()
        return self

    @classmethod
    def _build_rate_source_cls(cls, extra_tokens: List[str], api_key: str, api_tier: str) -> RateSourceBase:
        from hummingbot.data_feed.coin_gecko_data_feed.coin_gecko_constants import CoinGeckoAPITier
        try:
            api_tier_enum = CoinGeckoAPITier[api_tier.upper()]
        except KeyError:
            api_tier_enum = CoinGeckoAPITier.PUBLIC

        rate_source = RATE_ORACLE_SOURCES[cls.model_config["title"]](
            extra_token_ids=extra_tokens,
            api_key=api_key,
            api_tier=api_tier_enum,
        )
        rate_source.extra_token_ids = extra_tokens
        return rate_source


class CoinCapRateSourceMode(RateSourceModeBase):
    name: str = Field(default="coin_cap")
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
                }.items()
            ]
        ),
        description=(
            "The symbol-to-asset ID map for CoinCap. Assets IDs can be found by selecting a symbol"
            " on https://coincap.io/ and extracting the last segment of the URL path."
        ),
        json_schema_extra={
            "prompt": lambda cm: (
                "CoinCap symbol-to-asset ID map (e.g. 'BTC:bitcoin,ETH:ethereum', find IDs on https://coincap.io/"
                " by selecting a symbol and extracting the last segment of the URL path)"
            ),
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    api_key: SecretStr = Field(
        default=SecretStr(""),
        description="API key to use to request information from CoinCap (if empty public requests will be used)",
        json_schema_extra={
            "prompt": lambda cm: "CoinCap API key (optional, but improves rate limits)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="coin_cap")

    def build_rate_source(self) -> RateSourceBase:
        rate_source = RATE_ORACLE_SOURCES["coin_cap"](
            assets_map=self.assets_map, api_key=self.api_key.get_secret_value()
        )
        return rate_source

    @field_validator("assets_map", mode="before")
    @classmethod
    def validate_extra_tokens(cls, value: Union[str, Dict[str, str]]):
        if isinstance(value, str):
            value = {key: val for key, val in [v.split(":") for v in value.split(",")]}
        return value

    # === post-validations ===

    @model_validator(mode="after")
    def post_validations(self):
        RateOracle.get_instance().source = RATE_ORACLE_SOURCES["coin_cap"](
            assets_map=self.assets_map, api_key=self.api_key.get_secret_value())
        return self


class KuCoinRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(default="kucoin")
    model_config = ConfigDict(title="kucoin")


class GateIoRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(default="gate_io")
    model_config = ConfigDict(title="gate_io")


class DexalotRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(default="dexalot")
    model_config = ConfigDict(title="dexalot")


class CoinbaseAdvancedTradeRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(default="coinbase_advanced_trade")
    model_config = ConfigDict(title="coinbase_advanced_trade")
    use_auth_for_public_endpoints: bool = Field(
        default=False,
        description="Use authentication for public endpoints",
        json_schema_extra = {
            "prompt": lambda cm: "Would you like to use authentication for public endpoints? (Yes/No) (only affects rate limiting)",
            "prompt_on_new": True,
            "is_connect_key": True,
        },
    )

    def build_rate_source(self) -> RateSourceBase:
        return RATE_ORACLE_SOURCES[self.model_config["title"]](use_auth_for_public_endpoints=self.use_auth_for_public_endpoints)


class HyperliquidRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(default="hyperliquid")
    model_config = ConfigDict(title="hyperliquid")


class DeriveRateSourceMode(ExchangeRateSourceModeBase):
    name: str = Field(default="derive")
    model_config = ConfigDict(title="derive")


RATE_SOURCE_MODES = {
    AscendExRateSourceMode.model_config["title"]: AscendExRateSourceMode,
    BinanceRateSourceMode.model_config["title"]: BinanceRateSourceMode,
    BinanceUSRateSourceMode.model_config["title"]: BinanceUSRateSourceMode,
    CoinGeckoRateSourceMode.model_config["title"]: CoinGeckoRateSourceMode,
    CoinCapRateSourceMode.model_config["title"]: CoinCapRateSourceMode,
    DexalotRateSourceMode.model_config["title"]: DexalotRateSourceMode,
    KuCoinRateSourceMode.model_config["title"]: KuCoinRateSourceMode,
    GateIoRateSourceMode.model_config["title"]: GateIoRateSourceMode,
    CoinbaseAdvancedTradeRateSourceMode.model_config["title"]: CoinbaseAdvancedTradeRateSourceMode,
    CubeRateSourceMode.model_config["title"]: CubeRateSourceMode,
    HyperliquidRateSourceMode.model_config["title"]: HyperliquidRateSourceMode,
    DeriveRateSourceMode.model_config["title"]: DeriveRateSourceMode,
    MexcRateSourceMode.model_config["title"]: MexcRateSourceMode,
}


class ClientConfigMap(BaseClientModel):
    instance_id: str = Field(
        default=generate_client_id(),
        json_schema_extra={"prompt": lambda cm: "Enter a unique identifier for this instance of Hummingbot"},
    )
    fetch_pairs_from_all_exchanges: bool = Field(
        default=False,
        description="Fetch trading pairs from all exchanges if True, otherwise fetch only from connected exchanges.",
        json_schema_extra={
            "prompt": lambda cm: "Would you like to fetch trading pairs from all exchanges? (True/False)"
        }
    )
    log_level: str = Field(default="INFO")
    debug_console: bool = Field(default=False)
    strategy_report_interval: float = Field(default=900)
    logger_override_whitelist: List = Field(
        default=["hummingbot.strategy.arbitrage", "hummingbot.strategy.cross_exchange_market_making", "conf"]
    )
    log_file_path: Path = Field(
        default=DEFAULT_LOG_FILE_PATH,
        json_schema_extra={"prompt": lambda cm: "Where would you like to save your logs? (default 'logs/hummingbot_logs.log')"},
    )
    kill_switch_mode: Union[tuple(KILL_SWITCH_MODES.values())] = Field(
        default=KillSwitchDisabledMode(),
        json_schema_extra={"prompt": lambda cm: f"Select the desired kill-switch mode ({'/'.join(list(KILL_SWITCH_MODES.keys()))})"},
    )
    autofill_import: AutofillImportEnum = Field(
        default=AutofillImportEnum.disabled,
        description="What to auto-fill in the prompt after each import command (start/config)",
        json_schema_extra={
            "prompt": lambda cm: f"What to auto-fill in the prompt after each import command? ({'/'.join(list(AutofillImportEnum))})"
        }
    )
    mqtt_bridge: MQTTBridgeConfigMap = Field(
        default=MQTTBridgeConfigMap(),
        description=('MQTT Bridge configuration.'),
    )
    send_error_logs: bool = Field(
        default=True,
        description="Error log sharing",
        json_schema_extra={"prompt": lambda cm: "Would you like to send error logs to hummingbot? (True/False)"},
    )
    db_mode: Union[tuple(DB_MODES.values())] = Field(
        default=DBSqliteMode(),
        description=("Advanced database options, currently supports SQLAlchemy's included dialects"
                     "\nReference: https://docs.sqlalchemy.org/en/13/dialects/"
                     "\nTo use an instance of SQLite DB the required configuration is \n  db_engine: sqlite"
                     "\nTo use a DBMS the required configuration is"
                     "\n  db_host: 127.0.0.1\n  db_port: 3306\n  db_username: username\n  db_password: password"
                     "\n  db_name: dbname"),
        json_schema_extra={"prompt": lambda cm: f"Select the desired db mode ({'/'.join(list(DB_MODES.keys()))})"},
    )
    balance_asset_limit: Dict[str, Dict[str, Decimal]] = Field(
        default={exchange: {} for exchange in AllConnectorSettings.get_exchange_names()},
        description=("Balance Limit Configurations"
                     "\ne.g. Setting USDT and BTC limits on Binance."
                     "\nbalance_asset_limit:"
                     "\n  binance:"
                     "\n    BTC: 0.1"
                     "\n    USDT: 1000"),
        json_schema_extra={"prompt": lambda cm: "Use the `balance limit` command e.g. balance limit [EXCHANGE] [ASSET] [AMOUNT]"},
    )
    manual_gas_price: Decimal = Field(
        default=Decimal("50"),
        description="Fixed gas price (in Gwei) for Ethereum transactions",
        gt=Decimal("0"),
        json_schema_extra={"prompt": lambda cm: "Enter fixed gas price (in Gwei) you want to use for Ethereum transactions"},
    )
    gateway: GatewayConfigMap = Field(
        default=GatewayConfigMap(),
        description=("Gateway API Configurations"
                     "\ndefault host to only use localhost"
                     "\nPort need to match the final installation port for Gateway"),
    )

    anonymized_metrics_mode: Union[tuple(METRICS_MODES.values())] = Field(
        default=AnonymizedMetricsEnabledMode(),
        description="Whether to enable aggregated order and trade data collection",
        json_schema_extra={"prompt": lambda cm: f"Select the desired metrics mode ({'/'.join(list(METRICS_MODES.keys()))})"},
    )
    rate_oracle_source: Union[tuple(RATE_SOURCE_MODES.values())] = Field(
        default=BinanceRateSourceMode(),
        description=f"A source for rate oracle, currently {', '.join(RATE_SOURCE_MODES.keys())}",
        json_schema_extra={"prompt": lambda cm: f"Select the desired rate oracle source ({'/'.join(RATE_SOURCE_MODES.keys())})"},
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
        json_schema_extra={"prompt": lambda cm: (
            "What percentage of API rate limits do you want to allocate to this bot instance?"
            " (Enter 50 to indicate 50%)"
        )},
    )
    commands_timeout: CommandsTimeoutConfigMap = Field(default=CommandsTimeoutConfigMap())
    tables_format: ClientConfigEnum(
        value="TabulateFormats",  # noqa: F821
        names={e: e for e in tabulate_formats},
        type=str,
    ) = Field(
        default="psql",
        description="Tabulate table format style (https://github.com/astanin/python-tabulate#table-format)",
        json_schema_extra={"prompt": lambda cm: (
            "What tabulate formatting to apply to the tables? [https://github.com/astanin/python-tabulate#table-format]"
        )}
    )
    paper_trade: PaperTradeConfigMap = Field(default=PaperTradeConfigMap())
    color: ColorConfigMap = Field(default=ColorConfigMap())
    tick_size: float = Field(
        default=1.0,
        ge=0.1,
        description="The tick size is the frequency with which the clock notifies the time iterators by calling the"
                    "\nc_tick() method, that means for example that if the tick size is 1, the logic of the strategy"
                    " \nwill run every second.",
        json_schema_extra={"prompt": lambda cm: (
            "What tick size (in seconds) do you want to use? (Enter 0.5 to indicate 0.5 seconds)"
        )},
    )
    market_data_collection: MarketDataCollectionConfigMap = Field(default=MarketDataCollectionConfigMap())
    model_config = ConfigDict(title="client_config_map")

    @field_validator("kill_switch_mode", mode="before")
    @classmethod
    def validate_kill_switch_mode(cls, v: Any):
        if isinstance(v, tuple(KILL_SWITCH_MODES.values())):
            return v  # Already a valid model

        if v == {}:
            return KillSwitchDisabledMode()

        if isinstance(v, dict):
            # Try validating against known mode models
            for mode_cls in KILL_SWITCH_MODES.values():
                try:
                    return mode_cls.model_validate(v)
                except Exception:
                    continue
            raise ValueError(f"Could not match dict to any known kill switch mode: {v}")

        if isinstance(v, str):
            if v not in KILL_SWITCH_MODES:
                raise ValueError(
                    f"Invalid kill switch mode string. Choose from: {list(KILL_SWITCH_MODES.keys())}."
                )
            return KILL_SWITCH_MODES[v].model_construct()

        raise ValueError(f"Unsupported type for kill switch mode: {type(v)}")

    @field_validator("autofill_import", mode="before")
    @classmethod
    def validate_autofill_import(cls, v: Union[str, AutofillImportEnum]):
        if isinstance(v, str) and v not in AutofillImportEnum.__members__:
            raise ValueError(f"The value must be one of {', '.join(list(AutofillImportEnum))}.")
        return v

    @field_validator("send_error_logs", "fetch_pairs_from_all_exchanges", mode="before")
    @classmethod
    def validate_bool(cls, v: str):
        """Used for client-friendly error output."""
        if isinstance(v, str):
            ret = validate_bool(v)
            if ret is not None:
                raise ValueError(ret)
        return v

    @field_validator("db_mode", mode="before")
    @classmethod
    def validate_db_mode(cls, v: Union[(str, Dict) + tuple(DB_MODES.values())]):
        if isinstance(v, tuple(DB_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in DB_MODES:
            raise ValueError(
                f"Invalid DB mode, please choose a value from {list(DB_MODES.keys())}."
            )
        else:
            sub_model = DB_MODES[v].model_construct()
        return sub_model

    @field_validator("anonymized_metrics_mode", mode="before")
    @classmethod
    def validate_anonymized_metrics_mode(cls, v: Union[(str, Dict) + tuple(METRICS_MODES.values())]):
        if isinstance(v, tuple(METRICS_MODES.values()) + (Dict,)):
            sub_model = v
        elif v not in METRICS_MODES:
            raise ValueError(
                f"Invalid metrics mode, please choose a value from {list(METRICS_MODES.keys())}."
            )
        else:
            sub_model = METRICS_MODES[v].model_construct()
        return sub_model

    @field_validator("rate_oracle_source", mode="before")
    @classmethod
    def validate_rate_oracle_source(cls, v: Any):
        if isinstance(v, tuple(RATE_SOURCE_MODES.values())):
            sub_model = v
        elif isinstance(v, dict):
            sub_model = RATE_SOURCE_MODES[v["name"]].model_construct()
        elif isinstance(v, str):
            sub_model = RATE_SOURCE_MODES[v].model_construct()
        elif v not in RATE_SOURCE_MODES:
            raise ValueError(
                f"Invalid rate source, please choose a value from {list(RATE_SOURCE_MODES.keys())}."
            )
        else:
            raise ValueError("Invalid rate source.")
        return sub_model

    @field_validator("tables_format", mode="before")
    @classmethod
    def validate_tables_format(cls, v: str):
        """Used for client-friendly error output."""
        if v not in tabulate_formats:
            raise ValueError("Invalid table format.")
        return v

    @field_validator("tick_size", mode="before")
    @classmethod
    def validate_tick_size(cls, v: float):
        """Used for client-friendly error output."""
        ret = validate_float(v, min_value=0.1)
        if ret is not None:
            raise ValueError(ret)
        return v

    # === post-validations ===

    @model_validator(mode="after")
    def post_validations(self):
        rate_source_mode: RateSourceModeBase = self.rate_oracle_source
        RateOracle.get_instance().source = rate_source_mode.build_rate_source()
        RateOracle.get_instance().quote_token = self.global_token.global_token_name
        return self
