from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants as CONSTANTS
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Default fee schema for Decibel (fixed rates, no tier system)
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal(str(CONSTANTS.MAKER_FEE_RATE)),
    taker_percent_fee_decimal=Decimal(str(CONSTANTS.TAKER_FEE_RATE)),
    buy_percent_fee_deducted_from_returns=False,
)

CENTRALIZED = False      # Decibel is a DEX (decentralized)
EXAMPLE_PAIR = "BTC-USD"


def is_exchange_information_valid(market_info: Dict[str, Any]) -> bool:
    """
    Return True when a market entry from GET /api/v1/markets is tradeable.

    :param market_info: Single market dict from the markets API response.
    """
    return bool(market_info.get("market_name")) and market_info.get("active", True)


def exchange_symbol_to_hb_trading_pair(exchange_symbol: str) -> str:
    """
    Convert a Decibel exchange symbol to a Hummingbot trading pair.

    Example: ``"BTC/USD"`` -> ``"BTC-USD"``
    """
    return exchange_symbol.replace("/", "-")


def hb_trading_pair_to_exchange_symbol(trading_pair: str) -> str:
    """
    Convert a Hummingbot trading pair to a Decibel exchange symbol.

    Example: ``"BTC-USD"`` -> ``"BTC/USD"``
    """
    return trading_pair.replace("-", "/")


class DecibelPerpetualConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="decibel_perpetual", const=True, client_data=None)

    decibel_perpetual_api_wallet_public_key: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enter your Decibel API wallet public key (Aptos address for signing transactions)"
            ),
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    decibel_perpetual_api_wallet_private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enter your Decibel API wallet private key (Ed25519 hex, used to sign on-chain transactions)"
            ),
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    decibel_perpetual_main_wallet_public_key: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enter your Decibel main wallet public key (Aptos address for account lookups)"
            ),
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    decibel_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enter your Decibel API key from geomi.dev (Bearer token for REST API access)"
            ),
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "decibel_perpetual"


KEYS = DecibelPerpetualConfigMap.construct()

OTHER_DOMAINS = [CONSTANTS.TESTNET_DOMAIN]
OTHER_DOMAINS_PARAMETER = {CONSTANTS.TESTNET_DOMAIN: CONSTANTS.TESTNET_DOMAIN}
OTHER_DOMAINS_EXAMPLE_PAIR = {CONSTANTS.TESTNET_DOMAIN: "BTC-USD"}
OTHER_DOMAINS_DEFAULT_FEES = {CONSTANTS.TESTNET_DOMAIN: DEFAULT_FEES}


class DecibelPerpetualTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default=CONSTANTS.TESTNET_DOMAIN, const=True, client_data=None)

    decibel_perpetual_api_wallet_public_key: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enter your Decibel Testnet API wallet public key"
            ),
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    decibel_perpetual_api_wallet_private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enter your Decibel Testnet API wallet private key (Ed25519 hex)"
            ),
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    decibel_perpetual_main_wallet_public_key: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enter your Decibel Testnet main wallet public key"
            ),
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    decibel_perpetual_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: (
                "Enter your Decibel Testnet API key from geomi.dev"
            ),
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = CONSTANTS.TESTNET_DOMAIN


OTHER_DOMAINS_KEYS = {CONSTANTS.TESTNET_DOMAIN: DecibelPerpetualTestnetConfigMap.construct()}
