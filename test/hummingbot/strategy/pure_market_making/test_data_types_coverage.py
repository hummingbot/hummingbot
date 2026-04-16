"""Coverage tests for hummingbot/strategy/pure_market_making/data_types.py - line 51 (__repr__ of Proposal)."""

from decimal import Decimal

from hummingbot.strategy.pure_market_making.data_types import PriceSize, Proposal


def test_proposal_repr_with_buys_and_sells():
    """Line 51: exercises Proposal.__repr__ with populated buys and sells."""
    buys = [PriceSize(Decimal("100"), Decimal("1")), PriceSize(Decimal("101"), Decimal("2"))]
    sells = [PriceSize(Decimal("102"), Decimal("3"))]
    proposal = Proposal(buys=buys, sells=sells)
    result = repr(proposal)
    assert "2 buys" in result
    assert "1 sells" in result


def test_proposal_repr_empty_lists():
    """Line 51: exercises Proposal.__repr__ with empty buys and sells."""
    proposal = Proposal(buys=[], sells=[])
    result = repr(proposal)
    assert "0 buys" in result
    assert "0 sells" in result
