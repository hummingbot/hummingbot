import decimal


def calculate_spread(
    bid_price: decimal.Decimal,
    ask_price: decimal.Decimal,
    bid_fee: decimal.Decimal | None = None,
    ask_fee: decimal.Decimal | None = None
) -> decimal.Decimal:
    """
    Calculate arbitrage spread between a bid and ask price:
    Spread = ((bid - ask) / ask) * 100

    Fees are expected as decimals (e.g., 0.001 for 0.1%).
    Applies fees as:
        - bid_price reduced by bid_fee
        - ask_price increased by ask_fee
    """
    bid_fee = bid_fee or decimal.Decimal("0")
    ask_fee = ask_fee or decimal.Decimal("0")

    adj_bid = bid_price * (decimal.Decimal("1") - bid_fee)
    adj_ask = ask_price * (decimal.Decimal("1") + ask_fee)

    spread = ((adj_bid - adj_ask) / adj_ask) * decimal.Decimal("100")
    return spread
