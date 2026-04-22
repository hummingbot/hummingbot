import json
from decimal import Decimal

from pydantic import AliasChoices, ConfigDict, Field, SecretStr, field_validator

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "ETH-USDC"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.00015"),
    taker_percent_fee_decimal=Decimal("0.0004"),
)


def _is_encrypted_secret_payload(value: str) -> bool:
    candidate = value.strip()
    if len(candidate) < 20 or len(candidate) % 2 != 0:
        return False

    try:
        decoded_json = bytes.fromhex(candidate).decode("utf-8")
        payload = json.loads(decoded_json)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return False

    return isinstance(payload, dict) and "crypto" in payload and "version" in payload


def _is_hex_key(value: str) -> bool:
    candidate = value.strip()
    if candidate.lower().startswith("0x"):
        candidate = candidate[2:]
    return len(candidate) >= 64 and len(candidate) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in candidate)


_API_KEY_FORMAT_HINT = (
    "Lighter API key must be an even-length hex string of at least 64 characters "
    "(e.g. 3d6e9253dc51...4357). Copy it from the Lighter exchange API keys page."
)


class LighterConfigMap(BaseConnectorConfigMap):
    connector: str = "lighter"

    lighter_api_secret: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_api_secret", "lighter_api_key_index"),
        json_schema_extra={
            "prompt": "Enter your Lighter API key index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_account_index: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_account_index"),
        json_schema_extra={
            "prompt": "Enter your Lighter account index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_private_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("lighter_private_key", "lighter_signer_private_key", "lighter_eoa_private_key"),
        json_schema_extra={
            "prompt": "Enter your Lighter API private key (required for order placement/cancel; leave blank for read-only)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": False,
        },
    )

    lighter_api_key: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_api_key"),
        json_schema_extra={
            "prompt": "Enter your Lighter API key (hex string, e.g. 3d6e9253...4357)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    model_config = ConfigDict(title="lighter")

    @field_validator("lighter_api_secret", mode="before")
    @classmethod
    def validate_api_key_index(cls, value):
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        sanitized = raw_value.strip()
        if sanitized == "":
            return SecretStr("")
        if _is_encrypted_secret_payload(sanitized):
            return SecretStr(sanitized)
        if not sanitized.isdigit():
            raise ValueError("Lighter API key index must be an integer string")
        return SecretStr(sanitized)

    @field_validator("lighter_account_index", mode="before")
    @classmethod
    def validate_account_index(cls, value):
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        sanitized = raw_value.strip()
        if sanitized == "":
            return SecretStr("")
        if _is_encrypted_secret_payload(sanitized):
            return SecretStr(sanitized)
        if not sanitized.isdigit():
            raise ValueError("Lighter account index must be an integer string")
        return SecretStr(sanitized)

    @field_validator("lighter_api_key", mode="before")
    @classmethod
    def validate_api_key(cls, value):
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        sanitized = raw_value.strip()
        if sanitized == "":
            raise ValueError(_API_KEY_FORMAT_HINT)
        if _is_encrypted_secret_payload(sanitized):
            return SecretStr(sanitized)
        if not _is_hex_key(sanitized):
            raise ValueError(_API_KEY_FORMAT_HINT)
        return SecretStr(sanitized)


KEYS = LighterConfigMap.model_construct()

OTHER_DOMAINS = ["lighter_testnet"]
OTHER_DOMAINS_PARAMETER = {"lighter_testnet": "lighter_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"lighter_testnet": "ETH-USDC"}
OTHER_DOMAINS_DEFAULT_FEES = {"lighter_testnet": [0.00015, 0.0004]}


class LighterTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = "lighter_testnet"

    lighter_testnet_api_key: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_testnet_api_key"),
        json_schema_extra={
            "prompt": "Enter your Lighter testnet API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_testnet_api_secret: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_testnet_api_secret", "lighter_testnet_api_key_index"),
        json_schema_extra={
            "prompt": "Enter your Lighter testnet API key index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_testnet_account_index: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_testnet_account_index"),
        json_schema_extra={
            "prompt": "Enter your Lighter testnet account index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_testnet_private_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices(
            "lighter_testnet_private_key",
            "lighter_testnet_signer_private_key",
            "lighter_testnet_eoa_private_key",
        ),
        json_schema_extra={
            "prompt": "Enter your Lighter testnet API private key (required for order placement/cancel; leave blank for read-only)",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": False,
        },
    )

    model_config = ConfigDict(title="lighter_testnet")

    @field_validator("lighter_testnet_api_secret", mode="before")
    @classmethod
    def validate_testnet_api_key_index(cls, value):
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        sanitized = raw_value.strip()
        if sanitized == "":
            return SecretStr("")
        if _is_encrypted_secret_payload(sanitized):
            return SecretStr(sanitized)
        if not sanitized.isdigit():
            raise ValueError("Lighter API key index must be an integer string")
        return SecretStr(sanitized)

    @field_validator("lighter_testnet_account_index", mode="before")
    @classmethod
    def validate_testnet_account_index(cls, value):
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        sanitized = raw_value.strip()
        if sanitized == "":
            return SecretStr("")
        if _is_encrypted_secret_payload(sanitized):
            return SecretStr(sanitized)
        if not sanitized.isdigit():
            raise ValueError("Lighter account index must be an integer string")
        return SecretStr(sanitized)

    @field_validator("lighter_testnet_api_key", mode="before")
    @classmethod
    def validate_testnet_api_key(cls, value):
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        sanitized = raw_value.strip()
        if sanitized == "":
            raise ValueError(_API_KEY_FORMAT_HINT)
        if _is_encrypted_secret_payload(sanitized):
            return SecretStr(sanitized)
        if not _is_hex_key(sanitized):
            raise ValueError(_API_KEY_FORMAT_HINT)
        return SecretStr(sanitized)


OTHER_DOMAINS_KEYS = {
    "lighter_testnet": LighterTestnetConfigMap.model_construct(),
}


def is_exchange_information_valid(exchange_info: dict) -> bool:
    market_type = str(exchange_info.get("market_type", "")).lower()
    if market_type and market_type != "spot":
        return False

    status = str(exchange_info.get("status", "")).lower()
    if status in {"inactive", "disabled", "halted", "suspended", "delisted"}:
        return False

    return bool(exchange_info.get("symbol"))
