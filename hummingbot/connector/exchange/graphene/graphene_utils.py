# DISABLE SELECT PYLINT TESTS
# pylint: disable=no-member
"""
 ╔════════════════════════════════════════════════════╗
 ║ ╔═╗╦═╗╔═╗╔═╗╦ ╦╔═╗╔╗╔╔═╗  ╔╦╗╔═╗╔╦╗╔═╗╔╗╔╔═╗╔╦╗╔═╗ ║
 ║ ║ ╦╠╦╝╠═╣╠═╝╠═╣║╣ ║║║║╣   ║║║║╣  ║ ╠═╣║║║║ ║ ║║║╣  ║
 ║ ╚═╝╩╚═╩ ╩╩  ╩ ╩╚═╝╝╚╝╚═╝  ╩ ╩╚═╝ ╩ ╩ ╩╝╚╝╚═╝═╩╝╚═╝ ║
 ║    DECENTRALIZED EXCHANGE HUMMINGBOT CONNECTOR     ║
 ╚════════════════════════════════════════════════════╝
~
forked from binance_utils v1.0.0
~
"""
# STANDARD MODULES
import os
import socket

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData

# HUMMINGBOT MODULES
from hummingbot.connector.exchange.graphene.graphene_constants import GrapheneConstants
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce


class PeerplaysConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="peerplays", client_data=None)
    peerplays_user: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Peerplays username",
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    peerplays_wif: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Peerplays WIF",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    peerplays_pairs: str = Field(
        default="BTC-PPY,HIVE-PPY,HBD-PPY",
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Peerplays trading pairs in this format",
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "peerplays"


class PeerplaysTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="peerplays_testnet", client_data=None)
    peerplays_testnet_user: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Peerplays Testnet username",
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    peerplays_testnet_wif: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Peerplays Testnet WIF",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    peerplays_testnet_pairs: str = Field(
        default="TEST-ABC,TEST-XYZ",
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Peerplays Testnet trading pairs in this format",
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "peerplays_testnet"


class BitsharesConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="bitshares", client_data=None)
    bitshares_user: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitshares username",
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    bitshares_wif: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitshares WIF",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    bitshares_pairs: str = Field(
        default="BTS-HONEST.BTC",
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitshares trading pairs in this format",
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "bitshares"


class BitsharesTestnetConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="bitshares_testnet", client_data=None)
    bitshares_testnet_user: str = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitshares Testnet username",
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    bitshares_testnet_wif: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitshares Testnet WIF",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    bitshares_testnet_pairs: str = Field(
        default="TEST-USD,TEST-CNY",
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Bitshares Testnet trading pairs in this format",
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "bitshares_testnet"


# GLOBAL CONSTANTS
MSG = "active authority WIF key or press Enter for demonstration >>> "
CONSTANTS = GrapheneConstants()  # NOTE: not blockchain specific here
CENTRALIZED = False
EXAMPLE_PAIR = "PPY-BTC"
DEFAULT_FEES = [0.1, 0.1]
KEYS = PeerplaysConfigMap.construct()
OTHER_DOMAINS = [
    "bitshares",
    "peerplays_testnet",
    "bitshares_testnet",
]
OTHER_DOMAINS_PARAMETER = {
    "bitshares": "bitshares",
    "peerplays_testnet": "peerplays_testnet",
    "bitshares_testnet": "bitshares_testnet",
}
OTHER_DOMAINS_EXAMPLE_PAIR = {
    "bitshares": "BTS-BTC",
    "peerplays_testnet": "TEST-ABC",
    "bitshares_testnet": "TEST-ABC",
}
OTHER_DOMAINS_DEFAULT_FEES = {
    "bitshares": [0.1, 0.1],
    "peerplays_testnet": [0.1, 0.1],
    "bitshares_testnet": [0.1, 0.1],
}
OTHER_DOMAINS_KEYS = {
    "bitshares": BitsharesConfigMap.construct(),
    "peerplays_testnet": PeerplaysTestnetConfigMap.construct(),
    "bitshares_testnet": BitsharesTestnetConfigMap.construct(),
}


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    """
    Creates a client order id for a new order
    :param is_buy: True if the order is a buy order, False otherwise
    :param trading_pair: the trading pair the order will be operating with
    :return: an identifier for the new order to be used in the client
    """
    base, quote = trading_pair.upper().split("-")
    side = "B" if is_buy else "S"
    base_str = f"{base[0]}{base[-1]}"
    quote_str = f"{quote[0]}{quote[-1]}"
    client_instance_id = hex(abs(hash(f"{socket.gethostname()}{os.getpid()}")))[2:6]
    return (
        f"{CONSTANTS.hummingbot.ORDER_PREFIX}-{side}{base_str}{quote_str}"
        + f"{client_instance_id}{get_tracking_nonce()}"
    )
