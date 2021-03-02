from typing import Dict
from decimal import Decimal


def find_rate(prices: Dict[str, Decimal], pair: str) -> Decimal:
    if pair in prices:
        return prices[pair]
    base, quote = pair.split("-")
    reverse_pair = f"{quote}-{base}"
    if reverse_pair in prices:
        return Decimal("1") / prices[reverse_pair]
    base_prices = {k: v for k, v in prices.items() if k.startswith(f"{base}-")}
    for base_pair, proxy_price in base_prices.items():
        link_quote = base_pair.split("-")[1]
        link_pair = f"{link_quote}-{quote}"
        if link_pair in prices:
            return proxy_price * prices[link_pair]
        common_denom_pair = f"{quote}-{link_quote}"
        if common_denom_pair in prices:
            return proxy_price / prices[common_denom_pair]
