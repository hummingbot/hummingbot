import numbers
from decimal import Decimal
from random import randint
from typing import Any, Dict, Optional

from pydantic import Field, SecretStr

import hummingbot.connector.exchange.vertex.vertex_constants as CONSTANTS
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
USE_ETHEREUM_WALLET = False
EXAMPLE_PAIR = "WBTC-USDC"
DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.0"),
    taker_percent_fee_decimal=Decimal("0.0002"),
)


def hex_to_bytes32(hex_string: str) -> bytes:
    if hex_string.startswith("0x"):
        hex_string = hex_string[2:]
    data_bytes = bytes.fromhex(hex_string)
    padded_data = data_bytes + b"\x00" * (32 - len(data_bytes))
    return padded_data


def convert_timestamp(timestamp: Any) -> float:
    return float(timestamp) / 1e9


def trading_pair_to_product_id(trading_pair: str, exchange_market_info: Dict, is_perp: Optional[bool] = False) -> int:
    tp = trading_pair.replace("-", "/")
    for product_id in exchange_market_info:
        if is_perp and "perp" not in exchange_market_info[product_id]["symbol"].lower():
            continue
        if exchange_market_info[product_id]["market"] == tp:
            return product_id
    return -1


def market_to_trading_pair(market: str) -> str:
    """Converts a market symbol from Vertex to a trading pair."""
    return market.replace("/", "-")


def convert_from_x18(data: Any, precision: Optional[Decimal] = None) -> Any:
    """
    Converts numerical data encoded as x18 to a string representation of a
    floating point number, resursively applies the conversion for other data types.
    """
    if data is None:
        return None

    # Check if data type is str or float
    if isinstance(data, str) or isinstance(data, numbers.Number):
        data = Decimal(data) / Decimal("1000000000000000000")  # type: ignore
        if precision:
            data = data.quantize(precision)
        return str(data)

    if isinstance(data, dict):
        for k, v in data.items():
            data[k] = convert_from_x18(v, precision)
    elif isinstance(data, list):
        for i in range(0, len(data)):
            data[i] = convert_from_x18(data[i], precision)
    else:
        raise TypeError("Data is of unsupported type for convert_from_x18 to process", data)
    return data


def convert_to_x18(data: Any, precision: Optional[Decimal] = None) -> Any:
    """
    Converts numerical data encoded to a string representation of x18, resursively
    applies the conversion for other data types.
    """
    if data is None:
        return None

    # Check if data type is str or float
    if isinstance(data, str) or isinstance(data, numbers.Number):
        data = Decimal(str(data))  # type: ignore
        if precision:
            data = data.quantize(precision)
        return str((data * Decimal("1000000000000000000")).quantize(Decimal("1")))

    if isinstance(data, dict):
        for k, v in data.items():
            data[k] = convert_to_x18(v, precision)
    elif isinstance(data, list):
        for i in range(0, len(data)):
            data[i] = convert_to_x18(data[i], precision)
    else:
        raise TypeError("Data is of unsupported type for convert_to_x18 to process", data)
    return data


def generate_expiration(timestamp: float = None, order_type: Optional[str] = None) -> str:
    default_max_time = 8640000000000000  # NOTE: Forever
    default_day_time = 86400
    # Default significant bit is 0 for GTC
    # https://vertex-protocol.gitbook.io/docs/developer-resources/api/websocket-rest-api/executes/place-order
    sig_bit = 0

    if order_type == CONSTANTS.TIME_IN_FORCE_IOC:
        sig_bit = 1
    elif order_type == CONSTANTS.TIME_IN_FORCE_FOK:
        sig_bit = 2
    elif order_type == CONSTANTS.TIME_IN_FORCE_POSTONLY:
        sig_bit = 3

    # NOTE: We can setup maxtime
    expiration = str(default_max_time | (sig_bit << 62))

    if timestamp:
        unix_epoch = int(timestamp)
        expiration = str((unix_epoch + default_day_time) | (sig_bit << 62))

    return expiration


def generate_nonce(timestamp: float, expiry_ms: int = 90) -> int:
    unix_epoch_ms = int((timestamp * 1000) + (expiry_ms * 1000))
    nonce = (unix_epoch_ms << 20) + randint(1, 1001)
    return nonce


def convert_address_to_sender(address: str) -> str:
    # NOTE: the sender address includes the subaccount, which is "default" by default, you cannot interact with
    # subaccounts outside of default on the UI currently.
    # https://vertex-protocol.gitbook.io/docs/developer-resources/api/websocket-rest-api/executes#signing
    if isinstance(address, str):
        default_12bytes = "64656661756c740000000000"
        return address + default_12bytes
    raise TypeError("Address must be of type string")


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Default's to true, there isn't anything to check agaisnt.
    """
    return True


class VertexConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="vertex", const=True, client_data=None)
    vertex_arbitrum_private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Arbitrum private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    vertex_arbitrum_address: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Arbitrum wallet address",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    # NOTE: Vertex allows for spot leverage
    # vertex_spot_leverage: bool = Field(
    #     default=False,
    #     client_data=ClientFieldData(
    #         prompt=lambda cm: "Enable spot leverage? This auto-borrows assets against your margin to trade with larger size. Set to True to enable borrowing (default: False).",
    #         is_secure=False,
    #         is_connect_key=False,
    #         prompt_on_new=True,
    #     ),
    # )

    class Config:
        title = "vertex"


KEYS = VertexConfigMap.construct()


class VertexTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="vertex_testnet", client_data=None)
    vertex_testnet_arbitrum_private_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Arbitrum TESTNET private key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    vertex_testnet_arbitrum_address: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Arbitrum TESTNET wallet address",
            is_secure=False,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    # vertex_testnet_spot_leverage: bool = Field(
    #     default=False,
    #     client_data=ClientFieldData(
    #         prompt=lambda cm: "Enable spot leverage? This auto-borrows assets against your margin to trade with larger size. Set to True to enable borrowing (default: False).",
    #         is_secure=False,
    #         is_connect_key=False,
    #         prompt_on_new=True,
    #     ),
    # )

    class Config:
        title = "vertex_testnet"


OTHER_DOMAINS = ["vertex_testnet"]
OTHER_DOMAINS_PARAMETER = {"vertex_testnet": "vertex_testnet"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"vertex_testnet": "WBTC-USDC"}
OTHER_DOMAINS_DEFAULT_FEES = {"vertex_testnet": DEFAULT_FEES}

OTHER_DOMAINS_KEYS = {"vertex_testnet": VertexTestnetConfigMap.construct()}
