# Symbols treated as interchangeable with USDT for rate-oracle lookups. Exchanges
# quote almost exclusively against USDT, so a balance denominated in USD (e.g.
# perpetual collateral) is priced using the USDT markets that exchanges list.
# This default is overridden at startup from the ``global_token`` client config.
USD_EQUIVALENT_TOKENS = ["USD"]


def unwrap_token_symbol(token_symbol: str) -> str:
    """
    Normalizes a token symbol for rate-oracle lookups by mapping USD-equivalent
    symbols to USDT, so that for example USD and USDT resolve to the same rate.
    """
    if token_symbol in USD_EQUIVALENT_TOKENS:
        return "USDT"
    return token_symbol
