import re
from typing import Optional, Tuple

import requests
from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-BRL"

DEFAULT_FEES = [0.35, 0.45]  # The actual fees


class BlocktaneConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="blocktane", client_data=None)
    blocktane_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Blocktane API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    blocktane_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Blocktane API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "blocktane"


KEYS = BlocktaneConfigMap.construct()

TRADING_PAIR_SPLITTER = re.compile(r"^(\w+)(BTC|btc|ETH|eth|BRL|brl|PAX|pax|USDT|usdt|PAXG|paxg|LETH|leth|EURS|eurs|LRC|lrc|BKT|bkt)$")
MARKET_DATA = None
INVERSE_MARKET_LOOKUP = None
NAME_LOOKUP = None


def _populate_lookups():
    global MARKET_DATA
    global INVERSE_MARKET_LOOKUP
    global NAME_LOOKUP
    try:
        markets = requests.get('https://trade.blocktane.io/api/v2/xt/public/markets').json()
        MARKET_DATA = {market['id']: market for market in markets}
        INVERSE_MARKET_LOOKUP = {(market['base_unit'].upper(), market['quote_unit'].upper()): market for market in markets}
        NAME_LOOKUP = {market['name']: market for market in markets}
    except Exception:
        pass  # Will fall back to regex splitting


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    if MARKET_DATA is None:
        _populate_lookups()

    if MARKET_DATA is not None:
        if '/' in trading_pair:
            m = NAME_LOOKUP.get(trading_pair)
        else:
            m = MARKET_DATA.get(trading_pair)
        if m is None:
            return None
        return m['base_unit'], m['quote_unit']
    else:
        # Fall back to regex splitting
        try:
            if ('/' in trading_pair):
                m = trading_pair.split('/')
                return m[0], m[1]
            else:
                m = TRADING_PAIR_SPLITTER.match(trading_pair)
                return m.group(1), m.group(2)
        # Exceptions are now logged as warnings in trading pair fetcher
        except Exception:
            return None


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    split_pair_tuple = split_trading_pair(exchange_trading_pair)
    if split_pair_tuple is None:
        return None
    base_asset, quote_asset = split_pair_tuple
    return f"{base_asset}-{quote_asset}".upper()


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    if INVERSE_MARKET_LOOKUP is None:
        _populate_lookups()
    try:
        return INVERSE_MARKET_LOOKUP[hb_trading_pair.split('-')]['id']
    except Exception:
        return hb_trading_pair.lower().replace("-", "")
