from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0001"),
    taker_percent_fee_decimal=Decimal("0.0005"),
)


def clamp(value, minvalue, maxvalue):
    return max(minvalue, min(value, maxvalue))


class RubinPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "rubin_perpetual"
    rubin_perpetual_secret_phrase: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Rubin secret phrase (24 words)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    rubin_perpetual_chain_address: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Rubin chain address ( starts with 'rit' )",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="rubin_perpetual")


KEYS = RubinPerpetualConfigMap.model_construct()

# ── Testnet как отдельный коннектор (виден в `connect`, без env RUBIN_PERPETUAL_DOMAIN) ──
# Механизм hummingbot: OTHER_DOMAINS регистрирует доп. имя коннектора; OTHER_DOMAINS_PARAMETER[name]
# передаётся в конструктор как domain → наши constants резолвят testnet-endpoints/chain_id.
# Поля ConfigMap должны иметь префикс имени (rubin_perpetual_testnet_*): settings.py нормализует их
# k.replace("rubin_perpetual_testnet", "rubin_perpetual") → параметры конструктора.
OTHER_DOMAINS = ["rubin_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"rubin_perpetual_testnet": "testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"rubin_perpetual_testnet": "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {"rubin_perpetual_testnet": [0.0001, 0.0005]}


class RubinPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "rubin_perpetual_testnet"
    rubin_perpetual_testnet_secret_phrase: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Rubin TESTNET secret phrase (24 words)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    rubin_perpetual_testnet_chain_address: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Rubin TESTNET chain address ( starts with 'rit' )",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="rubin_perpetual_testnet")


OTHER_DOMAINS_KEYS = {"rubin_perpetual_testnet": RubinPerpetualTestnetConfigMap.model_construct()}
