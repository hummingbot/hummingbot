import json
from decimal import Decimal
from typing import Optional

from pydantic import AliasChoices, ConfigDict, Field, SecretStr, field_validator, model_validator

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

    lighter_api_key_index: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_api_key_index", "lighter_api_secret"),
        json_schema_extra={
            "prompt": "Enter your API Key Index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_account_index: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_account_index"),
        json_schema_extra={
            "prompt": "Enter your Account Index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_api_key_public_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("lighter_api_key_public_key"),
        json_schema_extra={
            "prompt": "Enter your Public Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_api_key_private_key: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_api_key_private_key", "lighter_api_key", "lighter_private_key"),
        json_schema_extra={
            "prompt": "Enter your Private Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    model_config = ConfigDict(title="lighter")

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_fields(cls, data):
        """Map old field names from saved YAML configs to the current names."""
        if not isinstance(data, dict):
            return data
        # lighter_api_secret → lighter_api_key_index
        if "lighter_api_secret" in data and "lighter_api_key_index" not in data:
            data["lighter_api_key_index"] = data.pop("lighter_api_secret")
        else:
            data.pop("lighter_api_secret", None)
        # lighter_api_key → lighter_api_key_private_key
        if "lighter_api_key" in data and "lighter_api_key_private_key" not in data:
            data["lighter_api_key_private_key"] = data.pop("lighter_api_key")
        else:
            data.pop("lighter_api_key", None)
        # lighter_private_key was a separate L1 key; discard (encrypted value is stale after rename)
        data.pop("lighter_private_key", None)
        return data

    @field_validator("lighter_api_key_index", mode="before")
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

    @field_validator("lighter_api_key_private_key", mode="before")
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

    lighter_testnet_api_key_index: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_testnet_api_key_index", "lighter_testnet_api_secret"),
        json_schema_extra={
            "prompt": "Enter your API Key Index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_testnet_account_index: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices("lighter_testnet_account_index"),
        json_schema_extra={
            "prompt": "Enter your Account Index",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_testnet_api_key_public_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("lighter_testnet_api_key_public_key"),
        json_schema_extra={
            "prompt": "Enter your Public Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    lighter_testnet_api_key_private_key: SecretStr = Field(
        default=...,
        validation_alias=AliasChoices(
            "lighter_testnet_api_key_private_key",
            "lighter_testnet_api_key",
            "lighter_testnet_private_key",
        ),
        json_schema_extra={
            "prompt": "Enter your Private Key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    model_config = ConfigDict(title="lighter_testnet")

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_fields(cls, data):
        """Map old field names from saved YAML configs to the current names."""
        if not isinstance(data, dict):
            return data
        # lighter_testnet_api_secret → lighter_testnet_api_key_index
        if "lighter_testnet_api_secret" in data and "lighter_testnet_api_key_index" not in data:
            data["lighter_testnet_api_key_index"] = data.pop("lighter_testnet_api_secret")
        else:
            data.pop("lighter_testnet_api_secret", None)
        # lighter_testnet_api_key → lighter_testnet_api_key_private_key
        if "lighter_testnet_api_key" in data and "lighter_testnet_api_key_private_key" not in data:
            data["lighter_testnet_api_key_private_key"] = data.pop("lighter_testnet_api_key")
        else:
            data.pop("lighter_testnet_api_key", None)
        # lighter_testnet_private_key was a separate L1 key; discard
        data.pop("lighter_testnet_private_key", None)
        return data

    @field_validator("lighter_testnet_api_key_index", mode="before")
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

    @field_validator("lighter_testnet_api_key_private_key", mode="before")
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


async def fetch_lighter_public_key(connector_name: str, account_index: str, api_key_index: str) -> Optional[str]:
    """Fetch the public key for a lighter API key from the exchange REST API.

    Returns the public key hex string, or None if the lookup fails.
    """
    import logging

    import aiohttp

    from hummingbot.connector.exchange.lighter.lighter_constants import REST_URL, TESTNET_REST_URL

    logger = logging.getLogger(__name__)
    base_url = TESTNET_REST_URL if connector_name in ("lighter_testnet", "lighter_perpetual_testnet") else REST_URL
    url = f"{base_url}/apikeys"
    params = {"account_index": account_index, "api_key_index": api_key_index}
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    api_keys = data.get("api_keys", [])
                    if api_keys:
                        return api_keys[0].get("public_key")
                    logger.warning(
                        f"fetch_lighter_public_key: no api_keys in response "
                        f"(account={account_index}, key_index={api_key_index}): {data}"
                    )
                else:
                    logger.warning(
                        f"fetch_lighter_public_key: HTTP {resp.status} "
                        f"(account={account_index}, key_index={api_key_index})"
                    )
    except Exception as e:
        logger.warning(f"fetch_lighter_public_key failed: {e}")
    return None


async def validate_lighter_api_key_index(connector_name: str, account_index: str, api_key_index: str) -> Optional[str]:
    """Validate that api_key_index exists within the given account.

    Returns None if the key is valid (or if the check cannot be performed due to a network error).
    Returns an error message string if the key index is not found in the account.
    """
    import aiohttp

    from hummingbot.connector.exchange.lighter.lighter_constants import REST_URL, TESTNET_REST_URL

    base_url = TESTNET_REST_URL if connector_name in ("lighter_testnet", "lighter_perpetual_testnet") else REST_URL
    url = f"{base_url}/apikeys"
    params = {"account_index": account_index, "api_key_index": api_key_index}
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if not data.get("api_keys"):
                        return (
                            f"No API key found at index {api_key_index} for account {account_index}. "
                            "Please verify your API key index."
                        )
    except Exception:
        pass
    return None
