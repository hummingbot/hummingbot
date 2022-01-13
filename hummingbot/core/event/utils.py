def interchangeable(token_a: str, token_b: str) -> bool:
    interchangeable_tokens = {"WETH", "ETH", "WBTC", "BTC"}
    if token_a == token_b:
        return True
    return {token_a, token_b} <= interchangeable_tokens
