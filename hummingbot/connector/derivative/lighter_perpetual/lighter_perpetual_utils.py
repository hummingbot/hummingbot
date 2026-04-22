from decimal import Decimal
from typing import Any

from pydantic import AliasChoices, ConfigDict, Field, SecretStr, field_validator

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

    lighter_perpetual_api_secret: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_api_secret",
            "lighter_api_secret",
            "lighter_perpetual_api_key_index",
            "lighter_api_key_index",
        ),
        json_schema_extra={
            "prompt": "Enter your Lighter API key index",
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
            "prompt": "Enter your Lighter account index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_perpetual_private_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices(
            "lighter_perpetual_private_key",
            "lighter_private_key",
            "lighter_signer_private_key",
            "lighter_eoa_private_key",
        ),
        json_schema_extra={
            "prompt": "Enter your Lighter API private key (required for order placement/cancel; leave blank for read-only)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": False,
        },
    )

    lighter_perpetual_api_key: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_api_key",
            "lighter_api_key",
        ),
        json_schema_extra={
            "prompt": "Enter your Lighter API key (hex string, e.g. 3d6e9253...4357)",
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
        return len(key) >= 64 and len(key) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in key)

    _API_KEY_FORMAT_HINT = (
        "Lighter API key must be an even-length hex string of at least 64 characters "
        "(e.g. 3d6e9253dc51...4357). Copy it from the Lighter exchange API keys page."
    )

    @field_validator("lighter_perpetual_api_secret", mode="before")
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

    @field_validator("lighter_perpetual_api_key", mode="before")
    @classmethod
    def validate_api_key(cls, v: Any) -> Any:
        raw = v.get_secret_value() if hasattr(v, "get_secret_value") else str(v)
        if raw == "":
            raise ValueError(cls._API_KEY_FORMAT_HINT)
        if cls._is_encrypted_blob(raw):
            return v
        if not cls._is_hex_key(raw):
            raise ValueError(cls._API_KEY_FORMAT_HINT)
        return v

    model_config = ConfigDict(title="lighter_perpetual")

    @field_validator("lighter_perpetual_private_key", mode="before")
    @classmethod
    def validate_private_key(cls, v: Any) -> Any:
        raw = v.get_secret_value() if hasattr(v, "get_secret_value") else str(v)
        if not raw:
            return v
        if cls._is_encrypted_blob(raw):
            return v
        key = raw[2:] if raw.startswith("0x") else raw
        if len(key) < 64 or len(key) % 2 != 0 or not all(c in "0123456789abcdefABCDEF" for c in key):
            raise ValueError(
                "Lighter private key must be a hex string (64+ characters, with or without 0x prefix). "
                "Copy it from the Lighter exchange API keys page."
            )
        return v


KEYS = LighterPerpetualConfigMap.model_construct()

OTHER_DOMAINS = ["lighter_perpetual_testnet"]
OTHER_DOMAINS_PARAMETER = {"lighter_perpetual_testnet": "lighter_perpetual_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"lighter_perpetual_testnet": "BTC-USDC"}
OTHER_DOMAINS_DEFAULT_FEES = {"lighter_perpetual_testnet": [0.00015, 0.0004]}


class LighterPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "lighter_perpetual_testnet"

    lighter_perpetual_testnet_api_key: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_testnet_api_key",
            "lighter_testnet_api_key",
        ),
        json_schema_extra={
            "prompt": "Enter your Lighter testnet API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_perpetual_testnet_api_secret: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_perpetual_testnet_api_secret",
            "lighter_testnet_api_secret",
            "lighter_perpetual_testnet_api_key_index",
            "lighter_testnet_api_key_index",
        ),
        json_schema_extra={
            "prompt": "Enter your Lighter testnet API key index",
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
            "prompt": "Enter your Lighter testnet account index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_perpetual_testnet_private_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices(
            "lighter_perpetual_testnet_private_key",
            "lighter_testnet_private_key",
            "lighter_perpetual_testnet_signer_private_key",
            "lighter_testnet_signer_private_key",
            "lighter_perpetual_testnet_eoa_private_key",
            "lighter_testnet_eoa_private_key",
        ),
        json_schema_extra={
            "prompt": "Enter your Lighter testnet API private key (required for order placement/cancel; leave blank for read-only)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": False,
        },
    )

    model_config = ConfigDict(title="lighter_perpetual_testnet")

    @staticmethod
    def _is_encrypted_blob(raw: str) -> bool:
        return len(raw) > 64 and all(c in "0123456789abcdefABCDEF" for c in raw)

    @staticmethod
    def _is_hex_key(raw: str) -> bool:
        key = raw[2:] if raw.lower().startswith("0x") else raw
        return len(key) >= 64 and len(key) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in key)

    _API_KEY_FORMAT_HINT = (
        "Lighter API key must be an even-length hex string of at least 64 characters "
        "(e.g. 3d6e9253dc51...4357). Copy it from the Lighter exchange API keys page."
    )

    @field_validator("lighter_perpetual_testnet_api_secret", mode="before")
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
                f"Lighter testnet API key index must be an integer (e.g. 4), got: {raw!r}."
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
                f"Lighter testnet account index must be an integer (e.g. 693751), got: {raw!r}."
            )
        return v

    @field_validator("lighter_perpetual_testnet_api_key", mode="before")
    @classmethod
    def validate_testnet_api_key(cls, v: Any) -> Any:
        raw = v.get_secret_value() if hasattr(v, "get_secret_value") else str(v)
        if raw == "":
            raise ValueError(cls._API_KEY_FORMAT_HINT)
        if cls._is_encrypted_blob(raw):
            return v
        if not cls._is_hex_key(raw):
            raise ValueError(cls._API_KEY_FORMAT_HINT)
        raw = v.get_secret_value() if hasattr(v, "get_secret_value") else str(v)
        if not raw:
            return v
        if cls._is_encrypted_blob(raw):
            return v
        key = raw[2:] if raw.startswith("0x") else raw
        if len(key) < 64 or len(key) % 2 != 0 or not all(c in "0123456789abcdefABCDEF" for c in key):
            raise ValueError(
                "Lighter testnet private key must be a hex string (64+ characters, with or without 0x prefix)."
            )
        return v


OTHER_DOMAINS_KEYS = {
    "lighter_perpetual_testnet": LighterPerpetualTestnetConfigMap.model_construct()
}
