from decimal import Decimal
from typing import Dict

from Crypto.PublicKey import RSA
from pydantic import Field, root_validator, validator
from pydantic.types import SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.connector.exchange.lbank import lbank_constants as CONSTANTS
from hummingbot.connector.exchange.lbank.lbank_auth import LbankAuth
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"


class LbankConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="lbank", const=True, client_data=None)
    lbank_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your LBank API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    lbank_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your LBank secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    lbank_auth_method: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                f"Enter your LBank API Authentication Method ({'/'.join(list(CONSTANTS.LBANK_AUTH_METHODS))})"
            ),
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "lbank"

    @validator("lbank_auth_method", pre=True)
    def validate_auth_method(cls, value: str):
        """Used for client-friendly error output."""
        if value not in CONSTANTS.LBANK_AUTH_METHODS:
            raise ValueError(f"Authentication Method: {value} not supported. Supported methods are RSA/HmacSHA256")
        return value

        # === post-validations ===

    @root_validator()
    def post_validations(cls, values: Dict):
        auth_method = values.get("lbank_auth_method")  # when using client, model constructed incrementally
        if auth_method == "RSA":
            secret_key = values.get("lbank_secret_key")  # when using client, model constructed incrementally
            if secret_key is not None:
                try:
                    RSA.importKey(LbankAuth.RSA_KEY_FORMAT.format(secret_key.get_secret_value()))
                except Exception as e:
                    raise ValueError(f"Unable to import RSA keys. Error: {str(e)}")
        return values


KEYS = LbankConfigMap.construct()
