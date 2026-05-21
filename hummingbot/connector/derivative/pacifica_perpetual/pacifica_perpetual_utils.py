from decimal import Decimal

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "SOL-USDC"

# https://docs.pacifica.fi/trading-on-pacifica/trading-fees
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.00015"),
    taker_percent_fee_decimal=Decimal("0.0004"),
)


class PacificaPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "pacifica_perpetual"

    # TODO (dizpers): we can drop this input and only ask for private key
    # bc public key could be extracted from private key

    pacifica_perpetual_agent_wallet_public_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Pacifica Perpetual Agent Wallet Public Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    pacifica_perpetual_agent_wallet_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Pacifica Perpetual Agent Wallet Private Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    pacifica_perpetual_user_wallet_public_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Pacifica Perpetual User Wallet Public Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    pacifica_perpetual_api_config_key: SecretStr = Field(
        default=SecretStr(""),
        json_schema_extra={
            "prompt": "Enter your Pacifica Perpetual API Config Key (optional)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": False  # Not required for new configs, automatic fallback or creation
        }
    )

    model_config = ConfigDict(title="pacifica_perpetual")


KEYS = PacificaPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["pacifica_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"pacifica_perpetual_testnet": "pacifica_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"pacifica_perpetual_testnet": "SOL-USDC"}
OTHER_DOMAINS_DEFAULT_FEES = {"pacifica_perpetual_testnet": [0.00015, 0.0004]}


class PacificaPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "pacifica_perpetual_testnet"

    pacifica_perpetual_testnet_agent_wallet_public_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Pacifica Perpetual Testnet Agent Wallet Public Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    pacifica_perpetual_testnet_agent_wallet_private_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Pacifica Perpetual Testnet Agent Wallet Private Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    pacifica_perpetual_testnet_user_wallet_public_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your Pacifica Perpetual Testnet User Wallet Public Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True
        }
    )

    pacifica_perpetual_testnet_api_config_key: SecretStr = Field(
        default=SecretStr(""),
        json_schema_extra={
            "prompt": "Enter your Pacifica Perpetual Testnet API Config Key (optional)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": False
        }
    )

    model_config = ConfigDict(title="pacifica_perpetual_testnet")


OTHER_DOMAINS_KEYS = {
    "pacifica_perpetual_testnet": PacificaPerpetualTestnetConfigMap.model_construct()
}
