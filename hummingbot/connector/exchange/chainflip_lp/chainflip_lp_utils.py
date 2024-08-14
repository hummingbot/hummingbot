from decimal import Decimal

from pydantic import Field, SecretStr, validator

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.client.config.config_validators import validate_with_regex
<<<<<<< HEAD
from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.client.config.config_validators import  validate_with_regex
=======
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "FLIP-USDT"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0"),
    taker_percent_fee_decimal=Decimal("0"),
)


<<<<<<< HEAD
<<<<<<< HEAD
def chains_as_str(asset: str):
    return ",".join(CONSTANTS.SAME_CHAINS[asset])

=======
def chains_as_str():
    return ",".join(CONSTANTS.SAME_CHAINS)
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
def chains_as_str(asset: str):
    return ",".join(CONSTANTS.SAME_CHAINS[asset])
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)


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
<<<<<<< HEAD
<<<<<<< HEAD
=======
            is_secure=True,
=======
            is_secure=False,
>>>>>>> cb0a3d276 ((refactor) implement review changes)
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    chainflip_eth_chain: str = Field(
        default=CONSTANTS.DEFAULT_CHAIN_CONFIG["ETH"],
        client_data=ClientFieldData(
            prompt=lambda cm: f'Enter the ETH chain you will like to use for this session. default: {CONSTANTS.DEFAULT_CHAIN_CONFIG["ETH"]}',
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
<<<<<<< HEAD
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
<<<<<<< HEAD
        client_data=ClientFieldData(
=======
    chainflip_usdc_chain: str = Field(
        default=CONSTANTS.DEFAULT_CHAIN_CONFIG["ETH"],
=======
>>>>>>> cb0a3d276 ((refactor) implement review changes)
        client_data=ClientFieldData(
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
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
        error_message = f"valid options are: {chains_as_str('ETH')}"
        if v not in CONSTANTS.SAME_CHAINS["ETH"]:
            raise ValueError(error_message)
        return v

    @validator("chainflip_usdc_chain", pre=True)
    def validate_chainflip_usdc_chain(cls, v: str):
<<<<<<< HEAD
<<<<<<< HEAD
        error_message = f"valid options are: {chains_as_str('USDC')}"
        if v not in CONSTANTS.SAME_CHAINS["USDC"]:
=======
        error_message = f"valid options are: {chains_as_str()}"
        if v not in CONSTANTS.SAME_CHAINS:
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
        error_message = f"valid options are: {chains_as_str('USDC')}"
        if v not in CONSTANTS.SAME_CHAINS["USDC"]:
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
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
<<<<<<< HEAD
<<<<<<< HEAD
        default=CONSTANTS.DEFAULT_CHAIN_CONFIG["USDC"],
=======
        default=CONSTANTS.DEFAULT_CHAIN_CONFIG["ETH"],
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
        default=CONSTANTS.DEFAULT_CHAIN_CONFIG["USDC"],
>>>>>>> cb0a3d276 ((refactor) implement review changes)
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
        error_message = f"valid options are: {chains_as_str('ETH')}"
        if v not in CONSTANTS.SAME_CHAINS["ETH"]:
            raise ValueError(error_message)
        return v

    @validator("chainflip_usdc_chain", pre=True)
    def validate_chainflip_usdc_chain(cls, v: str):
<<<<<<< HEAD
<<<<<<< HEAD
        error_message = f"valid options are: {chains_as_str('USDC')}"
        if v not in CONSTANTS.SAME_CHAINS["USDC"]:
=======
        error_message = f"valid options are: {chains_as_str()}"
        if v not in CONSTANTS.SAME_CHAINS:
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
=======
        error_message = f"valid options are: {chains_as_str('USDC')}"
        if v not in CONSTANTS.SAME_CHAINS["USDC"]:
>>>>>>> 622c18947 ((fix) fix tests and make chainflip lp codebase updates)
            raise ValueError(error_message)
        return v


OTHER_DOMAINS_KEYS = {"chainflip_lp_testnet": ChainflipLpTestnetConfigMap.construct()}
