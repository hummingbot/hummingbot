from decimal import Decimal
from typing import Dict

from hummingbot.connector.utils import combine_to_hb_trading_pair, split_hb_trading_pair

# Symbols treated as interchangeable with USDT for rate-oracle lookups. Exchanges
# quote almost exclusively against USDT, so a balance denominated in USD (e.g.
# perpetual collateral) is priced using the USDT markets that exchanges list.
# This default is overridden at startup from the ``global_token`` client config.
USD_EQUIVALENT_TOKENS = ["USD"]


def normalize_token_symbol(token_symbol: str) -> str:
    """
    Maps USD-equivalent symbols to USDT so that, for example, USD and USDT
    resolve to the same conversion rate.
    """
    if token_symbol in USD_EQUIVALENT_TOKENS:
        return "USDT"
    return token_symbol


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
    base = normalize_token_symbol(base)
    quote = normalize_token_symbol(quote)
    if base == quote:
        return Decimal("1")
    # Re-check the direct pair after normalizing (e.g. HYPE-USD -> HYPE-USDT) before
    # attempting reverse-pair or path-bridging lookups.
    normalized_pair = combine_to_hb_trading_pair(base=base, quote=quote)
    if normalized_pair in prices:
        return prices[normalized_pair]
    reverse_pair = combine_to_hb_trading_pair(base=quote, quote=base)
    if reverse_pair in prices and prices[reverse_pair] > Decimal("0"):
        return Decimal("1") / prices[reverse_pair]
    base_prices = {k: v for k, v in prices.items() if k.startswith(f"{base}-")}
    for base_pair, proxy_price in base_prices.items():
        link_quote = split_hb_trading_pair(base_pair)[1]
        link_pair = combine_to_hb_trading_pair(base=link_quote, quote=quote)
        if link_pair in prices:
            return proxy_price * prices[link_pair]
        common_denom_pair = combine_to_hb_trading_pair(base=quote, quote=link_quote)
        if common_denom_pair in prices and prices[common_denom_pair] > Decimal("0"):
            return proxy_price / prices[common_denom_pair]
