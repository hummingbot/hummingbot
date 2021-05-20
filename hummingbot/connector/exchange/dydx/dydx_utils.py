
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange

CENTRALIZED = True

USE_ETHEREUM_WALLET = False

EXAMPLE_PAIR = "WETH-DAI"

DEFAULT_FEES = [0.0, 0.3]

KEYS = {
    "dydx_eth_private_key":
        ConfigVar(key="dydx_eth_private_key",
                  prompt="Enter your Ethereum private key >>> ",
                  required_if=using_exchange("dydx"),
                  is_secure=True,
                  is_connect_key=True),
    "dydx_node_address":
        ConfigVar(key="dydx_node_address",
                  prompt="Which Ethereum node would you like your client to connect to?  >>> ",
                  required_if=using_exchange("dydx"),
                  is_secure=True,
                  is_connect_key=True)
}

DYDX_ROOT_API = "https://api.dydx.exchange/v1"

V2_TO_V1 = {
    "WETH-DAI": "ETH-DAI",
    "WETH-USDC": "ETH-USDC",
    "DAI-USDC": "DAI-USDC",
}


def convert_v2_pair_to_v1(trading_pair: str) -> str:
    return V2_TO_V1.get(trading_pair, trading_pair)


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    # dydx returns trading pairs in the correct format natively
    return exchange_trading_pair


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    # dydx expects trading pairs in the same format as hummingbot internally represents them
    return hb_trading_pair


def hash_order_id(hex_str_id):
    reduced_num = hash(hex_str_id)
    return reduced_num
