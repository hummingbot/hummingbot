from decimal import Decimal
from typing import Dict

from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair
from hummingbot.core.gateway.utils import unwrap_token_symbol


def find_rate(prices: Dict[str, Decimal], pair: str) -> Decimal:
    '''
    Finds exchange rate for a given trading pair from a dictionary of prices
    For example, given prices of {"HBOT-USDT": Decimal("100"), "AAVE-USDT": Decimal("50"), "USDT-GBP": Decimal("0.75")}
    A rate for USDT-HBOT will be 1 / 100
    A rate for HBOT-AAVE will be 100 / 50
    A rate for AAVE-HBOT will be 50 / 100
    A rate for HBOT-GBP will be 100 * 0.75
    :param prices: The dictionary of trading pairs and their prices
    :param pair: The trading pair
    '''
    if pair in prices:
        return prices[pair]
    base, quote = split_hb_trading_pair(trading_pair=pair)
    base = unwrap_token_symbol(base)
    quote = unwrap_token_symbol(quote)
    if base == quote:
        return Decimal("1")
    reverse_pair = combine_to_hb_trading_pair(base=quote, quote=base)
    if reverse_pair in prices:
        return Decimal("1") / prices[reverse_pair]
    base_prices = {k: v for k, v in prices.items() if k.startswith(f"{base}-")}
    for base_pair, proxy_price in base_prices.items():
        link_quote = split_hb_trading_pair(base_pair)[1]
        link_pair = combine_to_hb_trading_pair(base=link_quote, quote=quote)
        if link_pair in prices:
            return proxy_price * prices[link_pair]
        common_denom_pair = combine_to_hb_trading_pair(base=quote, quote=link_quote)
        if common_denom_pair in prices:
            return proxy_price / prices[common_denom_pair]
