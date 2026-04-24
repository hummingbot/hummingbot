from decimal import Decimal
from typing import Any

from pydantic import AliasChoices, ConfigDict, Field, SecretStr, field_validator, model_validator

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDC"

# Default fee values aligned with the currently observed base tier.
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.00015"),
    taker_percent_fee_decimal=Decimal("0.0004"),
)


class LighterPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = "lighter_perpetual"

    lighter_perpetual_api_key_index: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_api_key_index",
            "lighter_perpetual_api_secret",
            "lighter_api_secret",
            "lighter_api_key_index",
        ),
        json_schema_extra={
            "prompt": "Enter your API Key Index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_perpetual_account_index: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_account_index",
            "lighter_account_index",
        ),
        json_schema_extra={
            "prompt": "Enter your Account Index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_perpetual_api_key_private_key: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_api_key_private_key",
            "lighter_perpetual_api_key",
            "lighter_api_key",
        ),
        json_schema_extra={
            "prompt": "Enter your Private Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    @staticmethod
    def _is_encrypted_blob(raw: str) -> bool:
        return len(raw) > 64 and all(c in "0123456789abcdefABCDEF" for c in raw)

    @staticmethod
    def _is_hex_key(raw: str) -> bool:
        key = raw[2:] if raw.lower().startswith("0x") else raw
        return len(key) >= 64 and all(c in "0123456789abcdefABCDEF" for c in key)

    @field_validator("lighter_perpetual_api_key_index", mode="before")
    @classmethod
    def validate_api_key_index(cls, v: Any) -> Any:
        raw = v.get_secret_value() if hasattr(v, "get_secret_value") else str(v)
        if raw == "":
            return v
        if cls._is_encrypted_blob(raw):
            return v
        try:
            int(raw)
        except (ValueError, TypeError):
            raise ValueError(
                f"Lighter API key index must be an integer (e.g. 4), got: {raw!r}. "
                "Find your key index on the Lighter exchange API keys page."
            )
        return v

    @field_validator("lighter_perpetual_account_index", mode="before")
    @classmethod
    def validate_account_index(cls, v: Any) -> Any:
        raw = v.get_secret_value() if hasattr(v, "get_secret_value") else str(v)
        if raw == "":
            return v
        if cls._is_encrypted_blob(raw):
            return v
        try:
            int(raw)
        except (ValueError, TypeError):
            raise ValueError(
                f"Lighter account index must be an integer (e.g. 693751), got: {raw!r}. "
                "Find your account index on the Lighter exchange account page."
            )
        return v

    @field_validator("lighter_perpetual_api_key_private_key", mode="before")
    @classmethod
    def validate_api_key(cls, v: Any) -> Any:
        raw = v.get_secret_value() if hasattr(v, "get_secret_value") else str(v)
        if raw == "":
            return v
        if cls._is_encrypted_blob(raw):
            return v
        if not cls._is_hex_key(raw):
            raise ValueError(
                "Lighter API Private Key must be a hex string (64+ characters, with or without 0x prefix). "
                "Copy it from the Lighter exchange API keys page."
            )
        return v

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_fields(cls, data):
        """Discard removed fields from saved YAML configs."""
        if not isinstance(data, dict):
            return data
        data.pop("lighter_perpetual_api_key_public_key", None)
        return data

    model_config = ConfigDict(title="lighter_perpetual")


KEYS = LighterPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["lighter_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"lighter_perpetual_testnet": "lighter_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"lighter_perpetual_testnet": "BTC-USDC"}
OTHER_DOMAINS_DEFAULT_FEES = {"lighter_perpetual_testnet": [0.00015, 0.0004]}


class LighterPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "lighter_perpetual_testnet"

    lighter_perpetual_testnet_api_key_index: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_testnet_api_key_index",
            "lighter_perpetual_testnet_api_secret",
            "lighter_testnet_api_secret",
            "lighter_testnet_api_key_index",
        ),
        json_schema_extra={
            "prompt": "Enter your API Key Index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_perpetual_testnet_account_index: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_testnet_account_index",
            "lighter_testnet_account_index",
        ),
        json_schema_extra={
            "prompt": "Enter your Account Index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_perpetual_testnet_api_key_private_key: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_testnet_api_key_private_key",
            "lighter_perpetual_testnet_api_key",
            "lighter_testnet_api_key",
        ),
        json_schema_extra={
            "prompt": "Enter your Private Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    model_config = ConfigDict(title="lighter_perpetual_testnet")

    @staticmethod
    def _is_encrypted_blob(raw: str) -> bool:
        return len(raw) > 64 and all(c in "0123456789abcdefABCDEF" for c in raw)

    @staticmethod
    def _is_hex_key(raw: str) -> bool:
        key = raw[2:] if raw.lower().startswith("0x") else raw
        return len(key) >= 64 and all(c in "0123456789abcdefABCDEF" for c in key)

    @field_validator("lighter_perpetual_testnet_api_key_index", mode="before")
    @classmethod
    def validate_testnet_api_key_index(cls, v: Any) -> Any:
        raw = v.get_secret_value() if hasattr(v, "get_secret_value") else str(v)
        if raw == "":
            return v
        if cls._is_encrypted_blob(raw):
            return v
        try:
            int(raw)
        except (ValueError, TypeError):
            raise ValueError(
                f"Lighter API key index must be an integer (e.g. 4), got: {raw!r}."
            )
        return v

    @field_validator("lighter_perpetual_testnet_account_index", mode="before")
    @classmethod
    def validate_testnet_account_index(cls, v: Any) -> Any:
        raw = v.get_secret_value() if hasattr(v, "get_secret_value") else str(v)
        if raw == "":
            return v
        if cls._is_encrypted_blob(raw):
            return v
        try:
            int(raw)
        except (ValueError, TypeError):
            raise ValueError(
                f"Lighter account index must be an integer (e.g. 693751), got: {raw!r}."
            )
        return v

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_fields(cls, data):
        """Discard removed fields from saved YAML configs."""
        if not isinstance(data, dict):
            return data
        data.pop("lighter_perpetual_testnet_api_key_public_key", None)
        return data

    @field_validator("lighter_perpetual_testnet_api_key_private_key", mode="before")
    @classmethod
    def validate_testnet_api_key(cls, v: Any) -> Any:
        raw = v.get_secret_value() if hasattr(v, "get_secret_value") else str(v)
        if raw == "":
            return v
        if cls._is_encrypted_blob(raw):
            return v
        if not cls._is_hex_key(raw):
            raise ValueError(
                "Lighter API Private Key must be a hex string (64+ characters, with or without 0x prefix)."
            )
        return v


OTHER_DOMAINS_KEYS = {
    "lighter_perpetual_testnet": LighterPerpetualTestnetConfigMap.model_construct()
}
