from decimal import Decimal

from pydantic import Field, validator

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.client.config.config_validators import validate_with_regex
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "FLIP/Ethereum-USDT/Ethereum"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.00"),
    taker_percent_fee_decimal=Decimal("0.00"),
)


class ChainflipLpConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="chainflip_lp", const=True, client_data=None)
    chainflip_lp_api_url: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Chainflip LP API RPC Node Url (e.g http://localhost:10589)",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    chainflip_lp_address: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Chainflip LP Address",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "chainflip_lp"

    @validator("chainflip_lp_api_url", pre=True)
    def validate_chainflip_lp_api_url(cls, v: str):
        pattern = r"^https?:"
        error_message = "Please enter a url starting with http or https"
        ret = validate_with_regex(v, pattern, error_message)
        if ret is not None:
            raise ValueError(ret)
        return v


KEYS = ChainflipLpConfigMap.construct()

OTHER_DOMAINS = ["chainflip_lp_testnet"]
OTHER_DOMAINS_PARAMETER = {"chainflip_lp_testnet": "chainflip_lp_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"chainflip_lp_testnet": "FLIP/Ethereum-USDT/Ethereum"}
OTHER_DOMAINS_DEFAULT_FEES = {"chainflip_lp_testnet": DEFAULT_FEES}


class ChainflipLpTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="chainflip_lp_testnet", const=True, client_data=None)
    chainflip_lp_api_url: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Chainflip LP Testnet API RPC Node Url (e.g http://localhost:10589)",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    chainflip_lp_address: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Chainflip LP Address",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "chainflip_lp_testnet"

    @validator("chainflip_lp_api_url", pre=True)
    def validate_chainflip_lp_api_url(cls, v: str):
        pattern = r"^https?:"
        error_message = "Please enter a url starting with http or https"
        ret = validate_with_regex(v, pattern, error_message)
        if ret is not None:
            raise ValueError(ret)
        return v


OTHER_DOMAINS_KEYS = {"chainflip_lp_testnet": ChainflipLpTestnetConfigMap.construct()}
