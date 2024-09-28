import logging
from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-JPY"

# Update DEFAULT_FEES based on Zaif's actual fee structure
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0"),  # Assuming 0% maker fee
    taker_percent_fee_decimal=Decimal("0.03"),  # Assuming 0% taker fee
)

def is_pair_information_valid(pair_info: Dict[str, Any]) -> bool:
    required_keys = ['currency_pair', 'item_unit', 'currency_unit']
    return all(key in pair_info for key in required_keys)

class ZaifConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="zaif", client_data=None)
    zaif_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Zaif API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    zaif_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Zaif secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "zaif"

KEYS = ZaifConfigMap.construct()
    
