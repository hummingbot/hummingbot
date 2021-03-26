#!/usr/bin/env python

# API Feed adjusted to sandbox url
from hummingbot.core.event.events import TradeType, OrderType

IDEX_REST_URL_FMT = "https://api-sandbox-{blockchain}.idex.io/"
# WS Feed adjusted to sandbox url
IDEX_WS_FEED_FMT = "wss://websocket-sandbox-{blockchain}.idex.io/v1"


_IDEX_REST_URL_SANDBOX_ETH = "https://api-sandbox-eth.idex.io"
_IDEX_REST_URL_SANDBOX_BSC = "https://api-sandbox-bsc.idex.io"
_IDEX_REST_URL_PROD_ETH = "https://api-eth.idex.io"
_IDEX_REST_URL_PROD_BSC = "https://api-bsc.idex.io"

_IDEX_WS_FEED_SANDBOX_ETH = "wss://websocket-sandbox-eth.idex.io/v1"
_IDEX_WS_FEED_SANDBOX_BSC = "wss://websocket-sandbox-bsc.idex.io/v1"
_IDEX_WS_FEED_PROD_ETH = "wss://websocket-eth.idex.io/v1"
_IDEX_WS_FEED_PROD_BSC = "wss://websocket-bsc.idex.io/v1"


_IDEX_BLOCKCHAIN = None
_IS_IDEX_SANDBOX = None


def set_domain(domain):
    """Save user selected domain so we don't have to pass around domain to every method"""
    global _IDEX_BLOCKCHAIN, _IS_IDEX_SANDBOX

    if domain == "eth":  # prod eth
        _IDEX_BLOCKCHAIN = 'ETH'
        _IS_IDEX_SANDBOX = False
    elif domain == "bsc":  # prod bsc
        _IDEX_BLOCKCHAIN = 'BSC'
        _IS_IDEX_SANDBOX = False
    elif domain == "sandbox_eth":
        _IDEX_BLOCKCHAIN = 'ETH'
        _IS_IDEX_SANDBOX = True
    elif domain == "sandbox_bsc":
        _IDEX_BLOCKCHAIN = 'BSC'
        _IS_IDEX_SANDBOX = True
    else:
        raise Exception(f'Bad configuration of domain "{domain}"')


def get_rest_url_for_domain(domain):
    if domain == "eth":  # prod eth
        return _IDEX_REST_URL_PROD_ETH
    elif domain == "bsc":  # prod bsc
        return _IDEX_REST_URL_PROD_BSC
    elif domain == "sandbox_eth":
        return _IDEX_REST_URL_SANDBOX_ETH
    elif domain == "sandbox_bsc":
        return _IDEX_REST_URL_SANDBOX_BSC
    else:
        raise Exception(f'Bad configuration of domain "{domain}"')


def get_ws_url_for_domain(domain):
    if domain == "eth":  # prod eth
        return _IDEX_WS_FEED_PROD_ETH
    elif domain == "bsc":  # prod bsc
        return _IDEX_WS_FEED_PROD_BSC
    elif domain == "sandbox_eth":
        return _IDEX_WS_FEED_SANDBOX_ETH
    elif domain == "sandbox_bsc":
        return _IDEX_WS_FEED_SANDBOX_BSC
    else:
        raise Exception(f'Bad configuration of domain "{domain}"')


def get_idex_blockchain():
    """Late loading of user selected blockchain from configuration"""
    if _IDEX_BLOCKCHAIN is None:
        return 'ETH'
    return _IDEX_BLOCKCHAIN


def is_idex_sandbox():
    """Late loading of user selection of using sandbox from configuration"""
    if _IS_IDEX_SANDBOX is None:
        return False
    return _IS_IDEX_SANDBOX


def get_idex_rest_url(domain=None):
    """Late resolution of idex rest url to give time for configuration to load"""
    if domain is not None:
        # we need to pass the domain only if the method is called before the market is instantiated
        return get_rest_url_for_domain(domain)
    if is_idex_sandbox():
        return _IDEX_REST_URL_SANDBOX_ETH if get_idex_blockchain() == 'ETH' else _IDEX_REST_URL_SANDBOX_BSC
    else:
        return _IDEX_REST_URL_PROD_ETH if get_idex_blockchain() == 'ETH' else _IDEX_REST_URL_PROD_BSC


def get_idex_ws_feed(domain=None):
    """Late resolution of idex WS url to give time for configuration to load"""
    if domain is not None:
        # we need to pass the domain only if the method is called before the market is instantiated
        return get_ws_url_for_domain(domain)
    if is_idex_sandbox():
        return _IDEX_WS_FEED_SANDBOX_ETH if get_idex_blockchain() == 'ETH' else _IDEX_WS_FEED_SANDBOX_BSC
    else:
        return _IDEX_WS_FEED_PROD_ETH if get_idex_blockchain() == 'ETH' else _IDEX_WS_FEED_PROD_BSC


HB_ORDER_TYPE_MAP = {
    OrderType.MARKET: "market",
    OrderType.LIMIT: "limit",
    OrderType.LIMIT_MAKER: "limitMaker",
}


def to_idex_order_type(order_type: OrderType):
    return HB_ORDER_TYPE_MAP[order_type]


IDEX_ORDER_TYPE_MAP = {
    "market": OrderType.MARKET,
    "limit": OrderType.LIMIT,
    "limitMaker": OrderType.LIMIT_MAKER,
}


def from_idex_order_type(order_type: str):
    return IDEX_ORDER_TYPE_MAP[order_type]


IDEX_TRADE_TYPE_MAP = {
    "buy": TradeType.BUY,
    "sell": TradeType.SELL,
}


def from_idex_trade_type(side: str):
    return IDEX_TRADE_TYPE_MAP[side]
