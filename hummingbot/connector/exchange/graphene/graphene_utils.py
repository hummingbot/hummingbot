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

# HUMMINGBOT MODULES
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.connector.exchange.graphene.graphene_constants import \
    GrapheneConstants
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

# GLOBAL CONSTANTS
MSG = "active authority WIF key or press Enter for demonstration >>> "
CONSTANTS = GrapheneConstants()  # NOTE: not blockchain specific here
CENTRALIZED = False
EXAMPLE_PAIR = "PPY-BTC"
DEFAULT_FEES = [0.1, 0.1]
KEYS = {
    "peerplays_wif": ConfigVar(
        key="peerplays_wif",
        prompt=f"Enter your *Peerplays* {MSG}",
        required_if=using_exchange("peerplays"),
        is_secure=True,
        is_connect_key=True,
    ),
}
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
    "bitshares": {
        "bitshares_wif": ConfigVar(
            key="bitshares_wif",
            prompt=f"Enter your *Bitshares* {MSG}",
            required_if=using_exchange("bitshares"),
            is_secure=True,
            is_connect_key=True,
        ),
    },
    "peerplays_testnet": {
        "peerplays_testnet_wif": ConfigVar(
            key="peerplays_testnet_wif",
            prompt=f"Enter your *Peerplays Testnet* {MSG}",
            required_if=using_exchange("peerplays_testnet"),
            is_secure=True,
            is_connect_key=True,
        ),
    },
    "bitshares_testnet": {
        "bitshares_testnet_wif": ConfigVar(
            key="bitshares_testnet_wif",
            prompt=f"Enter your *Bitshares Testnet* {MSG}",
            required_if=using_exchange("bitshares_testnet"),
            is_secure=True,
            is_connect_key=True,
        ),
    },
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
