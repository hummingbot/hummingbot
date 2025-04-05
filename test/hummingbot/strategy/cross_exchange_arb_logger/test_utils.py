import decimal

import pytest

from hummingbot.strategy.cross_exchange_arb_logger.utils import calculate_spread


@pytest.mark.parametrize(
    "bid_price, ask_price, bid_fee, ask_fee, expected_spread",
    [
        # No fees
        (decimal.Decimal("101"), decimal.Decimal("100"), decimal.Decimal("0"), decimal.Decimal("0"), decimal.Decimal("1.0000")),
        (decimal.Decimal("100"), decimal.Decimal("100"), decimal.Decimal("0"), decimal.Decimal("0"), decimal.Decimal("0.0000")),
        (decimal.Decimal("99"), decimal.Decimal("100"), decimal.Decimal("0"), decimal.Decimal("0"), decimal.Decimal("-1.0000")),

        # With bid fee only
        (decimal.Decimal("101"), decimal.Decimal("100"), decimal.Decimal("0.001"), decimal.Decimal("0"), decimal.Decimal("0.8990")),
        (decimal.Decimal("100"), decimal.Decimal("100"), decimal.Decimal("0.005"), decimal.Decimal("0"), decimal.Decimal("-0.5000")),

        # With ask fee only
        (decimal.Decimal("101"), decimal.Decimal("100"), decimal.Decimal("0"), decimal.Decimal("0.001"), decimal.Decimal("0.8991")),
        (decimal.Decimal("100"), decimal.Decimal("100"), decimal.Decimal("0"), decimal.Decimal("0.005"), decimal.Decimal("-0.4975")),

        # With both fees
        (decimal.Decimal("101"), decimal.Decimal("100"), decimal.Decimal("0.001"), decimal.Decimal("0.001"), decimal.Decimal("0.7982")),
        (decimal.Decimal("99"), decimal.Decimal("100"), decimal.Decimal("0.001"), decimal.Decimal("0.001"), decimal.Decimal("-1.1978")),
        (decimal.Decimal("100"), decimal.Decimal("100"), decimal.Decimal("0.001"), decimal.Decimal("0.001"), decimal.Decimal("-0.1998")),

        # Edge case: zero bid
        (decimal.Decimal("0"), decimal.Decimal("100"), decimal.Decimal("0"), decimal.Decimal("0"), decimal.Decimal("-100.0000")),

        # Edge case: small price with fees
        (decimal.Decimal("0.01"), decimal.Decimal("0.009"), decimal.Decimal("0.01"), decimal.Decimal("0.01"), decimal.Decimal("8.9109")),
    ],
    ids=[
        "no_fees_positive",
        "no_fees_zero",
        "no_fees_negative",
        "bid_fee_only",
        "bid_fee_larger",
        "ask_fee_only",
        "ask_fee_larger",
        "both_fees_positive",
        "both_fees_negative",
        "both_fees_zero_base",
        "zero_bid",
        "tiny_prices"
    ]
)
def test_calculate_spread(bid_price, ask_price, bid_fee, ask_fee, expected_spread):
    spread = calculate_spread(bid_price, ask_price, bid_fee, ask_fee)
    assert spread.quantize(decimal.Decimal("0.0001")) == expected_spread
