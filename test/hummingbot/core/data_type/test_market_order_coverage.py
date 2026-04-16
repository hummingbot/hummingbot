"""
Coverage tests for MarketOrder.to_pandas() classmethod.
Targets line 21 of market_order.py.
"""

from hummingbot.core.data_type.common import PositionAction
from hummingbot.core.data_type.market_order import MarketOrder


def _make_market_order(order_id="O-001", is_buy=True, amount=1.5, timestamp=1_700_000_000.0):
    return MarketOrder(
        order_id=order_id,
        trading_pair="ETH-USDT",
        is_buy=is_buy,
        base_asset="ETH",
        quote_asset="USDT",
        amount=amount,
        timestamp=timestamp,
        position=PositionAction.NIL,
    )


def test_to_pandas_with_single_order():
    """Covers the list comprehension in to_pandas (line 21)."""
    order = _make_market_order()
    df = MarketOrder.to_pandas([order])
    assert len(df) == 1
    assert list(df.columns) == [
        "order_id",
        "trading_pair",
        "is_buy",
        "base_asset",
        "quote_asset",
        "quantity",
        "timestamp",
    ]
    assert df.iloc[0]["order_id"] == "O-001"
    assert df.iloc[0]["trading_pair"] == "ETH-USDT"
    assert df.iloc[0]["is_buy"] == True  # noqa: E712 — pandas returns np.True_
    assert df.iloc[0]["quantity"] == 1.5


def test_to_pandas_with_multiple_orders():
    orders = [
        _make_market_order(order_id="O-001", is_buy=True),
        _make_market_order(order_id="O-002", is_buy=False),
    ]
    df = MarketOrder.to_pandas(orders)
    assert len(df) == 2
    assert df.iloc[1]["order_id"] == "O-002"


def test_to_pandas_empty_list():
    df = MarketOrder.to_pandas([])
    assert len(df) == 0
    assert "order_id" in df.columns
