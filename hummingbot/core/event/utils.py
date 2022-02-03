def interchangeable(token_a: str, token_b: str) -> bool:
    interchangeable_tokens = {"WETH", "ETH", "WBTC", "BTC"}
    return token_a == token_b or ({token_a, token_b} <= interchangeable_tokens)
