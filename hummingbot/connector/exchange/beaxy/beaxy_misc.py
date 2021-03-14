# -*- coding: utf-8 -*-

import re
from typing import Optional, Tuple, List

TRADING_PAIR_SPLITTER = re.compile(r'^(\w+)?(BTC|ETH|BXY|USDT|USDC|USD)(\w+)?$')


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    """
    Converts Beaxy exchange API format to Hummingbot trading pair format
    example: BTCUSDC -> BTC-USDC
    """

    try:
        if '-' in trading_pair:
            return trading_pair.split('-')

        m = TRADING_PAIR_SPLITTER.match(trading_pair)
        # determine the main asset
        sub_pre, main, sub_post = m.group(1), m.group(2), m.group(3)
        # keep ordering like in pair
        if sub_pre:
            return sub_pre, main
        elif sub_post:
            return main, sub_post

    # Exceptions are now logged as warnings in trading pair fetcher
    except Exception:  # nopep8
        return None


def symbol_to_trading_pair(trading_pair: str) -> str:
    return '{}-{}'.format(*split_trading_pair(trading_pair))


def split_market_pairs(pairs: List[str]):
    """
    formats list of Beaxy pairs to Hummingbot trading pair format
    """
    for pair in pairs:
        formatted = split_trading_pair(pair)
        if formatted:
            yield formatted


def trading_pair_to_symbol(trading_pair: str) -> str:
    """
    Converts Hummingbot trading pair format to Beaxy exchange API format
    example: BTC-USDC -> BTCUSDC
    """
    return trading_pair.replace('-', '')


class BeaxyIOError(IOError):

    def __init__(self, msg, response, result, *args, **kwargs):
        self.response = response
        self.result = result
        super(BeaxyIOError, self).__init__(msg, *args, **kwargs)
