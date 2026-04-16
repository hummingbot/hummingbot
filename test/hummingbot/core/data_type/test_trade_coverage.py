"""
Coverage tests for Trade.to_pandas().
Targets lines 25 (empty flat_fees) and 44 (non-empty flat_fees).
"""

from decimal import Decimal
from unittest.mock import MagicMock

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.trade import Trade


def _make_trade_fee(flat_fees=None, percent=Decimal("0.001")):
    fee = MagicMock()
    fee.percent = percent
    fee.flat_fees = flat_fees if flat_fees is not None else []
    return fee


def _make_trade(flat_fees=None):
    return Trade(
        trading_pair="BTC-USDT",
        side=TradeType.BUY,
        price=30000.0,
        amount=0.1,
        order_type=OrderType.LIMIT,
        market="binance",
        timestamp=1_700_000_000.0,
        trade_fee=_make_trade_fee(flat_fees=flat_fees),
    )


def test_to_pandas_empty_flat_fees():
    """Covers line 39: flat_fees is empty -> flat_fee_str = 'None'."""
    trade = _make_trade(flat_fees=[])
    df = Trade.to_pandas([trade])
    assert len(df) == 1
    assert df.iloc[0]["flat_fee / gas"] == "None"


def test_to_pandas_non_empty_flat_fees():
    """Covers lines 41-42: flat_fees present -> fee strings joined."""
    trade = _make_trade(flat_fees=[("USDT", Decimal("0.3")), ("BNB", Decimal("0.001"))])
    df = Trade.to_pandas([trade])
    assert len(df) == 1
    flat_fee_str = df.iloc[0]["flat_fee / gas"]
    assert "USDT" in flat_fee_str
    assert "BNB" in flat_fee_str
    assert "," in flat_fee_str


def test_to_pandas_columns():
    trade = _make_trade()
    df = Trade.to_pandas([trade])
    expected_cols = [
        "trading_pair",
        "price",
        "quantity",
        "order_type",
        "trade_side",
        "market",
        "timestamp",
        "fee_percent",
        "flat_fee / gas",
    ]
    assert list(df.columns) == expected_cols


def test_to_pandas_empty_list():
    df = Trade.to_pandas([])
    assert len(df) == 0
