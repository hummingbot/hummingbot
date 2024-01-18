from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData


def decimal_val_or_none(string_value: str,
                        on_error_return_none: bool = True,
                        ) -> Decimal:
    try:
        return Decimal(string_value)
    except Exception:
        if on_error_return_none:
            return None
        else:
            return Decimal('0')


class CoinswitchxConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="coinswitchx", client_data=None)
    coinswitchx_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Coinswitchx API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    coinswitchx_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Coinswitchx API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "coinswitchx"


KEYS = CoinswitchxConfigMap.construct()

# TODO
OTHER_DOMAINS = []
# OTHER_DOMAINS_PARAMETER = {"binance_us": "us"}
# OTHER_DOMAINS_EXAMPLE_PAIR = {"binance_us": "BTC-USDT"}
# OTHER_DOMAINS_DEFAULT_FEES = {"binance_us": DEFAULT_FEES}
