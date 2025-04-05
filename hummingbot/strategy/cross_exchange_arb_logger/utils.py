import decimal


def calculate_spread(
    bid_price: decimal.Decimal,
    ask_price: decimal.Decimal,
    bid_fee: decimal.Decimal = decimal.Decimal("0"),
    ask_fee: decimal.Decimal = decimal.Decimal("0"),
) -> decimal.Decimal:
    """
    Calculates adjusted arbitrage spread:
    Spread = ((adjusted_bid - adjusted_ask) / adjusted_ask) * 100

    Fees are applied as:
        - bid reduced by bid_fee
        - ask increased by ask_fee
    """
    adjusted_bid = bid_price * (decimal.Decimal("1") - bid_fee)
    adjusted_ask = ask_price * (decimal.Decimal("1") + ask_fee)
    return ((adjusted_bid - adjusted_ask) / adjusted_ask) * decimal.Decimal("100")
