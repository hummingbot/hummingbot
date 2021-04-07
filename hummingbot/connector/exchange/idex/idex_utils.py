from typing import Optional

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce


CENTRALIZED = False

USE_ETHEREUM_WALLET = False

EXAMPLE_PAIR = "IDEX-ETH"

DEFAULT_FEES = [0.1, 0.2]

ETH_GAS_LIMIT = 170000  # estimation of upper limit of gas idex uses to move its smart contact for each fill
BSC_GAS_LIMIT = 60000  # estimate from real taker orders

USE_ETH_GAS_LOOKUP = False  # false even if idex do have gas fees, otherwise estimate_fee() would fail

HUMMINGBOT_GAS_LOOKUP = False  # set to False if getting gas from idex is better than from Hummingbot

HBOT_BROKER_ID = "HBOT-"

EXCHANGE_NAME = "idex"

IDEX_BLOCKCHAINS = ('ETH', 'BSC')


def validate_idex_contract_blockchain(value: str) -> Optional[str]:
    if value not in IDEX_BLOCKCHAINS:
        return f'Value {value} must be one of: {IDEX_BLOCKCHAINS}'


# Example: HBOT-B-DIL-ETH-64106538-8b61-11eb-b2bb-1e29c0300f46
def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    return f"{HBOT_BROKER_ID}{side}-{trading_pair}-{get_tracking_nonce()}"


HB_ORDER_TYPE_TO_IDEX_PARAM_MAP = {
    OrderType.MARKET: "market",
    OrderType.LIMIT: "limit",
    OrderType.LIMIT_MAKER: "limitMaker",
}


def hb_order_type_to_idex_param(order_type: OrderType):
    return HB_ORDER_TYPE_TO_IDEX_PARAM_MAP[order_type]


HB_TRADE_TYPE_TO_IDEX_PARAM_MAP = {
    TradeType.BUY: "buy",
    TradeType.SELL: "sell",
}


def hb_trade_type_to_idex_param(trade_type: TradeType):
    return HB_TRADE_TYPE_TO_IDEX_PARAM_MAP[trade_type]


IDEX_PARAM_TO_HB_ORDER_TYPE_MAP = {
    "market": OrderType.MARKET,
    "limit": OrderType.LIMIT,
    "limitMaker": OrderType.LIMIT_MAKER,
}


def idex_param_to_hb_order_type(order_type: str):
    return IDEX_PARAM_TO_HB_ORDER_TYPE_MAP[order_type]


IDEX_PARAM_TO_HB_TRADE_TYPE_MAP = {
    "buy": TradeType.BUY,
    "sell": TradeType.SELL,
}


def idex_param_to_hb_trade_type(side: str):
    return IDEX_PARAM_TO_HB_TRADE_TYPE_MAP[side]


KEYS = {
    "idex_api_key":
        ConfigVar(key="idex_api_key",
                  prompt="Enter your IDEX API key (smart contract blockchain: ETH) >>> ",
                  required_if=using_exchange(EXCHANGE_NAME),
                  is_secure=True,
                  is_connect_key=True),
    "idex_api_secret_key":
        ConfigVar(key="idex_api_secret_key",
                  prompt="Enter your IDEX API secret key>>> ",
                  required_if=using_exchange(EXCHANGE_NAME),
                  is_secure=True,
                  is_connect_key=True),
    "idex_wallet_private_key":
        ConfigVar(key="idex_wallet_private_key",
                  prompt="Enter your wallet private key>>> ",
                  required_if=using_exchange(EXCHANGE_NAME),
                  is_secure=True,
                  is_connect_key=True),
}


OTHER_DOMAINS = ["idex_bsc", "idex_sandbox_eth", "idex_sandbox_bsc"]
OTHER_DOMAINS_PARAMETER = {  # will be passed as argument "domain" to the exchange class
    "idex_bsc": "bsc",
    "idex_sandbox_eth": "sandbox_eth",
    "idex_sandbox_bsc": "sandbox_bsc",
}
OTHER_DOMAINS_EXAMPLE_PAIR = {"idex_bsc": "IDEX-ETH", "idex_sandbox_eth": "DIL-ETH", "idex_sandbox_bsc": "DIL-ETH"}
OTHER_DOMAINS_DEFAULT_FEES = {"idex_bsc": [0.1, 0.2], "idex_sandbox_eth": [0.1, 0.2], "idex_sandbox_bsc": [0.1, 0.2]}
OTHER_DOMAINS_KEYS = {
    "idex_bsc": {
        "idex_bsc_api_key":
            ConfigVar(key="idex_bsc_api_key",
                      prompt="Enter your IDEX API key (smart contract blockchain: BSC) >>> ",
                      required_if=using_exchange("idex_bsc"),
                      is_secure=True,
                      is_connect_key=True),
        "idex_bsc_api_secret_key":
            ConfigVar(key="idex_bsc_api_secret_key",
                      prompt="Enter your IDEX API secret key>>> ",
                      required_if=using_exchange("idex_bsc"),
                      is_secure=True,
                      is_connect_key=True),
        "idex_bsc_wallet_private_key":
            ConfigVar(key="idex_bsc_wallet_private_key",
                      prompt="Enter your wallet private key>>> ",
                      required_if=using_exchange("idex_bsc"),
                      is_secure=True,
                      is_connect_key=True),
    },
    "idex_sandbox_eth": {
        "idex_sandbox_eth_api_key":
            ConfigVar(key="idex_sandbox_eth_api_key",
                      prompt="Enter your IDEX API key ([sandbox] smart contract blockchain: ETH) >>> ",
                      required_if=using_exchange("idex_sandbox_eth"),
                      is_secure=True,
                      is_connect_key=True),
        "idex_sandbox_eth_api_secret_key":
            ConfigVar(key="idex_sandbox_eth_api_secret_key",
                      prompt="Enter your IDEX API secret key>>> ",
                      required_if=using_exchange("idex_sandbox_eth"),
                      is_secure=True,
                      is_connect_key=True),
        "idex_sandbox_eth_wallet_private_key":
            ConfigVar(key="idex_sandbox_eth_wallet_private_key",
                      prompt="Enter your wallet private key>>> ",
                      required_if=using_exchange("idex_sandbox_eth"),
                      is_secure=True,
                      is_connect_key=True),
    },
    "idex_sandbox_bsc": {
        "idex_sandbox_bsc_api_key":
            ConfigVar(key="idex_sandbox_bsc_api_key",
                      prompt="Enter your IDEX API key ([sandbox] smart contract blockchain: BSC) >>> ",
                      required_if=using_exchange("idex_sandbox_bsc"),
                      is_secure=True,
                      is_connect_key=True),
        "idex_sandbox_bsc_api_secret_key":
            ConfigVar(key="idex_sandbox_bsc_api_secret_key",
                      prompt="Enter your IDEX API secret key>>> ",
                      required_if=using_exchange("idex_sandbox_bsc"),
                      is_secure=True,
                      is_connect_key=True),
        "idex_sandbox_bsc_wallet_private_key":
            ConfigVar(key="idex_sandbox_bsc_wallet_private_key",
                      prompt="Enter your wallet private key>>> ",
                      required_if=using_exchange("idex_sandbox_bsc"),
                      is_secure=True,
                      is_connect_key=True),
    },
}


DEBUG = False
