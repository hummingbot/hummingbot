from decimal import Decimal

from pydantic import Field, SecretStr, validator

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.client.config.config_validators import validate_with_regex
from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "FLIP-USDT"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
)


def chains_as_str():
    return ",".join(CONSTANTS.SAME_CHAINS)


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
    chainflip_lp_address: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Chainflip LP Address",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    chainflip_eth_chain: str = Field(
        default=CONSTANTS.DEFAULT_CHAIN_CONFIG["ETH"],
        client_data=ClientFieldData(
            prompt=lambda cm: f'Enter the ETH chain you will like to use for this session. default: {CONSTANTS.DEFAULT_CHAIN_CONFIG["ETH"]}',
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    chainflip_usdc_chain: str = Field(
        default=CONSTANTS.DEFAULT_CHAIN_CONFIG["USDC"],
        client_data=ClientFieldData(
            prompt=lambda cm: f'Enter the USDC chain you will like to use for this session. default: {CONSTANTS.DEFAULT_CHAIN_CONFIG["USDC"]}',
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

    @validator("chainflip_eth_chain", pre=True)
    def validate_chainflip_eth_chain(cls, v: str):
        error_message = f"valid options are: {chains_as_str()}"
        if v not in CONSTANTS.SAME_CHAINS:
            raise ValueError(error_message)
        return v

    @validator("chainflip_usdc_chain", pre=True)
    def validate_chainflip_usdc_chain(cls, v: str):
        error_message = f"valid options are: {chains_as_str()}"
        if v not in CONSTANTS.SAME_CHAINS:
            raise ValueError(error_message)
        return v


KEYS = ChainflipLpConfigMap.construct()

OTHER_DOMAINS = ["chainflip_lp_testnet"]
OTHER_DOMAINS_PARAMETER = {"chainflip_lp_testnet": "chainflip_lp_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"chainflip_lp_testnet": "sFLIP-sUSDT"}
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
    chainflip_lp_address: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Chainflip LP Address",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    chainflip_eth_chain: str = Field(
        default=CONSTANTS.DEFAULT_CHAIN_CONFIG["ETH"],
        client_data=ClientFieldData(
            prompt=lambda cm: f'Enter the ETH chain you will like to use for this session. default: {CONSTANTS.DEFAULT_CHAIN_CONFIG["ETH"]}',
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    chainflip_usdc_chain: str = Field(
        default=CONSTANTS.DEFAULT_CHAIN_CONFIG["USDC"],
        client_data=ClientFieldData(
            prompt=lambda cm: f'Enter the USDC chain you will like to use for this session. default: {CONSTANTS.DEFAULT_CHAIN_CONFIG["USDC"]}',
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

    @validator("chainflip_eth_chain", pre=True)
    def validate_chainflip_eth_chain(cls, v: str):
        error_message = f"valid options are: {chains_as_str()}"
        if v not in CONSTANTS.SAME_CHAINS:
            raise ValueError(error_message)
        return v

    @validator("chainflip_usdc_chain", pre=True)
    def validate_chainflip_usdc_chain(cls, v: str):
        error_message = f"valid options are: {chains_as_str()}"
        if v not in CONSTANTS.SAME_CHAINS:
            raise ValueError(error_message)
        return v


OTHER_DOMAINS_KEYS = {"chainflip_lp_testnet": ChainflipLpTestnetConfigMap.construct()}
