#!/usr/bin/env python

from hummingbot.client.config.global_config_map import global_config_map

# API Feed adjusted to sandbox url
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


# late resolution to give time for exchange configuration to be ready
_IDEX_REST_URL = None
_IDEX_WS_FEED = None

_IDEX_BLOCKCHAIN = None
_IS_IDEX_SANDBOX = None


def get_idex_blockchain():
    """Late loading of user selected blockchain from configuration"""
    global _IDEX_BLOCKCHAIN
    if _IDEX_BLOCKCHAIN is None:
        _IDEX_BLOCKCHAIN = global_config_map["idex_contract_blockchain"].value or \
            global_config_map["idex_contract_blockchain"].default
    return _IDEX_BLOCKCHAIN


def is_idex_sandbox():
    """Late loading of user selection of using sandbox from configuration"""
    global _IS_IDEX_SANDBOX
    if _IS_IDEX_SANDBOX is None:
        _IS_IDEX_SANDBOX = True if global_config_map["idex_use_sandbox"].value in ('true', 'yes', 'y') else False
    return _IS_IDEX_SANDBOX


def get_idex_rest_url():
    """Late resolution of idex rest url to give time for configuration to load"""
    global _IDEX_REST_URL
    if _IDEX_REST_URL is None:
        if is_idex_sandbox():
            _IDEX_REST_URL = _IDEX_REST_URL_SANDBOX_ETH if get_idex_blockchain() == 'ETH' \
                else _IDEX_REST_URL_SANDBOX_BSC
        else:
            _IDEX_REST_URL = _IDEX_REST_URL_PROD_ETH if get_idex_blockchain() == 'ETH' else _IDEX_REST_URL_PROD_BSC
    return _IDEX_REST_URL


def get_idex_ws_feed():
    """Late resolution of idex WS url to give time for configuration to load"""
    global _IDEX_WS_FEED
    if not _IDEX_WS_FEED:
        if is_idex_sandbox():
            _IDEX_WS_FEED = _IDEX_WS_FEED_SANDBOX_ETH if get_idex_blockchain() == 'ETH' else _IDEX_WS_FEED_SANDBOX_BSC
        else:
            _IDEX_WS_FEED = _IDEX_WS_FEED_PROD_ETH if get_idex_blockchain() == 'ETH' else _IDEX_WS_FEED_PROD_BSC
    return _IDEX_WS_FEED
