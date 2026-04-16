"""
Coverage tests for strategy/data_types.py.
Targets HangingOrder.base_asset (line 66) and .quote_asset (line 70).
"""

from decimal import Decimal

import pytest

from hummingbot.strategy.data_types import HangingOrder


@pytest.fixture
def hanging_order():
    return HangingOrder(
        order_id="HO-001",
        trading_pair="ETH-USDT",
        is_buy=True,
        price=Decimal("2000"),
        amount=Decimal("0.5"),
        creation_timestamp=1_700_000_000.0,
    )


def test_base_asset_property(hanging_order):
    """Covers line 66: splits trading_pair on '-' and returns first part."""
    assert hanging_order.base_asset == "ETH"


def test_quote_asset_property(hanging_order):
    """Covers line 70: splits trading_pair on '-' and returns second part."""
    assert hanging_order.quote_asset == "USDT"


def test_base_and_quote_for_various_pairs():
    pairs = [
        ("BTC-USDT", "BTC", "USDT"),
        ("SOL-BTC", "SOL", "BTC"),
        ("HBOT-ETH", "HBOT", "ETH"),
    ]
    for pair, expected_base, expected_quote in pairs:
        order = HangingOrder(
            order_id="O",
            trading_pair=pair,
            is_buy=False,
            price=Decimal("1"),
            amount=Decimal("1"),
            creation_timestamp=0.0,
        )
        assert order.base_asset == expected_base
        assert order.quote_asset == expected_quote
